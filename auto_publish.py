"""
Auto Publish Pipeline
Automaticky stahne RSS, analyzuje, napise clanky a publikuje na GAMEfo.cz
Spousteno 4x denne pres launchd (8:00, 12:00, 15:00, 20:00)
"""

import os
import re
import sys
import time
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
import social_poster
import topic_dedup
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


def _extract_excerpt(html_content, max_len=200):
    """Vyextrahuje první odstavec z HTML a ořízne na max délku."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    # Najdi první <p> s textem
    for p in soup.find_all('p'):
        text = p.get_text(strip=True)
        if len(text) > 30:  # přeskoč krátké úvodní řádky
            if len(text) > max_len:
                # Ořízni na celé slovo
                truncated = text[:max_len]
                last_space = truncated.rfind(' ')
                if last_space > max_len // 2:
                    truncated = truncated[:last_space]
                return truncated + '…'
            return text
    return ''


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

    # 5. Claude analyza -> TOP 2 temata (strukturovaný výstup s fallbackem)
    #    Retry: pokud API vrátí 529 (Overloaded), čekáme 30 min a zkusíme znovu (max 3 pokusy)
    articles_text = rss_scraper.format_articles_for_analysis(articles)

    MAX_ANALYSIS_RETRIES = 3
    RETRY_WAIT_MINUTES = 30
    analysis = None
    topics = None

    for attempt in range(1, MAX_ANALYSIS_RETRIES + 1):
        structured = claude_analyzer.analyze_articles_structured(articles_text)
        if structured:
            analysis = structured["text"]
            topics = structured["topics"]
            log.info("Strukturovaná analýza: %d témat", len(topics))
            break

        log.info("Fallback na textovou analýzu + regex parsování")
        analysis = claude_analyzer.analyze_gaming_articles(articles_text)
        if analysis:
            topics = article_writer.parse_topics_from_report(analysis)
            break

        # Obě metody selhaly — retry pokud nejsme na posledním pokusu
        if attempt < MAX_ANALYSIS_RETRIES:
            log.warning("⏳ Claude API nedostupná (pokus %d/%d). Čekám %d minut před dalším pokusem...",
                        attempt, MAX_ANALYSIS_RETRIES, RETRY_WAIT_MINUTES)
            time.sleep(RETRY_WAIT_MINUTES * 60)
        else:
            log.error("❌ Claude analýza selhala po %d pokusech. Končím.", MAX_ANALYSIS_RETRIES)
            return

    file_manager.save_report(analysis, claude_analyzer.extract_key_insights(articles), run_dir, articles)

    if not topics:
        log.error("Zadna temata k publikaci")
        return

    log.info("Nalezeno %d temat", len(topics))

    # 6. Deduplikace témat (kontrola proti publish_log)
    topics, dup_topics = topic_dedup.filter_duplicate_topics(topics)
    for dup in dup_topics:
        publish_log.log_decision({
            'action': 'skipped',
            'reason': 'duplicate_topic',
            'topic': dup.get('topic', ''),
            'score': dup.get('virality_score', 0),
        })

    if not topics:
        log.info("Všechna témata jsou duplicitní. Končím.")
        return

    log.info("Po deduplikaci: %d témat k publikaci", len(topics))

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

        # YouTube embed (pokud kterakoliv verze zminuje video/trailer)
        # Video se hleda jednou a vlozi do obou verzi — CZ ctenari umi anglicky
        game_name = topic.get('game_name', '')
        if not game_name or game_name == 'N/A':
            game_name = topic_name

        cs_has_video = youtube_embed.has_video_reference(article['cs'], lang='cs')
        en_has_video = article.get('en') and youtube_embed.has_video_reference(article['en'], lang='en')

        if cs_has_video or en_has_video:
            query = f"{game_name} official trailer 2026"
            log.info("Hledám YouTube video: %s", query)
            videos = youtube_embed.search_youtube(query)
            if videos:
                video = videos[0]
                log.info("Nalezeno video: %s (%s)", video['title'], video['url'])
                video_id = video['id']
                # Vloz do CS — bud normalne (ma keyword) nebo force (EN trigger)
                if cs_has_video:
                    article['cs'] = youtube_embed.embed_youtube_in_html(article['cs'], game_name, lang='cs')
                else:
                    log.info("CS článek nemá video keyword, vkládám embed z EN detekce")
                    article['cs'] = youtube_embed.force_embed_youtube(article['cs'], video_id, lang='cs')
                # Vloz do EN
                if article.get('en'):
                    if en_has_video:
                        article['en'] = youtube_embed.embed_youtube_in_html(article['en'], game_name, lang='en')
                    else:
                        log.info("EN článek nemá video keyword, vkládám embed z CS detekce")
                        article['en'] = youtube_embed.force_embed_youtube(article['en'], video_id, lang='en')
            else:
                log.warning("YouTube video nenalezeno pro: %s", query)
        else:
            log.info("Žádná zmínka o videu v článku, přeskakuji YouTube embed")

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

        # Informace o zdroji pro WP meta pole
        source_info = '\n'.join(source_urls) if source_urls else None

        # Rank Math focus keyword = název hry/firmy bez číslovky, pokud je v titulku
        focus_kw = game_name if game_name and game_name != 'N/A' else None
        if focus_kw:
            # Odstraň koncovou číslovku (arabskou i římskou): "The Elder Scrolls VI" → "The Elder Scrolls"
            focus_kw = re.sub(r'\s+(\d+|[IVXLCDM]+)$', '', focus_kw).strip()
            # Kontrola: keyword musí být v titulku (case-insensitive)
            if focus_kw.lower() not in title.lower():
                log.info("Focus keyword '%s' není v CZ titulku, přeskakuji", focus_kw)
                focus_kw = None
            else:
                log.info("Focus keyword: '%s'", focus_kw)

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
            source_info=source_info,
            status='publish',
            focus_keyword=focus_kw,
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
            # Focus keyword pro EN — bez číslovky, zkontroluj v EN titulku
            en_focus_kw = game_name if game_name and game_name != 'N/A' else None
            if en_focus_kw:
                en_focus_kw = re.sub(r'\s+(\d+|[IVXLCDM]+)$', '', en_focus_kw).strip()
            if en_focus_kw and en_focus_kw.lower() not in en_title.lower():
                log.info("Focus keyword '%s' není v EN titulku, přeskakuji", en_focus_kw)
                en_focus_kw = None
            en_result, en_err = wp_publisher.create_draft(
                title=en_title,
                content=en_content,
                category_ids=[12],  # News
                tag_names=tag_names,
                lang='en',
                featured_image_id=featured_image_id,
                status_tag='news',
                source_info=source_info,
                status='publish',
                focus_keyword=en_focus_kw,
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

        # Generovani FB post obrazku (CZ + EN)
        if image_url:
            try:
                # Stahni thumbnail lokalne
                local_thumb = f"/tmp/fb_thumb_{datetime.now().strftime('%H%M%S')}.jpg"
                thumb_resp = requests.get(image_url, timeout=15)
                with open(local_thumb, 'wb') as f:
                    f.write(thumb_resp.content)

                safe_name = "".join(c if c.isalnum() or c in '-_ ' else '' for c in game_name).strip().replace(' ', '_')
                date_str = datetime.now().strftime('%Y-%m-%d')

                # CZ verze
                fb_output_cs = os.path.join(os.path.dirname(__file__), 'output', 'fb-posts', f'{date_str}_{safe_name}_CZ.png')
                fb_path_cs = generate_fb_post(
                    thumbnail_path=local_thumb,
                    title=game_name,
                    subtitle=title,
                    output_path=fb_output_cs,
                )
                log.info("FB post obrazek CZ vygenerovan: %s", fb_path_cs)

                # EN verze (pokud existuje anglicky clanek)
                if article.get('en'):
                    en_subtitle = article.get('en_title') or topic.get('topic', title)
                    fb_output_en = os.path.join(os.path.dirname(__file__), 'output', 'fb-posts', f'{date_str}_{safe_name}_EN.png')
                    fb_path_en = generate_fb_post(
                        thumbnail_path=local_thumb,
                        title=game_name,
                        subtitle=en_subtitle,
                        output_path=fb_output_en,
                    )
                    log.info("FB post obrazek EN vygenerovan: %s", fb_path_en)

                # Cleanup temp souboru
                if os.path.exists(local_thumb):
                    os.remove(local_thumb)
            except Exception as e:
                log.warning("FB post generovani selhalo: %s", e)

        # Social media posting
        social_results = {}
        try:
            excerpt = _extract_excerpt(article.get('cs', ''), max_len=200)
            hashtags = [f"#{tag.strip().replace(' ', '')}" for tag in topic.get('seo_keywords', '').split(',') if tag.strip()]
            hashtags.append("#GAMEfo")

            # CZ FB obrázek
            safe_name = "".join(c if c.isalnum() or c in '-_ ' else '' for c in game_name).strip().replace(' ', '_')
            date_str = datetime.now().strftime('%Y-%m-%d')
            social_image_cs = None
            social_image_en = None
            if image_url:
                candidate_cs = os.path.join(os.path.dirname(__file__), 'output', 'fb-posts', f'{date_str}_{safe_name}_CZ.png')
                if os.path.exists(candidate_cs):
                    social_image_cs = candidate_cs
                candidate_en = os.path.join(os.path.dirname(__file__), 'output', 'fb-posts', f'{date_str}_{safe_name}_EN.png')
                if os.path.exists(candidate_en):
                    social_image_en = candidate_en

            # EN data pro Facebook EN stránku
            en_title_social = article.get('en_title') or topic.get('topic') if en_result else None
            en_excerpt = _extract_excerpt(article.get('en', ''), max_len=200) if en_result else None
            en_url_social = en_result['view_url'] if en_result else None

            social_results = social_poster.post_to_all(
                title=title,
                excerpt=excerpt,
                image_path=social_image_cs,
                url=cs_result['view_url'],
                hashtags=hashtags[:5],
                en_title=en_title_social,
                en_excerpt=en_excerpt,
                en_image_path=social_image_en,
                en_url=en_url_social,
            )
            log.info("Social posting: %s", social_results)
        except Exception as e:
            log.warning("Social posting selhalo: %s", e)

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
            'social': social_results,
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
