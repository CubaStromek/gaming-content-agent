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
from logger import setup_logger
from urllib.parse import urlparse

log = setup_logger(__name__)

try:
    from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
    _HAS_TENACITY = True
except ImportError:
    _HAS_TENACITY = False


def _is_retryable(exc):
    """Retry na overload (529), rate limit (429), server error (5xx) a connection errory."""
    if isinstance(exc, (anthropic.APIConnectionError, anthropic.APITimeoutError)):
        return True
    if isinstance(exc, anthropic.APIStatusError):
        return exc.status_code in (429, 500, 502, 503, 529)
    return False


def _call_api(client, model, max_tokens, temperature, prompt):
    """Volání Claude API."""
    return client.messages.create(
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        messages=[{
            "role": "user",
            "content": prompt
        }]
    )


if _HAS_TENACITY:
    _call_api = retry(
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=4, min=15, max=120),
        retry=retry_if_exception(_is_retryable),
        before_sleep=lambda retry_state: log.warning(
            "⚠️  API volání selhalo (HTTP %s), pokus %d/5, čekám...",
            getattr(retry_state.outcome.exception(), 'status_code', '?'),
            retry_state.attempt_number
        ),
    )(_call_api)


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


def _make_first_paragraph_quote(html: str) -> str:
    """Zabalí první <p>...</p> do <blockquote> jako vizuálně odlišený úvod."""
    return re.sub(
        r'(<p[^>]*>.*?</p>)',
        r'<blockquote class="wp-block-quote">\1</blockquote>',
        html,
        count=1,
        flags=re.DOTALL,
    )


