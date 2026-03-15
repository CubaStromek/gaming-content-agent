"""
Article Cleanup — mazání starých WP článků bez vazby na Game Page.
Smaže post + featured image + section images + spárovaný překlad (CS↔EN).
Články propojené s Game Page (gameinfo_game_pages meta) se NIKDY nesmažou.

Použití:
    python article_cleanup.py              # živý run (maže články starší 30 dní)
    python article_cleanup.py --dry-run    # jen loguje co by smazal
    python article_cleanup.py --days 14    # starší než 14 dní
"""

import json
import argparse
from datetime import datetime, timedelta, timezone

import requests
import wp_publisher
from database import get_db
from logger import setup_logger

log = setup_logger('article_cleanup')

CLEANUP_AFTER_DAYS = 30


def _gamefo_api_url(path):
    """URL pro custom gamefo/v1 endpointy."""
    base = wp_publisher.config.WP_URL.rstrip('/')
    return f"{base}/wp-json/gamefo/v1/{path.lstrip('/')}"


def fetch_old_posts(days=CLEANUP_AFTER_DAYS):
    """Stáhne všechny published posty starší než `days` dní (obě jazyky)."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    headers = wp_publisher._auth_headers()
    all_posts = []
    page = 1

    while True:
        url = wp_publisher._api_url('posts')
        params = {
            'before': cutoff,
            'per_page': 100,
            'page': page,
            'status': 'publish',
            '_fields': 'id,title,date,meta,featured_media,lang',
        }

        try:
            resp = requests.get(url, headers=headers, params=params, timeout=30)
        except requests.RequestException as e:
            log.error("Chyba při stahování postů (strana %d): %s", page, e)
            break

        if resp.status_code == 400:
            # No more pages
            break

        if resp.status_code != 200:
            log.error("WP API vrátilo %d při stahování postů (strana %d)", resp.status_code, page)
            break

        posts = resp.json()
        if not posts:
            break

        all_posts.extend(posts)

        total_pages = int(resp.headers.get('X-WP-TotalPages', 1))
        if page >= total_pages:
            break
        page += 1

    log.info("Nalezeno %d postů starších než %d dní", len(all_posts), days)
    return all_posts


def is_protected(post):
    """True pokud post má vazbu na Game Page (gameinfo_game_pages meta)."""
    meta = post.get('meta', {})
    if not isinstance(meta, dict):
        # Defenzivně: pokud meta chybí nebo má neočekávaný formát, přeskočit
        log.warning("Post #%d nemá meta pole — přeskakuji (defenzivní)", post['id'])
        return True

    game_pages = meta.get('gameinfo_game_pages', [])
    if not isinstance(game_pages, list):
        game_pages = []

    # Filtrovat prázdné/nulové hodnoty
    game_pages = [gp for gp in game_pages if gp]
    return len(game_pages) > 0


def get_translation_id(post_id):
    """Vrátí ID spárovaného překladu (nebo None)."""
    headers = wp_publisher._auth_headers()
    url = _gamefo_api_url(f'post-translations/{post_id}')

    try:
        resp = requests.get(url, headers=headers, timeout=15)
        if resp.status_code != 200:
            return None

        translations = resp.json()
        # translations = {"cs": 123, "en": 456}
        for lang, tid in translations.items():
            if int(tid) != post_id:
                return int(tid)
    except Exception as e:
        log.warning("Nelze zjistit překlad pro post #%d: %s", post_id, e)

    return None


def get_post_details(post_id):
    """Stáhne detail postu (pro kontrolu meta překladu)."""
    headers = wp_publisher._auth_headers()
    url = wp_publisher._api_url(f'posts/{post_id}')
    params = {'_fields': 'id,title,date,meta,featured_media'}

    try:
        resp = requests.get(url, headers=headers, params=params, timeout=15)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        log.warning("Nelze stáhnout post #%d: %s", post_id, e)

    return None


def delete_media(media_id, dry_run=False):
    """Smaže media attachment z WP. Vrátí True pokud úspěch."""
    if not media_id or media_id == 0:
        return False

    if dry_run:
        log.info("  [DRY-RUN] Smazal bych media #%d", media_id)
        return True

    headers = wp_publisher._auth_headers()
    url = wp_publisher._api_url(f'media/{media_id}')

    try:
        resp = requests.delete(url, headers=headers, params={'force': 'true'}, timeout=15)
        if resp.status_code in (200, 204):
            return True
        elif resp.status_code == 404:
            log.debug("  Media #%d již neexistuje (404)", media_id)
            return True
        else:
            log.warning("  Nelze smazat media #%d: HTTP %d", media_id, resp.status_code)
            return False
    except Exception as e:
        log.warning("  Chyba při mazání media #%d: %s", media_id, e)
        return False


def delete_post_media(post, dry_run=False):
    """Smaže featured image a section images postu. Vrátí počet smazaných."""
    count = 0

    # Featured image
    featured = post.get('featured_media', 0)
    if featured and featured > 0:
        if delete_media(featured, dry_run):
            count += 1

    # Section images (Story Mode screenshots)
    meta = post.get('meta', {})
    section_images_raw = meta.get('gameinfo_section_images', '')
    if section_images_raw and isinstance(section_images_raw, str):
        try:
            section_images = json.loads(section_images_raw)
            if isinstance(section_images, list):
                for img in section_images:
                    mid = img.get('media_id') if isinstance(img, dict) else None
                    if mid:
                        if delete_media(mid, dry_run):
                            count += 1
        except json.JSONDecodeError:
            pass

    return count


def delete_post(post_id, dry_run=False):
    """Smaže WP post (force = bypass trash). Vrátí True pokud úspěch."""
    if dry_run:
        log.info("  [DRY-RUN] Smazal bych post #%d", post_id)
        return True

    headers = wp_publisher._auth_headers()
    url = wp_publisher._api_url(f'posts/{post_id}')

    try:
        resp = requests.delete(url, headers=headers, params={'force': 'true'}, timeout=15)
        if resp.status_code in (200, 204):
            return True
        elif resp.status_code == 404:
            log.debug("  Post #%d již neexistuje (404)", post_id)
            return True
        else:
            log.error("  Nelze smazat post #%d: HTTP %d", post_id, resp.status_code)
            return False
    except Exception as e:
        log.error("  Chyba při mazání postu #%d: %s", post_id, e)
        return False


def log_cleanup(post_id, title, lang, paired_id, media_count, dry_run):
    """Zapíše záznam do cleanup_log tabulky."""
    try:
        db = get_db()
        db.execute(
            """INSERT INTO cleanup_log
               (timestamp, post_id, post_title, lang, paired_post_id, media_deleted, dry_run)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (datetime.now().isoformat(), post_id, title, lang, paired_id, media_count, 1 if dry_run else 0)
        )
        db.commit()
        db.close()
    except Exception as e:
        log.warning("Nelze zapsat cleanup log: %s", e)


