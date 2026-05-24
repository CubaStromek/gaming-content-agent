"""
Internal Linking - automatické prolinkování článků uvnitř webu

Před publishem:
1. Ve vygenerovaném textu najde první výskyt každého tagu a obalí ho <a href="/tag/<slug>/">
2. Na konec článku (před sekci Zdroje) vloží sekci "Související články" s 3 staršími posty
   se stejnými tagy, v aktuálním jazyce (Polylang).

SEO přínos: lepší crawlovatelnost, distribuce autority, delší čas na webu.
"""

import re
from typing import Optional, List
import requests
import config
from logger import setup_logger
from wp_publisher import _auth_headers, _api_url

log = setup_logger(__name__)


def get_tag_details(tag_name: str, lang: str = 'cs') -> Optional[dict]:
    """
    Najde WP tag podle jména a vrátí {'id', 'slug', 'name'}.
    Respektuje jazyk (Polylang) — tagy mají -en suffix pro EN.
    """
    if not tag_name or not tag_name.strip():
        return None

    tag_name = tag_name.strip()

    try:
        params = {'search': tag_name, 'per_page': 20}
        if lang:
            params['lang'] = lang

        resp = requests.get(
            _api_url('tags'),
            headers=_auth_headers(),
            params=params,
            timeout=10,
        )
        if resp.status_code != 200:
            return None

        tags = resp.json()
        # Přesná shoda podle jména (case-insensitive)
        for t in tags:
            if t.get('name', '').lower() == tag_name.lower():
                return {'id': t['id'], 'slug': t['slug'], 'name': t['name']}
    except Exception as e:
        log.warning("get_tag_details selhalo pro '%s': %s", tag_name, e)

    return None


def _build_tag_url(slug: str, lang: str = 'cs') -> str:
    """Vrátí URL na tag archive (respektuje Polylang prefix /en/)."""
    base = config.WP_URL.rstrip('/')
    prefix = '/en' if lang == 'en' else ''
    return f"{base}{prefix}/tag/{slug}/"


def _replace_first_outside_tags(html: str, needle: str, replacement: str):
    """
    Nahradí první výskyt `needle` v HTML textu, ale jen:
    - mimo HTML tagy (ne uvnitř <...>)
    - mimo už existující <a>...</a> linky
    - mimo nadpisy <h1>..<h6>

    Vrací (new_html, replaced_bool).
    """
    # Split na tokeny: buď tag <...> nebo text mezi tagy.
    # Regex chytá: tag, nebo cokoli bez <
    tokens = re.split(r'(<[^>]+>)', html)

    in_link = False
    in_heading = False
    pattern = re.compile(r'\b' + re.escape(needle) + r'\b', re.IGNORECASE)

    for i, tok in enumerate(tokens):
        if tok.startswith('<'):
            tl = tok.lower()
            if tl.startswith('<a '): in_link = True
            elif tl.startswith('</a>'): in_link = False
            elif re.match(r'<h[1-6][\s>]', tl): in_heading = True
            elif re.match(r'</h[1-6]>', tl): in_heading = False
            continue

        if in_link or in_heading:
            continue

        m = pattern.search(tok)
        if m:
            start, end = m.span()
            matched_text = tok[start:end]
            tokens[i] = tok[:start] + replacement.replace('{MATCH}', matched_text) + tok[end:]
            return (''.join(tokens), True)

    return (html, False)


def inject_tag_links(html: str, tag_names: list, lang: str = 'cs', max_links: int = 5) -> str:
    """
    Pro každý tag najde první výskyt v článku a obalí ho <a> linkem na tag archive.
    Maximálně `max_links` linků na článek (prevence over-optimization).
    """
    if not html or not tag_names:
        return html

    linked = 0
    tag_details_cache = {}

    # Seřadit tagy od nejdelších — delší match bere prednost (např. "GTA 6" před "GTA")
    sorted_tags = sorted([t.strip() for t in tag_names if t and t.strip()], key=len, reverse=True)

    for tag_name in sorted_tags:
        if linked >= max_links:
            break

        details = tag_details_cache.get(tag_name) or get_tag_details(tag_name, lang=lang)
        if not details:
            continue
        tag_details_cache[tag_name] = details

        url = _build_tag_url(details['slug'], lang=lang)
        replacement = f'<a href="{url}">{{MATCH}}</a>'

        new_html, replaced = _replace_first_outside_tags(html, tag_name, replacement)
        if replaced:
            html = new_html
            linked += 1
            log.debug("Interní link vložen: '%s' → %s", tag_name, url)

    if linked:
        log.info("Internal linking: vloženo %d tag linků", linked)

    return html


