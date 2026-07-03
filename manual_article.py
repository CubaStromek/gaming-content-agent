#!/usr/bin/env python3
"""
Manual Article Publisher — CLI skript pro ruční zadání tématu.
Přeskočí RSS/analýzu a rovnou generuje + publikuje článek na GAMEfo.cz.

Použití:
    python manual_article.py --topic "Gothic remake" --sources "url1,url2,url3"
    python manual_article.py --topic "Gothic remake" --game-name "Gothic" --sources "url1,url2" --seo-keywords "gothic,remake,rpg"

Voláno z Telegram bota přes Claude Code CLI:
    /task napiš článek na GAMEfo o Gothic remake
"""

import argparse
import os
import sys
from datetime import datetime

# Zajisti správný working directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import config
import article_writer
import publish_pipeline
from logger import setup_logger

log = setup_logger('manual_article')


def publish_manual_article(topic_name, game_name, source_urls, title=None,
                           seo_keywords=None, status_tag='news', length='long'):
    """
    Generuje a publikuje článek na základě ručně zadaného tématu.

    Args:
        topic_name: Popis tématu (např. "Gothic remake - vše co víme")
        game_name: Název hry pro RAWG, SEO, obrázky
        source_urls: Seznam URL zdrojových článků
        title: Volitelný CZ titulek (jinak vygeneruje Claude)
        seo_keywords: Volitelný seznam SEO klíčových slov
        status_tag: Status tag pro WP (default 'news')

    Returns:
        dict s výsledky nebo None při chybě
    """
    start_time = datetime.now()
    log.info("=" * 60)
    log.info("MANUAL ARTICLE — %s", start_time.strftime('%d.%m.%Y %H:%M'))
    log.info("Téma: %s", topic_name)
    log.info("Hra: %s", game_name)
    log.info("Zdroje: %d URL", len(source_urls))
    log.info("=" * 60)

    # Validace
    if not config.validate_config():
        log.error("Chybí konfigurace (CLAUDE_API_KEY)")
        return None

    if not config.is_wp_configured():
        log.error("WordPress není nakonfigurován")
        return None

    if not source_urls:
        log.error("Žádné zdrojové URL")
        return None

    # 1. Stažení zdrojových článků (+ filtrování nefunkčních URL)
    log.info("Stahuji zdrojové články...")
    source_texts = []
    valid_source_urls = []
    for url in source_urls[:5]:  # max 5 zdrojů
        text = article_writer.scrape_full_article(url)
        if not text.startswith('[Chyba'):
            source_texts.append(text)
            valid_source_urls.append(url)
            log.info("  OK: %s (%d znaků)", url[:80], len(text))
        else:
            log.warning("  FAIL (nebude v zdrojích): %s — %s", url[:80], text)
    source_urls = valid_source_urls

    if not source_texts:
        log.error("Žádné zdrojové texty se nepodařilo stáhnout")
        return None

    log.info("Staženo %d/%d zdrojů", len(source_texts), len(source_urls))

    # 2. Sestavení topic dict (kompatibilní s article_writer.write_article)
    topic = {
        'topic': topic_name,
        'title': title or topic_name,
        'angle': '',
        'context': '',
        'seo_keywords': ', '.join(seo_keywords) if seo_keywords else '',
        'sources': source_urls,
        'game_name': game_name,
        'status_tag': status_tag,
        'virality_score': 0,
    }

    # 3. Generování článku (CZ + EN)
    log.info("Generuji článek přes Claude AI (délka: %s)...", length)
    article = article_writer.write_article(topic, source_texts, length=length)
    if 'error' in article:
        log.error("Generování selhalo: %s", article['error'])
        return None

    # Použij opravený titulek pokud existuje
    if article.get('corrected_title'):
        title = article['corrected_title']
        log.info("Titulek z Claude: %s", title)
    elif not title:
        title = topic_name

    log.info("Článek vygenerován (%s)", article.get('cost', '?'))

    # 4. Sdílená publish pipeline: YouTube embed, featured image, WP CZ+EN,
    # FB obrázky, social media, publish_log (stejný kód jako auto_publish)
    result, publish_err = publish_pipeline.publish_article(
        topic=topic,
        article=article,
        title=title,
        source='manual',
        source_urls=source_urls,
    )

    if publish_err:
        log.error("CZ publish selhal: %s", publish_err)
        return None

    cs_result = result['cs_result']
    en_result = result['en_result']
    en_title = result['en_title']
    social_results = result['social_results']

    # 5. Výstup
    elapsed = (datetime.now() - start_time).total_seconds()
    log.info("=" * 60)
    log.info("HOTOVO za %.0f sekund", elapsed)
    log.info("CZ: %s", cs_result['view_url'])
    if en_result:
        log.info("EN: %s", en_result['view_url'])
    log.info("=" * 60)

    # Lidsky čitelný výstup pro Claude Code CLI / Telegram
    print(f"\n{'='*50}")
    print(f"ČLÁNEK PUBLIKOVÁN NA GAMEfo.cz")
    print(f"{'='*50}")
    print(f"Titulek: {title}")
    print(f"CZ: {cs_result['view_url']}")
    if en_result:
        print(f"EN: {en_result['view_url']}")
    if social_results:
        for platform, data in social_results.items():
            if isinstance(data, dict):
                status = data.get('url', 'N/A')
            else:
                status = str(data)
            print(f"{platform}: {status}")
    print(f"Náklady: {article.get('cost', '?')}")
    print(f"Čas: {elapsed:.0f}s")
    print(f"{'='*50}")

    return {
        'cs_url': cs_result['view_url'],
        'cs_id': cs_result['id'],
        'en_url': en_result['view_url'] if en_result else None,
        'en_id': en_result['id'] if en_result else None,
        'title': title,
        'cost': article.get('cost', '?'),
        'social': social_results,
        'elapsed': f"{elapsed:.0f}s",
    }


