"""
RSS Scraper pro herní weby
Stahuje nejnovější články z RSS feedů — async interně, sync API zvenku.
"""

import asyncio
import os
from datetime import datetime
from typing import List, Dict
from urllib.parse import urlparse
import json
import csv

import aiohttp
import feedparser

import config
import feed_manager
import feed_health
from logger import setup_logger

log = setup_logger(__name__)


def _get_domain(url: str) -> str:
    """Extrahuje doménu z URL."""
    return urlparse(url).netloc


async def _fetch_feed(
    session: aiohttp.ClientSession,
    feed_info: Dict,
    skip_urls: set,
    global_sem: asyncio.Semaphore,
    domain_sems: dict,
) -> List[Dict]:
    """Async stažení jednoho RSS feedu."""
    domain = _get_domain(feed_info['url'])
    if domain not in domain_sems:
        domain_sems[domain] = asyncio.Semaphore(config.MAX_CONCURRENT_PER_DOMAIN)

    articles = []
    skipped = 0

    async with global_sem:
        async with domain_sems[domain]:
            try:
                log.info("  Stahuji %s...", feed_info['name'])

                async with session.get(
                    feed_info['url'],
                    timeout=aiohttp.ClientTimeout(total=config.FEED_TIMEOUT),
                    headers={'User-Agent': 'Mozilla/5.0 (compatible; GamefoBot/1.0)'},
                ) as resp:
                    content = await resp.read()

                # feedparser.parse() je CPU-bound — spustíme v executoru
                loop = asyncio.get_event_loop()
                feed = await loop.run_in_executor(None, feedparser.parse, content)

                if feed.bozo and not feed.entries:
                    log.warning("  Chyba při parsování %s: %s", feed_info['name'], feed.bozo_exception)
                    exceeded = feed_health.record_failure(feed_info['name'])
                    if exceeded:
                        log.warning("  %s: %d+ po sobě jdoucích selhání -> auto-deaktivace",
                                    feed_info['name'], feed_health.MAX_CONSECUTIVE_FAILURES)
                        feed_manager.auto_disable_feed(feed_info['name'])
                    return articles

                for entry in feed.entries[:config.MAX_ARTICLES_PER_SOURCE]:
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
                        'published': entry.get('published', ''),
                    }

                    if len(article['summary']) > config.SUMMARY_MAX_LENGTH:
                        article['summary'] = article['summary'][:config.SUMMARY_MAX_LENGTH] + '...'

                    articles.append(article)

                feed_health.record_success(feed_info['name'])

                if skipped > 0:
                    log.info("  %s: %d nových (%d přeskočeno)", feed_info['name'], len(articles), skipped)
                else:
                    log.info("  %s: %d článků", feed_info['name'], len(articles))

            except asyncio.TimeoutError:
                log.error("  Timeout při stahování %s (%ds)", feed_info['name'], config.FEED_TIMEOUT)
                exceeded = feed_health.record_failure(feed_info['name'])
                if exceeded:
                    log.warning("  %s: %d+ po sobě jdoucích selhání -> auto-deaktivace",
                                feed_info['name'], feed_health.MAX_CONSECUTIVE_FAILURES)
                    feed_manager.auto_disable_feed(feed_info['name'])
            except Exception as e:
                log.error("  Chyba při stahování %s: %s", feed_info['name'], e)
                exceeded = feed_health.record_failure(feed_info['name'])
                if exceeded:
                    log.warning("  %s: %d+ po sobě jdoucích selhání -> auto-deaktivace",
                                feed_info['name'], feed_health.MAX_CONSECUTIVE_FAILURES)
                    feed_manager.auto_disable_feed(feed_info['name'])

    return articles


async def _scrape_all_feeds_async(skip_urls: set = None) -> List[Dict]:
    """Async stažení všech feedů paralelně."""
    skip_urls = skip_urls or set()
    global_sem = asyncio.Semaphore(config.MAX_CONCURRENT_FEEDS)
    domain_sems = {}

    feeds = feed_manager.get_enabled_feeds()

    async with aiohttp.ClientSession() as session:
        tasks = [
            _fetch_feed(session, feed_info, skip_urls, global_sem, domain_sems)
            for feed_info in feeds
        ]
        results = await asyncio.gather(*tasks)

    all_articles = []
    for articles in results:
        all_articles.extend(articles)

    return all_articles


def scrape_rss_feed(feed_info: Dict, skip_urls: set = None) -> List[Dict]:
    """
    Stáhne články z jednoho RSS feedu (sync wrapper).

    Args:
        feed_info: Slovník s 'name', 'url', 'lang'
        skip_urls: Set URL adres k přeskočení (již zpracované)

    Returns:
        Seznam článků
    """
    skip_urls = skip_urls or set()

    async def _single():
        global_sem = asyncio.Semaphore(1)
        domain_sems = {}
        async with aiohttp.ClientSession() as session:
            return await _fetch_feed(session, feed_info, skip_urls, global_sem, domain_sems)

    return asyncio.run(_single())


def scrape_all_feeds(skip_urls: set = None) -> List[Dict]:
    """
    Stáhne články ze všech nakonfigurovaných RSS feedů (sync API).

    Args:
        skip_urls: Set URL adres k přeskočení (již zpracované)

    Returns:
        Seznam všech článků ze všech zdrojů
    """
    log.info("Stahuji články z herních webů...")

    all_articles = asyncio.run(_scrape_all_feeds_async(skip_urls))

    log.info("Celkem staženo: %d nových článků", len(all_articles))
    return all_articles


def format_articles_for_analysis(articles: List[Dict]) -> str:
    """
    Naformátuje články pro Claude analýzu.

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
    """Uloží články do JSON souboru."""
    filename = os.path.join(run_dir, "articles.json")

    data = {
        "downloaded_at": datetime.now().isoformat(),
        "total_articles": len(articles),
        "sources": list(set(article['source'] for article in articles)),
        "articles": articles,
    }

    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        log.info("Články uloženy do: %s", filename)
        return filename

    except Exception as e:
        log.error("Chyba při ukládání článků: %s", e)
        return None


def save_articles_to_csv(articles: List[Dict], run_dir: str = ".") -> str:
    """Uloží články do CSV souboru."""
    filename = os.path.join(run_dir, "articles.csv")

    try:
        with open(filename, 'w', encoding='utf-8-sig', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['Zdroj', 'Jazyk', 'Titulek', 'Popis', 'Link', 'Publikováno'])

            for article in articles:
                writer.writerow([
                    article['source'],
                    article['language'],
                    article['title'],
                    article['summary'],
                    article['link'],
                    article['published'],
                ])

        log.info("Články uloženy do: %s", filename)
        return filename

    except Exception as e:
        log.error("Chyba při ukládání CSV: %s", e)
        return None


if __name__ == "__main__":
    log.info("Test RSS scraperu")
    articles = scrape_all_feeds()

    if articles:
        log.info("Ukázka prvního článku:")
        log.info("   %s", articles[0]['title'])
        log.info("   Zdroj: %s", articles[0]['source'])
