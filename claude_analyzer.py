"""
Claude AI Analyzer
Analyzuje herní články a generuje nápady na obsah
"""

import anthropic
import json
from typing import List, Dict
import config

def analyze_gaming_articles(articles_text: str) -> str:
    """
    Pošle články Claude AI k analýze

    Args:
        articles_text: Naformátované články jako text

    Returns:
        Analýza a nápady od Claude
    """
    print("\n🧠 Analyzuji články pomocí Claude AI...")

    client = anthropic.Anthropic(api_key=config.CLAUDE_API_KEY)

    prompt = f"""Analyzuj tyto herní články z dnešního dne a vytvoř report pro českého herního blogera.

ÚKOL:
1. Identifikuj TOP 5 nejvíce relevantních témat pro český herní blog
2. Pro každé téma navrhni konkrétní článek, který by mohl napsat
3. Uveď důvod, proč je téma zajímavé a aktuální

FORMÁT VÝSTUPU:
Pro každé téma napiš:
- 🎮 TÉMA: [název tématu]
- 📰 NAVRŽENÝ TITULEK: [catchy český titulek článku]
- 🎯 ÚHEL POHLEDU: [jak téma uchopit, jaký angle použít]
- 🔥 VIRALITA: [hodnocení 1-100, jak virální může být]
- 💡 PROČ TEĎKA: [proč je to aktuální, proč to napsat teď]
- 🔗 ZDROJE: [odkazy na relevantní články ze vstupních dat]
- 🏷️ SEO KLÍČOVÁ SLOVA: [3-5 klíčových slov pro SEO]

DŮLEŽITÉ:
- Zaměř se na témata zajímavá pro ČESKÉ publikum
- Preferuj témata, která jsou AKTUÁLNÍ (dnes/tento týden)
- Ignoruj témata starší než 3 dny (pokud nejsou viral)
- Dej přednost news a analýzám před recenzemi
- Pokud jsou tam oznámení nových her, dej jim prioritu

ČLÁNKY K ANALÝZE:
{articles_text}

---

VÝSTUP (seřaď od nejdůležitějšího):"""

    try:
        message = client.messages.create(
            model="claude-3-haiku-20240307",
            max_tokens=3000,
            temperature=0.7,
            messages=[{
                "role": "user",
                "content": prompt
            }]
        )

        result = message.content[0].text

        # Statistiky použití
        print(f"✅ Analýza dokončena")
        print(f"   📊 Input tokeny: {message.usage.input_tokens}")
        print(f"   📊 Output tokeny: {message.usage.output_tokens}")

        # Odhad ceny (Sonnet 3.5 pricing)
        cost_input = (message.usage.input_tokens / 1_000_000) * 3
        cost_output = (message.usage.output_tokens / 1_000_000) * 15
        total_cost = cost_input + cost_output

        print(f"   💰 Odhadovaná cena: ${total_cost:.4f}")

        return result

    except Exception as e:
        print(f"❌ Chyba při volání Claude API: {e}")
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


if __name__ == "__main__":
    # Test analyzeru
    print("🧪 Test Claude Analyzeru")
    print("Poznámka: Toto spotřebuje API tokeny!\n")

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
        print("\n" + "="*60)
        print(result)
