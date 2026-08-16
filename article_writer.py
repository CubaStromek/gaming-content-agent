"""
Article Writer - generovani clanku z TOP temat
Stahne zdrojove clanky, posle do Claude a vygeneruje CZ + EN verzi
"""

import json
import re
import requests
import anthropic
from bs4 import BeautifulSoup
from typing import List, Dict, Optional

import config
from logger import setup_logger
from models import VALID_STATUS_TAGS, SUBCATEGORY_IDS
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


# Modely, které odmítají nedefaultní temperature/top_p/top_k chybou 400 a mají
# zároveň ve výchozím stavu zapnuté přemýšlení (počítá se do max_tokens).
_MODERN_MODEL = re.compile(r'-(?:opus|sonnet|fable|mythos)-5\b|-opus-4-[78]\b')


def _is_modern(model: str) -> bool:
    return bool(_MODERN_MODEL.search(model or ''))


def _response_text(message) -> str:
    """Text z odpovědi. U modelů s přemýšlením není content[0] textový blok,
    takže se nesmí sahat na content[0].text — spadlo by to na ThinkingBlock."""
    return "".join(
        b.text for b in message.content if getattr(b, 'type', None) == 'text'
    )


def _call_api(client, model, max_tokens, temperature, messages):
    """Volání Claude API přes STREAMING.

    Streaming drží spojení trvale živé (tokeny tečou průběžně po stovkách ms),
    takže ho nezabije NAT/CGNAT/VPN idle-timeout u dlouhých requestů (>180s) —
    což byla příčina APIConnectionError přes NordVPN/Starlink (placený výstup
    do koše). get_final_message() vrací stejný Message objekt jako
    messages.create(), takže call-sites (.usage) zůstávají beze změny.
    messages je list zpráv (může obsahovat multi-block content s cache_control).

    U moderních modelů se temperature vynechává (jinak HTTP 400) a max_tokens
    se navyšuje — je to strop na přemýšlení i text dohromady.
    """
    kwargs = {"model": model, "max_tokens": max_tokens, "messages": messages}
    if _is_modern(model):
        kwargs["max_tokens"] = max(max_tokens, 32000)
    else:
        kwargs["temperature"] = temperature

    with client.messages.stream(**kwargs) as stream:
        return stream.get_final_message()


if _HAS_TENACITY:
    _call_api = retry(
        stop=stop_after_attempt(2),
        wait=wait_exponential(multiplier=4, min=15, max=60),
        retry=retry_if_exception(_is_retryable),
        before_sleep=lambda retry_state: log.warning(
            "⚠️  API volání selhalo (HTTP %s), pokus %d/2, čekám...",
            getattr(retry_state.outcome.exception(), 'status_code', '?'),
            retry_state.attempt_number
        ),
    )(_call_api)


# Ceník per model (input, output, cache read, cache write $/MTok) — match
# podle substringu v config.ARTICLE_MODEL. Dřív byl Sonnet hardcoded, takže
# při přepnutí modelu byly cost logy řádově vedle.
_MODEL_PRICING = {
    # Sazba za 1M tokenů: (vstup, výstup, cache read, cache write).
    # Opus byl na 15/75 z éry Opusu 3 — Opus 5 stojí 5/25, takže cost logy
    # u něj nadsazovaly zhruba trojnásobně (ověřeno na testu 15. 8. 2026).
    'opus': (5.00, 25.00, 0.50, 6.25),
    'sonnet': (3.00, 15.00, 0.30, 3.75),
    'haiku': (1.00, 5.00, 0.10, 1.25),
}


def _estimate_cost(usage, model):
    """Odhad ceny volání z usage objektu. Vrací (total_cost, cache_read, cache_write)."""
    pricing = None
    for key, p in _MODEL_PRICING.items():
        if key in model:
            pricing = p
            break
    if pricing is None:
        pricing = _MODEL_PRICING['sonnet']
    p_in, p_out, p_cr, p_cw = pricing

    _cr = getattr(usage, "cache_read_input_tokens", 0)
    _cw = getattr(usage, "cache_creation_input_tokens", 0)
    cache_read = _cr if isinstance(_cr, int) else 0
    cache_write = _cw if isinstance(_cw, int) else 0
    total = (
        (usage.input_tokens / 1_000_000) * p_in
        + (usage.output_tokens / 1_000_000) * p_out
        + (cache_read / 1_000_000) * p_cr
        + (cache_write / 1_000_000) * p_cw
    )
    return total, cache_read, cache_write


