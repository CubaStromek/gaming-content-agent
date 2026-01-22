"""
Gaming Content Agent - Hlavní skript
Automaticky analyzuje herní weby a navrhuje témata článků
"""

import sys
import io
from datetime import datetime

# Fix pro Windows konzoli - UTF-8 encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

import config
import rss_scraper
import claude_analyzer
import email_sender

def print_banner():
    """Vykreslí banner agenta"""
    print("""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║           🎮  GAMING CONTENT AGENT  🤖                    ║
║                                                           ║
║         Automatické objevování herních témat              ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
    """)
    print(f"⏰ Spuštěno: {datetime.now().strftime('%d.%m.%Y v %H:%M:%S')}\n")


def main():
    """Hlavní funkce agenta"""

    # Banner
    print_banner()

    # 1. Kontrola konfigurace
    print("🔍 Kontroluji konfiguraci...")
    if not config.validate_config():
        print("\n❌ Prosím, uprav soubor .env podle .env.example")
        print("   Minimálně nastav CLAUDE_API_KEY a EMAIL_TO\n")
        sys.exit(1)

    print("✅ Konfigurace OK\n")

    # 2. Stahování článků z RSS
    try:
        articles = rss_scraper.scrape_all_feeds()

        if not articles:
            print("\n❌ Nepodařilo se stáhnout žádné články!")
            print("   Zkontroluj internetové připojení a RSS feedy v config.py\n")
            sys.exit(1)

        # Uložení článků do JSON a CSV
        print()
        rss_scraper.save_articles_to_json(articles)
        rss_scraper.save_articles_to_csv(articles)

    except Exception as e:
        print(f"\n❌ Chyba při stahování článků: {e}\n")
        sys.exit(1)

    # 3. Příprava dat pro analýzu
    print("\n📝 Připravuji články pro analýzu...")
    articles_text = rss_scraper.format_articles_for_analysis(articles)
    print(f"✅ Připraveno {len(articles)} článků\n")

    # 4. Analýza pomocí Claude AI
    try:
        analysis = claude_analyzer.analyze_gaming_articles(articles_text)

        if not analysis:
            print("\n❌ Nepodařilo se analyzovat články!")
            sys.exit(1)

    except Exception as e:
        print(f"\n❌ Chyba při analýze: {e}\n")
        sys.exit(1)

    # 5. Extrakce statistik
    stats = claude_analyzer.extract_key_insights(articles)

    # 6. Odeslání reportu
    try:
        email_sent = email_sender.send_email_report(analysis, stats)

        # Pokud email selhal, ulož do souboru
        if not email_sent:
            print("\nℹ️  Ukládám report do souboru...")
            email_sender.save_report_to_file(analysis, stats)

    except Exception as e:
        print(f"\n⚠️  Chyba při odesílání reportu: {e}")
        print("   Ukládám report do souboru...\n")
        email_sender.save_report_to_file(analysis, stats)

    # 7. Shrnutí
    print("\n" + "="*70)
    print("✅ HOTOVO!")
    print("="*70)
    print(f"📊 Analyzováno: {stats['total_articles']} článků")
    print(f"🌐 Zdroje: {len(stats['sources'])}")
    print(f"⏰ Dokončeno: {datetime.now().strftime('%H:%M:%S')}")
    print("="*70 + "\n")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  Agent přerušen uživatelem")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Neočekávaná chyba: {e}")
        sys.exit(1)
