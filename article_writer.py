"""
Article Writer - generovani clanku z TOP temat
Stahne zdrojove clanky, posle do Claude a vygeneruje CZ + EN verzi
"""

import re
import requests
import anthropic
from bs4 import BeautifulSoup
from typing import List, Dict, Optional

import config
from urllib.parse import urlparse


def _build_sources_html(source_urls: List[str], lang: str = 'cs') -> str:
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


def _strip_generated_sources(html: str) -> str:
    """Odstraní AI-generovanou sekci zdrojů (Zdroje/Sources) pokud existuje."""
    # Odstraní <h2>Zdroje</h2> nebo <h2>Sources</h2> a následující <ul>...</ul>
    return re.sub(
        r'\s*<h2>\s*(?:Zdroje|Sources)\s*</h2>\s*<ul>[\s\S]*?</ul>\s*',
        '',
        html,
        flags=re.IGNORECASE
    )


def _strip_markdown_artifacts(html: str) -> str:
    """Odstraní markdown artefakty, které Haiku občas přidá do HTML výstupu."""
    # Odstraň ```html ... ``` code fences
    html = re.sub(r'```html\s*\n?', '', html)
    html = re.sub(r'```\s*$', '', html, flags=re.MULTILINE)
    # Převeď markdown nadpisy (## Nadpis) na <h2>
    html = re.sub(r'^#{3,}\s+(.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^#{2}\s+(.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^#\s+(.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    # Převeď markdown --- na <hr>
    html = re.sub(r'^-{3,}\s*$', '<hr>', html, flags=re.MULTILINE)
    # Převeď **bold** na <strong>
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    return html.strip()


def scrape_full_article(url: str) -> str:
    """
    Stahne plny text clanku z URL

    Args:
        url: URL clanku

    Returns:
        Text clanku (max 3000 znaku)
    """
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        resp = requests.get(url, headers=headers, timeout=15)
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, 'html.parser')

        # Odstran scripty a styly
        for tag in soup(['script', 'style', 'nav', 'footer', 'header', 'aside', 'iframe', 'noscript']):
            tag.decompose()

        # Zkus najit hlavni obsah
        content = None
        for selector in ['article', 'main', '[role="main"]', '.article-body', '.post-content', '.entry-content']:
            content = soup.select_one(selector)
            if content:
                break

        if not content:
            content = soup.body if soup.body else soup

        text = content.get_text(separator='\n', strip=True)

        # Vycisti prazdne radky
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        text = '\n'.join(lines)

        return text[:3000]

    except Exception as e:
        return f"[Chyba pri stahovani: {e}]"


def parse_topics_from_report(report_text: str) -> List[Dict]:
    """
    Parsuje text reportu na strukturovana temata

    Args:
        report_text: Plny text report.txt

    Returns:
        List slovniku s tematy
    """
    topics = []

    # Rozdeleni na bloky podle 🎮 TÉMA (s volitelnym cislem, toleruje **bold**)
    blocks = re.split(r'(?=🎮\s*\*{0,2}\s*TÉMA\s*\d*:\*{0,2})', report_text)

    for block in blocks:
        block = block.strip()
        if not re.match(r'.*🎮\s*\*{0,2}\s*TÉMA\s*\d*:\*{0,2}', block):
            continue

        topic = {}

        # Parsuj jednotlive sekce
        # Patterny toleruji markdown bold (**) pred emoji i kolem labelu
        # a obsah muze byt na stejnem radku nebo na nasledujicim
        _val = r'\s*\n?\s*(.+)'
        patterns = {
            'topic': r'\*{0,2}🎮\s*\*{0,2}\s*TÉMA\s*\d*:\*{0,2}' + _val,
            'title': r'\*{0,2}📰\s*\*{0,2}\s*NAVRŽENÝ TITULEK:\*{0,2}' + _val,
            'angle': r'\*{0,2}🎯\s*\*{0,2}\s*ÚHEL POHLEDU:\*{0,2}' + _val,
            'context': r'\*{0,2}📝\s*\*{0,2}\s*KONTEXT:\*{0,2}' + _val,
            'hook': r'\*{0,2}💬\s*\*{0,2}\s*HLAVNÍ HOOK:\*{0,2}' + _val,
            'visual': r'\*{0,2}🖼️\s*\*{0,2}\s*VIZUÁLNÍ NÁVRH:\*{0,2}' + _val,
            'virality': r'\*{0,2}🔥\s*\*{0,2}\s*VIRALITA:\*{0,2}' + _val,
            'why_now': r'\*{0,2}💡\s*\*{0,2}\s*PROČ TEĎKA:\*{0,2}' + _val,
            'seo_keywords': r'\*{0,2}🏷️\s*\*{0,2}\s*SEO KLÍČOVÁ SLOVA:\*{0,2}' + _val,
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, block)
            value = match.group(1).strip() if match else ''
            # Odstranit uvozovky a markdown bold z hodnoty
            value = value.strip('"\'').strip('*')
            topic[key] = value

        # Parsuj virality score jako cislo
        virality_match = re.search(r'(\d+)', topic.get('virality', ''))
        topic['virality_score'] = int(virality_match.group(1)) if virality_match else 0

        # Parsuj zdroje (URL na samostatnych radcich)
        sources_section = re.search(r'\*{0,2}🔗\s*\*{0,2}\s*ZDROJE:\*{0,2}\s*\n?([\s\S]*?)(?=\*{0,2}🏷️|$)', block)
        if sources_section:
            urls = re.findall(r'https?://[^\s<>"\')\]]+[^\s<>"\')\].,]', sources_section.group(1))
            topic['sources'] = urls
        else:
            topic['sources'] = []

        if topic.get('topic'):
            topics.append(topic)

    return topics


