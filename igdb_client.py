"""IGDB (Twitch) klient — primární zdroj herních obrázků.

Vznikl při totálním výpadku RAWG.io 2026-08-02/03 (celá origin infrastruktura
včetně status stránky, Cloudflare 522/521; RAWG je dlouhodobě neudržovaný).
IGDB provozuje Twitch/Amazon — spolehlivá infrastruktura, zdarma, limit 4 req/s.
RAWG byl 2026-08-12 z pipeline vyhozen — po výpadku nenaběhl a každé volání
končilo timeoutem (~20 s na článek, nula zachráněných obrázků).

Auth: OAuth2 client credentials na id.twitch.tv → Bearer token (platnost
~60 dní), cache v paměti procesu, při 401 jeden refresh + retry.

Setup credentials: https://dev.twitch.tv/console/apps → Register Your
Application (kategorie Application Integration, OAuth redirect http://localhost)
→ Client ID + Client Secret → .env IGDB_CLIENT_ID / IGDB_CLIENT_SECRET.
"""

import re
import time
import unicodedata

import requests

import config
from logger import setup_logger

log = setup_logger(__name__)

_TOKEN_URL = 'https://id.twitch.tv/oauth2/token'
_API_URL = 'https://api.igdb.com/v4'

# Velikosti: https://api-docs.igdb.com/#images
_SIZE_FEATURED = 't_1080p'          # artwork/screenshot pro featured image
_SIZE_SCREENSHOT = 't_screenshot_huge'  # 1280×720 pro Story Mode karty

_token = None
_token_expires_at = 0.0


def is_configured():
    return bool(config.IGDB_CLIENT_ID and config.IGDB_CLIENT_SECRET)


def _get_token(force_refresh=False):
    """Bearer token z Twitch OAuth (client credentials), cache do expirace."""
    global _token, _token_expires_at
    if _token and not force_refresh and time.time() < _token_expires_at:
        return _token

    resp = requests.post(
        _TOKEN_URL,
        params={
            'client_id': config.IGDB_CLIENT_ID,
            'client_secret': config.IGDB_CLIENT_SECRET,
            'grant_type': 'client_credentials',
        },
        timeout=10,
    )
    if resp.status_code != 200:
        log.warning("IGDB token error %d: %s", resp.status_code, resp.text[:150])
        return None

    data = resp.json()
    _token = data.get('access_token')
    # 60s rezerva před expirací, ať request neodejde s právě umírajícím tokenem
    _token_expires_at = time.time() + int(data.get('expires_in', 3600)) - 60
    return _token


def _query(endpoint, body):
    """POST na IGDB API. Vrací list výsledků, nebo None při chybě.

    Tělo se posílá jako UTF-8 bajty, ne str: `requests.super_len()` počítá
    Content-Length přes `len(str)` = počet ZNAKŮ, kdežto urllib3 tělo zakóduje
    do UTF-8. U názvu s diakritikou (Pokémon, Ghost of Yōtei) je tak hlavička
    o N bajtů kratší než tělo, server request ořízne o koncové bajty a IGDB
    vrátí „400 Syntax Error: Missing `;` at end of query".
    """
    token = _get_token()
    if not token:
        return None

    payload = body.encode('utf-8')
    headers = {'Client-ID': config.IGDB_CLIENT_ID, 'Authorization': f'Bearer {token}'}
    resp = requests.post(f'{_API_URL}/{endpoint}', headers=headers, data=payload, timeout=10)

    if resp.status_code == 401:  # expirovaný/revokovaný token → 1× refresh
        token = _get_token(force_refresh=True)
        if not token:
            return None
        headers['Authorization'] = f'Bearer {token}'
        resp = requests.post(f'{_API_URL}/{endpoint}', headers=headers, data=payload, timeout=10)

    if resp.status_code != 200:
        log.warning("IGDB API error %d: %s", resp.status_code, resp.text[:150])
        return None
    return resp.json()


def _image_url(image_id, size):
    return f'https://images.igdb.com/igdb/image/upload/{size}/{image_id}.jpg'


