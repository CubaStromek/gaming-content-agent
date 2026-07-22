"""Sdílená publish pipeline pro auto_publish.py a manual_article.py.

Vše po vygenerování článku (article_writer.write_article) až po publish_log:
YouTube embed, featured image (brand-first → RAWG → brand fallback), focus
keyword, publikace CZ+EN na WP, FB post obrázky, social media, publish_log.

Vzniklo extrakcí duplicitního kódu z auto_publish.py a manual_article.py —
oba skripty měly ~300 řádků zkopírovaných 1:1 a už divergovaly (mj. dva
nezávislé `image_url` unbound bugy u brand témat).
"""

import contextlib
import fcntl
import json
import os
import re
import sys
import tempfile
import time
from datetime import datetime

import requests

import config
import wp_publisher
import youtube_embed
import section_images
import social_poster
import brand_logos
import internal_linking
import publish_log
from article_postprocess import sanitize_article_html
from models import VALID_STATUS_TAGS, SUBCATEGORY_IDS
from logger import setup_logger
from fb_generator.generate_fb_post import generate_fb_post

log = setup_logger(__name__)

_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_LOCK_PATH = os.path.join(_BASE_DIR, 'data', '.publish.lock')

CATEGORY_IDS = {'cs': [9], 'en': [12]}  # Zprávy / News


@contextlib.contextmanager
def publish_lock(wait=False, wait_timeout=900, poll_interval=10):
    """Exclusivní fcntl lock proti souběhu publish procesů.

    wait=False (launchd slot): pokud lock drží jiný proces, exit 0 + log —
    překrývající se sloty se nesmí hromadit.
    wait=True (manuální/Telegram publikace): čeká až wait_timeout sekund,
    aby ruční článek nekolidoval se scheduled během (social sloty, WP dedup).
    """
    os.makedirs(os.path.dirname(_LOCK_PATH), exist_ok=True)
    # 'a' místo 'w' — nechceme truncatovat PID držícího procesu ještě před flock
    fp = open(_LOCK_PATH, 'a')
    try:
        deadline = time.monotonic() + wait_timeout
        while True:
            try:
                fcntl.flock(fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if not wait:
                    log.info("Publish lock drží jiný proces, končím (exit 0)")
                    fp.close()
                    sys.exit(0)
                if time.monotonic() >= deadline:
                    log.error("Publish lock drží jiný proces déle než %ds, vzdávám to", wait_timeout)
                    fp.close()
                    sys.exit(1)
                log.info("Publish lock drží jiný proces, čekám...")
                time.sleep(poll_interval)
        fp.truncate(0)
        fp.write(f"{os.getpid()}\n")
        fp.flush()
        yield
    finally:
        try:
            fcntl.flock(fp.fileno(), fcntl.LOCK_UN)
        except Exception:
            pass
        fp.close()


def search_rawg_image(game_name):
    """Vyhledá obrázek hry na RAWG.io. Vrací URL nebo None."""
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


def extract_excerpt(html_content, max_len=200):
    """Vyextrahuje první odstavec z HTML a ořízne na max délku."""
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html_content, 'html.parser')
    for p in soup.find_all('p'):
        text = p.get_text(strip=True)
        if len(text) > 30:  # přeskoč krátké úvodní řádky
            if len(text) > max_len:
                truncated = text[:max_len]
                last_space = truncated.rfind(' ')
                if last_space > max_len // 2:
                    truncated = truncated[:last_space]
                return truncated + '…'
            return text
    return ''


def normalize_status_tag(raw_tag):
    """Validace status tagu proti VALID_STATUS_TAGS, fallback 'news'."""
    tag = (raw_tag or 'news').lower().strip()
    return tag if tag in VALID_STATUS_TAGS else 'news'


def resolve_game_name(topic):
    """Název hry pro RAWG/SEO/social: game_name z tématu, fallback na topic."""
    raw = topic.get('game_name', '')
    topic_name = topic.get('topic', 'Neznámé')
    return raw if (raw and raw != 'N/A') else topic_name


def embed_youtube(article, game_name):
    """Vloží YouTube embed do CZ i EN verze (in-place na dict `article`).

    Video se hledá JEDNOU a stejné ID se vkládá do obou verzí — dřívější kód
    hledal až 3× (2 yt-dlp subprocesy navíc) a CZ/EN mohly dostat různá videa.
    """
    cs_has_video = youtube_embed.has_video_reference(article['cs'], lang='cs')
    en_has_video = bool(article.get('en')) and youtube_embed.has_video_reference(article['en'], lang='en')

    if not (cs_has_video or en_has_video):
        log.info("Žádná zmínka o videu v článku, přeskakuji YouTube embed")
        return article

    query = f"{game_name} official trailer 2026"
    log.info("Hledám YouTube video: %s", query)
    videos = youtube_embed.search_youtube(query)
    if not videos:
        log.warning("YouTube video nenalezeno pro: %s", query)
        return article

    video = videos[0]
    log.info("Nalezeno video: %s (%s)", video['title'], video['url'])
    article['cs'] = youtube_embed.force_embed_youtube(article['cs'], video['id'], lang='cs')
    if article.get('en'):
        article['en'] = youtube_embed.force_embed_youtube(article['en'], video['id'], lang='en')
    return article


