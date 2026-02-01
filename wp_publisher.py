"""
WordPress Publisher - WP REST API modul
Vytváří draft posty přes WP REST API s Basic Auth.
Podporuje kategorie, tagy, featured image upload a Polylang propojení.
"""

import base64
import re
import time
import requests
import config


# In-memory cache pro kategorie (per-language) a status tagy
_categories_cache = {}
_status_tags_cache = {'data': None, 'fetched_at': 0}
_CACHE_TTL = 300  # 5 minut


def _auth_headers():
    """Vrátí headers s Basic Auth pro WP REST API."""
    credentials = f"{config.WP_USER}:{config.WP_APP_PASSWORD}"
    token = base64.b64encode(credentials.encode()).decode()
    return {
        'Authorization': f'Basic {token}',
    }


def _api_url(path):
    """Sestaví plnou URL pro WP REST API."""
    base = config.WP_URL.rstrip('/')
    return f"{base}/wp-json/wp/v2/{path.lstrip('/')}"


def is_configured():
    """Wrapper pro config.is_wp_configured()."""
    return config.is_wp_configured()


def strip_first_heading(html):
    """Odstraní první h1/h2 z HTML obsahu (WP zobrazuje title zvlášť).
    Zvládne i markdown artefakty (```html, # heading) před/místo HTML tagu."""
    # Nejdřív vyčisti markdown code fences a leading whitespace
    cleaned = re.sub(r'^\s*```html\s*\n?', '', html)
    cleaned = re.sub(r'```\s*$', '', cleaned, flags=re.MULTILINE)
    # Odstraň markdown heading (# Title) na začátku
    cleaned = re.sub(r'^\s*#{1,3}\s+.+\n?', '', cleaned, count=1)
    # Odstraň HTML h1/h2 na začátku
    cleaned = re.sub(r'^\s*<h[12][^>]*>.*?</h[12]>\s*', '', cleaned, count=1, flags=re.DOTALL)
    return cleaned


def get_categories(force_refresh=False, lang=None):
    """
    Fetch kategorií z WP REST API s in-memory cache (5 min).
    lang: 'cs', 'en' nebo None (všechny).
    Vrací (list, None) nebo (None, error_string).
    """
    cache_key = lang or '_all'
    now = time.time()
    cached = _categories_cache.get(cache_key)
    if not force_refresh and cached and cached['data'] is not None and (now - cached['fetched_at']) < _CACHE_TTL:
        return (cached['data'], None)

    try:
        if lang:
            # Polylang free: use custom gamefo endpoint for language filtering
            base = config.WP_URL.rstrip('/')
            params = {'lang': lang}
            resp = requests.get(
                f"{base}/wp-json/gamefo/v1/categories",
                headers=_auth_headers(),
                params=params,
                timeout=10,
            )
            if resp.status_code != 200:
                return (None, f"WP API error {resp.status_code}: {resp.text[:200]}")

            all_categories = resp.json()
            # Already simplified by the custom endpoint
            result = all_categories
        else:
            # Standard WP REST API (all categories)
            all_categories = []
            page = 1
            while True:
                resp = requests.get(
                    _api_url('categories'),
                    headers=_auth_headers(),
                    params={'per_page': 100, 'page': page},
                    timeout=10,
                )
                if resp.status_code != 200:
                    return (None, f"WP API error {resp.status_code}: {resp.text[:200]}")

                batch = resp.json()
                if not batch:
                    break
                all_categories.extend(batch)

                total_pages = int(resp.headers.get('X-WP-TotalPages', 1))
                if page >= total_pages:
                    break
                page += 1

            # Zjednodušená struktura pro frontend
            result = []
            for cat in all_categories:
                result.append({
                    'id': cat['id'],
                    'name': cat['name'],
                    'slug': cat['slug'],
                    'parent': cat['parent'],
                    'count': cat['count'],
                })

        # Sort: parents first, then children alphabetically
        result.sort(key=lambda c: (c['parent'], c['name']))

        _categories_cache[cache_key] = {
            'data': result,
            'fetched_at': time.time(),
        }

        return (result, None)

    except requests.exceptions.ConnectionError:
        return (None, f"Cannot connect to {config.WP_URL}")
    except requests.exceptions.Timeout:
        return (None, "WP API timeout")
    except Exception as e:
        return (None, f"Error fetching categories: {str(e)}")


