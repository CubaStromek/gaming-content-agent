"""
Social Media Poster — postuje na X.com (Twitter) a Facebook Page.
Volán z auto_publish.py po úspěšné publikaci článku na WordPress.

Twitter: jen CZ (uživatel má jen českou mutaci)
Facebook: CZ stránka (GAMEfo) + EN stránka (GAMEFOen)
Threads: VYPNUTO (účet @gamefo.cz permanentně zabanován Metou 2026-02-25).
         Kód zachován pro případ re-aktivace s novým účtem (config.THREADS_ENABLED).
"""

import os
import random
import time
from datetime import datetime

import config
from database import get_db
from logger import setup_logger

log = setup_logger(__name__)


# Časová okna pro rozložení social postů přes den
# Auto-publish běží v 8, 11, 14, 17, 20h — každé okno dostane max 1 social post
SOCIAL_SLOTS = {
    'morning':   (6, 12),   # 6:00–11:59 → run 8:00, 11:00
    'afternoon': (12, 17),  # 12:00–16:59 → run 14:00
    'evening':   (17, 23),  # 17:00–22:59 → run 17:00, 20:00
}


def get_current_slot():
    """Vrátí aktuální časový slot (morning/afternoon/evening) nebo None."""
    hour = datetime.now().hour
    for slot_name, (start, end) in SOCIAL_SLOTS.items():
        if start <= hour < end:
            return slot_name
    return None


def is_slot_used(slot_name):
    """Zkontroluje, jestli už byl daný slot dnes využitý."""
    today = datetime.now().strftime('%Y-%m-%d')
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM social_posts WHERE date = ? AND platform = ? ",
            (today, f'_slot_{slot_name}'),
        ).fetchone()
        return (row[0] if row else 0) > 0
    except Exception:
        return False
    finally:
        conn.close()


def get_today_social_count():
    """Vrátí počet social media postů (slotů) odeslaných dnes."""
    today = datetime.now().strftime('%Y-%m-%d')
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT COUNT(*) FROM social_posts WHERE date = ? AND platform LIKE '_slot_%'", (today,)
        ).fetchone()
        return row[0] if row else 0
    except Exception:
        return 0
    finally:
        conn.close()


def log_social_post(platform, post_id, article_title):
    """Zaznamená odeslaný social post do DB."""
    now = datetime.now()
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO social_posts (date, platform, post_id, article_title, timestamp) VALUES (?, ?, ?, ?, ?)",
            (now.strftime('%Y-%m-%d'), platform, str(post_id) if post_id else None,
             article_title, now.strftime('%Y-%m-%dT%H:%M:%S')),
        )
        conn.commit()
    except Exception as e:
        log.warning("Nepodařilo se zalogovat social post: %s", e)
    finally:
        conn.close()


def can_post_social():
    """Zkontroluje, jestli aktuální časový slot ještě nemá social post.
    Rozloží posty přes den: 1x ráno, 1x odpoledne, 1x večer."""
    slot = get_current_slot()
    if not slot:
        log.info("Mimo social posting okno, přeskakuji")
        return False

    if is_slot_used(slot):
        log.info("Slot '%s' už dnes využitý, přeskakuji social posting", slot)
        return False

    count = get_today_social_count()
    log.info("Social posting: slot '%s' volný (%d/3 dnes)", slot, count)
    return True


def random_delay():
    """Počká náhodnou dobu před social postem (aby to nevypadalo jako bot)."""
    delay = random.randint(config.SOCIAL_DELAY_MIN, config.SOCIAL_DELAY_MAX)
    log.info("Náhodný delay před social postem: %ds", delay)
    time.sleep(delay)