def resolve_featured_image(game_name, title, topic=None):
    """Featured image: brand-first → RAWG upload → brand logo fallback.

    Vrací (featured_image_id, section_images_meta, image_url).
    `image_url` je VŽDY definované (None pokud se RAWG nepoužil) — původní
    kód ho přiřazoval jen v RAWG větvi, takže brand téma buď spadlo na
    UnboundLocalError, nebo použilo obrázek předchozího tématu ve smyčce.
    """
    featured_image_id = brand_logos.resolve_brand_logo_strict(game_name)
    section_images_meta = None
    image_url = None

    if featured_image_id:
        log.info("Brand tema '%s' → brand logo (ID: %d), RAWG preskocen",
                 game_name, featured_image_id)
        return featured_image_id, section_images_meta, image_url

    # Bez reálné hry (analyzer vrátil game_name = N/A) je game_name jen fallback
    # na téma — celá česká věta. RAWG je databáze her a na takový dotaz VŽDY
    # vrátí nesmyslnou hru (viz "Petice za záchranu disků" → náhodný screenshot),
    # a brand fallback pod RAWG se pak nikdy nespustí. Když tedy žádná hra není,
    # zkus nejdřív brand logo z titulku/tématu/SEO a RAWG přeskoč.
    raw_game = (topic or {}).get('game_name', '')
    has_real_game = bool(raw_game) and raw_game != 'N/A'
    if not has_real_game:
        seo = (topic or {}).get('seo_keywords', '')
        brand_id = brand_logos.resolve_brand_logo(title, game_name, seo)
        if brand_id:
            log.info("Bez reálné hry, brand match v titulku/tématu → brand logo "
                     "(ID: %d), RAWG preskocen", brand_id)
            return brand_id, section_images_meta, image_url

    # RAWG screenshoty → WP meta pro Story Mode v appce (ne inline v HTML)
    section_images_meta = section_images.get_or_fetch_screenshots(game_name)

    image_url = search_rawg_image(game_name)
    if image_url:
        log.info("RAWG image nalezen, uploaduji...")
        media_id, _, err = wp_publisher.upload_media(image_url, title=title)
        if media_id:
            featured_image_id = media_id
            log.info("Featured image uploaded (ID: %d)", media_id)
        else:
            log.warning("Upload image selhal: %s", err)

    if not featured_image_id:
        brand_logo_id = brand_logos.resolve_brand_logo(game_name, title)
        if brand_logo_id:
            featured_image_id = brand_logo_id
            log.info("RAWG nenasel image, pouzivam brand logo (ID: %d)", brand_logo_id)

    return featured_image_id, section_images_meta, image_url


def resolve_focus_keyword(ai_keyword, game_name, title, lang='cs'):
    """Rank Math focus keyword: AI návrh (max 2 slova), fallback game_name.

    Fallback keyword musí být obsažen v titulku (přesná shoda zvedá score).
    """
    focus_kw = ai_keyword
    if focus_kw and len(focus_kw.split()) > 2:
        log.info("AI vrátilo dlouhý %s keyword '%s' (%d slov) → fallback na game_name",
                 lang.upper(), focus_kw, len(focus_kw.split()))
        focus_kw = None
    if focus_kw:
        log.info("%s focus keyword (AI): '%s'", lang.upper(), focus_kw)
        return focus_kw

    focus_kw = game_name if game_name and game_name != 'N/A' else None
    if focus_kw:
        focus_kw = re.sub(r'\s+(\d+|[IVXLCDM]+)$', '', focus_kw).strip()
        if not title or focus_kw.lower() not in title.lower():
            log.info("%s fallback focus keyword '%s' není v titulku, přeskakuji",
                     lang.upper(), focus_kw)
            focus_kw = None
        else:
            log.info("%s focus keyword (fallback game_name): '%s'", lang.upper(), focus_kw)
    return focus_kw


