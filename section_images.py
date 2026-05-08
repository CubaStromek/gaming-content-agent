"""
Section Images - RAWG screenshoty pro Story Mode v mobilní appce.
Stahuje short_screenshots z RAWG API a ukládá je jako WP post meta
(gameinfo_section_images). Na webu se nezobrazují — jen v appce.

Před stažením z RAWG nejdřív hledá existující obrázky ve WP Media Library
podle názvu hry — šetří RAWG API volání i WP storage.
"""

import json
import re
import requests
import config
import wp_publisher
from logger import setup_logger

log = setup_logger(__name__)


def _slugify(text):
    """Převede název hry na URL-safe slug (např. 'GTA 6' → 'gta-6')."""
    text = text.lower().strip()
    text = re.sub(r'[^a-z0-9]+', '-', text)
    return text.strip('-') or 'game'


def find_screenshots_by_filename(game_name, max_count=5):
    """
    Dedup č. 1: hledá screenshoty podle deterministického filename slugu
    `<slug>-screenshot-N.jpg` (1..max_count). Robustní vůči přepsanému/chybějícímu titulku.
    Vrací list (media_id, source_url) v pořadí 1..N. Prázdný list = nenalezeno.
    (WP timeout je polknutý uvnitř _find_existing_media — projeví se jako prázdný list.
    Detekce nedostupnosti WP je řešená v navazujícím find_existing_screenshots.)
    """
    slug = _slugify(game_name)
    matched = []
    for i in range(1, max_count + 1):
        fname = f"{slug}-screenshot-{i}.jpg"
        mid, src = wp_publisher._find_existing_media(fname)
        if mid and src:
            matched.append((mid, src))
        else:
            break  # mezera v sérii — další indexy nemá smysl zkoušet
    return matched


def find_existing_screenshots(game_name, min_count=3, max_count=5):
    """
    Dedup č. 2 (fallback): hledá obrázky podle title equals game_name přes WP search.
    Vrací list of (media_id, source_url), nebo prázdný list.
    Vrací None pokud WP není dostupný (timeout/connection error).
    """
    try:
        resp = requests.get(
            wp_publisher._api_url('media'),
            headers=wp_publisher._auth_headers(),
            params={
                'search': game_name,
                'per_page': 50,  # dost prostoru pro exact-title filtr
                'media_type': 'image',
                'orderby': 'date',
                'order': 'desc',
            },
            timeout=10,
        )
        if resp.status_code != 200:
            return []

        results = resp.json()
        # Filtruj jen obrázky, jejichž title skutečně odpovídá hře
        game_lower = game_name.lower().strip()
        matched = []
        for item in results:
            title = item.get('title', {}).get('rendered', '').lower().strip()
            if title == game_lower:
                src = item.get('source_url', '')
                if src:
                    matched.append((item['id'], src))

        if len(matched) >= min_count:
            log.info("WP cache hit pro '%s' (title): %d existujících obrázků", game_name, len(matched))
            return matched[:max_count]

        return []

    except requests.exceptions.Timeout:
        log.warning("WP media search timeout pro '%s' — WP nedostupný, přeskakuji upload screenshotů", game_name)
        return None  # None = WP nedostupný, nespouštět upload
    except Exception as e:
        log.warning("WP media search error pro '%s': %s", game_name, e)
        return []


def fetch_rawg_screenshots(game_name, max_count=5):
    """
    Stáhne screenshoty hry z RAWG API (short_screenshots).
    Vrací list URL obrázků (max max_count), prázdný list při chybě.
    """
    if not game_name or game_name == 'N/A':
        return []

    if not config.RAWG_API_KEY:
        log.warning("RAWG_API_KEY není nastavený, přeskakuji screenshoty")
        return []

    try:
        resp = requests.get(
            'https://api.rawg.io/api/games',
            params={'key': config.RAWG_API_KEY, 'search': game_name, 'page_size': 1},
            timeout=10,
        )
        if resp.status_code != 200:
            log.warning("RAWG API error %d pro '%s'", resp.status_code, game_name)
            return []

        results = resp.json().get('results', [])
        if not results:
            log.info("RAWG: žádné výsledky pro '%s'", game_name)
            return []

        screenshots = results[0].get('short_screenshots', [])
        urls = [s['image'] for s in screenshots if s.get('image')]

        urls = urls[:max_count]
        log.info("RAWG screenshoty pro '%s': %d nalezeno", game_name, len(urls))
        return urls

    except Exception as e:
        log.warning("RAWG screenshots error pro '%s': %s", game_name, e)
        return []


def get_or_fetch_screenshots(game_name, max_count=5):
    """
    Hlavní entry point pro Story Mode screenshoty.
    1. Hledá existující ve WP Media Library (žádný upload)
    2. Fallback: stáhne z RAWG API a uploadne do WP

    Vrací JSON string pro WP meta, nebo None.
    """
    if not game_name or game_name == 'N/A':
        return None

    # 1a. Filename-based dedup (deterministický slug — robustní vůči přepsaným titulkům)
    by_filename = find_screenshots_by_filename(game_name, max_count=max_count)
    if len(by_filename) >= 3:
        log.info("Screenshoty pro Story Mode: %d z WP cache (filename dedup)", len(by_filename))
        return build_section_images_meta(by_filename)

    # 1b. Title-based dedup (fallback pro starší obrázky bez deterministického filename)
    existing = find_existing_screenshots(game_name, min_count=3, max_count=max_count)
    if existing is None:
        return None
    if existing:
        log.info("Screenshoty pro Story Mode: %d z WP cache (title dedup)", len(existing))
        return build_section_images_meta(existing)

    # 2. Fallback RAWG → upload
    urls = fetch_rawg_screenshots(game_name, max_count=max_count)
    if not urls:
        return None

    uploaded = []
    slug = _slugify(game_name)
    for i, sc_url in enumerate(urls, 1):
        fname = f"{slug}-screenshot-{i}.jpg"
        sc_id, sc_src, sc_err = wp_publisher.upload_media(sc_url, title=game_name, custom_filename=fname)
        if sc_id and sc_src:
            uploaded.append((sc_id, sc_src))
        else:
            log.warning("Screenshot upload selhal: %s", sc_err)
            if "timeout" in (sc_err or "").lower():
                log.warning("WP upload timeout — přerušuji sérii uploadů pro '%s'", game_name)
                break  # Při timeoutu neopakovat další pokusy — prevence Fail2Ban banu

    if not uploaded:
        return None

    log.info("Screenshoty pro Story Mode: %d uploadnuto z RAWG", len(uploaded))
    return build_section_images_meta(uploaded)


def build_section_images_meta(uploaded_images):
    """
    Převede list uploadnutých screenshotů na JSON string pro WP post meta.

    Args:
        uploaded_images: list of (media_id, source_url) tuples

    Returns:
        JSON string pro uložení do gameinfo_section_images meta pole,
        nebo None pokud prázdný list.
    """
    if not uploaded_images:
        return None

    data = [{'media_id': mid, 'url': url} for mid, url in uploaded_images]
    return json.dumps(data)
