#!/usr/bin/env python3
"""
Fix script: Opraví špatné obrázky (Forza) u story karet Subnautica 2 článku.
Posts: 7214 (CZ), 7215 (EN)

Spuštění: python fix_subnautica_story_images.py
(z kořenové složky projektu gaming-content-agent)
"""

import json
import sys
import os

# Přidej projekt do path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import config
import wp_publisher
from section_images import fetch_rawg_screenshots, build_section_images_meta, _slugify


POST_IDS = [7214, 7215]
GAME_NAME = "Subnautica 2"


def get_post_meta(post_id):
    """Načte meta data postu z WP REST API."""
    import requests
    resp = requests.get(
        wp_publisher._api_url(f'posts/{post_id}'),
        headers=wp_publisher._auth_headers(),
        params={'_fields': 'id,title,meta,featured_media'},
        timeout=15,
    )
    if resp.status_code != 200:
        print(f"  ERROR: HTTP {resp.status_code} - {resp.text[:200]}")
        return None
    return resp.json()


def update_post_meta(post_id, meta_key, meta_value):
    """Aktualizuje meta pole postu."""
    import requests
    resp = requests.post(
        wp_publisher._api_url(f'posts/{post_id}'),
        headers=wp_publisher._auth_headers(),
        json={'meta': {meta_key: meta_value}},
        timeout=15,
    )
    if resp.status_code not in (200, 201):
        print(f"  ERROR při update post {post_id}: HTTP {resp.status_code} - {resp.text[:200]}")
        return False
    return True


def main():
    print("=" * 60)
    print("FIX: Oprava story karet obrázků pro Subnautica 2")
    print("=" * 60)

    # 1. Zjisti aktuální stav
    print("\n[1] Zjišťuji aktuální stav postů...")
    for post_id in POST_IDS:
        data = get_post_meta(post_id)
        if data:
            title = data.get('title', {}).get('rendered', '?')
            meta = data.get('meta', {})
            section_images = meta.get('gameinfo_section_images', '')
            print(f"\n  Post {post_id}: {title}")
            print(f"  Featured media ID: {data.get('featured_media')}")
            if section_images:
                try:
                    imgs = json.loads(section_images) if isinstance(section_images, str) else section_images
                    print(f"  Section images ({len(imgs)} ks):")
                    for img in imgs:
                        print(f"    - ID {img.get('media_id')}: {img.get('url', '?')}")
                except (json.JSONDecodeError, TypeError):
                    print(f"  Section images (raw): {str(section_images)[:200]}")
            else:
                print("  Section images: PRÁZDNÉ")

    # 2. Stáhni správné screenshoty z RAWG
    print(f"\n[2] Stahuji screenshoty z RAWG pro '{GAME_NAME}'...")
    screenshots_urls = fetch_rawg_screenshots(GAME_NAME, max_count=5)

    if not screenshots_urls:
        print("  RAWG nevrátil žádné screenshoty!")
        print("  Zkouším alternativní hledání...")
        # Fallback: zkus 'subnautica-2' přímo
        screenshots_urls = fetch_rawg_screenshots("Subnautica 2", max_count=5)

    if not screenshots_urls:
        print("  FATAL: Žádné screenshoty nenalezeny. Zkus ručně zadat slug na RAWG.")
        sys.exit(1)

    print(f"  Nalezeno {len(screenshots_urls)} screenshotů:")
    for i, url in enumerate(screenshots_urls, 1):
        print(f"    {i}. {url}")

    # 3. Smaž staré (špatné) screenshoty z WP pokud existují
    print(f"\n[3] Uploaduji správné screenshoty do WP Media Library...")
    slug = _slugify(GAME_NAME)
    uploaded = []

    for i, sc_url in enumerate(screenshots_urls, 1):
        fname = f"{slug}-screenshot-{i}.jpg"
        print(f"  Uploading {fname}...", end=" ")

        # Nejdřív zkontroluj jestli existuje starý se stejným jménem
        existing_id, existing_url = wp_publisher._find_existing_media(fname)
        if existing_id:
            # Smaž starý (obsahuje Forza obrázek)
            import requests
            print(f"mazání starého ID {existing_id}...", end=" ")
            del_resp = requests.delete(
                wp_publisher._api_url(f'media/{existing_id}'),
                headers=wp_publisher._auth_headers(),
                params={'force': 'true'},
                timeout=10,
            )
            if del_resp.status_code in (200, 201):
                print("smazáno.", end=" ")
            else:
                print(f"smazání selhalo ({del_resp.status_code}).", end=" ")

        # Upload nový
        sc_id, sc_src, sc_err = wp_publisher.upload_media(sc_url, title=GAME_NAME, custom_filename=fname)
        if sc_id and sc_src:
            uploaded.append((sc_id, sc_src))
            print(f"OK (ID: {sc_id})")
        else:
            print(f"CHYBA: {sc_err}")

    if not uploaded:
        print("  FATAL: Žádný screenshot se nepodařilo uploadnout!")
        sys.exit(1)

    print(f"\n  Úspěšně uploadováno: {len(uploaded)}/{len(screenshots_urls)}")

    # 4. Aktualizuj meta u obou postů
    new_meta_value = build_section_images_meta(uploaded)
    print(f"\n[4] Aktualizuji section_images meta u postů {POST_IDS}...")

    for post_id in POST_IDS:
        print(f"  Post {post_id}...", end=" ")
        if update_post_meta(post_id, 'gameinfo_section_images', new_meta_value):
            print("OK")
        else:
            print("CHYBA!")

    # 5. Verifikace
    print(f"\n[5] Verifikace...")
    for post_id in POST_IDS:
        data = get_post_meta(post_id)
        if data:
            meta = data.get('meta', {})
            section_images = meta.get('gameinfo_section_images', '')
            if section_images:
                try:
                    imgs = json.loads(section_images) if isinstance(section_images, str) else section_images
                    print(f"  Post {post_id}: {len(imgs)} obrázků ✓")
                    for img in imgs:
                        url = img.get('url', '')
                        # Check if it's NOT forza
                        if 'forza' in url.lower():
                            print(f"    ⚠️  STÁLE FORZA: {url}")
                        else:
                            print(f"    ✓ {url[:80]}...")
                except (json.JSONDecodeError, TypeError):
                    print(f"  Post {post_id}: nelze parsovat section_images")
            else:
                print(f"  Post {post_id}: section_images prázdné!")

    print("\n" + "=" * 60)
    print("HOTOVO! Zkontroluj story karty v appce.")
    print("=" * 60)


if __name__ == '__main__':
    main()