# Postprocess funkce přesunuty do article_postprocess.py (testovatelné bez sítě).
# Aliasy zachovávají zpětnou kompatibilitu uvnitř tohoto modulu.
from article_postprocess import (
    build_sources_html as _build_sources_html,
    strip_generated_sources as _strip_generated_sources,
    strip_markdown_artifacts as _strip_markdown_artifacts,
    make_first_paragraph_quote as _make_first_paragraph_quote,
    insert_separators_before_h2 as _insert_separators_before_h2,
    extract_story_cards as _extract_story_cards,
    parse_entity as _parse_entity,
)


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
        raw_tag = topic.get('status_tag', 'news').lower().strip()
        topic['status_tag'] = raw_tag if raw_tag in VALID_STATUS_TAGS else 'news'

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


_EN_PROMPT = """Z hotového českého článku vytvoř ANGLICKOU verzi pro mezinárodní publikum (USA, UK, západní Evropa).

Není to doslovný překlad, je to lokalizace: zachovej úhel, tón, strukturu i všechny <h2> sekce a fakta, ale piš přirozenou angličtinou, ne přeloženou češtinou.

PRAVIDLA:
- NIKDY nezmiňuj "Czech", "Czech Republic", "Czech players/gamers/market", "in Czechia" — ani v titulku, ani v meta, ani v textu. Kde česká verze mluví o českých hráčích, použij obecnější pojem ("players", "PC gamers", "Steam users", "Western audiences") podle kontextu. Výjimka: fakticky podstatné téma, třeba české studio jako Warhorse (CD Projekt je polské, ne české).
- Formát: ČISTÉ HTML (<h2>, <p>, <strong>), žádný markdown.
- V <h2> NEPOUŽÍVEJ Title Case. ŠPATNĚ: "What This Means For Players". SPRÁVNĚ: "What this means for players".
- Zachovej délku originálu, MINIMUM 600 slov.
- NEPŘIDÁVEJ <h1> ani sekci "Sources".

NA ZAČÁTEK výstupu uveď na samostatných řádcích:
  KEYWORD EN: [main SEO keyword in English, 1-2 words, SHORT — Rank Math scores exact match in title/H2/intro, long-tail phrases lower the score. Priority: 1) exact game/platform/studio name ("xbox", "gta 6", "gothic remake"), 2) max 2 words. NEVER 3+ word phrases.]
  TITULEK EN: [English title, MAX 60 characters, KEYWORD EN in the first third, no clickbait, no rhetorical questions, no colon teasers]
  META EN: [English meta description, 140-155 characters, ends with punctuation, contains KEYWORD EN]
  STORY_CARDS EN: [ONE-LINE JSON array of 3-5 objects {"heading": "max 40 chars", "body": "max 160 chars, 1-2 sentences"}. Not a section-by-section summary — the 3-5 most important points (key fact → context/angle → consequence). Each card is read standalone on a vertical mobile screen. Plain text only, no HTML, no markdown. Never mention the Czech Republic.]

SEO KONTROLA před odevzdáním: KEYWORD EN je v TITULEK EN (první třetina), v prvním odstavci, v META EN, alespoň v jednom <h2> a v textu minimálně 3×.

FORMÁT VÝSTUPU:
=== ENGLISH ===
<článek v angličtině jako HTML>"""


def _localize_to_english(client, cs_html: str, title_cs: Optional[str],
                         keyword_cs: Optional[str]) -> Dict:
    """Druhá fáze: z hotového českého článku udělá anglickou verzi + EN metadata.

    Běží na TRANSLATION_MODEL, protože překlad hotového textu je mechanická
    práce — cenu Opusu má smysl platit jen za české psaní v první fázi.
    Selhání téhle fáze nesmí zabít celý článek: vrací {'error': ...} a volající
    článek publikuje jen česky.
    """
    if not cs_html:
        return {'error': 'prázdný český článek'}

    context = f"""=== ČESKÝ ČLÁNEK K LOKALIZACI ===
ČESKÝ TITULEK: {title_cs or ''}
ČESKÝ KEYWORD: {keyword_cs or ''}

{cs_html}

Vygeneruj nyní EN metadata a anglickou verzi ve formátu popsaném výše."""

    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": _EN_PROMPT, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": context},
        ],
    }]

    try:
        message = _call_api(client, config.TRANSLATION_MODEL, 8192, 0.7, messages)
        if message.stop_reason == 'max_tokens':
            return {'error': 'EN výstup useknut na max_tokens'}

        text = _response_text(message)

        def _line(label):
            m = re.search(r'^\s*' + label + r':\s*(.+)$', text, re.MULTILINE)
            return m.group(1).strip().strip('"\'').strip('*') if m else None

        keyword_en = _line(r'KEYWORD\s*EN')
        title_en = _line(r'TITULEK\s*EN')
        meta_en = _line(r'META\s*EN')
        story_cards_en = _extract_story_cards(text, 'EN')

        body = text
        body = re.sub(r'^\s*(?:KEYWORD|TITULEK|META)\s*EN:\s*.+$', '', body, flags=re.MULTILINE)
        body = re.sub(r'^\s*STORY_CARDS\s*EN:\s*\[[\s\S]*?\]\s*$', '', body, flags=re.MULTILINE)

        m = re.search(r'===\s*ENGLISH\s*===\s*([\s\S]*)$', body)
        en_html = (m.group(1) if m else body).strip()

        en_html = _strip_markdown_artifacts(en_html)
        en_html = _insert_separators_before_h2(en_html)
        en_html = _make_first_paragraph_quote(en_html)
        en_html = _strip_generated_sources(en_html)

        cost, cache_read, cache_write = _estimate_cost(message.usage, config.TRANSLATION_MODEL)
        log.info("EN lokalizace [%s]: in=%d (cache read=%d, write=%d), out=%d, $%.4f",
                 config.TRANSLATION_MODEL, message.usage.input_tokens, cache_read,
                 cache_write, message.usage.output_tokens, cost)

        return {
            'en': en_html,
            'en_title': title_en,
            'meta_en': meta_en,
            'keyword_en': keyword_en.lower() if keyword_en else None,
            'story_cards_en': story_cards_en,
            'tokens_in': message.usage.input_tokens,
            'tokens_out': message.usage.output_tokens,
            'cache_read': cache_read,
            'cache_write': cache_write,
            'cost': cost,
        }
    except Exception as e:  # noqa: BLE001
        return {'error': str(e)}


