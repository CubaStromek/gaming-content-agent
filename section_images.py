"""
Section Images - RAWG screenshoty pro Story Mode v mobilní appce.
Stahuje short_screenshots z RAWG API a ukládá je jako WP post meta
(gameinfo_section_images). Na webu se nezobrazují — jen v appce.
"""

import json
import requests
import config
from logger import setup_logger

log = setup_logger(__name__)


def fetch_rawg_screenshots(game_name, max_count=5):
    """
    Stáhne screenshoty hry z RAWG API (short_screenshots).
    Vrací list URL obrázků (max max_count), prázdný list při chybě.
    """
    if not config.RAWG_API_KEY:
        log.warning("RAWG_API_KEY není nastavený, přeskakuji screenshoty")
        return []

    if not game_name or game_name == 'N/A':
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