def _build_post_text(title, excerpt, url, hashtags, max_len=None, include_url=True):
    """Sestaví text postu. Pokud je max_len, zkrátí excerpt aby se vešel."""
    hashtag_str = ' '.join(hashtags) if hashtags else ''
    url_line = f"👉 {url}" if (include_url and url) else ''

    if max_len:
        # Spočítej fixní části
        fixed = f"🎮 {title}"
        if url_line:
            fixed += f"\n\n\n\n{url_line}"
        if hashtag_str:
            fixed += f"\n\n{hashtag_str}"
        remaining = max_len - len(fixed)
        if remaining > 20:
            short_excerpt = excerpt[:remaining].rstrip()
            # Ořízni na celé slovo
            if len(excerpt) > remaining:
                last_space = short_excerpt.rfind(' ')
                if last_space > remaining // 2:
                    short_excerpt = short_excerpt[:last_space]
                short_excerpt += '…'
        else:
            short_excerpt = ''
    else:
        short_excerpt = excerpt

    parts = [f"🎮 {title}"]
    if short_excerpt:
        parts.append(short_excerpt)
    if url_line:
        parts.append(url_line)
    if hashtag_str:
        parts.append(hashtag_str)

    return '\n\n'.join(parts)


def post_to_twitter(text, image_path=None, url=None):
    """
    Postne tweet s textem a volitelně obrázkem.
    Vrací (tweet_id, tweet_url) nebo (None, error_message).
    """
    if not config.is_twitter_configured():
        return None, 'Twitter není nakonfigurován'

    if config.SOCIAL_DRY_RUN:
        log.info("[DRY RUN] Twitter post: %s", text[:100])
        return 'dry-run', 'https://x.com/dry-run'

    try:
        import tweepy

        client = tweepy.Client(
            consumer_key=config.TWITTER_API_KEY,
            consumer_secret=config.TWITTER_API_SECRET,
            access_token=config.TWITTER_ACCESS_TOKEN,
            access_token_secret=config.TWITTER_ACCESS_TOKEN_SECRET,
        )

        media_id = None
        if image_path and os.path.exists(image_path):
            # V1.1 API pro upload médií (tweepy v2 Client nemá upload)
            auth = tweepy.OAuth1UserHandler(
                config.TWITTER_API_KEY,
                config.TWITTER_API_SECRET,
                config.TWITTER_ACCESS_TOKEN,
                config.TWITTER_ACCESS_TOKEN_SECRET,
            )
            api_v1 = tweepy.API(auth)
            media = api_v1.media_upload(filename=image_path)
            media_id = media.media_id
            log.info("Twitter media uploaded: %s", media_id)

        response = client.create_tweet(
            text=text,
            media_ids=[media_id] if media_id else None,
        )

        tweet_id = response.data['id']
        tweet_url = f"https://x.com/{config.TWITTER_USERNAME}/status/{tweet_id}"

        log.info("Tweet posted: %s", tweet_url)
        return tweet_id, tweet_url

    except Exception as e:
        log.error("Twitter post selhal: %s", e)
        return None, str(e)