def _fb_image_paths(game_name):
    """Cesty k FB post obrázkům (CZ, EN) pro dané téma a dnešní datum."""
    safe_name = "".join(c if c.isalnum() or c in '-_ ' else '' for c in game_name).strip().replace(' ', '_')
    date_str = datetime.now().strftime('%Y-%m-%d')
    base = os.path.join(_BASE_DIR, 'output', 'fb-posts')
    return (
        os.path.join(base, f'{date_str}_{safe_name}_CZ.png'),
        os.path.join(base, f'{date_str}_{safe_name}_EN.png'),
    )


def generate_fb_images(image_url, game_name, topic_name, title, en_title, has_en):
    """Vygeneruje FB post obrázky (CZ + EN). Vrací (path_cs, path_en) — None při selhání."""
    if not image_url:
        return None, None

    fb_output_cs, fb_output_en = _fb_image_paths(game_name)
    path_cs = None
    path_en = None
    local_thumb = None
    try:
        thumb_resp = requests.get(image_url, timeout=15)
        if thumb_resp.status_code != 200:
            log.warning("Thumbnail download HTTP %d, FB obrázky přeskakuji", thumb_resp.status_code)
            return None, None
        with tempfile.NamedTemporaryFile(suffix='.jpg', prefix='fb_thumb_', delete=False) as tmp:
            tmp.write(thumb_resp.content)
            local_thumb = tmp.name

        path_cs = generate_fb_post(
            thumbnail_path=local_thumb,
            title=game_name,
            subtitle=title,
            output_path=fb_output_cs,
        )
        log.info("FB post obrazek CZ vygenerovan: %s", path_cs)

        if has_en and en_title:
            # EN obrázek: game_name jen pokud je to reálný (anglický) název hry,
            # ne fallback na (český) topic a ne 'N/A'
            en_fb_title = game_name if (game_name and game_name != 'N/A' and game_name != topic_name) else ''
            path_en = generate_fb_post(
                thumbnail_path=local_thumb,
                title=en_fb_title,
                subtitle=en_title,
                output_path=fb_output_en,
            )
            log.info("FB post obrazek EN vygenerovan: %s", path_en)
    except Exception:
        log.exception("FB post generovani selhalo")
    finally:
        if local_thumb and os.path.exists(local_thumb):
            try:
                os.remove(local_thumb)
            except OSError:
                log.warning("Nepodařilo se smazat temp thumbnail: %s", local_thumb)

    return path_cs, path_en