def get_post_title(post):
    """Extrahuje titulek z WP REST API response."""
    title = post.get('title', {})
    if isinstance(title, dict):
        return title.get('rendered', f"Post #{post['id']}")
    return str(title)


def get_post_lang(post):
    """Vrátí jazyk postu (z Polylang)."""
    return post.get('lang', '??')


def run(dry_run=False, days=CLEANUP_AFTER_DAYS):
    """Hlavní entry point — najde a smaže staré články bez game page linku."""
    prefix = "[DRY-RUN] " if dry_run else ""
    log.info("=== %sArticle Cleanup START (starší než %d dní) ===", prefix, days)

    posts = fetch_old_posts(days)
    if not posts:
        log.info("Žádné staré posty k vyhodnocení.")
        return

    processed_ids = set()  # Abychom nezduplikovali páry
    deleted_count = 0
    skipped_count = 0
    media_count = 0

    for post in posts:
        post_id = post['id']
        if post_id in processed_ids:
            continue

        title = get_post_title(post)
        lang = get_post_lang(post)

        # Kontrola ochrany
        if is_protected(post):
            log.info("SKIP #%d [%s] \"%s\" — má Game Page link", post_id, lang, title)
            skipped_count += 1
            processed_ids.add(post_id)
            continue

        # Najdi spárovaný překlad
        paired_id = get_translation_id(post_id)
        paired_post = None

        if paired_id:
            processed_ids.add(paired_id)
            # Zkontroluj i překlad
            paired_post = get_post_details(paired_id)
            if paired_post and is_protected(paired_post):
                log.info("SKIP #%d [%s] \"%s\" — překlad #%d má Game Page link",
                         post_id, lang, title, paired_id)
                skipped_count += 1
                processed_ids.add(post_id)
                continue

        # Smazat media obou verzí
        log.info("%sDELETE #%d [%s] \"%s\"%s",
                 prefix, post_id, lang, title,
                 f" (+ překlad #{paired_id})" if paired_id else "")

        mc = delete_post_media(post, dry_run)
        if paired_post:
            mc += delete_post_media(paired_post, dry_run)

        # Smazat oba posty
        delete_post(post_id, dry_run)
        if paired_id:
            delete_post(paired_id, dry_run)

        media_count += mc
        deleted_count += 1
        processed_ids.add(post_id)

        # Logovat do DB
        log_cleanup(post_id, title, lang, paired_id, mc, dry_run)

    log.info("=== %sArticle Cleanup DONE ===", prefix)
    log.info("Smazáno: %d článků (+ překlady), Přeskočeno: %d (game page), Média smazána: %d",
             deleted_count, skipped_count, media_count)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Cleanup starých WP článků bez Game Page linku')
    parser.add_argument('--dry-run', action='store_true',
                        help='Jen loguje co by smazal, nic nemaže')
    parser.add_argument('--days', type=int, default=CLEANUP_AFTER_DAYS,
                        help=f'Smazat posty starší než N dní (default: {CLEANUP_AFTER_DAYS})')
    args = parser.parse_args()

    run(dry_run=args.dry_run, days=args.days)