def _search_game(game_name):
    """Najde hru podle názvu. Vrací dict s cover/screenshots/artworks, nebo None.

    Bere až 5 výsledků a preferuje první, který má screenshoty nebo artworky —
    fulltext často vrací na prvním místě DLC/edici bez obrázků.
    """
    if not game_name or game_name == 'N/A':
        return None
    if not is_configured():
        return None

    safe_name = re.sub(r'["\\;]', ' ', game_name).strip()
    body = (
        f'search "{safe_name}"; '
        'fields name, cover.image_id, screenshots.image_id, artworks.image_id; '
        'limit 5;'
    )
    try:
        results = _query('games', body)
    except Exception as e:
        log.warning("IGDB search error for '%s': %s", game_name, e)
        return None

    if not results:
        return None

    for game in results:
        if game.get('screenshots') or game.get('artworks'):
            return game
    return results[0]


def _canon(text):
    """Název bez diakritiky, interpunkce a velikosti písmen pro porovnání."""
    text = unicodedata.normalize('NFKD', text or '')
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return re.sub(r'[^a-z0-9]+', ' ', text.lower()).strip()


def name_matches(query, found_name):
    """Je nalezená hra opravdu ta hledaná značka, nebo jen náhodný výsledek?

    Fulltext IGDB vždycky něco vrátí — na „Pokémon" odpoví „Name That Pokemon",
    na „Nintendo" zase „Animal Crossing: New Horizons - Nintendo Switch 2
    Edition". U témat o značce (kde nejde o konkrétní hru) proto výsledek
    uznáme jen tehdy, když se název shoduje nebo jím začíná („Roblox" →
    „Roblox", „Roblox Studio"), ne když se značka jen někde mihne.
    """
    q, found = _canon(query), _canon(found_name)
    return bool(q) and (found == q or found.startswith(q + ' '))


def search_game_image(game_name, exact_only=False):
    """Hlavní obrázek hry pro featured image. Vrací URL nebo None.

    Preference: artwork (marketingová grafika, ekvivalent RAWG background_image)
    → screenshot → cover (portrét, až poslední možnost).

    `exact_only` zapíná kontrolu `name_matches` — viz její docstring.
    """
    game = _search_game(game_name)
    if not game:
        return None

    if exact_only and not name_matches(game_name, game.get('name', '')):
        log.info("IGDB vratil '%s' na dotaz '%s' — neshoda, obrazek zahozen",
                 game.get('name', '?'), game_name)
        return None

    for key, size in (('artworks', _SIZE_FEATURED), ('screenshots', _SIZE_FEATURED)):
        items = game.get(key) or []
        if items and items[0].get('image_id'):
            log.info("IGDB image nalezen pro '%s' (%s)", game_name, key)
            return _image_url(items[0]['image_id'], size)

    cover = game.get('cover') or {}
    if cover.get('image_id'):
        log.info("IGDB image nalezen pro '%s' (cover)", game_name)
        return _image_url(cover['image_id'], 't_cover_big')

    return None


def search_games(query, limit=6, max_images=6):
    """Kandidáti pro ruční výběr obrázku v dashboardu.

    Vrací list dictů {id, name, background, screenshots} — tvar odpovídá
    tomu, co dřív vracelo RAWG (dashboard JS ho konzumuje beze změny).
    """
    if not query or not is_configured():
        return []

    safe_query = re.sub(r'["\\;]', ' ', query).strip()
    body = (
        f'search "{safe_query}"; '
        'fields name, cover.image_id, screenshots.image_id, artworks.image_id; '
        f'limit {int(limit)};'
    )
    try:
        results = _query('games', body)
    except Exception as e:
        log.warning("IGDB search error for '%s': %s", query, e)
        return []

    games = []
    for game in results or []:
        shots = [_image_url(s['image_id'], _SIZE_SCREENSHOT)
                 for s in (game.get('screenshots') or []) if s.get('image_id')]
        arts = [_image_url(a['image_id'], _SIZE_FEATURED)
                for a in (game.get('artworks') or []) if a.get('image_id')]
        images = (arts + shots)[:max_images]
        if not images:
            continue
        games.append({
            'id': game.get('id'),
            'name': game.get('name', ''),
            'background': images[0],
            'screenshots': images,
        })
    return games


def fetch_screenshots(game_name, max_count=5):
    """Screenshoty hry pro Story Mode. Vrací list URL (max max_count), [] při chybě."""
    game = _search_game(game_name)
    if not game:
        return []

    urls = [
        _image_url(s['image_id'], _SIZE_SCREENSHOT)
        for s in (game.get('screenshots') or [])
        if s.get('image_id')
    ][:max_count]

    if urls:
        log.info("IGDB screenshoty pro '%s': %d nalezeno", game_name, len(urls))
    return urls
