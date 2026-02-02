"""
Gaming Content Agent - Hlavní skript
Automaticky analyzuje herní weby a navrhuje témata článků
"""

import os
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
import file_manager
import article_history

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
        print("   Minimálně nastav CLAUDE_API_KEY\n")
        sys.exit(1)

    print("✅ Konfigurace OK\n")

    # 1.5. Vytvoření složky pro tento běh
    run_dir = file_manager.create_run_directory()
    print(f"📁 Výstupní složka: {run_dir}\n")

    # 2. Načtení historie zpracovaných článků
    print("📚 Načítám historii zpracovaných článků...")
    history = article_history.load_history()
    history_stats = article_history.get_stats(history)
    processed_urls = article_history.get_processed_urls(history)
    print(f"   Již zpracováno: {history_stats['total_processed']} článků\n")

    # 3. Stahování článků z RSS (přeskakuje již zpracované)
    try:
        articles = rss_scraper.scrape_all_feeds(skip_urls=processed_urls)

        if not articles:
            msg = "Žádné nové články k analýze.\nVšechny články v RSS feedech již byly zpracovány dříve."
            print(f"\n✅ {msg}")
            # Uložení info souboru, aby web UI zobrazil smysluplnou zprávu
            info_path = os.path.join(run_dir, 'no_new_articles.txt')
            with open(info_path, 'w', encoding='utf-8') as f:
                f.write(f"{msg}\nDokončeno: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n")
            print(f"⏰ Dokončeno: {datetime.now().strftime('%H:%M:%S')}\n")
            sys.exit(0)

        print(f"✅ Nalezeno {len(articles)} nových článků\n")

        # Uložení článků do JSON a CSV
        rss_scraper.save_articles_to_json(articles, run_dir)
        rss_scraper.save_articles_to_csv(articles, run_dir)

    except Exception as e:
        print(f"\n❌ Chyba při stahování článků: {e}\n")
        sys.exit(1)

    # 4. Příprava dat pro analýzu
    print("\n📝 Připravuji články pro analýzu...")
    articles_text = rss_scraper.format_articles_for_analysis(articles)
    print(f"✅ Připraveno {len(articles)} článků\n")

    # 5. Analýza pomocí Claude AI
    try:
        analysis = claude_analyzer.analyze_gaming_articles(articles_text)

        if not analysis:
            print("\n❌ Nepodařilo se analyzovat články!")
            sys.exit(1)

    except Exception as e:
        print(f"\n❌ Chyba při analýze: {e}\n")
        sys.exit(1)

    # 6. Extrakce statistik
    stats = claude_analyzer.extract_key_insights(articles)

    # 7. Stručný log analýzy
    print("\n✅ Analýza dokončena. Témata uložena do reportu.")

    # 8. Uložení reportu
    print("\n💾 Ukládám report...")
    file_manager.save_report(analysis, stats, run_dir, articles)

    # 9. Uložení zpracovaných článků do historie
    print("\n💾 Ukládám zpracované články do historie...")
    history = article_history.mark_as_processed(articles, history)
    history = article_history.cleanup_old_entries(history)
    if article_history.save_history(history):
        print("✅ Historie aktualizována")

    # 10. Shrnutí
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
