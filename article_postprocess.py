"""Čisté string transformace nad HTML článku.

Vyčleněno z article_writer.py — testovatelné samostatně, bez závislosti
na Claude API ani síti.
"""

import json
import re
from typing import Dict, List, Optional
from urllib.parse import urlparse

from logger import setup_logger

log = setup_logger(__name__)


def build_sources_html(source_urls: List[str], lang: str = 'cs') -> str:
    """Sestaví HTML sekci zdrojů z reálných URL."""
    if not source_urls:
        return ''

    heading = 'Zdroje' if lang == 'cs' else 'Sources'
    items = []
    for url in source_urls:
        try:
            domain = urlparse(url).netloc.replace('www.', '')
        except Exception:
            domain = url
        items.append(f'<li><a href="{url}" target="_blank" rel="noopener">{domain}</a></li>')

    return f'\n<h2>{heading}</h2>\n<ul>\n' + '\n'.join(items) + '\n</ul>'


def strip_generated_sources(html: str) -> str:
    """Odstraní AI-generovanou sekci zdrojů (Zdroje/Sources) pokud existuje."""
    return re.sub(
        r'\s*<h2>\s*(?:Zdroje|Sources)\s*</h2>\s*<ul>[\s\S]*?</ul>\s*',
        '',
        html,
        flags=re.IGNORECASE,
    )


def strip_markdown_artifacts(html: str) -> str:
    """Odstraní markdown artefakty, které model občas přidá do HTML výstupu."""
    html = re.sub(r'```html\s*\n?', '', html)
    html = re.sub(r'```\s*$', '', html, flags=re.MULTILINE)
    html = re.sub(r'^#{3,}\s+(.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^#{2}\s+(.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^#\s+(.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^-{3,}\s*$', '<hr>', html, flags=re.MULTILINE)
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    return html.strip()


def make_first_paragraph_quote(html: str) -> str:
    """Zabalí první <p>...</p> do <blockquote> jako vizuálně odlišený úvod."""
    return re.sub(
        r'(<p[^>]*>.*?</p>)',
        r'<blockquote class="wp-block-quote">\1</blockquote>',
        html,
        count=1,
        flags=re.DOTALL,
    )


def insert_separators_before_h2(html: str) -> str:
    """Vloží WP blokový oddělovač (<hr>) před každý <h2> kromě prvního."""
    separator = '\n<hr class="wp-block-separator has-alpha-channel-opacity"/>\n'
    parts = re.split(r'(?=<h2)', html)
    if len(parts) <= 1:
        return html
    result = parts[0] + parts[1]
    for part in parts[2:]:
        result += separator + part
    return result


def extract_story_cards(text: str, lang: str) -> Optional[List[Dict]]:
    """Najde STORY_CARDS <lang>: [...] v AI výstupu, vrátí list dictů nebo None.

    Robustní bracket-matching parser — JSON může obsahovat zalomení řádků
    i vnořené uvozovky.
    """
    label = f'STORY_CARDS {lang}:'
    idx = text.find(label)
    if idx == -1:
        return None
    start = text.find('[', idx)
    if start == -1:
        return None

    depth = 0
    in_string = False
    escape = False
    end = -1
    for i in range(start, len(text)):
        ch = text[i]
        if escape:
            escape = False
            continue
        if ch == '\\' and in_string:
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == '[':
            depth += 1
        elif ch == ']':
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end == -1:
        log.warning("STORY_CARDS %s: chybí uzavírací závorka, fallback aktivní", lang)
        return None

    raw = text[start:end]
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        log.warning("STORY_CARDS %s: JSON parse error (%s), fallback aktivní", lang, e)
        return None

    if not isinstance(data, list):
        return None

    cards = []
    for item in data:
        if not isinstance(item, dict):
            continue
        heading = (item.get('heading') or '').strip()
        body = (item.get('body') or '').strip()
        if not body:
            continue
        cards.append({'heading': heading[:60], 'body': body[:200]})

    if not cards:
        return None
    return cards[:5]
