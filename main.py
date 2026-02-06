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
from logger import setup_logger

log = setup_logger(__name__)


def print_banner():
    """Vykreslí banner agenta"""
    log.info("""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║           🎮  GAMING CONTENT AGENT  🤖                    ║
║                                                           ║
║         Automatické objevování herních témat              ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
    """)
    log.info("⏰ Spuštěno: %s", datetime.now().strftime('%d.%m.%Y v %H:%M:%S'))


def main():
    """Hlavní funkce agenta"""

    # Banner
    print_banner()

    # 1. Kontrola konfigurace
    log.info("🔍 Kontroluji konfiguraci...")
    if not config.validate_config():
        log.error("❌ Prosím, uprav soubor .env podle .env.example")
        log.error("   Minimálně nastav CLAUDE_API_KEY")
        sys.exit(1)

    log.info("✅ Konfigurace OK")

    # 1.5. Vytvoření složky pro tento běh
    run_dir = file_manager.create_run_directory()
    log.info("📁 Výstupní složka: %s", run_dir)

    # 2. Načtení historie zpracovaných článků
    log.info("📚 Načítám historii zpracovaných článků...")
    history = article_history.load_history()
    history_stats = article_history.get_stats(history)
    processed_urls = article_history.get_processed_urls(history)
    log.info("   Již zpracováno: %d článků", history_stats['total_processed'])

    # 3. Stahování článků z RSS (přeskakuje již zpracované)
    try:
        articles = rss_scraper.scrape_all_feeds(skip_urls=processed_urls)

        if not articles:
            msg = "Žádné nové články k analýze.\nVšechny články v RSS feedech již byly zpracovány dříve."
            log.info("✅ %s", msg)
            # Uložení info souboru, aby web UI zobrazil smysluplnou zprávu
            info_path = os.path.join(run_dir, 'no_new_articles.txt')
            with open(info_path, 'w', encoding='utf-8') as f:
                f.write(f"{msg}\nDokončeno: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n")
            log.info("⏰ Dokončeno: %s", datetime.now().strftime('%H:%M:%S'))
            sys.exit(0)

        log.info("✅ Nalezeno %d nových článků", len(articles))

        # Uložení článků do JSON a CSV
        rss_scraper.save_articles_to_json(articles, run_dir)
        rss_scraper.save_articles_to_csv(articles, run_dir)

    except Exception as e:
        log.error("❌ Chyba při stahování článků: %s", e)
        sys.exit(1)

    # 4. Příprava dat pro analýzu
    log.info("📝 Připravuji články pro analýzu...")
    articles_text = rss_scraper.format_articles_for_analysis(articles)
    log.info("✅ Připraveno %d článků", len(articles))

    # 5. Analýza pomocí Claude AI
    try:
        analysis = claude_analyzer.analyze_gaming_articles(articles_text)

        if not analysis:
            log.error("❌ Nepodařilo se analyzovat články!")
            sys.exit(1)

    except Exception as e:
        log.error("❌ Chyba při analýze: %s", e)
        sys.exit(1)

    # 6. Extrakce statistik
    stats = claude_analyzer.extract_key_insights(articles)

    # 7. Stručný log analýzy
    log.info("✅ Analýza dokončena. Témata uložena do reportu.")

    # 8. Uložení reportu
    log.info("💾 Ukládám report...")
    file_manager.save_report(analysis, stats, run_dir, articles)

    # 9. Uložení zpracovaných článků do historie
    log.info("💾 Ukládám zpracované články do historie...")
    history = article_history.mark_as_processed(articles, history)
    history = article_history.cleanup_old_entries(history)
    if article_history.save_history(history):
        log.info("✅ Historie aktualizována")

    # 10. Shrnutí
    log.info("=" * 70)
    log.info("✅ HOTOVO!")
    log.info("=" * 70)
    log.info("📊 Analyzováno: %d článků", stats['total_articles'])
    log.info("🌐 Zdroje: %d", len(stats['sources']))
    log.info("⏰ Dokončeno: %s", datetime.now().strftime('%H:%M:%S'))
    log.info("=" * 70)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.warning("⚠️  Agent přerušen uživatelem")
        sys.exit(0)
    except Exception as e:
        log.error("❌ Neočekávaná chyba: %s", e)
        sys.exit(1)
