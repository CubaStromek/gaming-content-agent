"""Čisté string transformace nad HTML článku.

Vyčleněno z article_writer.py — testovatelné samostatně, bez závislosti
na Claude API ani síti.
"""

import html as html_module
import json
import re
from html.parser import HTMLParser
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
        safe_url = html_module.escape(url, quote=True)
        safe_domain = html_module.escape(domain)
        items.append(f'<li><a href="{safe_url}" target="_blank" rel="noopener">{safe_domain}</a></li>')

    return f'\n<h2>{heading}</h2>\n<ul>\n' + '\n'.join(items) + '\n</ul>'


# --- Sanitizace LLM-generovaného HTML před publikací do WP -------------------
#
# Obsah článku generuje Claude ze scrapnutých textů třetích stran — škodlivý
# zdroj může modelu podstrčit instrukci vygenerovat <script>/<iframe>. WP user
# má typicky `unfiltered_html`, takže kses nic nevyfiltruje. Allowlist řeší
# obojí. Volá se na SUROVÝ výstup modelu, PŘED vložením vlastního markupu
# (YouTube embed, interní odkazy) — ten už je důvěryhodný.

_ALLOWED_TAGS = {
    # h1 zůstává povolený, aby ho následně odstranil wp_publisher.strip_first_heading
    # (unwrap na holý text by nadpis nechal v článku jako duplicitní řádek)
    'p', 'h1', 'h2', 'h3', 'h4', 'strong', 'em', 'b', 'i', 'u', 'a',
    'ul', 'ol', 'li', 'blockquote', 'hr', 'br', 'figure', 'figcaption',
    'code', 'pre', 'span', 'table', 'thead', 'tbody', 'tr', 'th', 'td', 'img',
}
_VOID_TAGS = {'hr', 'br', 'img'}
# Tagy, jejichž OBSAH se zahazuje celý (ne jen tag samotný)
_DROP_CONTENT_TAGS = {'script', 'style', 'iframe', 'object', 'embed', 'form', 'svg'}
_ALLOWED_ATTRS = {
    'a': {'href', 'target', 'rel', 'title'},
    'img': {'src', 'alt', 'title', 'width', 'height'},
    '*': {'class'},
}


class _ArticleSanitizer(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.out: List[str] = []
        self._drop_depth = 0

    def _clean_attrs(self, tag, attrs):
        allowed = _ALLOWED_ATTRS.get(tag, set()) | _ALLOWED_ATTRS['*']
        cleaned = []
        for name, value in attrs:
            name = name.lower()
            if name.startswith('on') or name == 'style' or name not in allowed:
                continue
            if name in ('href', 'src'):
                v = (value or '').strip()
                if not v.lower().startswith(('http://', 'https://')):
                    continue
            cleaned.append((name, value))
        return cleaned

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in _DROP_CONTENT_TAGS:
            if tag not in _VOID_TAGS:
                self._drop_depth += 1
            return
        if self._drop_depth or tag not in _ALLOWED_TAGS:
            return  # nepovolený tag zahodit, obsah (text) projde přes handle_data
        attr_str = ''.join(
            f' {n}="{html_module.escape(v or "", quote=True)}"'
            for n, v in self._clean_attrs(tag, attrs)
        )
        self.out.append(f'<{tag}{attr_str}>')

    def handle_startendtag(self, tag, attrs):
        tag = tag.lower()
        if tag in _VOID_TAGS and not self._drop_depth:
            self.handle_starttag(tag, attrs)
            return
        self.handle_starttag(tag, attrs)
        self.handle_endtag(tag)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in _DROP_CONTENT_TAGS:
            if self._drop_depth:
                self._drop_depth -= 1
            return
        if self._drop_depth or tag not in _ALLOWED_TAGS or tag in _VOID_TAGS:
            return
        self.out.append(f'</{tag}>')

    def handle_data(self, data):
        if not self._drop_depth:
            self.out.append(html_module.escape(data, quote=False))

    def handle_entityref(self, name):
        if not self._drop_depth:
            self.out.append(f'&{name};')

    def handle_charref(self, name):
        if not self._drop_depth:
            self.out.append(f'&#{name};')

    def handle_comment(self, data):
        pass  # komentáře z LLM výstupu zahodit (Gutenberg markup přidáváme až po sanitizaci)


def sanitize_article_html(html: str) -> str:
    """Allowlist sanitizace HTML článku z Claude před publikací do WP.

    Zahodí <script>/<iframe>/event handlery/javascript: URL; povolené tagy
    a atributy projdou beze změny. Volat na výstup modelu PŘED přidáním
    vlastního markupu (YouTube embed bloky, interní odkazy).
    """
    if not html:
        return html
    parser = _ArticleSanitizer()
    parser.feed(html)
    parser.close()
    return ''.join(parser.out)


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