def get_status_tags(force_refresh=False):
    """
    Fetch status tagů z custom gamefo endpointu.
    Vrací (list, None) nebo (None, error_string).
    """
    now = time.time()
    if not force_refresh and _status_tags_cache['data'] is not None and (now - _status_tags_cache['fetched_at']) < _CACHE_TTL:
        return (_status_tags_cache['data'], None)

    try:
        base = config.WP_URL.rstrip('/')
        resp = requests.get(
            f"{base}/wp-json/gamefo/v1/status-tags",
            headers=_auth_headers(),
            timeout=10,
        )
        if resp.status_code != 200:
            return (None, f"WP API error {resp.status_code}: {resp.text[:200]}")

        result = resp.json()
        _status_tags_cache['data'] = result
        _status_tags_cache['fetched_at'] = time.time()
        return (result, None)

    except requests.exceptions.ConnectionError:
        return (None, f"Cannot connect to {config.WP_URL}")
    except requests.exceptions.Timeout:
        return (None, "WP API timeout")
    except Exception as e:
        return (None, f"Error fetching status tags: {str(e)}")


def upload_media(image_url, title=""):
    """
    Stáhne obrázek z URL a uploadne ho do WP media library.
    Vrací (media_id, None) nebo (None, error_string).
    """
    try:
        # Stáhni obrázek
        img_resp = requests.get(image_url, timeout=15, stream=True)
        if img_resp.status_code != 200:
            return (None, f"Cannot download image: HTTP {img_resp.status_code}")

        content_type = img_resp.headers.get('Content-Type', 'image/jpeg')

        # Určení názvu souboru z URL
        from urllib.parse import urlparse
        path = urlparse(image_url).path
        filename = path.split('/')[-1] if '/' in path else 'image.jpg'
        if '.' not in filename:
            ext = content_type.split('/')[-1].replace('jpeg', 'jpg')
            filename = f"image.{ext}"

        # Upload do WP
        headers = _auth_headers()
        headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        headers['Content-Type'] = content_type

        resp = requests.post(
            _api_url('media'),
            headers=headers,
            data=img_resp.content,
            timeout=30,
        )

        if resp.status_code not in (200, 201):
            return (None, f"WP media upload error {resp.status_code}: {resp.text[:200]}")

        media_data = resp.json()
        return (media_data['id'], None)

    except requests.exceptions.Timeout:
        return (None, "Image upload timeout")
    except Exception as e:
        return (None, f"Media upload error: {str(e)}")


def upload_media_file(file_data, filename, content_type, caption="", alt_text=""):
    """
    Uploadne soubor (bytes) do WP media library s volitelným popiskem a alt textem.
    Vrací (media_id, None) nebo (None, error_string).
    """
    try:
        headers = _auth_headers()
        headers['Content-Disposition'] = f'attachment; filename="{filename}"'
        headers['Content-Type'] = content_type

        resp = requests.post(
            _api_url('media'),
            headers=headers,
            data=file_data,
            timeout=30,
        )

        if resp.status_code not in (200, 201):
            return (None, f"WP media upload error {resp.status_code}: {resp.text[:200]}")

        media_data = resp.json()
        media_id = media_data['id']

        # Nastav caption a alt text (separátní PATCH request)
        if caption or alt_text:
            update_data = {}
            if caption:
                update_data['caption'] = caption
            if alt_text:
                update_data['alt_text'] = alt_text
            requests.post(
                _api_url(f'media/{media_id}'),
                headers=_auth_headers(),
                json=update_data,
                timeout=10,
            )

        return (media_id, None)

    except requests.exceptions.Timeout:
        return (None, "Image upload timeout")
    except Exception as e:
        return (None, f"Media upload error: {str(e)}")