def write_article(topic: Dict, source_texts: List[str], length: str = 'medium') -> Dict:
    """
    Vygeneruje clanek pomoci Claude API

    Args:
        topic: Slovnik s tematem (z parse_topics_from_report)
        source_texts: Seznam plnych textu zdrojovych clanku

    Returns:
        {"cs": "<html>...", "en": "<html>..."} nebo {"error": "..."}
    """
    client = anthropic.Anthropic(api_key=config.CLAUDE_API_KEY)

    # Pripravi zdrojove texty
    sources_combined = ""
    for i, text in enumerate(source_texts, 1):
        sources_combined += f"\n--- ZDROJ {i} ---\n{text}\n"

    # Pripravi seznam URL zdroju pro konec clanku
    source_urls = topic.get('sources', [])
    sources_list = "\n".join(source_urls)

    if length == 'short':
        length_instruction = "Článek musí mít 400-800 znaků (krátká zpráva, 2-3 odstavce)"
    else:
        length_instruction = "Článek musí mít 1000-2000 znaků (střední délka, 4-6 odstavců)"

    prompt = f"""Napíš originální herní článek na základě zdrojových textů.

TÉMA: {topic.get('topic', '')}
NAVRŽENÝ TITULEK: {topic.get('title', '')}
ÚHEL POHLEDU: {topic.get('angle', '')}
KONTEXT: {topic.get('context', '')}
SEO KLÍČOVÁ SLOVA: {topic.get('seo_keywords', '')}

ZDROJOVÉ TEXTY:
{sources_combined}

PRAVIDLA:
- Piš VLASTNÍMI SLOVY, ne kopíruj ze zdrojů
- {length_instruction}
- Formát: ČISTÉ HTML (h2 nadpisy, p odstavce, strong pro důležité)
- NEPOUŽÍVEJ markdown! Žádné ```, ---, #, ** — POUZE HTML tagy
- Styl: informativní, poutavý, pro české herní publikum
- Zahrň konkrétní fakta a čísla ze zdrojů
- NEZMIŇUJ zdroje v textu článku (ne "podle IGN...")
- NEPŘIDÁVEJ h1 nadpis - ten bude jako titulek článku
- KRITICKÉ: V nadpisech (h2) NEPOUŽÍVEJ Title Case! Velké písmeno POUZE na začátku věty a u vlastních jmen. ŠPATNĚ: "Nová Éra Pro Herní Průmysl". SPRÁVNĚ: "Nová éra pro herní průmysl". ŠPATNĚ: "What This Means For Players". SPRÁVNĚ: "What this means for players".
- NEPŘIDÁVEJ sekci "Zdroje" ani "Sources" — odkazy na zdroje se přidají automaticky

POSTUP:
1. Nejdřív napiš článek v ČEŠTINĚ (BEZ sekce zdrojů)
2. Potom PŘELOŽ celý článek do angličtiny

=== ČESKY ===
<článek v češtině jako HTML>

=== ENGLISH ===
<přesný překlad českého článku výše>"""

    try:
        message = client.messages.create(
            model=config.ARTICLE_MODEL,
            max_tokens=4096,
            temperature=0.7,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        result_text = message.content[0].text

        # Parsuj CZ a EN casti
        cs_match = re.search(r'===\s*ČESKY\s*===\s*([\s\S]*?)(?====\s*ENGLISH\s*===|$)', result_text)
        en_match = re.search(r'===\s*ENGLISH\s*===\s*([\s\S]*?)$', result_text)

        if cs_match:
            cs_html = cs_match.group(1).strip()
        elif en_match:
            cs_html = result_text[:en_match.start()].strip()
        else:
            cs_html = result_text
        en_html = en_match.group(1).strip() if en_match else ''

        # Vyčisti markdown artefakty (Haiku 3.5 je občas přidává)
        cs_html = _strip_markdown_artifacts(cs_html)
        if en_html:
            en_html = _strip_markdown_artifacts(en_html)

        # Odstraň AI-generované zdroje a připoj reálné URL
        cs_html = _strip_generated_sources(cs_html)
        cs_html += _build_sources_html(source_urls, 'cs')

        if en_html:
            en_html = _strip_generated_sources(en_html)
            en_html += _build_sources_html(source_urls, 'en')

        # Odhad ceny (Claude Haiku 4.5 pricing: $1.00/MTok input, $5.00/MTok output)
        cost_input = (message.usage.input_tokens / 1_000_000) * 1.00
        cost_output = (message.usage.output_tokens / 1_000_000) * 5.00
        total_cost = cost_input + cost_output

        return {
            'cs': cs_html,
            'en': en_html,
            'tokens_in': message.usage.input_tokens,
            'tokens_out': message.usage.output_tokens,
            'cost': f"${total_cost:.4f}"
        }

    except Exception as e:
        return {'error': str(e)}


def generate_podcast_script(article_html: str, lang: str = 'cs') -> Dict:
    """
    Vygeneruje podcast script ze clanku (styl NotebookLM - 2 moderatori)

    Args:
        article_html: HTML obsah clanku
        lang: 'cs' pro cestinu, 'en' pro anglictinu

    Returns:
        {"script": "...", "tokens_in": ..., "tokens_out": ..., "cost": "..."} nebo {"error": "..."}
    """
    client = anthropic.Anthropic(api_key=config.CLAUDE_API_KEY)

    # Odstran HTML tagy pro citelnejsi vstup
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(article_html, 'html.parser')
    article_text = soup.get_text(separator='\n', strip=True)

    if lang == 'cs':
        prompt = f"""Vytvoř podcast script ze následujícího článku. Formát: konverzace dvou moderátorů (ALEX a MAYA).

ČLÁNEK:
{article_text}

PRAVIDLA PRO SCRIPT:
- Styl: přátelský, informativní, jako NotebookLM podcast
- Délka: 3-5 minut mluveného slova (cca 500-800 slov)
- ALEX začíná, představí téma
- MAYA doplňuje, klade otázky, přidává kontext
- Střídají se přirozeně, ne mechanicky
- Používej hovorovou češtinu, ne spisovnou
- Zahrň všechny důležité informace z článku
- Konec: krátké shrnutí a rozloučení

FORMÁT VÝSTUPU (přesně dodržuj):
ALEX: [text]

MAYA: [text]

ALEX: [text]
...

Začni přímo scriptem, bez úvodu."""

    else:
        prompt = f"""Create a podcast script from the following article. Format: conversation between two hosts (ALEX and MAYA).

ARTICLE:
{article_text}

SCRIPT RULES:
- Style: friendly, informative, NotebookLM podcast style
- Length: 3-5 minutes of spoken word (approx 500-800 words)
- ALEX starts, introduces the topic
- MAYA adds context, asks questions, provides insights
- Natural back-and-forth, not mechanical
- Use conversational English
- Include all important information from the article
- End: brief summary and sign-off

OUTPUT FORMAT (follow exactly):
ALEX: [text]

MAYA: [text]

ALEX: [text]
...

Start directly with the script, no preamble."""

    try:
        message = client.messages.create(
            model=config.ARTICLE_MODEL,
            max_tokens=4000,
            temperature=0.8,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        script = message.content[0].text.strip()

        # Odhad ceny (Claude Haiku 4.5 pricing: $1.00/MTok input, $5.00/MTok output)
        cost_input = (message.usage.input_tokens / 1_000_000) * 1.00
        cost_output = (message.usage.output_tokens / 1_000_000) * 5.00
        total_cost = cost_input + cost_output

        return {
            'script': script,
            'tokens_in': message.usage.input_tokens,
            'tokens_out': message.usage.output_tokens,
            'cost': f"${total_cost:.4f}"
        }

    except Exception as e:
        return {'error': str(e)}
