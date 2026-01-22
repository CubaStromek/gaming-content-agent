"""
RSS Scraper pro herní weby
Stahuje nejnovější články z RSS feedů
"""

import feedparser
from datetime import datetime
from typing import List, Dict
import json
import csv
import config

def scrape_rss_feed(feed_info: Dict) -> List[Dict]:
    """
    Stáhne články z jednoho RSS feedu

    Args:
        feed_info: Slovník s 'name', 'url', 'lang'

    Returns:
        Seznam článků
    """
    articles = []

    try:
        print(f"  📡 Stahuji {feed_info['name']}...")
        feed = feedparser.parse(feed_info['url'])

        # Ošetření chyby při parsování
        if feed.bozo:
            print(f"  ⚠️  Varování při parsování {feed_info['name']}")

        # Zpracuj články (max MAX_ARTICLES_PER_SOURCE)
        for entry in feed.entries[:config.MAX_ARTICLES_PER_SOURCE]:
            article = {
                'source': feed_info['name'],
                'language': feed_info['lang'],
                'title': entry.title if hasattr(entry, 'title') else 'Bez názvu',
                'link': entry.link if hasattr(entry, 'link') else '',
                'summary': entry.summary if hasattr(entry, 'summary') else '',
                'published': entry.published if hasattr(entry, 'published') else ''
            }

            # Zkrácení summary (max 300 znaků pro analýzu)
            if len(article['summary']) > 300:
                article['summary'] = article['summary'][:300] + '...'

            articles.append(article)

        print(f"  ✅ {feed_info['name']}: {len(articles)} článků")

    except Exception as e:
        print(f"  ❌ Chyba při stahování {feed_info['name']}: {e}")

    return articles


def scrape_all_feeds() -> List[Dict]:
    """
    Stáhne články ze všech nakonfigurovaných RSS feedů

    Returns:
        Seznam všech článků ze všech zdrojů
    """
    print("🌐 Stahuji články z herních webů...\n")

    all_articles = []

    for feed_info in config.RSS_FEEDS:
        articles = scrape_rss_feed(feed_info)
        all_articles.extend(articles)

    print(f"\n✅ Celkem staženo: {len(all_articles)} článků")
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
    import os
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

        print(f"💾 Články uloženy do: {filename}")
        return filename

    except Exception as e:
        print(f"❌ Chyba při ukládání článků: {e}")
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
    import os
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

        print(f"📊 Články uloženy do: {filename}")
        return filename

    except Exception as e:
        print(f"❌ Chyba při ukládání CSV: {e}")
        return None


if __name__ == "__main__":
    # Test scraperu
    print("🧪 Test RSS scraperu\n")
    articles = scrape_all_feeds()

    if articles:
        print("\n📄 Ukázka prvního článku:")
        print(f"   {articles[0]['title']}")
        print(f"   Zdroj: {articles[0]['source']}")
