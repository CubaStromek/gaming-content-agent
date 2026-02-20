"""
Claude AI Analyzer
Analyzuje herní články a generuje nápady na obsah.
Podporuje strukturované výstupy přes tool_use (Fáze 1).
"""

import re
import anthropic
import json
from typing import List, Dict, Optional
import config
import topic_dedup
from logger import setup_logger
from models import Topic, AnalysisResult

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
            anthropic.InternalServerError,
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
{topic_dedup.format_recent_topics_for_prompt(days=3)}
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


def _build_analysis_tool(max_topics: int) -> dict:
    """Sestaví definici toolu pro strukturovaný výstup analýzy."""
    return {
        "name": "submit_analysis",
        "description": f"Odešle strukturovanou analýzu s TOP {max_topics} herními tématy pro český herní blog",
        "input_schema": {
            "type": "object",
            "required": ["topics"],
            "properties": {
                "topics": {
                    "type": "array",
                    "description": f"Přesně {max_topics} témat seřazených od nejdůležitějšího",
                    "items": {
                        "type": "object",
                        "required": ["topic", "title", "angle", "context", "hook",
                                     "visual", "virality_score", "why_now", "sources",
                                     "seo_keywords", "game_name"],
                        "properties": {
                            "topic": {"type": "string", "description": "Název tématu"},
                            "title": {"type": "string", "description": "Navržený český titulek článku"},
                            "angle": {"type": "string", "description": "Úhel pohledu - jak téma uchopit"},
                            "context": {"type": "string", "description": "2-3 věty kontextu s konkrétními fakty a čísly"},
                            "hook": {"type": "string", "description": "Hlavní hook pro banner - úderná věta nebo číslo"},
                            "visual": {"type": "string", "description": "Vizuální návrh pro banner - hra, postava, scéna, barvy, nálada"},
                            "virality_score": {"type": "integer", "minimum": 1, "maximum": 100, "description": "Hodnocení virality 1-100"},
                            "why_now": {"type": "string", "description": "Proč je to aktuální, proč to napsat teď"},
                            "sources": {"type": "array", "items": {"type": "string"}, "description": "Plné URL adresy zdrojových článků (https://...)"},
                            "seo_keywords": {"type": "string", "description": "3-5 SEO klíčových slov oddělených čárkou"},
                            "game_name": {"type": "string", "description": "Přesný anglický název hlavní hry (např. 'Grand Theft Auto VI'), nebo 'N/A'"},
                        }
                    }
                }
            }
        }
    }


def _call_structured_api(client, prompt, tools):
    """Volání Claude API se strukturovaným výstupem (tool_use)."""
    return client.messages.create(
        model=config.ANALYSIS_MODEL,
        max_tokens=4000,
        temperature=0.7,
        tools=tools,
        tool_choice={"type": "tool", "name": "submit_analysis"},
        messages=[{"role": "user", "content": prompt}]
    )


if _HAS_TENACITY:
    _call_structured_api = retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=8),
        retry=retry_if_exception_type((
            anthropic.APIConnectionError,
            anthropic.RateLimitError,
            anthropic.InternalServerError,
        )),
        before_sleep=lambda retry_state: log.warning(
            "⚠️  Structured API volání selhalo, pokus %d/3, čekám...", retry_state.attempt_number
        ),
    )(_call_structured_api)


def format_topics_as_report(topics: list) -> str:
    """
    Vygeneruje čitelný report text ze strukturovaných témat.
    Formát je kompatibilní s parse_topics_from_report() pro zpětnou kompatibilitu.
    """
    parts = []
    for i, topic in enumerate(topics, 1):
        sources_text = "\n".join(topic.get("sources", []))
        parts.append(
            f"🎮 TÉMA {i}: {topic['topic']}\n"
            f"📰 NAVRŽENÝ TITULEK: {topic['title']}\n"
            f"🎯 ÚHEL POHLEDU: {topic['angle']}\n"
            f"📝 KONTEXT: {topic['context']}\n"
            f"💬 HLAVNÍ HOOK: {topic['hook']}\n"
            f"🖼️ VIZUÁLNÍ NÁVRH: {topic['visual']}\n"
            f"🔥 VIRALITA: {topic['virality_score']}/100\n"
            f"💡 PROČ TEĎKA: {topic['why_now']}\n"
            f"🔗 ZDROJE:\n{sources_text}\n"
            f"🏷️ SEO KLÍČOVÁ SLOVA: {topic['seo_keywords']}\n"
            f"🕹️ NÁZEV HRY: {topic.get('game_name', 'N/A')}"
        )
    return "\n\n".join(parts)


