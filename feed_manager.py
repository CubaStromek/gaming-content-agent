"""
Sprava RSS feedu s JSON perzistenci
CRUD operace + seed z config.RSS_FEEDS pri prvnim spusteni
"""

import json
import os
import re
from datetime import datetime

import config
from logger import setup_logger

log = setup_logger(__name__)

FEEDS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "custom_feeds.json")


def _generate_id(name):
    """Vytvori slug ID z nazvu feedu"""
    slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
    return slug or 'feed'


def _ensure_unique_id(feed_id, existing_ids):
    """Zajisti unikatni ID pridanim suffixu"""
    if feed_id not in existing_ids:
        return feed_id
    counter = 2
    while f"{feed_id}-{counter}" in existing_ids:
        counter += 1
    return f"{feed_id}-{counter}"


def load_feeds():
    """Nacte feedy z JSON. Pokud soubor neexistuje, vytvori ho z config.RSS_FEEDS."""
    if os.path.exists(FEEDS_FILE):
        try:
            with open(FEEDS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return data.get("feeds", [])
        except (json.JSONDecodeError, Exception) as e:
            log.error("Chyba pri nacitani feedu: %s", e)

    # Seed z configu
    feeds = []
    used_ids = set()
    for item in config.RSS_FEEDS:
        feed_id = _generate_id(item["name"])
        feed_id = _ensure_unique_id(feed_id, used_ids)
        used_ids.add(feed_id)
        feeds.append({
            "id": feed_id,
            "name": item["name"],
            "url": item["url"],
            "lang": item["lang"],
            "enabled": True,
        })

    save_feeds(feeds)
    return feeds


def save_feeds(feeds):
    """Ulozi feedy do JSON souboru"""
    data = {
        "last_updated": datetime.now().isoformat(),
        "feeds": feeds,
    }
    try:
        with open(FEEDS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        log.error("Chyba pri ukladani feedu: %s", e)
        return False


def get_enabled_feeds():
    """Vrati pouze aktivni feedy ve formatu pro rss_scraper (list of dicts s name/url/lang)"""
    feeds = load_feeds()
    return [
        {"name": f["name"], "url": f["url"], "lang": f["lang"]}
        for f in feeds if f.get("enabled", True)
    ]


def _validate_feed(name, url, lang, feeds=None, exclude_id=None):
    """Validuje feed data. Vraci chybovou hlasku nebo None."""
    if not name or not name.strip():
        return "Name is required"
    if not url or not url.strip():
        return "URL is required"
    if not re.match(r'^https?://', url):
        return "URL must start with http:// or https://"
    if lang not in ("en", "cs"):
        return "Lang must be 'en' or 'cs'"

    # Unikatni URL
    if feeds:
        for f in feeds:
            if f["url"] == url.strip() and f["id"] != exclude_id:
                return "Feed with this URL already exists"

    return None


def add_feed(name, url, lang):
    """Prida novy feed. Vraci (feed, None) nebo (None, error)."""
    feeds = load_feeds()
    error = _validate_feed(name, url, lang, feeds)
    if error:
        return None, error

    existing_ids = {f["id"] for f in feeds}
    feed_id = _generate_id(name.strip())
    feed_id = _ensure_unique_id(feed_id, existing_ids)

    feed = {
        "id": feed_id,
        "name": name.strip(),
        "url": url.strip(),
        "lang": lang,
        "enabled": True,
    }
    feeds.append(feed)
    save_feeds(feeds)
    return feed, None


def update_feed(feed_id, **kwargs):
    """Aktualizuje existujici feed. Vraci (feed, None) nebo (None, error)."""
    feeds = load_feeds()

    target = None
    for f in feeds:
        if f["id"] == feed_id:
            target = f
            break

    if not target:
        return None, "Feed not found"

    name = kwargs.get("name", target["name"])
    url = kwargs.get("url", target["url"])
    lang = kwargs.get("lang", target["lang"])

    error = _validate_feed(name, url, lang, feeds, exclude_id=feed_id)
    if error:
        return None, error

    target["name"] = name.strip()
    target["url"] = url.strip()
    target["lang"] = lang

    if "enabled" in kwargs:
        target["enabled"] = bool(kwargs["enabled"])

    save_feeds(feeds)
    return target, None


def auto_disable_feed(feed_name):
    """Automaticky deaktivuje feed podle jména (volá feed_health)."""
    feeds = load_feeds()
    for f in feeds:
        if f["name"] == feed_name:
            if f.get("enabled", True):
                f["enabled"] = False
                f["auto_disabled"] = True
                save_feeds(feeds)
                log.info("🚫 Feed '%s' automaticky deaktivován (opakovaná selhání)", feed_name)
            return True
    return False


def delete_feed(feed_id):
    """Smaze feed. Vraci True/False."""
    feeds = load_feeds()
    original_len = len(feeds)
    feeds = [f for f in feeds if f["id"] != feed_id]

    if len(feeds) == original_len:
        return False

    save_feeds(feeds)
    return True
