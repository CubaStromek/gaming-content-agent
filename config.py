"""
Konfigurace pro Gaming Content Agent
Načítá nastavení z .env souboru
"""

import os
from dotenv import load_dotenv
from logger import setup_logger

log = setup_logger(__name__)

# Načti .env soubor
load_dotenv()

# Claude API
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "")

# Email konfigurace
EMAIL_TO = os.getenv("EMAIL_TO", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "content-agent@gaming.cz")

# SMTP nastavení
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

# WordPress publishing
WP_URL = os.getenv("WP_URL", "")
WP_USER = os.getenv("WP_USER", "")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD", "")

# RAWG.io API (herní databáze - obrázky)
RAWG_API_KEY = os.getenv("RAWG_API_KEY", "")

# X.com (Twitter) API
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY", "")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET", "")

# Facebook Page API (CZ + EN stránky)
FACEBOOK_PAGE_ID_CS = os.getenv("FACEBOOK_PAGE_ID_CS", "")
FACEBOOK_PAGE_TOKEN_CS = os.getenv("FACEBOOK_PAGE_TOKEN_CS", "")
FACEBOOK_PAGE_ID_EN = os.getenv("FACEBOOK_PAGE_ID_EN", "")
FACEBOOK_PAGE_TOKEN_EN = os.getenv("FACEBOOK_PAGE_TOKEN_EN", "")

# Social media dry-run (loguje, ale nepostuje)
SOCIAL_DRY_RUN = os.getenv("SOCIAL_DRY_RUN", "").lower() in ("1", "true", "yes")

def is_wp_configured():
    return bool(WP_URL and WP_USER and WP_APP_PASSWORD)

def is_twitter_configured():
    return bool(TWITTER_API_KEY and TWITTER_API_SECRET and TWITTER_ACCESS_TOKEN and TWITTER_ACCESS_TOKEN_SECRET)

def is_facebook_configured(lang='cs'):
    if lang == 'en':
        return bool(FACEBOOK_PAGE_ID_EN and FACEBOOK_PAGE_TOKEN_EN)
    return bool(FACEBOOK_PAGE_ID_CS and FACEBOOK_PAGE_TOKEN_CS)

# SQLite databáze
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'gamefo.db')

# Nastavení agenta
MAX_ARTICLES_PER_SOURCE = int(os.getenv("MAX_ARTICLES_PER_SOURCE", "10"))
MIN_VIRALITY_SCORE = int(os.getenv("MIN_VIRALITY_SCORE", "50"))

# Model pro generování článků
ARTICLE_MODEL = "claude-sonnet-4-20250514"

# Model pro analýzu (přepisovatelný přes .env)
ANALYSIS_MODEL = os.getenv("ANALYSIS_MODEL", "claude-sonnet-4-20250514")

# Maximální délka summary při scrapování RSS (znaky)
SUMMARY_MAX_LENGTH = int(os.getenv("SUMMARY_MAX_LENGTH", "500"))

# Async RSS scraping
FEED_TIMEOUT = int(os.getenv("FEED_TIMEOUT", "15"))
MAX_CONCURRENT_FEEDS = int(os.getenv("MAX_CONCURRENT_FEEDS", "8"))
MAX_CONCURRENT_PER_DOMAIN = int(os.getenv("MAX_CONCURRENT_PER_DOMAIN", "2"))

# Dashboard autentizace (volitelný bearer token, POVINNÝ v produkci)
DASHBOARD_TOKEN = os.getenv("DASHBOARD_TOKEN", "")

# Produkční režim — vyžaduje DASHBOARD_TOKEN a zpřísňuje bezpečnost
PRODUCTION_MODE = os.getenv("PRODUCTION_MODE", "").lower() in ("1", "true", "yes")

# RSS Feedy herních webů
RSS_FEEDS = [
    # Mezinárodní weby
    {"name": "IGN", "url": "https://feeds.ign.com/ign/all", "lang": "en"},
    {"name": "GameSpot", "url": "https://www.gamespot.com/feeds/news/", "lang": "en"},
    {"name": "PC Gamer", "url": "https://www.pcgamer.com/rss/", "lang": "en"},
    {"name": "Rock Paper Shotgun", "url": "https://www.rockpapershotgun.com/feed", "lang": "en"},
    {"name": "Kotaku", "url": "https://kotaku.com/rss", "lang": "en"},
    {"name": "Polygon", "url": "https://www.polygon.com/rss/index.xml", "lang": "en"},
    {"name": "GamesRadar", "url": "https://www.gamesradar.com/rss/", "lang": "en"},
    {"name": "Pure Xbox", "url": "https://www.purexbox.com/feeds/latest", "lang": "en"},
    {"name": "TheGamer", "url": "https://www.thegamer.com/feed/", "lang": "en"},
    {"name": "VG247", "url": "https://www.vg247.com/feed", "lang": "en"},
    # {"name": "VideoGamer", "url": "https://www.videogamer.com/rss", "lang": "en"},  # broken XML
    {"name": "Game Developer", "url": "https://www.gamedeveloper.com/rss.xml", "lang": "en"},

    # Oficiální zdroje (platformy)
    {"name": "PlayStation Blog", "url": "https://blog.playstation.com/feed/", "lang": "en"},
    {"name": "Xbox Wire", "url": "https://news.xbox.com/en-us/feed/", "lang": "en"},
    {"name": "Steam News", "url": "https://store.steampowered.com/feeds/news.xml", "lang": "en"},

    # České a slovenské weby
    {"name": "Hrej.cz", "url": "https://hrej.cz/rss/all", "lang": "cs"},
    {"name": "Zing.cz", "url": "https://zing.cz/rss/clanky", "lang": "cs"},
    {"name": "Jiří Bigas", "url": "https://jiribigas.substack.com/feed", "lang": "cs"},
    {"name": "Games.cz", "url": "https://games.tiscali.cz/rss.xml", "lang": "cs"},
    {"name": "HernýWeb.sk", "url": "https://hernyweb.sk/feed/", "lang": "cs"},
    {"name": "Vortex.cz", "url": "https://www.vortex.cz/feed/", "lang": "cs"},
    {"name": "PLAYzone.cz", "url": "https://playzone.cz/rss.xml", "lang": "cs"},
]

def validate_config():
    """Zkontroluje, že všechny důležité proměnné jsou nastavené"""
    errors = []

    if not CLAUDE_API_KEY or CLAUDE_API_KEY == "sk-ant-api03-your-api-key-here":
        errors.append("CLAUDE_API_KEY")

    if errors:
        log.warning("⚠️  Chybí následující nastavení v .env:")
        for err in errors:
            log.warning("   - %s", err)
        return False

    # Produkční varování
    if PRODUCTION_MODE and not DASHBOARD_TOKEN:
        log.warning("⚠️  PRODUCTION_MODE je aktivní, ale DASHBOARD_TOKEN není nastaven!")
        log.warning("   Dashboard nebude přístupný bez DASHBOARD_TOKEN v produkci.")

    return True