def write_article(topic: Dict, source_texts: List[str], length: str = 'medium') -> Dict:
    """
    Vygeneruje clanek pomoci Claude API

    Args:
        topic: Slovnik s tematem (z parse_topics_from_report)
        source_texts: Seznam plnych textu zdrojovych clanku

    Returns:
        {"cs": "<html>...", "en": "<html>..."} nebo {"error": "..."}
    """
    # max_retries=1: tenacity řeší vyšší retry; nižší SDK retry brání násobení nákladů
    client = anthropic.Anthropic(api_key=config.CLAUDE_API_KEY, max_retries=1)

    # Pripravi zdrojove texty
    sources_combined = ""
    for i, text in enumerate(source_texts, 1):
        sources_combined += f"\n--- ZDROJ {i} ---\n{text}\n"

    # Pripravi seznam URL zdroju pro konec clanku
    source_urls = topic.get('sources', [])
    sources_list = "\n".join(source_urls)

    if length == 'short':
        length_instruction = "Článek musí mít 600-800 slov (krátká analýza, 5-7 odstavců). MINIMUM je 600 slov — Rank Math pod tím hlásí 'zvažte použití alespoň 600 slov'. Pokud se blížíš ke spodní hranici, přidej další odstavec s kontextem nebo srovnáním."
    elif length == 'long':
        length_instruction = "Článek musí mít 1200-1800 slov (deep-dive, 12-18 odstavců, více h2 sekcí, silná analýza a kontext)"
    else:
        length_instruction = "Článek musí mít 700-1000 slov (střední analýza, 7-10 odstavců). MINIMUM je 600 slov kvůli Rank Math SEO skóre."

    static_prompt = """Napíš ANALYTICKÝ herní článek s vlastním úhlem pohledu. Toto NENÍ přepis zprávy — je to komentář redaktora, který zpravodajskou událost zasazuje do kontextu a říká, CO TO ZNAMENÁ.

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

DOBRÉ ÚVODY (analytické, věcné, bez rétorických triků):
- Zasazení do kontextu: "Odložení přichází v době, kdy tři z pěti největších AAA titulů letošního roku posunuly termín o víc než rok."
- Konkrétní pozorování: "Rockstar poprvé od roku 2013 drží oznámený termín vydání déle než rok — a u GTA 6 to zatím platí."
- Srovnání s trendem: "Zatímco menší studia zkracují vývojové cykly, u velkých vydavatelů se prodlužují. Nejnovější oznámení zapadá přesně do toho vzorce."
- Přímé pojmenování tématu: "Nový trailer potvrzuje, co se šeptalo od léta: hra se odkládá podruhé a směřuje k jarnímu oknu 2027."

ZAKÁZANÉ ÚVODY I ZDE:
- Rétorické otázky ("Kdo na tom vydělal?", "Je to skutečně konec?")
- Pomlčkové teasery ("A hráči jsou podivně klidní.")
- Superlativy a emocionální hodnocení v první větě ("šokující", "konečně", "bomba")

=== ZAKÁZANÉ AI VZORCE (čtenáři je okamžitě poznávají jako "ChatGPT text") ===
NIC z následujícího se v článku nesmí objevit. Pokud něco napíšeš, smaž a přepiš.

1. **Vzorec "Není X. Je to Y." / "Nejde o X, jde o Y."** — typický esejistický pattern. Maximálně 1× v celém článku, ideálně 0×.
   - ŠPATNĚ: "Tohle není jen herní kuriozita. Je to učebnicový příklad..."
   - SPRÁVNĚ: "Steam tu má další řízenou krizi z review bombingu — typickou, ale s nezvyklým detailem..."

2. **Em-dash (–) jako zázračný interpunkční nástroj** — používej pomlčku JEN když opravdu odděluje vsuvku, kterou jinak nelze vyjádřit. Většinu pomlček nahraď tečkou, čárkou nebo závorkou. Maximálně 3 em-dashe na 1000 slov. AI texty mívají 15–25.

3. **Esejistický slovník** — okamžité red flags, NEPOUŽÍVAT:
   - "učebnicový příklad", "učebnicová ukázka"
   - "zásadně problematický", "strukturálně zabudované"
   - "obojí je reálné a obojí je relevantní"
   - "specifická cena", "specifický kontext", "specifičnost tohoto případu"
   - "v zcela různých světech", "ve dvou různých světech"
   - "nepsaná dohoda", "implicitní kontrakt"
   - "permanentní zkouška", "permanentní napětí"

4. **Dvojitý balancing v závěru** — "Data má X. Frustrace má Y. Obojí je reálné." Tohle je doslova ChatGPT signature. Závěr má názor, ne vyvážení.

5. **Předvídání budoucnosti binární volbou** — "X teď stojí před konkrétní volbou: buď A, nebo B." Život není binární; nepiš jako učebnice rozhodovací teorie.

6. **Vata/zástupné fráze** — "ve specifickém kontextu", "z jiného úhlu pohledu", "je důležité si uvědomit, že", "stojí za zmínku, že".

7. **"Co z toho plyne pro X i pro Y"** v textu — je to AI strukturní fráze. Pokud chceš důsledky, popiš je rovnou.

=== STRUKTURA & H2 NADPISY (KRITICKÉ — tady čtenáři nejvíc poznají AI) ===

**ZAKÁZANÉ H2 (šablonové, ChatGPT-style — NIKDY nepoužívat):**
- ❌ "Co se stalo" / "What happened"
- ❌ "Proč to vadí" / "Why this matters" / "Why it matters"
- ❌ "Co z toho plyne" / "What this means" / "What this means for X"
- ❌ "Co z toho plyne pro X i pro Y"
- ❌ "Hlubší otázka" / "The deeper question"
- ❌ "X jako permanentní zkouška Y" / "X as a permanent test of Y"
- ❌ Jakýkoli nadpis začínající "Proč X..." / "Why X..." (kromě případů, kdy je to citace)

**POVINNÉ vlastnosti dobrého H2:**
- Konkrétní jméno (hra, studio, postava, číslo) NEBO konkrétní akce. Generické pojmy ("komunita", "hráči", "trh") nestačí.
- Maximum 7 slov. Krátký, hutný.
- Ne vysvětluje, oznamuje. NE "Proč Mega Crit selhala v komunikaci" → ANO "Mega Crit ukázala čísla. Pomohla si tím méně."
- NE titlecase. První písmeno věty + vlastní jména. (Stávající pravidlo, platí dál.)

**DOBRÉ H2 — vzory z reálného herního zpravodajství:**
- "Mega Crit ukázala čísla, ale komunita je nepřijala"
- "The Doormaker má nejvyšší win rate ze tří bossů"
- "27 000 záporných recenzí za deset dní"
- "Patch v0.104.0 obrátil situaci proti vývojářům"
- "Rockstar drží termín GTA 6 přes 12 měsíců"
- "Gothic remake mění boj, atmosféra zůstává"
- "Sony stáhla PS5 Pro reklamu po 48 hodinách"

**Struktura článku:**
- Úvodní hook (první <p> = silná teze/paradox/konkrétní fakt, NE shrnutí faktů). MUSÍ obsahovat hlavní KEYWORD (CZ i EN) — ideálně v první větě, nejpozději do 100 znaků od začátku článku.
- 2–4 <h2> sekce, každá s konkrétním H2 podle pravidel výše. Alespoň jeden H2 obsahuje KEYWORD nebo jeho variantu.
- První sekce po úvodu: holá fakta (kdy, kde, kdo, kolik). MAX 2–3 věty. NIKDY ne "Co se stalo".
- Prostřední sekce: kontext, čísla, srovnání s podobnými případy. Tady patří analýza.
- Poslední sekce / odstavec: názor/provokativní shrnutí/otevřená otázka — ne "uvidíme, jak se to vyvine", ne dvojitý balancing, ne "X teď stojí před volbou".

=== PRAVIDLA ===
- Piš VLASTNÍMI SLOVY, ze zdrojů přebírej JEN fakta a čísla, nikdy ne formulace
- Délkové požadavky najdeš v sekci ZADÁNÍ níže
- Formát: ČISTÉ HTML (<h2>, <p>, <strong>)
- NEPOUŽÍVEJ markdown! Žádné ```, ---, #, ** — POUZE HTML tagy
- Styl: analytický, s názorem. NE neutrální zpravodajský tón. Nebojí se mít postoj. Píšeš pro české herní publikum (můžeš zmínit český trh, české hráče, lokální kontext).

=== ČEŠTINA (piš česky, nepřekládej z angličtiny) ===
Zdroje jsou anglické, článek je český. Nepřevádět anglickou vazbu do češtiny slovo od slova:
- Neživá věc se v češtině NECÍTÍ. ŠPATNĚ: "Zóna se cítila spíš jako střelnice." SPRÁVNĚ: "Zóna působila spíš jako střelnice." (Člověk nebo komunita se cítit může — to je v pořádku.)
- Nezačínej větu příslovcem převzatým z anglické stavby. ŠPATNĚ: "Mechanicky zásadnější je změna systému A-Life." SPRÁVNĚ: "Zásadnější zásah do hratelnosti je změna systému A-Life."

=== VĚCNÁ SPRÁVNOST PŘÍČIN A NÁSLEDKŮ (KRITICKÉ) ===
Než napíšeš, že něco něco způsobilo, ověř si ve zdroji SMĚR té vazby. Nejčastější chyba je zaměnit funkci za její selhání: když hráči kritizovali, že svět působí mrtvě, nemůže za to systém, který ho má oživovat — může za to jeho NEFUNKČNOST. ŠPATNĚ: "A-Life byl označován za příčinu toho, proč Zóna působila jako střelnice." SPRÁVNĚ: "Za hlavní příčinu byl označován rozbitý A-Life, který po vydání prakticky nefungoval." Pokud si směrem nejsi jistý, napiš jen to, co zdroj tvrdí, a kauzalitu vynech.
- Zahrň konkrétní fakta a čísla (to je zásadní pro důvěryhodnost analýzy)
- NEZMIŇUJ zdroje v textu článku (ne "podle IGN...")
- NEPŘIDÁVEJ h1 nadpis — ten bude jako titulek článku
- NEPOUŽÍVEJ vatu typu "jak se situace vyvine, ukáže čas", "zatím není jasné", "uvidíme". Pokud je otazník, POJMENUJ ho konkrétně.
- FAKTICKÁ PŘESNOST: Zkontroluj, že titulek odpovídá obsahu. Pokud navržený titulek obsahuje nepravdivé tvrzení (např. označuje hru jako "českou", i když studio je zahraniční), OPRAV titulek.
- TITULEK: věcný, profesionální, analytický tón — nikdy clickbait.
  - DÉLKA: MAX 60 znaků (tolerance do 65). Google v SERPu usekává nad 60 znaků. Neměj souvětí, jedna věta, jedna myšlenka.
  - KLÍČOVÉ SLOVO: hlavní SEO klíčové slovo (nebo název hry, pokud je klíčové slovo jeho součástí) MUSÍ být v první třetině titulku — ideálně úplně na začátku.
  - ZAKÁZÁNO: rétorické otázky ("Proč tomu věřit?", "Kdo na tom vydělá?"), pomlčkové dovětky typu "— a tady je problém" / "a to není vše", superlativy a emocionální nálepky ("šokující", "bomba", "konečně"), fráze "tentokrát vážně" / "teď už doopravdy", vykřičníky, dvojtečkové teasery ("GTA 6: co o tom nevíte").
  - SPRÁVNĚ: titulek pojmenuje KONKRÉTNÍ fakt + úhel jednou krátkou větou bez hype. Příklady (všechny pod 60 znaků, klíčové slovo vpředu): "GTA 6 potvrzeno na listopad 2026, Rockstar drží termín" (54), "Gothic remake mění bojový systém, atmosféra zůstává" (52), "Silksong se odkládá, Team Cherry ukazuje limity solo studií" (59).
  - Musí mít ÚHEL (ne jen "X oznámil Y"), ale úhel = informace navíc nebo zasazení do kontextu, NE rétorická figura.
- NA ZAČÁTEK výstupu VŽDY uveď titulky, klíčová slova a meta popisy na samostatných řádcích:
  KEYWORD CZ: [hlavní SEO klíčové slovo v češtině, 1-2 slova, KRÁTKÉ — Rank Math hodnotí přesnou shodu v titulku/H2/úvodu, takže long-tail fráze score srážejí. Priorita: 1) přesný název hry/platformy/studia ("xbox", "gta 6", "gothic remake", "silksong", "rockstar"), 2) max 2 slova ("herní leaky", "gaming awards"). NIKDY 3+ slovné fráze typu "gta 6 datum vydání leak". Pokud jsou výše zadaná SEO KLÍČOVÁ SLOVA, vyber z nich nejkratší a nejsilnější, jinak navrhni sám.]
  TITULEK CZ: [český titulek, MAX 60 znaků, KEYWORD CZ v první třetině]
  META CZ: [český meta description, 140-155 znaků, VŽDY ukončené tečkou/otazníkem, obsahuje KEYWORD CZ, musí lákat k prokliku]
  RUBRIKA: [právě JEDNA hodnota z: aaa | indie | playstation | microsoft | nintendo | valve | technologie | ekonomika | mimoherni | cesko-slovensko | zadna. Podrubrika Zpráv podle HLAVNÍHO tématu článku: aaa = velkorozpočtové hry a jejich studia (Rockstar, Ubisoft, CD Projekt…); indie = nezávislé hry a malá studia; playstation = Sony/PlayStation (konzole, exkluzivity, PS Plus); microsoft = Microsoft/Xbox (konzole, Game Pass, Bethesda/ABK studia); nintendo = Nintendo (Switch, first-party hry); valve = Valve/Steam (platforma, Steam Deck/Machine, Half-Life); technologie = hardware a technika mimo jednu platformu (GPU, RAM, VR, handheldy obecně); ekonomika = byznys, prodeje, akvizice, propouštění bez vazby na jednu firmu/platformu; mimoherni = přesahy mimo hry (film, seriály, esport, společnost); cesko-slovensko = česká/slovenská studia a scéna. Pokud sedí víc rubrik, vyber NEJKONKRÉTNĚJŠÍ — rubrika platformy/firmy má přednost před obecnou (aaa, ekonomika). Pokud nic jednoznačně nesedí, napiš zadna.]
  ENTITA: [anglický název HLAVNÍHO subjektu článku + svislítko + typ. Používá se JEN k vyhledání náhledového obrázku v herní databázi, do textu se nedostane. Formát: `název | hra` nebo `název | znacka`. Typ `hra` = konkrétní hra nebo herní série, kterou lze najít v databázi her (`Diablo IV | hra`, `The Witcher | hra`, `Big Walk | hra`). Typ `znacka` = firma, studio, vydavatel, konzole, platforma, obchod nebo akce (`Nintendo | znacka`, `Roblox | znacka`, `Devolver Digital | znacka`, `Summer Game Fest | znacka`). PRAVIDLA: (1) VŽDY anglicky a v kanonickém tvaru, jak se jméno píše oficiálně — ne česky, ne skloňované, bez roku a bez podtitulu článku. (2) Nikdy nepiš celou větu ani popis události — jen holé jméno. (3) Když je článek o konzoli nebo firmě a žádná konkrétní hra v něm nedominuje, je to `znacka`, i kdyby se nějaká hra v textu zmiňovala. (4) Když článek srovnává víc her, vyber tu, které se text věnuje nejvíc. Příklady: článek „Nintendo Switch 2 překonala GameCube v prodejích" → `Nintendo | znacka`; „Roblox v krizi, akcie padají o 70 %" → `Roblox | znacka`; „Witcher seriál na Netflixu se posouvá na 2027" → `The Witcher | hra`.]
  STORY_CARDS CZ: [JEDNO-ŘÁDKOVÝ JSON array 3-5 objektů ve tvaru {"heading": "max 40 znaků", "body": "max 160 znaků, 1-2 věty"}. Toto NENÍ shrnutí článku po sekcích — vyber 3-5 nejdůležitějších bodů (klíčový fakt → kontext/úhel → důsledek). Každá karta = 1 myšlenka, čte se na svislé mobilní obrazovce SAMOSTATNĚ, čtenář vidí jen tu jednu kartu a musí pochopit pointu bez ostatních. Bez HTML, bez markdown, plain text v JSON stringu. Heading je věcný (ne otázka, ne clickbait). Body 1-2 reálné věty. Příklad jedné karty: {"heading":"Rockstar drží termín přes rok","body":"Od oznámení v roce 2024 GTA 6 nezměnilo datum vydání, což je u AAA tahounů nezvyklé."}}]
- KRITICKÉ: V nadpisech (h2) NEPOUŽÍVEJ Title Case! Velké písmeno POUZE na začátku věty a u vlastních jmen. ŠPATNĚ: "Nová Éra Pro Herní Průmysl". SPRÁVNĚ: "Nová éra pro herní průmysl". ŠPATNĚ: "What This Means For Players". SPRÁVNĚ: "What this means for players".
- KRITICKÉ: META CZ/EN NESMÍ být uťaté v půli věty! Krátký svébytný popis (1-2 věty) končící interpunkcí — NIKDY NE kopie úvodního odstavce.
- NEPŘIDÁVEJ sekci "Zdroje" ani "Sources" — přidají se automaticky

=== SEO CHECKLIST (povinné, ne doporučení) ===
Před odesláním článku zkontroluj, že platí VŠECHNO:
1. KEYWORD CZ je v TITULEK CZ, v první třetině.
2. KEYWORD CZ je v prvním odstavci článku (do 100 znaků od začátku).
3. KEYWORD CZ je v META CZ.
4. KEYWORD CZ se v celém článku objeví minimálně 3× (přirozeně, ne spam).
5. Alespoň jeden <h2> obsahuje KEYWORD nebo jeho variantu.
6. TITULEK CZ má max 60 znaků.
7. Článek má MINIMUM 600 slov (ideál podle požadované délky výše). Spočítej si slova před odevzdáním — tohle je tvrdá hranice, pod ní Rank Math hlásí chybu. Pokud je méně, dopiš odstavec s kontextem/srovnáním/důsledkem — NE vatou ("ukáže čas", "uvidíme"), ale konkrétními informacemi nebo úhlem navíc.
Pokud některý bod nesedí, PŘEPIŠ titulek nebo úvod, ne článek celý. U bodu 7 rozšiř analytický obsah.

FORMÁT VÝSTUPU (nejdřív metadata na samostatných řádcích, pak článek):
=== ČESKY ===
<článek v češtině jako HTML, BEZ sekce zdrojů>"""

    dynamic_prompt = f"""=== ZADÁNÍ ===
TÉMA: {topic.get('topic', '')}
NAVRŽENÝ TITULEK: {topic.get('title', '')}
ÚHEL POHLEDU: {topic.get('angle', '')}
KONTEXT: {topic.get('context', '')}
SEO KLÍČOVÁ SLOVA: {topic.get('seo_keywords', '')}

DÉLKA ČLÁNKU: {length_instruction}

ZDROJOVÉ TEXTY (použij JEN pro fakta, ne jako šablonu):
{sources_combined}

Vygeneruj nyní výstup ve formátu popsaném výše (KEYWORD/TITULEK/META/RUBRIKA/ENTITA/STORY_CARDS metadata, pak sekce === ČESKY ===)."""

    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": static_prompt, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": dynamic_prompt},
        ],
    }]

    try:
        # Velkorysý strop — max_tokens je jen cap, negenerované tokeny nic
        # nestojí. Anglická verze se od 16. 8. 2026 generuje zvlášť, takže
        # tahle fáze vyrábí jen český článek + metadata.
        max_tokens = 16384 if length == 'long' else 8192
        message = _call_api(client, config.ARTICLE_MODEL, max_tokens, 0.7, messages)

        if message.stop_reason == 'max_tokens':
            log.error("Výstup useknut na max_tokens (%d) — článek by byl neúplný", max_tokens)
            return {'error': f'Output truncated at max_tokens={max_tokens}'}

        result_text = _response_text(message)

        # Extrahuj titulky, klíčová slova a meta CZ/EN
        corrected_title = None
        en_title = None
        meta_cs = None
        meta_en = None
        keyword_cs = None
        keyword_en = None
        subcategory = None
        entity_name = None
        entity_type = None

        title_cs_match = re.search(r'^\s*TITULEK\s*CZ:\s*(.+)$', result_text, re.MULTILINE)
        title_en_match = re.search(r'^\s*TITULEK\s*EN:\s*(.+)$', result_text, re.MULTILINE)
        meta_cs_match = re.search(r'^\s*META\s*CZ:\s*(.+)$', result_text, re.MULTILINE)
        meta_en_match = re.search(r'^\s*META\s*EN:\s*(.+)$', result_text, re.MULTILINE)
        keyword_cs_match = re.search(r'^\s*KEYWORD\s*CZ:\s*(.+)$', result_text, re.MULTILINE)
        keyword_en_match = re.search(r'^\s*KEYWORD\s*EN:\s*(.+)$', result_text, re.MULTILINE)
        subcategory_match = re.search(r'^\s*RUBRIKA:\s*(.+)$', result_text, re.MULTILINE)
        entity_match = re.search(r'^\s*ENTITA:\s*(.+)$', result_text, re.MULTILINE)
        story_cards_cs = _extract_story_cards(result_text, 'CZ')
        story_cards_en = _extract_story_cards(result_text, 'EN')
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

        if keyword_cs_match:
            keyword_cs = keyword_cs_match.group(1).strip().strip('"\'').strip('*').lower()
        if keyword_en_match:
            keyword_en = keyword_en_match.group(1).strip().strip('"\'').strip('*').lower()

        if subcategory_match:
            raw_subcat = subcategory_match.group(1).strip().strip('"\'').strip('*').lower()
            if raw_subcat in SUBCATEGORY_IDS:
                subcategory = raw_subcat
            elif raw_subcat not in ('zadna', 'žádná', 'none'):
                log.warning("Neznámá RUBRIKA z LLM: '%s' — článek půjde jen do Zpráv", raw_subcat)

        if entity_match:
            entity_name, entity_type = _parse_entity(entity_match.group(1))

        # Odstraň řádky s titulky, klíčovými slovy a meta popisy z textu, aby se nedostaly do HTML
        result_text = re.sub(r'^\s*TITULEK\s*(?:CZ|EN)?:\s*.+$', '', result_text, flags=re.MULTILINE)
        result_text = re.sub(r'^\s*META\s*(?:CZ|EN):\s*.+$', '', result_text, flags=re.MULTILINE)
        result_text = re.sub(r'^\s*KEYWORD\s*(?:CZ|EN)?:\s*.+$', '', result_text, flags=re.MULTILINE)
        result_text = re.sub(r'^\s*RUBRIKA:\s*.+$', '', result_text, flags=re.MULTILINE)
        result_text = re.sub(r'^\s*ENTITA:\s*.+$', '', result_text, flags=re.MULTILINE)
        # STORY_CARDS může být víceřádkový JSON, mažeme od labelu po uzavírací ]
        result_text = re.sub(r'^\s*STORY_CARDS\s*(?:CZ|EN):\s*\[[\s\S]*?\]\s*$', '', result_text, flags=re.MULTILINE)
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

        total_cost, cache_read, cache_write = _estimate_cost(message.usage, config.ARTICLE_MODEL)
        tokens_in = message.usage.input_tokens
        tokens_out = message.usage.output_tokens

        log.info("CZ článek [%s]: in=%d (cache read=%d, write=%d), out=%d, $%.4f",
                 config.ARTICLE_MODEL, tokens_in, cache_read, cache_write,
                 tokens_out, total_cost)

        # --- FÁZE 2: anglická lokalizace samostatným (levnějším) voláním ---
        en = _localize_to_english(client, cs_html, corrected_title, keyword_cs)
        if en.get('error'):
            log.warning("EN lokalizace selhala (%s) — článek půjde jen česky", en['error'])
        else:
            en_html = en.get('en', '')
            en_title = en.get('en_title') or en_title
            meta_en = en.get('meta_en') or meta_en
            keyword_en = en.get('keyword_en') or keyword_en
            story_cards_en = en.get('story_cards_en') or story_cards_en
            total_cost += en.get('cost', 0.0)
            tokens_in += en.get('tokens_in', 0)
            tokens_out += en.get('tokens_out', 0)
            cache_read += en.get('cache_read', 0)
            cache_write += en.get('cache_write', 0)

        log.info("Článek celkem: out=%d tokenů, $%.4f", tokens_out, total_cost)

        result = {
            'cs': cs_html,
            'en': en_html,
            'tokens_in': tokens_in,
            'tokens_out': tokens_out,
            'cache_read': cache_read,
            'cache_write': cache_write,
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
        if keyword_cs:
            result['focus_keyword_cs'] = keyword_cs
        if keyword_en:
            result['focus_keyword_en'] = keyword_en
        if subcategory:
            result['subcategory'] = subcategory
            log.info("RUBRIKA: %s", subcategory)
        if entity_name:
            result['entity_name'] = entity_name
            result['entity_type'] = entity_type
            log.info("ENTITA: %s (%s)", entity_name, entity_type)
        if story_cards_cs:
            result['story_cards_cs'] = story_cards_cs
            log.info("STORY_CARDS CZ: %d karet", len(story_cards_cs))
        if story_cards_en:
            result['story_cards_en'] = story_cards_en
            log.info("STORY_CARDS EN: %d karet", len(story_cards_en))
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
    # max_retries=1: tenacity řeší vyšší retry; nižší SDK retry brání násobení nákladů
    client = anthropic.Anthropic(api_key=config.CLAUDE_API_KEY, max_retries=1)

    # Odstran HTML tagy pro citelnejsi vstup
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(article_html, 'html.parser')
    article_text = soup.get_text(separator='\n', strip=True)

    if lang == 'cs':
        static_prompt = """Vytvoř podcast script ze článku přiloženého níže. Formát: konverzace dvou moderátorů (ALEX a MAYA).

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
        dynamic_prompt = f"ČLÁNEK:\n{article_text}"

    else:
        static_prompt = """Create a podcast script from the article provided below. Format: conversation between two hosts (ALEX and MAYA).

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
        dynamic_prompt = f"ARTICLE:\n{article_text}"

    messages = [{
        "role": "user",
        "content": [
            {"type": "text", "text": static_prompt, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": dynamic_prompt},
        ],
    }]

    try:
        message = _call_api(client, config.ARTICLE_MODEL, 4000, 0.8, messages)

        script = _response_text(message).strip()

        total_cost, cache_read, cache_write = _estimate_cost(message.usage, config.ARTICLE_MODEL)

        return {
            'script': script,
            'tokens_in': message.usage.input_tokens,
            'tokens_out': message.usage.output_tokens,
            'cache_read': cache_read,
            'cache_write': cache_write,
            'cost': f"${total_cost:.4f}"
        }

    except Exception as e:
        return {'error': str(e)}
