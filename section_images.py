"""
Section Images - RAWG screenshoty pro Story Mode v mobilní appce.
Stahuje short_screenshots z RAWG API a ukládá je jako WP post meta
(gameinfo_section_images). Na webu se nezobrazují — jen v appce.

Před stažením z RAWG nejdřív hledá existující obrázky ve WP Media Library
podle názvu hry — šetří RAWG API volání i WP storage.
"""

import json
import requests
import config
import wp_publisher
from logger import setup_logger

log = setup_logger(__name__)


def find_existing_screenshots(game_name, min_count=3, max_count=5):
    """
    Hledá existující obrázky ve WP Media Library podle názvu hry (title search).
    Vrací list of (media_id, source_url) tuples, nebo prázdný list.
    """
    try:
        resp = requests.get(
            wp_publisher._api_url('media'),
            headers=wp_publisher._auth_headers(),
            params={
                'search': game_name,
                'per_page': max_count,
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
            log.info("WP cache hit pro '%s': %d existujících obrázků", game_name, len(matched))
            return matched[:max_count]

        return []

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

    # 1. Zkus WP cache
    existing = find_existing_screenshots(game_name, min_count=3, max_count=max_count)
    if existing:
        log.info("Screenshoty pro Story Mode: %d z WP cache", len(existing))
        return build_section_images_meta(existing)

    # 2. Fallback RAWG → upload
    urls = fetch_rawg_screenshots(game_name, max_count=max_count)
    if not urls:
        return None

    uploaded = []
    for sc_url in urls:
        sc_id, sc_src, sc_err = wp_publisher.upload_media(sc_url, title=game_name)
        if sc_id and sc_src:
            uploaded.append((sc_id, sc_src))
        else:
            log.warning("Screenshot upload selhal: %s", sc_err)

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
