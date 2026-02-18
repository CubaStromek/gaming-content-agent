"""
Auto Publish Pipeline
Automaticky stahne RSS, analyzuje, napise clanky a publikuje na GAMEfo.cz
Spousteno 4x denne pres launchd (8:00, 12:00, 15:00, 20:00)
"""

import os
import sys
import requests
from datetime import datetime

# Zajisti spravny working directory (dulezite pro launchd)
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import config
import rss_scraper
import claude_analyzer
import article_writer
import article_history
import file_manager
import wp_publisher
import publish_log
import youtube_embed
from logger import setup_logger
from fb_generator.generate_fb_post import generate_fb_post

log = setup_logger('auto_publish')


def search_rawg_image(game_name):
    """Vyhleda obrazek hry na RAWG.io. Vraci URL nebo None."""
    if not config.RAWG_API_KEY:
        return None

    try:
        resp = requests.get(
            'https://api.rawg.io/api/games',
            params={'key': config.RAWG_API_KEY, 'search': game_name, 'page_size': 1},
            timeout=10,
        )
        if resp.status_code != 200:
            return None

        results = resp.json().get('results', [])
        if results and results[0].get('background_image'):
            return results[0]['background_image']
    except Exception as e:
        log.warning("RAWG search error for '%s': %s", game_name, e)

    return None