def publish_article(topic, article, title, run_id=None, source='auto',
                    source_urls=None, extra_log=None):
    """Publikuje vygenerovaný článek: WP (CZ+EN), FB obrázky, social, publish_log.

    Args:
        topic: dict tématu (topic, game_name, seo_keywords, status_tag, ...)
        article: výstup article_writer.write_article (cs, en, meta, story cards)
        title: finální CZ titulek (volající už aplikoval corrected_title)
        run_id: ID běhu pro publish_log (auto pipeline)
        source: 'auto' | 'manual' — do publish_log
        source_urls: seznam zdrojových URL pro WP meta pole
        extra_log: dict polí navíc do publish_log záznamu (score, failed_sources...)

    Returns:
        (result_dict, None) při úspěchu (aspoň CZ publikován),
        (None, error_string) při selhání.
    """
    topic_name = topic.get('topic', 'Neznámé')
    game_name = resolve_game_name(topic)
    source_urls = source_urls if source_urls is not None else topic.get('sources', [])

    # Sanitizace LLM výstupu PŘED přidáním vlastního markupu (YouTube embed,
    # interní odkazy) — obrana proti prompt-injection ze scrapnutých zdrojů.
    article['cs'] = sanitize_article_html(article['cs'])
    if article.get('en'):
        article['en'] = sanitize_article_html(article['en'])

    # YouTube embed (jedno hledání pro obě verze)
    article = embed_youtube(article, game_name)

    # Featured image + Story Mode screenshoty
    featured_image_id, section_images_meta, image_url = resolve_featured_image(game_name, title, topic)

    # SEO keywords jako tagy
    seo_keywords = topic.get('seo_keywords', '')
    tag_names = [kw.strip() for kw in seo_keywords.split(',') if kw.strip()] if seo_keywords else None

    status_tag = normalize_status_tag(topic.get('status_tag'))
    log.info("Status tag: '%s'", status_tag)

    # Rubriky: vždy Zprávy/News + volitelná podrubrika. Klasifikuje LLM při
    # psaní článku (article['subcategory']), ruční publikace může přebít
    # přes topic['subcategory'] (manual_article --category).
    subcategory = topic.get('subcategory') or article.get('subcategory')
    cs_category_ids = list(CATEGORY_IDS['cs'])
    en_category_ids = list(CATEGORY_IDS['en'])
    if subcategory:
        sub_ids = SUBCATEGORY_IDS.get(subcategory)
        if sub_ids:
            cs_category_ids.append(sub_ids['cs'])
            if sub_ids['en']:
                en_category_ids.append(sub_ids['en'])
            log.info("Podrubrika: '%s' (cs=%d, en=%s)",
                     subcategory, sub_ids['cs'], sub_ids['en'])
        else:
            log.warning("Neznámá podrubrika '%s' — publikuji jen do Zpráv", subcategory)
            subcategory = None

    source_info = '\n'.join(source_urls) if source_urls else None
    focus_kw = resolve_focus_keyword(article.get('focus_keyword_cs'), game_name, title, lang='cs')

    story_cards_cs_json = json.dumps(article['story_cards_cs'], ensure_ascii=False) if article.get('story_cards_cs') else None
    story_cards_en_json = json.dumps(article['story_cards_en'], ensure_ascii=False) if article.get('story_cards_en') else None

    # --- Publikace CZ ---
    log.info("Publikuji CZ verzi...")
    cs_content = wp_publisher.strip_first_heading(article['cs'])
    if tag_names:
        cs_content = internal_linking.enrich_with_internal_links(cs_content, tag_names, lang='cs')

    cs_result, cs_err = wp_publisher.create_draft(
        title=title,
        content=cs_content,
        category_ids=cs_category_ids,
        tag_names=tag_names,
        lang='cs',
        featured_image_id=featured_image_id,
        status_tag=status_tag,
        source_info=source_info,
        status='publish',
        focus_keyword=focus_kw,
        section_images=section_images_meta,
        meta_description=article.get('meta_description_cs'),
        story_cards=story_cards_cs_json,
    )

    if cs_err:
        return None, cs_err

    log.info("CZ publikovan: %s", cs_result['view_url'])

    # --- Publikace EN ---
    en_result = None
    en_title = None
    if article.get('en'):
        en_title = article.get('en_title')
        if not en_title:
            en_title = topic.get('topic', title)
            log.warning("EN titulek chybí v article_writer výstupu, fallback: %s", en_title)

        log.info("Publikuji EN verzi...")
        en_content = wp_publisher.strip_first_heading(article['en'])
        if tag_names:
            en_content = internal_linking.enrich_with_internal_links(en_content, tag_names, lang='en')
        en_focus_kw = resolve_focus_keyword(article.get('focus_keyword_en'), game_name, en_title, lang='en')

        en_result, en_err = wp_publisher.create_draft(
            title=en_title,
            content=en_content,
            category_ids=en_category_ids,
            tag_names=tag_names,
            lang='en',
            featured_image_id=featured_image_id,
            status_tag=status_tag,
            source_info=source_info,
            status='publish',
            focus_keyword=en_focus_kw,
            section_images=section_images_meta,
            meta_description=article.get('meta_description_en'),
            story_cards=story_cards_en_json,
        )

        if en_err:
            log.warning("EN publish selhal: %s", en_err)
        else:
            log.info("EN publikovan: %s", en_result['view_url'])
            link_ok, link_err = wp_publisher.link_translations(cs_result['id'], en_result['id'])
            if link_ok:
                log.info("CZ/EN propojeni OK")
            else:
                log.warning("Propojeni selhalo: %s", link_err)

    # --- FB post obrázky ---
    social_image_cs, social_image_en = generate_fb_images(
        image_url, game_name, topic_name, title, en_title, has_en=bool(article.get('en')),
    )

    # --- Social media ---
    social_results = {}
    try:
        excerpt = extract_excerpt(article.get('cs', ''), max_len=200)
        hashtags = [f"#{kw.strip().replace(' ', '')}" for kw in seo_keywords.split(',') if kw.strip()]
        hashtags.append("#GAMEfo")

        en_excerpt_social = extract_excerpt(article.get('en', ''), max_len=200) if en_result else None
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
    except Exception:
        log.exception("Social posting selhalo")

    # --- Publish log ---
    log_entry = {
        'action': 'published',
        'topic': topic_name,
        'title': title,
        'score': topic.get('virality_score', 0),
        'status_tag': status_tag,
        'subcategory': subcategory,
        'game_name': game_name,
        'cs_post_id': cs_result['id'],
        'en_post_id': en_result['id'] if en_result else None,
        'cs_url': cs_result['view_url'],
        'en_url': en_result['view_url'] if en_result else None,
        'sources': source_urls,
        'cost': article.get('cost', '?'),
        'social': social_results,
    }
    if run_id:
        log_entry['run_id'] = run_id
    if source != 'auto':
        log_entry['source'] = source
    if extra_log:
        log_entry.update(extra_log)
    publish_log.log_decision(log_entry)

    return {
        'cs_result': cs_result,
        'en_result': en_result,
        'title': title,
        'en_title': en_title,
        'social_results': social_results,
    }, None
