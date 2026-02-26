"""
Social Media Poster — postuje na X.com (Twitter) a Facebook Page.
Volán z auto_publish.py po úspěšné publikaci článku na WordPress.

Twitter: jen CZ (uživatel má jen českou mutaci)
Facebook: CZ stránka (GAMEfo) + EN stránka (GAMEFOen)
Threads: VYPNUTO (účet @gamefo.cz permanentně zabanován Metou 2026-02-25).
         Kód zachován pro případ re-aktivace s novým účtem (config.THREADS_ENABLED).
"""

import os
import config
from logger import setup_logger

log = setup_logger(__name__)


def _build_post_text(title, excerpt, url, hashtags, max_len=None):
    """Sestaví text postu. Pokud je max_len, zkrátí excerpt aby se vešel."""
    hashtag_str = ' '.join(hashtags) if hashtags else ''

    if max_len:
        # Spočítej fixní části
        fixed = f"🎮 {title}\n\n\n\n👉 {url}"
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
    parts.append(f"👉 {url}")
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
        # Zjisti username pro URL
        me = client.get_me()
        username = me.data.username if me.data else 'unknown'
        tweet_url = f"https://x.com/{username}/status/{tweet_id}"

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

    Vrací dict s výsledky.
    """
    results = {}

    # Twitter — jen CZ (max 280 znaků)
    if config.is_twitter_configured() or config.SOCIAL_DRY_RUN:
        try:
            tw_text = _build_post_text(title, excerpt, url, hashtags, max_len=280)
            tw_id, tw_url = post_to_twitter(tw_text, image_path=image_path, url=url)
            results['twitter'] = {'id': tw_id, 'url': tw_url}
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
        except Exception as e:
            log.warning("Threads posting selhalo: %s", e)
            results['threads'] = {'id': None, 'url': str(e)}

    # Facebook CZ
    if config.is_facebook_configured('cs') or config.SOCIAL_DRY_RUN:
        try:
            fb_text = _build_post_text(title, excerpt, url, hashtags)
            fb_id, fb_url = post_to_facebook(fb_text, image_path=image_path, lang='cs')
            results['facebook_cs'] = {'id': fb_id, 'url': fb_url}
        except Exception as e:
            log.warning("Facebook CZ posting selhalo: %s", e)
            results['facebook_cs'] = {'id': None, 'url': str(e)}

    # Facebook EN (pokud máme EN verzi článku)
    if en_title and en_url and (config.is_facebook_configured('en') or config.SOCIAL_DRY_RUN):
        try:
            fb_en_text = _build_post_text(en_title, en_excerpt or '', en_url, hashtags)
            fb_en_id, fb_en_url = post_to_facebook(fb_en_text, image_path=en_image_path, lang='en')
            results['facebook_en'] = {'id': fb_en_id, 'url': fb_en_url}
        except Exception as e:
            log.warning("Facebook EN posting selhalo: %s", e)
            results['facebook_en'] = {'id': None, 'url': str(e)}

    if not results:
        log.info("Žádná sociální síť není nakonfigurována, přeskakuji social posting")

    return results