def _resolve_tag_ids(tag_names):
    """
    Převede seznam tag názvů na WP tag IDs.
    Pokud tag neexistuje, vytvoří ho.
    Vrací (list_of_ids, None) nebo (None, error_string).
    """
    if not tag_names:
        return ([], None)

    headers = _auth_headers()
    tag_ids = []

    for tag_name in tag_names:
        tag_name = tag_name.strip()
        if not tag_name:
            continue

        # Hledej existující tag
        try:
            resp = requests.get(
                _api_url('tags'),
                headers=headers,
                params={'search': tag_name, 'per_page': 10},
                timeout=10,
            )

            if resp.status_code == 200:
                tags = resp.json()
                # Přesná shoda (case-insensitive)
                found = None
                for t in tags:
                    if t['name'].lower() == tag_name.lower():
                        found = t
                        break

                if found:
                    tag_ids.append(found['id'])
                    continue

            # Tag neexistuje — vytvoř ho
            resp = requests.post(
                _api_url('tags'),
                headers=headers,
                json={'name': tag_name},
                timeout=10,
            )

            if resp.status_code in (200, 201):
                tag_ids.append(resp.json()['id'])
            else:
                # Pokud se nepodaří vytvořit tag, pokračuj bez něj
                pass

        except Exception:
            # Tag se nepodařilo zpracovat, pokračuj
            continue

    return (tag_ids, None)


def create_draft(title, content, category_ids=None, tag_names=None, lang=None, featured_image_id=None, status_tag=None, source_info=None):
    """
    Vytvoří draft post na WP.
    Vrací ({id, edit_url, view_url}, None) nebo (None, error_string).
    """
    try:
        # Resolve tagy
        tag_ids = []
        if tag_names:
            tag_ids, tag_error = _resolve_tag_ids(tag_names)
            if tag_error:
                return (None, tag_error)

        post_data = {
            'title': title,
            'content': content,
            'status': 'draft',
        }

        if category_ids:
            post_data['categories'] = category_ids

        if tag_ids:
            post_data['tags'] = tag_ids

        if featured_image_id:
            post_data['featured_media'] = featured_image_id

        meta = {}
        if status_tag:
            meta['gameinfo_status_tag'] = status_tag
        if source_info:
            meta['gameinfo_source'] = source_info
        if meta:
            post_data['meta'] = meta

        # Polylang language param
        if lang:
            post_data['lang'] = lang

        resp = requests.post(
            _api_url('posts'),
            headers=_auth_headers(),
            json=post_data,
            timeout=15,
        )

        if resp.status_code not in (200, 201):
            return (None, f"WP API error {resp.status_code}: {resp.text[:300]}")

        post = resp.json()
        post_id = post['id']

        # Debug: log sent vs assigned categories
        assigned_cats = post.get('categories', [])
        if category_ids and set(category_ids) != set(assigned_cats):
            print(f"[WP] Category mismatch for post {post_id}: sent={category_ids}, assigned={assigned_cats}, lang={lang}")

        # Sestav URLs
        wp_base = config.WP_URL.rstrip('/')
        edit_url = f"{wp_base}/wp-admin/post.php?post={post_id}&action=edit"
        view_url = post.get('link', f"{wp_base}/?p={post_id}")

        return ({
            'id': post_id,
            'edit_url': edit_url,
            'view_url': view_url,
        }, None)

    except requests.exceptions.ConnectionError:
        return (None, f"Cannot connect to {config.WP_URL}")
    except requests.exceptions.Timeout:
        return (None, "WP API timeout")
    except Exception as e:
        return (None, f"Error creating draft: {str(e)}")


def link_translations(post_id_cs, post_id_en):
    """
    Propojí CS a EN posty přes custom GameFo Polylang REST endpoint.
    Vyžaduje mu-plugin gamefo-polylang-rest.php na WP straně.
    Vrací (True, None) nebo (None, error_string).
    """
    try:
        base = config.WP_URL.rstrip('/')
        resp = requests.post(
            f"{base}/wp-json/gamefo/v1/link-translations",
            headers=_auth_headers(),
            json={'cs': post_id_cs, 'en': post_id_en},
            timeout=10,
        )

        if resp.status_code not in (200, 201):
            return (None, f"Failed to link translations: {resp.status_code}: {resp.text[:200]}")

        return (True, None)

    except Exception as e:
        return (None, f"Error linking translations: {str(e)}")