def analyze_articles_structured(articles_text: str) -> Optional[dict]:
    """
    Analyzuje herní články pomocí Claude s tool_use pro strukturovaný výstup.

    Args:
        articles_text: Naformátované články jako text

    Returns:
        {"text": str, "topics": list[dict]} nebo None při selhání
    """
    log.info("🧠 Analyzuji články pomocí Claude AI (strukturovaný výstup)...")

    client = anthropic.Anthropic(api_key=config.CLAUDE_API_KEY)

    article_count = articles_text.count("ČLÁNEK ")
    max_topics = min(2, max(1, article_count))

    prompt = f"""Analyzuj tyto herní články z dnešního dne a vytvoř report pro českého herního blogera.

ÚKOL:
1. Identifikuj TOP {max_topics} nejvíce relevantních témat pro český herní blog (PŘESNĚ {max_topics})
2. Pro každé téma navrhni konkrétní článek, který by mohl napsat
3. Poskytni dostatek kontextu pro vytvoření grafických bannerů

PRAVIDLA:
- Zaměř se na témata zajímavá pro ČESKÉ publikum
- Preferuj témata, která jsou AKTUÁLNÍ (dnes/tento týden)
- Ignoruj témata starší než 3 dny (pokud nejsou viral)
- Dej přednost news a analýzám před recenzemi
- Pokud jsou tam oznámení nových her, dej jim prioritu
- KONTEXT musí obsahovat konkrétní fakta a čísla, ne obecné fráze
- V sources musíš uvést PLNÉ URL adresy (začínající https://) ze zdrojových článků
- FAKTICKÁ PŘESNOST: NIKDY nepřipisuj hře českou/slovenskou origin, pokud to není faktem
- Počet témat musí být PŘESNĚ {max_topics}
{topic_dedup.format_recent_topics_for_prompt(days=3)}
Použij tool submit_analysis k odeslání výsledků.

ČLÁNKY K ANALÝZE:
{articles_text}"""

    try:
        tool = _build_analysis_tool(max_topics)
        message = _call_structured_api(client, prompt, [tool])

        # Extrahuj tool_use blok
        topics_data = None
        for block in message.content:
            if block.type == "tool_use" and block.name == "submit_analysis":
                topics_data = block.input
                break

        if not topics_data or not topics_data.get("topics"):
            log.warning("⚠️  Strukturovaný výstup neobsahuje témata, fallback na text")
            return None

        # Validace přes Pydantic
        try:
            result = AnalysisResult.model_validate(topics_data)
            topics = [t.model_dump() for t in result.topics]
        except Exception as e:
            log.warning("⚠️  Pydantic validace selhala: %s, používám raw data", e)
            topics = topics_data["topics"]

        # Generuj čitelný report text
        report_text = format_topics_as_report(topics)

        # Statistiky
        log.info("✅ Strukturovaná analýza dokončena (%d témat)", len(topics))
        log.info("   📊 Input tokeny: %d", message.usage.input_tokens)
        log.info("   📊 Output tokeny: %d", message.usage.output_tokens)

        cost_input = (message.usage.input_tokens / 1_000_000) * 3.00
        cost_output = (message.usage.output_tokens / 1_000_000) * 15.00
        total_cost = cost_input + cost_output
        log.info("   💰 Odhadovaná cena: $%.4f", total_cost)

        return {"text": report_text, "topics": topics}

    except Exception as e:
        log.error("❌ Chyba při strukturované analýze: %s", e)
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