def post_to_facebook(text, image_path=None, lang='cs'):
    """
    Postne na Facebook Page s textem a volitelně obrázkem.
    lang='cs' → GAMEfo stránka, lang='en' → GAMEFOen stránka.
    Vrací (post_id, post_url) nebo (None, error_message).
    """
    if not config.is_facebook_configured(lang):
        return None, f'Facebook ({lang}) není nakonfigurován'

    if lang == 'en':
        page_id = config.FACEBOOK_PAGE_ID_EN
        token = config.FACEBOOK_PAGE_TOKEN_EN
    else:
        page_id = config.FACEBOOK_PAGE_ID_CS
        token = config.FACEBOOK_PAGE_TOKEN_CS

    if config.SOCIAL_DRY_RUN:
        log.info("[DRY RUN] Facebook %s post: %s", lang.upper(), text[:100])
        return 'dry-run', f'https://facebook.com/{page_id}/dry-run'

    import requests

    try:
        if image_path and os.path.exists(image_path):
            endpoint = f"https://graph.facebook.com/v21.0/{page_id}/photos"
            with open(image_path, 'rb') as img:
                resp = requests.post(
                    endpoint,
                    data={'message': text, 'access_token': token},
                    files={'source': img},
                    timeout=30,
                )
        else:
            endpoint = f"https://graph.facebook.com/v21.0/{page_id}/feed"
            resp = requests.post(
                endpoint,
                data={'message': text, 'access_token': token},
                timeout=30,
            )

        if resp.status_code != 200:
            error_data = resp.json() if resp.text else {}
            error_msg = error_data.get('error', {}).get('message', resp.text)
            log.error("Facebook %s API error %d: %s", lang.upper(), resp.status_code, error_msg)
            return None, f"Facebook API {resp.status_code}: {error_msg}"

        data = resp.json()

        post_id = data.get('id') or data.get('post_id', '')
        post_url = f"https://facebook.com/{post_id}" if post_id else ''

        log.info("Facebook %s post published: %s", lang.upper(), post_url)
        return post_id, post_url

    except Exception as e:
        log.error("Facebook %s post selhal: %s", lang.upper(), e)
        return None, str(e)


def post_to_threads(text, image_url=None):
    """
    Postne na Threads přes Meta Graph API (dvoukrokový flow).
    image_url musí být veřejně dostupné URL (ne lokální soubor).
    Vrací (post_id, post_url) nebo (None, error_message).
    """
    if not config.is_threads_configured():
        return None, 'Threads není nakonfigurován'

    if config.SOCIAL_DRY_RUN:
        log.info("[DRY RUN] Threads post: %s", text[:100])
        return 'dry-run', 'https://threads.net/dry-run'

    import time
    import requests

    user_id = config.THREADS_USER_ID
    token = config.THREADS_ACCESS_TOKEN
    base_url = "https://graph.threads.net/v1.0"

    try:
        # Krok 1: Vytvoření media containeru
        container_params = {
            'text': text,
            'access_token': token,
        }
        if image_url:
            container_params['media_type'] = 'IMAGE'
            container_params['image_url'] = image_url
        else:
            container_params['media_type'] = 'TEXT'

        resp = requests.post(
            f"{base_url}/{user_id}/threads",
            data=container_params,
            timeout=30,
        )

        if resp.status_code != 200:
            error_data = resp.json() if resp.text else {}
            error_msg = error_data.get('error', {}).get('message', resp.text)
            log.error("Threads container error %d: %s", resp.status_code, error_msg)
            return None, f"Threads API {resp.status_code}: {error_msg}"

        container_id = resp.json().get('id')
        if not container_id:
            return None, "Threads API nevrátilo container ID"

        log.info("Threads container vytvořen: %s", container_id)

        # Krok 2: Počkat na zpracování médií
        wait_seconds = 30 if image_url else 5
        log.info("Čekám %ds na zpracování Threads containeru...", wait_seconds)
        time.sleep(wait_seconds)

        # Krok 3: Publikace containeru
        publish_resp = requests.post(
            f"{base_url}/{user_id}/threads_publish",
            data={
                'creation_id': container_id,
                'access_token': token,
            },
            timeout=30,
        )

        if publish_resp.status_code != 200:
            error_data = publish_resp.json() if publish_resp.text else {}
            error_msg = error_data.get('error', {}).get('message', publish_resp.text)
            log.error("Threads publish error %d: %s", publish_resp.status_code, error_msg)
            return None, f"Threads publish {publish_resp.status_code}: {error_msg}"

        post_id = publish_resp.json().get('id')
        post_url = f"https://www.threads.net/@gamefo/post/{post_id}" if post_id else ''

        log.info("Threads post published: %s", post_url)
        return post_id, post_url

    except Exception as e:
        log.error("Threads post selhal: %s", e)
        return None, str(e)