def _insert_separators_before_h2(html: str) -> str:
    """Vloží WP blokový oddělovač (<hr>) před každý <h2> kromě prvního."""
    separator = '\n<hr class="wp-block-separator has-alpha-channel-opacity"/>\n'
    parts = re.split(r'(?=<h2)', html)
    if len(parts) <= 1:
        return html
    # parts[0] = text před prvním h2 (může být prázdný)
    # parts[1] = první h2 + obsah (přeskočíme separator)
    # parts[2+] = další h2 + obsah (přidáme separator)
    result = parts[0] + parts[1]
    for part in parts[2:]:
        result += separator + part
    return result


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
    # Format muze byt: "TÉMA 1:", "**TÉMA 1**:", "**TÉMA 1:**" atd.
    _tema_pat = r'🎮\s*\*{0,2}\s*TÉMA\s*\d*\s*\*{0,2}\s*:\s*\*{0,2}'
    blocks = re.split(r'(?=' + _tema_pat + r')', report_text)

    for block in blocks:
        block = block.strip()
        if not re.match(r'.*' + _tema_pat, block):
            continue

        topic = {}

        # Parsuj jednotlive sekce
        # Patterny toleruji markdown bold (**) pred emoji i kolem labelu
        # Format muze byt: "**LABEL**:" nebo "**LABEL:**" nebo "LABEL:"
        # Proto: LABEL\*{0,2}\s*:\s*\*{0,2} pokryva vsechny varianty
        _val = r'\s*\n?\s*(.+)'
        _b = r'\*{0,2}'  # optional bold markers
        patterns = {
            'topic': _b + r'🎮\s*' + _b + r'\s*TÉMA\s*\d*\s*' + _b + r'\s*:\s*' + _b + _val,
            'title': _b + r'📰\s*' + _b + r'\s*NAVRŽENÝ TITULEK' + _b + r'\s*:\s*' + _b + _val,
            'angle': _b + r'🎯\s*' + _b + r'\s*ÚHEL POHLEDU' + _b + r'\s*:\s*' + _b + _val,
            'context': _b + r'📝\s*' + _b + r'\s*KONTEXT' + _b + r'\s*:\s*' + _b + _val,
            'hook': _b + r'💬\s*' + _b + r'\s*HLAVNÍ HOOK' + _b + r'\s*:\s*' + _b + _val,
            'visual': _b + r'🖼️\s*' + _b + r'\s*VIZUÁLNÍ NÁVRH' + _b + r'\s*:\s*' + _b + _val,
            'virality': _b + r'🔥\s*' + _b + r'\s*VIRALITA' + _b + r'\s*:\s*' + _b + _val,
            'why_now': _b + r'💡\s*' + _b + r'\s*PROČ TEĎKA' + _b + r'\s*:\s*' + _b + _val,
            'seo_keywords': _b + r'🏷️\s*' + _b + r'\s*SEO KLÍČOVÁ SLOVA' + _b + r'\s*:\s*' + _b + _val,
            'game_name': _b + r'🕹️\s*' + _b + r'\s*NÁZEV HRY' + _b + r'\s*:\s*' + _b + _val,
            'status_tag': _b + r'📌\s*' + _b + r'\s*STATUS TAG' + _b + r'\s*:\s*' + _b + _val,
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

        # Validace status_tag — musí být z povolených hodnot
        valid_status_tags = {'news', 'update', 'leak', 'critical', 'success', 'indie', 'review', 'trailer', 'rumor', 'info', 'finance', 'tema', 'preview'}
        raw_tag = topic.get('status_tag', 'news').lower().strip()
        topic['status_tag'] = raw_tag if raw_tag in valid_status_tags else 'news'

        # Parsuj zdroje (URL na samostatnych radcich)
        sources_section = re.search(r'\*{0,2}🔗\s*\*{0,2}\s*ZDROJE\*{0,2}\s*:\s*\*{0,2}\s*\n?([\s\S]*?)(?=\*{0,2}🏷️|$)', block)
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
        length_instruction = "Článek musí mít 800-1500 znaků (krátká analýza, 3-4 odstavce)"
    elif length == 'long':
        length_instruction = "Článek musí mít 5000-8000 znaků (deep-dive, 10-15 odstavců, více h2 sekcí, silná analýza a kontext)"
    else:
        length_instruction = "Článek musí mít 2000-3500 znaků (střední analýza, 5-8 odstavců)"

    prompt = f"""Napíš ANALYTICKÝ herní článek s vlastním úhlem pohledu. Toto NENÍ přepis zprávy — je to komentář redaktora, který zpravodajskou událost zasazuje do kontextu a říká, CO TO ZNAMENÁ.

TÉMA: {topic.get('topic', '')}
NAVRŽENÝ TITULEK: {topic.get('title', '')}
ÚHEL POHLEDU: {topic.get('angle', '')}
KONTEXT: {topic.get('context', '')}
SEO KLÍČOVÁ SLOVA: {topic.get('seo_keywords', '')}

ZDROJOVÉ TEXTY (použij JEN pro fakta, ne jako šablonu):
{sources_combined}

=== FILOZOFIE ČLÁNKU (KRITICKÉ) ===
Zdrojové weby (IGN, PC Gamer...) už napsaly CO se stalo. Náš úkol je říct PROČ TO VADÍ / PROČ TO STOJÍ ZA POZORNOST. Google i čtenáři už tu novinku četli jinde. Pokud článek jen převypráví fakta, NEMÁ DŮVOD EXISTOVAT.

Každý článek MUSÍ mít:
1. **Jasný úhel** — redaktor má názor, ne jen "oznámeno X, očekává se Y"
2. **Kontext** — proč je to součást většího trendu v herním průmyslu / žánru / u vývojáře
3. **Důsledek** — co to znamená pro hráče, konkurenci, nebo budoucnost hry/studia
4. **Hook v úvodu** — první odstavec NENÍ "Společnost X oznámila Y." Je to provokativní teze, paradox, srovnání, nebo otázka, která nutí číst dál

ZAKÁZANÉ ÚVODY (inverted pyramid novinářského stylu):
- "Vývojář X oznámil novou hru Y..."
- "Na akci Z byl představen..."
- "Podle nejnovějších zpráv..."

DOBRÉ ÚVODY:
- Paradox: "Čekalo se oznámení, přišlo odložení. A hráči jsou podivně klidní."
- Teze: "Tohle není jen další delay. Je to symptom něčeho většího v celém AAA segmentu."
- Kontrast: "Před rokem by to byl skandál. Dnes už nikoho nepřekvapí."
- Otázka s napětím: "Kdo tu vlastně vyhrál — studio, vydavatel, nebo hráči?"

STRUKTURA (doporučená, ne povinná — přizpůsob tématu):
- Úvodní hook (první <p> = silná teze/paradox, NE shrnutí faktů)
- <h2>Co se stalo</h2> — MAXIMÁLNĚ 2-3 věty holých faktů. Nerozmazávej.
- <h2>Proč to vadí / proč je to jinak</h2> — ANALÝZA, kontext, srovnání
- <h2>Co z toho plyne</h2> — důsledky, výhled, otázky do budoucna
- Poslední odstavec: názor/provokativní shrnutí/otevřená otázka — NE "uvidíme, jak se to vyvine"

=== PRAVIDLA ===
- Piš VLASTNÍMI SLOVY, ze zdrojů přebírej JEN fakta a čísla, nikdy ne formulace
- {length_instruction}
- Formát: ČISTÉ HTML (<h2>, <p>, <strong>)
- NEPOUŽÍVEJ markdown! Žádné ```, ---, #, ** — POUZE HTML tagy
- Styl: analytický, s názorem, pro české herní publikum. NE neutrální zpravodajský tón. Nebojí se mít postoj.
- Zahrň konkrétní fakta a čísla (to je zásadní pro důvěryhodnost analýzy)
- NEZMIŇUJ zdroje v textu článku (ne "podle IGN...")
- NEPŘIDÁVEJ h1 nadpis — ten bude jako titulek článku
- NEPOUŽÍVEJ vatu typu "jak se situace vyvine, ukáže čas", "zatím není jasné", "uvidíme". Pokud je otazník, POJMENUJ ho konkrétně.
- FAKTICKÁ PŘESNOST: Zkontroluj, že titulek odpovídá obsahu. Pokud navržený titulek obsahuje nepravdivé tvrzení (např. označuje hru jako "českou", i když studio je zahraniční), OPRAV titulek.
- TITULEK: ne clickbait, ale musí mít ÚHEL (ne "X oznámil Y", spíš "X oznámil Y — a tady je problém" / "Proč X mění pravidla žánru" / "Co X neřekl o Y").
- NA ZAČÁTEK výstupu VŽDY uveď titulky a meta popisy na samostatných řádcích:
  TITULEK CZ: [český titulek s úhlem]
  TITULEK EN: [anglický titulek s úhlem]
  META CZ: [český meta description, 140-155 znaků, VŽDY ukončené tečkou/otazníkem, obsahuje klíčové slovo, musí lákat k prokliku]
  META EN: [anglický meta description, 140-155 znaků, VŽDY ukončené tečkou/otazníkem, obsahuje klíčové slovo, musí lákat k prokliku]
- KRITICKÉ: V nadpisech (h2) NEPOUŽÍVEJ Title Case! Velké písmeno POUZE na začátku věty a u vlastních jmen. ŠPATNĚ: "Nová Éra Pro Herní Průmysl". SPRÁVNĚ: "Nová éra pro herní průmysl". ŠPATNĚ: "What This Means For Players". SPRÁVNĚ: "What this means for players".
- KRITICKÉ: META CZ/EN NESMÍ být uťaté v půli věty! Krátký svébytný popis (1-2 věty) končící interpunkcí — NIKDY NE kopie úvodního odstavce.
- NEPŘIDÁVEJ sekci "Zdroje" ani "Sources" — přidají se automaticky

POSTUP:
1. Nejdřív napiš článek v ČEŠTINĚ (BEZ sekce zdrojů) — s úhlem, s názorem, ne neutrální referát
2. Potom PŘELOŽ celý článek do angličtiny (zachovej úhel a tón)

=== ČESKY ===
<článek v češtině jako HTML>

=== ENGLISH ===
<přesný překlad českého článku výše>"""

    try:
        max_tokens = 8192 if length == 'long' else 4096
        message = _call_api(client, config.ARTICLE_MODEL, max_tokens, 0.7, prompt)

        result_text = message.content[0].text

        # Extrahuj titulky CZ a EN
        corrected_title = None
        en_title = None
        meta_cs = None
        meta_en = None

        title_cs_match = re.search(r'^\s*TITULEK\s*CZ:\s*(.+)$', result_text, re.MULTILINE)
        title_en_match = re.search(r'^\s*TITULEK\s*EN:\s*(.+)$', result_text, re.MULTILINE)
        meta_cs_match = re.search(r'^\s*META\s*CZ:\s*(.+)$', result_text, re.MULTILINE)
        meta_en_match = re.search(r'^\s*META\s*EN:\s*(.+)$', result_text, re.MULTILINE)
        # Fallback na starý formát
        title_old_match = re.search(r'^\s*TITULEK:\s*(.+)$', result_text, re.MULTILINE)

        if title_cs_match:
            corrected_title = title_cs_match.group(1).strip()
        elif title_old_match:
            corrected_title = title_old_match.group(1).strip()

        if title_en_match:
            en_title = title_en_match.group(1).strip()

        if meta_cs_match:
            meta_cs = meta_cs_match.group(1).strip().strip('"\'').strip('*')
        if meta_en_match:
            meta_en = meta_en_match.group(1).strip().strip('"\'').strip('*')

        # Odstraň řádky s titulky a meta popisy z textu, aby se nedostaly do HTML
        result_text = re.sub(r'^\s*TITULEK\s*(?:CZ|EN)?:\s*.+$', '', result_text, flags=re.MULTILINE)
        result_text = re.sub(r'^\s*META\s*(?:CZ|EN):\s*.+$', '', result_text, flags=re.MULTILINE)
        result_text = re.sub(r'^KEYWORD\s*(?:CZ|EN)?:\s*.+$', '', result_text, flags=re.MULTILINE)  # zpětná kompatibilita
        result_text = result_text.strip()

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
        cs_html = _insert_separators_before_h2(cs_html)
        cs_html = _make_first_paragraph_quote(cs_html)
        if en_html:
            en_html = _strip_markdown_artifacts(en_html)
            en_html = _insert_separators_before_h2(en_html)
            en_html = _make_first_paragraph_quote(en_html)

        # Odstraň AI-generované zdroje (nepřidáváme žádné)
        cs_html = _strip_generated_sources(cs_html)

        if en_html:
            en_html = _strip_generated_sources(en_html)

        # Odhad ceny (Claude Sonnet 4 pricing: $3.00/MTok input, $15.00/MTok output)
        cost_input = (message.usage.input_tokens / 1_000_000) * 3.00
        cost_output = (message.usage.output_tokens / 1_000_000) * 15.00
        total_cost = cost_input + cost_output

        result = {
            'cs': cs_html,
            'en': en_html,
            'tokens_in': message.usage.input_tokens,
            'tokens_out': message.usage.output_tokens,
            'cost': f"${total_cost:.4f}"
        }
        if corrected_title:
            result['corrected_title'] = corrected_title
        if en_title:
            result['en_title'] = en_title
        if meta_cs:
            result['meta_description_cs'] = meta_cs
        if meta_en:
            result['meta_description_en'] = meta_en
        return result

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
        message = _call_api(client, config.ARTICLE_MODEL, 4000, 0.8, prompt)

        script = message.content[0].text.strip()

        # Odhad ceny (Claude Sonnet 4 pricing: $3.00/MTok input, $15.00/MTok output)
        cost_input = (message.usage.input_tokens / 1_000_000) * 3.00
        cost_output = (message.usage.output_tokens / 1_000_000) * 15.00
        total_cost = cost_input + cost_output

        return {
            'script': script,
            'tokens_in': message.usage.input_tokens,
            'tokens_out': message.usage.output_tokens,
            'cost': f"${total_cost:.4f}"
        }

    except Exception as e:
        return {'error': str(e)}