def main():
    parser = argparse.ArgumentParser(
        description='Ruční publikace článku na GAMEfo.cz',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Příklady:
  python manual_article.py --topic "Gothic remake" --sources "url1,url2"
  python manual_article.py --topic "GTA 6 odloženo" --game-name "GTA 6" --sources "url1,url2" --status-tag critical
  python manual_article.py --topic "Indie hit Balatro" --game-name "Balatro" --sources "url1" --seo-keywords "balatro,indie,roguelike" --status-tag indie
        """,
    )
    parser.add_argument('--topic', required=True, help='Popis tématu článku')
    parser.add_argument('--game-name', default=None, help='Název hry (default: stejný jako topic)')
    parser.add_argument('--title', default=None, help='Vlastní CZ titulek (jinak vygeneruje Claude)')
    parser.add_argument('--sources', required=True, help='Zdrojové URL oddělené čárkou')
    parser.add_argument('--seo-keywords', default=None, help='SEO klíčová slova oddělená čárkou')
    parser.add_argument('--status-tag', default='news', help='Status tag: news, update, leak, critical, success, indie, review, trailer, rumor, info, finance, tema, preview')
    parser.add_argument('--length', default='long', choices=['short', 'medium', 'long'], help='Délka článku: short (800-1500), medium (2000-3500), long (5000-8000 znaků, default)')

    args = parser.parse_args()

    game_name = args.game_name or args.topic
    source_urls = [u.strip() for u in args.sources.split(',') if u.strip()]
    seo_keywords = [k.strip() for k in args.seo_keywords.split(',') if k.strip()] if args.seo_keywords else None

    # Sdílený lock s auto_publish — ruční publikace (z Telegramu) nesmí běžet
    # souběžně se scheduled slotem (social sloty, WP media dedup). Na rozdíl
    # od launchd slotu ČEKÁ (max 15 min), místo aby skončila.
    with publish_pipeline.publish_lock(wait=True):
        result = publish_manual_article(
            topic_name=args.topic,
            game_name=game_name,
            source_urls=source_urls,
            title=args.title,
            seo_keywords=seo_keywords,
            status_tag=args.status_tag,
            length=args.length,
        )

    sys.exit(0 if result else 1)


if __name__ == '__main__':
    main()
