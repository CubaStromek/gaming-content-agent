"""
RSS Scraper pro herní weby
Stahuje nejnovější články z RSS feedů
"""

import os
import requests
import feedparser
from datetime import datetime
from typing import List, Dict
import json
import csv
import config
import feed_manager
from logger import setup_logger

log = setup_logger(__name__)


def scrape_rss_feed(feed_info: Dict, skip_urls: set = None) -> List[Dict]:
    """
    Stáhne články z jednoho RSS feedu

    Args:
        feed_info: Slovník s 'name', 'url', 'lang'
        skip_urls: Set URL adres k přeskočení (již zpracované)

    Returns:
        Seznam článků
    """
    articles = []
    skipped = 0
    skip_urls = skip_urls or set()

    try:
        log.info("  📡 Stahuji %s...", feed_info['name'])

        # Timeout přes requests, pak parsuj obsah feedparserem
        headers = {'User-Agent': 'Mozilla/5.0 (compatible; GamefoBot/1.0)'}
        resp = requests.get(feed_info['url'], timeout=15, headers=headers)
        feed = feedparser.parse(resp.content)

        # Ošetření chyby při parsování
        if feed.bozo and not feed.entries:
            log.warning("  ⚠️  Chyba při parsování %s: %s", feed_info['name'], feed.bozo_exception)

        # Zpracuj články (max MAX_ARTICLES_PER_SOURCE)
        for entry in feed.entries[:config.MAX_ARTICLES_PER_SOURCE]:
            # Přeskoč již zpracované články
            link = entry.get('link', '')
            if link in skip_urls:
                skipped += 1
                continue

            article = {
                'source': feed_info['name'],
                'language': feed_info['lang'],
                'title': entry.get('title', 'Bez názvu'),
                'link': link,
                'summary': entry.get('summary', ''),
                'published': entry.get('published', '')
            }

            # Zkrácení summary (konfigurovatelný limit)
            if len(article['summary']) > config.SUMMARY_MAX_LENGTH:
                article['summary'] = article['summary'][:config.SUMMARY_MAX_LENGTH] + '...'

            articles.append(article)

        if skipped > 0:
            log.info("  ✅ %s: %d nových (⏭️ %d přeskočeno)", feed_info['name'], len(articles), skipped)
        else:
            log.info("  ✅ %s: %d článků", feed_info['name'], len(articles))

    except Exception as e:
        log.error("  ❌ Chyba při stahování %s: %s", feed_info['name'], e)

    return articles


def scrape_all_feeds(skip_urls: set = None) -> List[Dict]:
    """
    Stáhne články ze všech nakonfigurovaných RSS feedů

    Args:
        skip_urls: Set URL adres k přeskočení (již zpracované)

    Returns:
        Seznam všech článků ze všech zdrojů
    """
    log.info("🌐 Stahuji články z herních webů...")

    all_articles = []

    for feed_info in feed_manager.get_enabled_feeds():
        articles = scrape_rss_feed(feed_info, skip_urls)
        all_articles.extend(articles)

    log.info("✅ Celkem staženo: %d nových článků", len(all_articles))
    return all_articles


def format_articles_for_analysis(articles: List[Dict]) -> str:
    """
    Naformátuje články pro Claude analýzu

    Args:
        articles: Seznam článků

    Returns:
        Textový formát pro AI
    """
    formatted = []

    for i, article in enumerate(articles, 1):
        formatted.append(
            f"ČLÁNEK {i}:\n"
            f"Zdroj: {article['source']} ({article['language']})\n"
            f"Titulek: {article['title']}\n"
            f"Popis: {article['summary']}\n"
            f"Link: {article['link']}\n"
        )

    return "\n".join(formatted)


def save_articles_to_json(articles: List[Dict], run_dir: str = ".") -> str:
    """
    Uloží články do JSON souboru

    Args:
        articles: Seznam článků
        run_dir: Složka, kam uložit (výchozí aktuální složka)

    Returns:
        Cesta k uloženému souboru
    """
    filename = os.path.join(run_dir, "articles.json")

    data = {
        "downloaded_at": datetime.now().isoformat(),
        "total_articles": len(articles),
        "sources": list(set(article['source'] for article in articles)),
        "articles": articles
    }

    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        log.info("💾 Články uloženy do: %s", filename)
        return filename

    except Exception as e:
        log.error("❌ Chyba při ukládání článků: %s", e)
        return None


def save_articles_to_csv(articles: List[Dict], run_dir: str = ".") -> str:
    """
    Uloží články do CSV souboru

    Args:
        articles: Seznam článků
        run_dir: Složka, kam uložit (výchozí aktuální složka)

    Returns:
        Cesta k uloženému souboru
    """
    filename = os.path.join(run_dir, "articles.csv")

    try:
        with open(filename, 'w', encoding='utf-8-sig', newline='') as f:
            # utf-8-sig přidá BOM pro správné zobrazení v Excelu
            writer = csv.writer(f)

            # Hlavička
            writer.writerow(['Zdroj', 'Jazyk', 'Titulek', 'Popis', 'Link', 'Publikováno'])

            # Data
            for article in articles:
                writer.writerow([
                    article['source'],
                    article['language'],
                    article['title'],
                    article['summary'],
                    article['link'],
                    article['published']
                ])

        log.info("📊 Články uloženy do: %s", filename)
        return filename

    except Exception as e:
        log.error("❌ Chyba při ukládání CSV: %s", e)
        return None


if __name__ == "__main__":
    # Test scraperu
    log.info("🧪 Test RSS scraperu")
    articles = scrape_all_feeds()

    if articles:
        log.info("📄 Ukázka prvního článku:")
        log.info("   %s", articles[0]['title'])
        log.info("   Zdroj: %s", articles[0]['source'])
