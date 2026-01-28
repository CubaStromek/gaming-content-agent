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

    # Rozdeleni na bloky podle 🎮 TÉMA:
    blocks = re.split(r'(?=🎮 TÉMA:)', report_text)

    for block in blocks:
        block = block.strip()
        if not block.startswith('🎮 TÉMA:'):
            continue

        topic = {}

        # Parsuj jednotlive sekce
        patterns = {
            'topic': r'🎮 TÉMA:\s*(.+)',
            'title': r'📰 NAVRŽENÝ TITULEK:\s*(.+)',
            'angle': r'🎯 ÚHEL POHLEDU:\s*(.+)',
            'context': r'📝 KONTEXT:\s*(.+)',
            'hook': r'💬 HLAVNÍ HOOK:\s*(.+)',
            'visual': r'🖼️ VIZUÁLNÍ NÁVRH:\s*(.+)',
            'virality': r'🔥 VIRALITA:\s*(.+)',
            'why_now': r'💡 PROČ TEĎKA:\s*(.+)',
            'seo_keywords': r'🏷️ SEO KLÍČOVÁ SLOVA:\s*(.+)',
        }

        for key, pattern in patterns.items():
            match = re.search(pattern, block)
            topic[key] = match.group(1).strip() if match else ''

        # Parsuj virality score jako cislo
        virality_match = re.search(r'(\d+)', topic.get('virality', ''))
        topic['virality_score'] = int(virality_match.group(1)) if virality_match else 0

        # Parsuj zdroje (URL na samostatnych radcich)
        sources_section = re.search(r'🔗 ZDROJE:\s*\n?([\s\S]*?)(?=🏷️|$)', block)
        if sources_section:
            urls = re.findall(r'https?://[^\s<>"\')\]]+[^\s<>"\')\].,]', sources_section.group(1))
            topic['sources'] = urls
        else:
            topic['sources'] = []

        if topic.get('topic'):
            topics.append(topic)

    return topics


def write_article(topic: Dict, source_texts: List[str]) -> Dict:
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
- Článek musí mít 600-1000 slov
- Formát: HTML (h2 nadpisy, p odstavce, strong pro důležité)
- Styl: informativní, poutavý, pro české herní publikum
- Zahrň konkrétní fakta a čísla ze zdrojů
- NEZMIŇUJ zdroje v textu článku (ne "podle IGN...")
- NEPŘIDÁVEJ h1 nadpis - ten bude jako titulek článku
- KRITICKÉ: V nadpisech (h2) NEPOUŽÍVEJ Title Case! Velké písmeno POUZE na začátku věty a u vlastních jmen. ŠPATNĚ: "Nová Éra Pro Herní Průmysl". SPRÁVNĚ: "Nová éra pro herní průmysl". ŠPATNĚ: "What This Means For Players". SPRÁVNĚ: "What this means for players".
- Na konec článku VŽDY přidej sekci "Zdroje" (v EN "Sources") jako HTML seznam odkazů

ZDROJOVÉ URL PRO SEKCI ZDROJE:
{sources_list}

POSTUP:
1. Nejdřív napiš článek v ČEŠTINĚ
2. Na konec české verze přidej <h2>Zdroje</h2> s odkazy jako <ul><li><a href="URL">název webu</a></li></ul>
3. Potom PŘELOŽ celý článek do angličtiny včetně sekce zdrojů (nadpis "Sources")

=== ČESKY ===
<článek v češtině jako HTML, na konci sekce Zdroje s odkazy>

=== ENGLISH ===
<přesný překlad českého článku výše, na konci sekce Sources s odkazy>"""

    try:
        message = client.messages.create(
            model=config.ARTICLE_MODEL,
            max_tokens=8000,
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

        cs_html = cs_match.group(1).strip() if cs_match else result_text
        en_html = en_match.group(1).strip() if en_match else ''

        # Odhad ceny
        cost_input = (message.usage.input_tokens / 1_000_000) * 0.25
        cost_output = (message.usage.output_tokens / 1_000_000) * 1.25
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