def find_related_posts(tag_ids: list, exclude_id: Optional[int] = None, lang: str = 'cs', limit: int = 3) -> list:
    """
    Najde související posty podle tagů (stejný jazyk, vyloučený current post).
    Vrací list {'id', 'title', 'url', 'featured_media_url'}.
    """
    if not tag_ids:
        return []

    try:
        params = {
            'tags': ','.join(str(t) for t in tag_ids),
            'per_page': limit + 5,  # buffer pokud některé vyloučíme
            '_embed': 'wp:featuredmedia',
            'orderby': 'date',
            'order': 'desc',
        }
        if lang:
            params['lang'] = lang
        if exclude_id:
            params['exclude'] = exclude_id

        resp = requests.get(
            _api_url('posts'),
            headers=_auth_headers(),
            params=params,
            timeout=10,
        )
        if resp.status_code != 200:
            log.warning("find_related_posts: WP vrátilo %d", resp.status_code)
            return []

        posts = resp.json()
        result = []
        for p in posts[:limit]:
            media_url = ''
            embedded = p.get('_embedded', {}).get('wp:featuredmedia', [])
            if embedded and isinstance(embedded, list) and len(embedded) > 0:
                media_url = embedded[0].get('source_url', '')

            result.append({
                'id': p['id'],
                'title': p.get('title', {}).get('rendered', ''),
                'url': p.get('link', ''),
                'featured_media_url': media_url,
            })
        return result
    except Exception as e:
        log.warning("find_related_posts selhalo: %s", e)
        return []


def build_related_section(related_posts: list, lang: str = 'cs') -> str:
    """
    Postaví HTML sekci "Související články" pro vložení na konec článku.
    """
    if not related_posts:
        return ''

    heading = 'Články s podobným tématem' if lang == 'cs' else 'Articles on similar topics'
    items = []
    for p in related_posts:
        title = p.get('title', '')
        img = ''
        if p.get('featured_media_url'):
            # Use article title as alt (each related article has unique title → unique alt).
            img = f'<img src="{p["featured_media_url"]}" alt="{title}" loading="lazy" style="max-width:120px;height:auto;margin-right:12px;vertical-align:middle;"/>'
        items.append(
            f'<li style="margin-bottom:12px;">'
            f'<a href="{p["url"]}" style="text-decoration:none;display:flex;align-items:center;">'
            f'{img}'
            f'<span>{title}</span>'
            f'</a></li>'
        )

    # Use h3 (not h2) — h2 collides with article section headings and confuses Google's
    # outline parser. h3 properly nests under the article's h1/h2 hierarchy.
    return (
        f'\n<hr class="wp-block-separator has-alpha-channel-opacity"/>\n'
        f'<h3>{heading}</h3>\n'
        f'<ul style="list-style:none;padding-left:0;">\n'
        + '\n'.join(items)
        + '\n</ul>\n'
    )


def enrich_with_internal_links(html: str, tag_names: list, lang: str = 'cs', exclude_post_id: Optional[int] = None) -> str:
    """
    High-level funkce — udělá obojí v jednom:
    1. Injectne tag linky do textu
    2. Přidá sekci "Související články" na konec
    """
    if not html:
        return html

    # 1) Inline tag linky
    html = inject_tag_links(html, tag_names, lang=lang)

    # 2) Related articles (potřebujeme tag IDs)
    tag_ids = []
    for tn in tag_names:
        d = get_tag_details(tn, lang=lang)
        if d:
            tag_ids.append(d['id'])

    if tag_ids:
        related = find_related_posts(tag_ids, exclude_id=exclude_post_id, lang=lang, limit=3)
        if related:
            html += build_related_section(related, lang=lang)

    return html