def post_to_all(title, excerpt, image_path, url, hashtags=None,
                en_title=None, en_excerpt=None, en_image_path=None, en_url=None,
                image_url=None):
    """
    Orchestrační funkce — postne na všechny nakonfigurované platformy.

    Twitter: jen CZ verze
    Facebook: CZ na GAMEfo, EN na GAMEFOen (pokud jsou k dispozici EN data)

    Denní limit: SOCIAL_DAILY_LIMIT (default 3) — počítá se 1 článek = 1 post
    (i když se postne na víc platforem najednou).
    Náhodný delay před postem: SOCIAL_DELAY_MIN–SOCIAL_DELAY_MAX sekund.

    Vrací dict s výsledky.
    """
    results = {}

    # Kontrola denního limitu
    if not can_post_social():
        results['skipped'] = 'daily_limit_reached'
        return results

    # Náhodný delay (přeskočí v dry-run režimu)
    if not config.SOCIAL_DRY_RUN:
        random_delay()

    # Twitter — jen CZ (max 280 znaků)
    if config.is_twitter_configured() or config.SOCIAL_DRY_RUN:
        try:
            tw_text = _build_post_text(title, excerpt, url, hashtags, max_len=280, include_url=False)
            tw_id, tw_url = post_to_twitter(tw_text, image_path=image_path, url=url)
            results['twitter'] = {'id': tw_id, 'url': tw_url}
            if tw_id:
                log_social_post('twitter', tw_id, title)
        except Exception as e:
            log.warning("Twitter posting selhalo: %s", e)
            results['twitter'] = {'id': None, 'url': str(e)}

    # Threads — jen CZ (max 500 znaků)
    # POZOR: THREADS_ENABLED=false → celý blok se přeskočí (účet zabanován 2026-02-25)
    if config.THREADS_ENABLED and (config.is_threads_configured() or config.SOCIAL_DRY_RUN):
        try:
            th_text = _build_post_text(title, excerpt, url, hashtags, max_len=500)
            th_id, th_url = post_to_threads(th_text, image_url=image_url)
            results['threads'] = {'id': th_id, 'url': th_url}
            if th_id:
                log_social_post('threads', th_id, title)
        except Exception as e:
            log.warning("Threads posting selhalo: %s", e)
            results['threads'] = {'id': None, 'url': str(e)}

    # Facebook CZ
    if config.is_facebook_configured('cs') or config.SOCIAL_DRY_RUN:
        try:
            fb_text = _build_post_text(title, excerpt, url, hashtags)
            fb_id, fb_url = post_to_facebook(fb_text, image_path=image_path, lang='cs')
            results['facebook_cs'] = {'id': fb_id, 'url': fb_url}
            if fb_id:
                log_social_post('facebook_cs', fb_id, title)
        except Exception as e:
            log.warning("Facebook CZ posting selhalo: %s", e)
            results['facebook_cs'] = {'id': None, 'url': str(e)}

    # Facebook EN (pokud máme EN verzi článku)
    if en_title and en_url and (config.is_facebook_configured('en') or config.SOCIAL_DRY_RUN):
        try:
            fb_en_text = _build_post_text(en_title, en_excerpt or '', en_url, hashtags)
            fb_en_id, fb_en_url = post_to_facebook(fb_en_text, image_path=en_image_path, lang='en')
            results['facebook_en'] = {'id': fb_en_id, 'url': fb_en_url}
            if fb_en_id:
                log_social_post('facebook_en', fb_en_id, title)
        except Exception as e:
            log.warning("Facebook EN posting selhalo: %s", e)
            results['facebook_en'] = {'id': None, 'url': str(e)}

    # Zaloguj využití časového slotu (1 článek = 1 slot: ráno/odpoledne/večer)
    if results and 'skipped' not in results:
        slot = get_current_slot()
        if slot:
            log_social_post(f'_slot_{slot}', None, title)

    if not results:
        log.info("Žádná sociální síť není nakonfigurována, přeskakuji social posting")

    return results
