"""Zpětné doplnění YouTube embedů u publikovaných článků.

yt-dlp hledání bylo v produkci rozbité od 21. 7. 2026 (plná extrakce padala na
age-restricted videích a bot-checku) a keyword brána navíc přeskakovala články,
které o videu nemluvily. Skript projde publish_log záznamy od --since, u článků
o reálné hře bez YouTube embedu najde embedovatelný trailer
(youtube_embed.find_embeddable_video) a vloží ho do CZ i EN verze — jedno video
pro obě jazykové verze, stejně jako publish_pipeline.embed_youtube.

Idempotentní — posty, které už YouTube obsahují, přeskakuje. Brand témata
a témata bez konkrétní hry (game_name == topic) se přeskakují — stejná logika
jako publish_pipeline.

Použití:
    python backfill_youtube.py [--since 2026-07-21] [--limit 100] [--dry-run]
"""

import argparse
import json

import requests

import brand_logos
import wp_publisher
import youtube_embed
from database import get_db
from logger import setup_logger

log = setup_logger(__name__)


def _published_since(since, limit):
    """'published' záznamy z publish_log od data `since` (nejstarší první)."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT data_json FROM publish_log WHERE action='published' "
            "AND timestamp >= ? ORDER BY timestamp ASC LIMIT ?",
            (since, limit),
        ).fetchall()
    finally:
        conn.close()
    entries = []
    for (raw,) in rows:
        try:
            entries.append(json.loads(raw))
        except (TypeError, ValueError):
            continue
    return entries


def _get_post_raw_content(post_id):
    """Raw (neredenderovaný) obsah postu, nebo None."""
    resp = requests.get(
        wp_publisher._api_url(f'posts/{post_id}'),
        headers=wp_publisher._auth_headers(),
        params={'context': 'edit', '_fields': 'id,content,link'},
        timeout=15,
    )
    if resp.status_code != 200:
        log.warning("GET post %s selhal (%d)", post_id, resp.status_code)
        return None
    return (resp.json().get('content') or {}).get('raw')


def _update_post_content(post_id, content, dry_run=False):
    if dry_run:
        log.info("[DRY RUN] update post %s (content %d znaků)", post_id, len(content))
        return True
    resp = requests.post(
        wp_publisher._api_url(f'posts/{post_id}'),
        headers=wp_publisher._auth_headers(),
        json={'content': content},
        timeout=30,
    )
    if resp.status_code not in (200, 201):
        log.warning("Update post %s selhal (%d): %s", post_id, resp.status_code, resp.text[:200])
        return False
    return True


def _has_youtube(content):
    return 'youtube.com' in content or 'youtu.be' in content


def heal_entry(entry, dry_run=False):
    """Doplní YouTube embed do CZ i EN postu jednoho článku (pokud chybí)."""
    game_name = entry.get('game_name') or ''
    title = entry.get('title') or ''
    # game_name == topic → analyzer žádnou reálnou hru neurčil; brand téma →
    # query by vrátila náhodné video. Obojí přeskočit (viz embed_youtube).
    has_real_game = (bool(game_name) and game_name != entry.get('topic')
                     and not brand_logos.resolve_brand_logo_strict(game_name))
    if not has_real_game:
        return

    posts = {}  # post_id -> (lang, raw_content)
    for pid, lang in ((entry.get('cs_post_id'), 'cs'), (entry.get('en_post_id'), 'en')):
        if not pid:
            continue
        raw = _get_post_raw_content(pid)
        if raw is None:
            continue
        if _has_youtube(raw):
            log.info("Post %s ('%s', %s) už YouTube obsahuje, přeskakuji", pid, title, lang)
            continue
        posts[pid] = (lang, raw)

    if not posts:
        return

    query = f"{game_name} official trailer 2026"
    log.info("— '%s' (posty %s): hledám video: %s", title, list(posts), query)
    video = youtube_embed.find_embeddable_video(query, game_name=game_name)
    if not video:
        log.warning("YouTube video nenalezeno pro: %s", query)
        return
    log.info("Nalezeno video: %s (%s)", video['title'], video['url'])

    for pid, (lang, raw) in posts.items():
        new_content = youtube_embed.force_embed_youtube(raw, video['id'], lang=lang)
        if _update_post_content(pid, new_content, dry_run=dry_run):
            log.info("Post %d (%s): embed vložen", pid, lang)


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--since', default='2026-07-21',
                        help='Od kterého data (timestamp prefix) procházet publish_log')
    parser.add_argument('--limit', type=int, default=100,
                        help='Max záznamů publish_log (default 100)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Jen vypsat, co by se změnilo — nic nezapisovat')
    args = parser.parse_args()

    entries = _published_since(args.since, args.limit)
    log.info("Kontroluji %d publikovaných článků od %s (dry_run=%s)",
             len(entries), args.since, args.dry_run)
    for entry in entries:
        heal_entry(entry, dry_run=args.dry_run)
    log.info("Hotovo.")


if __name__ == '__main__':
    main()
