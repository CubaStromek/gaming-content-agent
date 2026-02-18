"""
Claude AI Analyzer
Analyzuje herní články a generuje nápady na obsah
"""

import re
import anthropic
import json
from typing import List, Dict
import config
from logger import setup_logger

log = setup_logger(__name__)

try:
    from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
    _HAS_TENACITY = True
except ImportError:
    _HAS_TENACITY = False


def _call_analysis_api(client, prompt):
    """Volání Claude API."""
    message = client.messages.create(
        model=config.ANALYSIS_MODEL,
        max_tokens=4000,
        temperature=0.7,
        messages=[{
            "role": "user",
            "content": prompt
        }]
    )
    return message


if _HAS_TENACITY:
    _call_analysis_api = retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=8),
        retry=retry_if_exception_type((
            anthropic.APIConnectionError,
            anthropic.RateLimitError,
        )),
        before_sleep=lambda retry_state: log.warning(
            "⚠️  API volání selhalo, pokus %d/3, čekám...", retry_state.attempt_number
        ),
    )(_call_analysis_api)


def analyze_gaming_articles(articles_text: str) -> str:
    """
    Pošle články Claude AI k analýze

    Args:
        articles_text: Naformátované články jako text

    Returns:
        Analýza a nápady od Claude
    """
    log.info("🧠 Analyzuji články pomocí Claude AI...")

    client = anthropic.Anthropic(api_key=config.CLAUDE_API_KEY)

    # Spočítej počet článků pro dynamický prompt
    article_count = articles_text.count("ČLÁNEK ")
    max_topics = min(2, max(1, article_count))

    prompt = f"""Analyzuj tyto herní články z dnešního dne a vytvoř report pro českého herního blogera.

ÚKOL:
1. Identifikuj TOP {max_topics} nejvíce relevantních témat pro český herní blog (POUZE {max_topics} - NE VÍCE!)
2. Pro každé téma navrhni konkrétní článek, který by mohl napsat
3. Poskytni dostatek kontextu pro vytvoření grafických bannerů k článku
4. DŮLEŽITÉ: Každé téma MUSÍ mít vyplněné VŠECHNY sekce včetně KONTEXTU a ZDROJŮ. Nevytvářej prázdná témata!

FORMÁT VÝSTUPU:
Pro každé téma napiš:
- 🎮 TÉMA: [název tématu]
- 📰 NAVRŽENÝ TITULEK: [catchy český titulek článku]
- 🎯 ÚHEL POHLEDU: [jak téma uchopit, jaký angle použít]
- 📝 KONTEXT: [2-3 věty shrnující klíčové informace - co se stalo, proč je to důležité, jaké jsou detaily]
- 💬 HLAVNÍ HOOK: [jedna úderná věta nebo číslo pro banner - např. "Prodáno 10 milionů kopií za 3 dny" nebo "První gameplay záběry odhaleny"]
- 🖼️ VIZUÁLNÍ NÁVRH: [co by mělo být na banneru - jaká hra, postava, scéna, barvy, nálada]
- 🔥 VIRALITA: [hodnocení 1-100, jak virální může být]
- 💡 PROČ TEĎKA: [proč je to aktuální, proč to napsat teď]
- 🔗 ZDROJE: [PŘESNÉ URL adresy relevantních článků - zkopíruj celé URL z Link: polí výše]
- 🏷️ SEO KLÍČOVÁ SLOVA: [3-5 klíčových slov pro SEO]
- 🕹️ NÁZEV HRY: [přesný anglický název hlavní hry v tématu, např. "The Elder Scrolls V: Skyrim" nebo "Grand Theft Auto VI". Pokud téma není o konkrétní hře, napiš "N/A"]

DŮLEŽITÉ:
- Zaměř se na témata zajímavá pro ČESKÉ publikum
- Preferuj témata, která jsou AKTUÁLNÍ (dnes/tento týden)
- Ignoruj témata starší než 3 dny (pokud nejsou viral)
- Dej přednost news a analýzám před recenzemi
- Pokud jsou tam oznámení nových her, dej jim prioritu
- V sekci ZDROJE musíš uvést PLNÉ URL adresy (začínající https://), ne čísla článků!
- KONTEXT musí obsahovat konkrétní fakta a čísla, ne obecné fráze
- NIKDY nevytvářej prázdná témata! Každé téma musí mít kompletní obsah všech sekcí
- FAKTICKÁ PŘESNOST: NIKDY nepřipisuj hře českou/slovenskou origin, pokud to není faktem. Neoznačuj hry jako "český", "česká hra", "od českých tvůrců" apod., pokud vývojářské studio skutečně není z ČR/SR. Psaní pro české publikum NEZNAMENÁ, že máš hry falešně vydávat za české!
- Počet témat musí odpovídat počtu dostupných článků (max {max_topics})

ČLÁNKY K ANALÝZE:
{articles_text}

---

VÝSTUP (seřaď od nejdůležitějšího, vytvoř PŘESNĚ {max_topics} témat s kompletním obsahem):"""

    try:
        message = _call_analysis_api(client, prompt)

        result = message.content[0].text

        # Statistiky použití
        log.info("✅ Analýza dokončena")
        log.info("   📊 Input tokeny: %d", message.usage.input_tokens)
        log.info("   📊 Output tokeny: %d", message.usage.output_tokens)

        # Odhad ceny (Claude Sonnet 4 pricing: $3.00/MTok input, $15.00/MTok output)
        cost_input = (message.usage.input_tokens / 1_000_000) * 3.00
        cost_output = (message.usage.output_tokens / 1_000_000) * 15.00
        total_cost = cost_input + cost_output

        log.info("   💰 Odhadovaná cena: $%.4f", total_cost)

        return result

    except Exception as e:
        log.error("❌ Chyba při volání Claude API: %s", e)
        return None


def extract_key_insights(articles: List[Dict]) -> Dict:
    """
    Extrahuje základní statistiky z článků

    Args:
        articles: Seznam článků

    Returns:
        Slovník se statistikami
    """
    insights = {
        'total_articles': len(articles),
        'sources': {},
        'languages': {},
        'most_common_words': []
    }

    # Počet článků podle zdrojů
    for article in articles:
        source = article['source']
        insights['sources'][source] = insights['sources'].get(source, 0) + 1

    # Počet článků podle jazyků
    for article in articles:
        lang = article['language']
        insights['languages'][lang] = insights['languages'].get(lang, 0) + 1

    return insights


def extract_used_urls_from_analysis(analysis: str) -> set:
    """
    Extrahuje URL adresy použité v analýze Claude

    Args:
        analysis: Text analýzy od Claude

    Returns:
        Set URL adres
    """
    url_pattern = r'https?://[^\s<>"\')\]]+[^\s<>"\')\].,]'
    urls = re.findall(url_pattern, analysis)
    return set(urls)


if __name__ == "__main__":
    # Test analyzeru
    log.info("🧪 Test Claude Analyzeru")
    log.info("Poznámka: Toto spotřebuje API tokeny!")

    test_articles = """ČLÁNEK 1:
Zdroj: IGN (en)
Titulek: GTA 6 New Trailer Breaks Records
Popis: Rockstar Games released the second trailer for Grand Theft Auto 6...
Link: https://ign.com/gta6

ČLÁNEK 2:
Zdroj: PC Gamer (en)
Titulek: Palworld hits 2 million concurrent players
Popis: The Pokemon-like survival game has become a massive hit...
Link: https://pcgamer.com/palworld"""

    result = analyze_gaming_articles(test_articles)
    if result:
        log.info("=" * 60)
        log.info(result)
