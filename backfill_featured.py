"""Zpětné doplnění featured images a Story Mode screenshotů u publikovaných postů.

Vznikl při výpadku RAWG.io 2026-08-02/03: články tehdy vycházely úplně bez
náhledového obrázku (fallback řetěz končil u brand loga) a bez Story Mode
(žádné screenshoty). Skript projde poslední záznamy v publish_log a u postů
s featured_media 0 (nebo nouzovým GAMEfo logem) doplní obrázek stejným řetězem
jako publish_pipeline: RAWG image → Story Mode screenshot → brand logo →
GAMEfo logo. Zároveň doplní chybějící gameinfo_section_images meta (aktivuje
Story Mode) u témat s reálnou hrou.

Idempotentní — bezpečné pouštět opakovaně. Po náběhu RAWG povýší nouzová
GAMEfo loga na skutečné obrázky; posty s jiným featured obrázkem nechává být.

Použití:
    python backfill_featured.py [--limit 30] [--dry-run]
"""

import argparse
import json

import requests

import brand_logos
import section_images
import wp_publisher
from database import get_db
from logger import setup_logger
from publish_pipeline import search_game_image

log = setup_logger(__name__)

# featured_media hodnoty považované za "chybí obrázek" — 0 (žádný) a nouzové
# GAMEfo logo, které má být při dostupném RAWG povýšeno na skutečný obrázek.
_PLACEHOLDER_IDS = (0, brand_logos.GAMEFO_LOGO)


def _get_post(post_id):
    resp = requests.get(
        wp_publisher._api_url(f'posts/{post_id}'),
        headers=wp_publisher._auth_headers(),
        params={'_fields': 'id,featured_media,meta,link'},
        timeout=15,
    )
    if resp.status_code != 200:
        log.warning("GET post %s selhal (%d)", post_id, resp.status_code)
        return None
    return resp.json()


def _update_post(post_id, payload, dry_run=False):
    if dry_run:
        log.info("[DRY RUN] update post %s: %s", post_id, payload)
        return True
    resp = requests.post(
        wp_publisher._api_url(f'posts/{post_id}'),
        headers=wp_publisher._auth_headers(),
        json=payload,
        timeout=20,
    )
    if resp.status_code not in (200, 201):
        log.warning("Update post %s selhal (%d): %s", post_id, resp.status_code, resp.text[:200])
        return False
    return True


def _recent_published(limit):
    """Poslední 'published' záznamy z publish_log (nejnovější první)."""
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT data_json FROM publish_log WHERE action='published' "
            "ORDER BY timestamp DESC LIMIT ?", (limit,),
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


def heal_entry(entry, dry_run=False):
    """Doplní featured image + section_images meta u CZ i EN postu jednoho článku."""
    game_name = entry.get('game_name') or ''
    title = entry.get('title') or ''
    # resolve_game_name fallback: game_name == topic znamená, že analyzer žádnou
    # reálnou hru neurčil (brand/obecné téma) — RAWG by na celou českou větu
    # vrátil nesmysl, takže screenshoty ani RAWG image nezkoušíme.
    has_real_game = bool(game_name) and game_name != entry.get('topic')

    post_ids = [pid for pid in (entry.get('cs_post_id'), entry.get('en_post_id')) if pid]
    if not post_ids:
        return

    posts = {pid: _get_post(pid) for pid in post_ids}
    posts = {pid: p for pid, p in posts.items() if p}
    if not posts:
        return

    needs_featured = [pid for pid, p in posts.items()
                      if p.get('featured_media', 0) in _PLACEHOLDER_IDS]
    existing_meta = next(
        (p['meta'].get('gameinfo_section_images') for p in posts.values()
         if (p.get('meta') or {}).get('gameinfo_section_images')),
        None,
    )
    needs_meta = has_real_game and [
        pid for pid, p in posts.items()
        if not (p.get('meta') or {}).get('gameinfo_section_images')
    ]

    if not needs_featured and not needs_meta:
        return

    log.info("— '%s' (posty %s): featured chybí u %s, screenshoty u %s",
             title, post_ids, needs_featured or 'nikoho', needs_meta or 'nikoho')

    # Screenshoty: existující meta z druhé jazykové verze, jinak WP cache/RAWG
    meta_json = existing_meta
    if not meta_json and has_real_game:
        meta_json = section_images.get_or_fetch_screenshots(game_name)

    # Featured: stejné pořadí jako resolve_featured_image
    featured = None
    if has_real_game and needs_featured:
        image_url = search_game_image(game_name)
        if image_url:
            media_id, _, err = wp_publisher.upload_media(image_url, title=title)
            if media_id:
                featured = media_id
                log.info("Game image uploadnut (ID: %d)", media_id)
            else:
                log.warning("Upload game image selhal: %s", err)
    if not featured and meta_json:
        featured = json.loads(meta_json)[0].get('media_id')
        if featured:
            log.info("Featured = prvni Story Mode screenshot (ID: %d)", featured)
    if not featured:
        featured = brand_logos.resolve_brand_logo(game_name, title)
        if featured:
            log.info("Featured = brand logo (ID: %d)", featured)
    if not featured:
        featured = brand_logos.GAMEFO_LOGO
        log.info("Featured = genericke GAMEfo logo (ID: %d)", featured)

    for pid, post in posts.items():
        payload = {}
        if pid in needs_featured and featured not in (None, post.get('featured_media')):
            payload['featured_media'] = featured
        if needs_meta and pid in needs_meta and meta_json:
            payload['meta'] = {'gameinfo_section_images': meta_json}
        if payload:
            if _update_post(pid, payload, dry_run=dry_run):
                log.info("Post %d aktualizovan: %s", pid, ', '.join(payload.keys()))


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--limit', type=int, default=30,
                        help='Kolik posledních publish_log záznamů projít (default 30)')
    parser.add_argument('--dry-run', action='store_true',
                        help='Jen vypsat, co by se změnilo — nic nezapisovat')
    args = parser.parse_args()

    entries = _recent_published(args.limit)
    log.info("Kontroluji %d publikovaných článků (dry_run=%s)", len(entries), args.dry_run)
    for entry in entries:
        heal_entry(entry, dry_run=args.dry_run)
    log.info("Hotovo.")


if __name__ == '__main__':
    main()