def run():
    """Hlavni pipeline: RSS -> analyza -> clanky -> publish."""
    start_time = datetime.now()
    log.info("=" * 60)
    log.info("AUTO PUBLISH - %s", start_time.strftime('%d.%m.%Y %H:%M'))
    log.info("=" * 60)

    # 1. Validace
    if not config.validate_config():
        log.error("Chybi konfigurace (CLAUDE_API_KEY)")
        return

    if not config.is_wp_configured():
        log.error("WordPress neni nakonfigurovan (WP_URL, WP_USER, WP_APP_PASSWORD)")
        return

    # 2. Vytvoreni output slozky
    run_dir = file_manager.create_run_directory()
    log.info("Output: %s", run_dir)

    # 3. Nacteni historie a stahnuti novych clanku
    history = article_history.load_history()
    processed_urls = article_history.get_processed_urls(history)

    articles = rss_scraper.scrape_all_feeds(skip_urls=processed_urls)
    if not articles:
        log.info("Zadne nove clanky k analyze. Koncim.")
        return

    log.info("Stazeno %d novych clanku", len(articles))

    # 4. Ulozeni clanku
    rss_scraper.save_articles_to_json(articles, run_dir)

    # 5. Claude analyza -> TOP 2 temata
    articles_text = rss_scraper.format_articles_for_analysis(articles)
    analysis = claude_analyzer.analyze_gaming_articles(articles_text)
    if not analysis:
        log.error("Claude analyza selhala")
        return

    file_manager.save_report(analysis, claude_analyzer.extract_key_insights(articles), run_dir, articles)

    # 6. Parsovani temat
    topics = article_writer.parse_topics_from_report(analysis)
    if not topics:
        log.error("Zadna temata k publikaci")
        return

    log.info("Nalezeno %d temat", len(topics))

    # 7. Pro kazde tema: napsat clanek + publikovat
    published_count = 0
    for i, topic in enumerate(topics, 1):
        topic_name = topic.get('topic', 'Neznámé')
        title = topic.get('title', topic_name)
        virality = topic.get('virality_score', 0)

        log.info("-" * 40)
        log.info("TEMA %d/%d: %s (viralita: %d)", i, len(topics), topic_name, virality)

        # Stahnuti zdrojovych clanku
        source_urls = topic.get('sources', [])
        source_texts = []
        for url in source_urls[:3]:  # max 3 zdroje
            text = article_writer.scrape_full_article(url)
            if not text.startswith('[Chyba'):
                source_texts.append(text)

        if not source_texts:
            log.warning("Zadne zdrojove texty pro '%s', preskakuji", topic_name)
            publish_log.log_decision({
                'action': 'skipped',
                'reason': 'no_source_texts',
                'topic': topic_name,
                'score': virality,
            })
            continue

        # Generovani clanku (CZ + EN)
        log.info("Generuji clanek...")
        article = article_writer.write_article(topic, source_texts)
        if 'error' in article:
            log.error("Chyba pri generovani: %s", article['error'])
            publish_log.log_decision({
                'action': 'skipped',
                'reason': 'write_error',
                'topic': topic_name,
                'error': article['error'],
            })
            continue

        # Pouzij opraveny titulek pokud existuje
        if article.get('corrected_title'):
            title = article['corrected_title']
            log.info("Titulek opraven na: %s", title)

        log.info("Clanek vygenerovan (%s)", article.get('cost', '?'))

        # YouTube embed (pokud clanek zminuje video/trailer)
        game_name = topic.get('game_name', '')
        if not game_name or game_name == 'N/A':
            game_name = topic_name
        article['cs'] = youtube_embed.embed_youtube_in_html(article['cs'], game_name, lang='cs')
        if article.get('en'):
            article['en'] = youtube_embed.embed_youtube_in_html(article['en'], game_name, lang='en')

        # Hledani featured image pres RAWG (pouzij cisty nazev hry)
        featured_image_id = None
        image_url = search_rawg_image(game_name)
        if image_url:
            log.info("RAWG image nalezen, uploaduji...")
            media_id, err = wp_publisher.upload_media(image_url, title=title)
            if media_id:
                featured_image_id = media_id
                log.info("Featured image uploaded (ID: %d)", media_id)
            else:
                log.warning("Upload image selhal: %s", err)

        # SEO keywords jako tagy
        seo_keywords = topic.get('seo_keywords', '')
        tag_names = [kw.strip() for kw in seo_keywords.split(',') if kw.strip()] if seo_keywords else None

        # Publikace CZ verze
        log.info("Publikuji CZ verzi...")
        cs_content = wp_publisher.strip_first_heading(article['cs'])
        cs_result, cs_err = wp_publisher.create_draft(
            title=title,
            content=cs_content,
            category_ids=[9],  # Zprávy
            tag_names=tag_names,
            lang='cs',
            featured_image_id=featured_image_id,
            status_tag='news',
            status='publish',
        )

        if cs_err:
            log.error("CZ publish selhal: %s", cs_err)
            publish_log.log_decision({
                'action': 'skipped',
                'reason': 'wp_error_cs',
                'topic': topic_name,
                'error': cs_err,
            })
            continue

        log.info("CZ publikovan: %s", cs_result['view_url'])

        # Publikace EN verze
        en_result = None
        if article.get('en'):
            # Anglicky titulek z article_writer, fallback na topic name
            en_title = article.get('en_title') or topic.get('topic', title)

            log.info("Publikuji EN verzi...")
            en_content = wp_publisher.strip_first_heading(article['en'])
            en_result, en_err = wp_publisher.create_draft(
                title=en_title,
                content=en_content,
                category_ids=[12],  # News
                tag_names=tag_names,
                lang='en',
                featured_image_id=featured_image_id,
                status_tag='news',
                status='publish',
            )

            if en_err:
                log.warning("EN publish selhal: %s", en_err)
            else:
                log.info("EN publikovan: %s", en_result['view_url'])

                # Propojeni CZ <-> EN pres Polylang
                link_ok, link_err = wp_publisher.link_translations(cs_result['id'], en_result['id'])
                if link_ok:
                    log.info("CZ/EN propojeni OK")
                else:
                    log.warning("Propojeni selhalo: %s", link_err)

        # Generovani FB post obrazku
        if image_url:
            try:
                # Stahni thumbnail lokalne
                local_thumb = f"/tmp/fb_thumb_{datetime.now().strftime('%H%M%S')}.jpg"
                thumb_resp = requests.get(image_url, timeout=15)
                with open(local_thumb, 'wb') as f:
                    f.write(thumb_resp.content)

                # Subtitle = CZ titulek clanku
                fb_subtitle = title

                # Nazev souboru z game_name
                safe_name = "".join(c if c.isalnum() or c in '-_ ' else '' for c in game_name).strip().replace(' ', '_')
                date_str = datetime.now().strftime('%Y-%m-%d')
                fb_output = os.path.join(os.path.dirname(__file__), 'output', 'fb-posts', f'{date_str}_{safe_name}.png')

                fb_path = generate_fb_post(
                    thumbnail_path=local_thumb,
                    title=game_name,
                    subtitle=fb_subtitle,
                    output_path=fb_output,
                )
                log.info("FB post obrazek vygenerovan: %s", fb_path)

                # Cleanup temp souboru
                if os.path.exists(local_thumb):
                    os.remove(local_thumb)
            except Exception as e:
                log.warning("FB post generovani selhalo: %s", e)

        # Log
        publish_log.log_decision({
            'action': 'published',
            'topic': topic_name,
            'title': title,
            'score': virality,
            'cs_post_id': cs_result['id'],
            'en_post_id': en_result['id'] if en_result else None,
            'cs_url': cs_result['view_url'],
            'en_url': en_result['view_url'] if en_result else None,
            'sources': source_urls,
            'cost': article.get('cost', '?'),
        })

        published_count += 1

    # 8. Aktualizace historie
    history = article_history.mark_as_processed(articles, history)
    history = article_history.cleanup_old_entries(history)
    article_history.save_history(history)

    # 9. Shrnutí
    elapsed = (datetime.now() - start_time).total_seconds()
    log.info("=" * 60)
    log.info("HOTOVO! Publikovano %d/%d clanku za %.0f sekund", published_count, len(topics), elapsed)
    log.info("=" * 60)


if __name__ == '__main__':
    try:
        run()
    except KeyboardInterrupt:
        log.warning("Preruseno uzivatelem")
        sys.exit(0)
    except Exception as e:
        log.error("Neocekavana chyba: %s", e, exc_info=True)
        sys.exit(1)
