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
import re
import sys
from datetime import datetime

# Zajisti správný working directory
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import config
import article_writer
import wp_publisher
import social_poster
import youtube_embed
import section_images
import publish_log
import internal_linking
from logger import setup_logger
from auto_publish import search_rawg_image, _extract_excerpt
from fb_generator.generate_fb_post import generate_fb_post

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

    en_title = article.get('en_title')
    log.info("Článek vygenerován (%s)", article.get('cost', '?'))

    # 4. YouTube embed
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
            if cs_has_video:
                article['cs'] = youtube_embed.embed_youtube_in_html(article['cs'], game_name, lang='cs')
            else:
                article['cs'] = youtube_embed.force_embed_youtube(article['cs'], video_id, lang='cs')
            if article.get('en'):
                if en_has_video:
                    article['en'] = youtube_embed.embed_youtube_in_html(article['en'], game_name, lang='en')
                else:
                    article['en'] = youtube_embed.force_embed_youtube(article['en'], video_id, lang='en')

    # 5. RAWG screenshoty → WP meta pro Story Mode v appce (ne inline v HTML)
    # Nejdřív hledá existující ve WP, fallback na RAWG API + upload
    section_images_meta = section_images.get_or_fetch_screenshots(game_name)

    # 6. Featured image (RAWG)
    featured_image_id = None
    image_url = search_rawg_image(game_name)
    if image_url:
        log.info("RAWG image nalezen, uploaduji...")
        media_id, _, err = wp_publisher.upload_media(image_url, title=title)
        if media_id:
            featured_image_id = media_id
            log.info("Featured image uploaded (ID: %d)", media_id)
        else:
            log.warning("Upload image selhal: %s", err)

    # 7. SEO keywords jako tagy
    tag_names = list(seo_keywords) if seo_keywords else None

    # Validace status_tag
    valid_status_tags = {'news', 'update', 'leak', 'critical', 'success', 'indie', 'review', 'trailer', 'rumor', 'info', 'finance', 'tema', 'preview'}
    status_tag = status_tag.lower().strip() if status_tag else 'news'
    if status_tag not in valid_status_tags:
        status_tag = 'news'
    log.info("Status tag: '%s'", status_tag)

    # Rank Math focus keyword — priorita: AI-generované → game_name fallback
    focus_kw = article.get('focus_keyword_cs')
    if focus_kw:
        log.info("Focus keyword (AI): '%s'", focus_kw)
    else:
        focus_kw = game_name if game_name else None
        if focus_kw:
            focus_kw = re.sub(r'\s+(\d+|[IVXLCDM]+)$', '', focus_kw).strip()
            if focus_kw.lower() not in title.lower():
                log.info("Fallback focus keyword '%s' není v CZ titulku, přeskakuji", focus_kw)
                focus_kw = None
            else:
                log.info("Focus keyword (fallback game_name): '%s'", focus_kw)

    source_info = '\n'.join(source_urls)

    # 8. Publikace CZ
    log.info("Publikuji CZ verzi...")
    cs_content = wp_publisher.strip_first_heading(article['cs'])
    if tag_names:
        cs_content = internal_linking.enrich_with_internal_links(cs_content, tag_names, lang='cs')
    cs_result, cs_err = wp_publisher.create_draft(
        title=title,
        content=cs_content,
        category_ids=[9],  # Zprávy
        tag_names=tag_names,
        lang='cs',
        featured_image_id=featured_image_id,
        status_tag=status_tag,
        source_info=source_info,
        status='publish',
        focus_keyword=focus_kw,
        section_images=section_images_meta,
        meta_description=article.get('meta_description_cs'),
    )

    if cs_err:
        log.error("CZ publish selhal: %s", cs_err)
        return None

    log.info("CZ publikován: %s", cs_result['view_url'])

    # 9. Publikace EN
    en_result = None
    if article.get('en'):
        if not en_title:
            en_title = topic_name

        en_focus_kw = article.get('focus_keyword_en')
        if en_focus_kw:
            log.info("EN focus keyword (AI): '%s'", en_focus_kw)
        else:
            en_focus_kw = game_name if game_name else None
            if en_focus_kw:
                en_focus_kw = re.sub(r'\s+(\d+|[IVXLCDM]+)$', '', en_focus_kw).strip()
            if en_focus_kw and en_title and en_focus_kw.lower() not in en_title.lower():
                en_focus_kw = None

        log.info("Publikuji EN verzi...")
        en_content = wp_publisher.strip_first_heading(article['en'])
        if tag_names:
            en_content = internal_linking.enrich_with_internal_links(en_content, tag_names, lang='en')
        en_result, en_err = wp_publisher.create_draft(
            title=en_title,
            content=en_content,
            category_ids=[12],  # News
            tag_names=tag_names,
            lang='en',
            featured_image_id=featured_image_id,
            status_tag=status_tag,
            source_info=source_info,
            status='publish',
            focus_keyword=en_focus_kw,
            section_images=section_images_meta,
            meta_description=article.get('meta_description_en'),
        )

        if en_err:
            log.warning("EN publish selhal: %s", en_err)
        else:
            log.info("EN publikován: %s", en_result['view_url'])
            link_ok, link_err = wp_publisher.link_translations(cs_result['id'], en_result['id'])
            if link_ok:
                log.info("CZ/EN propojení OK")
            else:
                log.warning("Propojení selhalo: %s", link_err)

    # 10. FB post obrázky
    import requests as req
    if image_url:
        try:
            local_thumb = f"/tmp/fb_thumb_{datetime.now().strftime('%H%M%S')}.jpg"
            thumb_resp = req.get(image_url, timeout=15)
            with open(local_thumb, 'wb') as f:
                f.write(thumb_resp.content)

            safe_name = "".join(c if c.isalnum() or c in '-_ ' else '' for c in game_name).strip().replace(' ', '_')
            date_str = datetime.now().strftime('%Y-%m-%d')

            fb_output_cs = os.path.join(os.path.dirname(__file__), 'output', 'fb-posts', f'{date_str}_{safe_name}_CZ.png')
            generate_fb_post(
                thumbnail_path=local_thumb,
                title=game_name,
                subtitle=title,
                output_path=fb_output_cs,
            )
            log.info("FB post obrázek CZ vygenerován")

            if article.get('en') and en_title:
                fb_output_en = os.path.join(os.path.dirname(__file__), 'output', 'fb-posts', f'{date_str}_{safe_name}_EN.png')
                # Pro EN obrázek: game_name je anglický název hry (z --game-name),
                # ale pokud fallbacknul na topic (český), použij jen en_title
                en_fb_title = game_name if game_name != topic_name else ''
                generate_fb_post(
                    thumbnail_path=local_thumb,
                    title=en_fb_title,
                    subtitle=en_title,
                    output_path=fb_output_en,
                )
                log.info("FB post obrázek EN vygenerován")

            if os.path.exists(local_thumb):
                os.remove(local_thumb)
        except Exception as e:
            log.warning("FB post generování selhalo: %s", e)

    # 11. Social media posting
    social_results = {}
    try:
        excerpt = _extract_excerpt(article.get('cs', ''), max_len=200)
        hashtags = []
        if seo_keywords:
            hashtags = [f"#{kw.strip().replace(' ', '')}" for kw in seo_keywords]
        hashtags.append("#GAMEfo")

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

        en_excerpt_social = _extract_excerpt(article.get('en', ''), max_len=200) if en_result else None
        en_url_social = en_result['view_url'] if en_result else None

        social_results = social_poster.post_to_all(
            title=title,
            excerpt=excerpt,
            image_path=social_image_cs,
            url=cs_result['view_url'],
            hashtags=hashtags[:5],
            en_title=en_title if en_result else None,
            en_excerpt=en_excerpt_social,
            en_image_path=social_image_en,
            en_url=en_url_social,
            image_url=image_url,
        )
        log.info("Social posting: %s", social_results)
    except Exception as e:
        log.warning("Social posting selhalo: %s", e)

    # 12. Publish log
    publish_log.log_decision({
        'action': 'published',
        'source': 'manual',
        'topic': topic_name,
        'title': title,
        'score': 0,
        'cs_post_id': cs_result['id'],
        'en_post_id': en_result['id'] if en_result else None,
        'cs_url': cs_result['view_url'],
        'en_url': en_result['view_url'] if en_result else None,
        'sources': source_urls,
        'cost': article.get('cost', '?'),
        'social': social_results,
    })

    # 13. Výstup
    elapsed = (datetime.now() - start_time).total_seconds()
    log.info("=" * 60)
    log.info("HOTOVO za %.0f sekund", elapsed)
    log.info("CZ: %s", cs_result['view_url'])
    if en_result:
        log.info("EN: %s", en_result['view_url'])
    log.info("=" * 60)

    result = {
        'cs_url': cs_result['view_url'],
        'cs_id': cs_result['id'],
        'en_url': en_result['view_url'] if en_result else None,
        'en_id': en_result['id'] if en_result else None,
        'title': title,
        'cost': article.get('cost', '?'),
        'social': social_results,
        'elapsed': f"{elapsed:.0f}s",
    }

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

    return result


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
