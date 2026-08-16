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


def _env_int(name: str, default: int) -> int:
    """Bezpečné načtení int hodnoty z env.

    Překlep v .env (např. SMTP_PORT=58x7) nesmí shodit import celého modulu —
    zaloguje warning a vrátí default.
    """
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        return int(raw.strip())
    except ValueError:
        log.warning("⚠️  Neplatná hodnota %s=%r v .env — používám default %d", name, raw, default)
        return default

# Claude API
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY", "")

# Email konfigurace
EMAIL_TO = os.getenv("EMAIL_TO", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "content-agent@gaming.cz")

# SMTP nastavení
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = _env_int("SMTP_PORT", 587)
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

# Telegram alerty (znovupoužívá bota @Cubajs_bot) — upozornění při zastavení běhu
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# WordPress publishing
WP_URL = os.getenv("WP_URL", "")
WP_USER = os.getenv("WP_USER", "")
WP_APP_PASSWORD = os.getenv("WP_APP_PASSWORD", "")

# IGDB / Twitch API (herní databáze - obrázky, primární zdroj od 8/2026)
IGDB_CLIENT_ID = os.getenv("IGDB_CLIENT_ID", "")
IGDB_CLIENT_SECRET = os.getenv("IGDB_CLIENT_SECRET", "")

# RAWG.io API — LEGACY. Z pipeline vyhozeno 2026-08-12 (po výpadku 8/2026
# nenaběhlo, samé timeouty). Zůstává jen kvůli scripts/oneoff/, nové kódy
# obrázky berou z igdb_client.
RAWG_API_KEY = os.getenv("RAWG_API_KEY", "")

# X.com (Twitter) API
TWITTER_API_KEY = os.getenv("TWITTER_API_KEY", "")
TWITTER_API_SECRET = os.getenv("TWITTER_API_SECRET", "")
TWITTER_ACCESS_TOKEN = os.getenv("TWITTER_ACCESS_TOKEN", "")
TWITTER_ACCESS_TOKEN_SECRET = os.getenv("TWITTER_ACCESS_TOKEN_SECRET", "")
TWITTER_USERNAME = os.getenv("TWITTER_USERNAME", "GAMEfo_cz")

# Facebook Page API (CZ + EN stránky)
FACEBOOK_PAGE_ID_CS = os.getenv("FACEBOOK_PAGE_ID_CS", "")
FACEBOOK_PAGE_TOKEN_CS = os.getenv("FACEBOOK_PAGE_TOKEN_CS", "")
FACEBOOK_PAGE_ID_EN = os.getenv("FACEBOOK_PAGE_ID_EN", "")
FACEBOOK_PAGE_TOKEN_EN = os.getenv("FACEBOOK_PAGE_TOKEN_EN", "")

# Threads API (Meta Graph API)
# POZOR: Účet @gamefo.cz byl permanentně zabanován Metou dne 2026-02-25.
# THREADS_ENABLED=false vypíná posting na Threads. Pro re-aktivaci s novým účtem
# nastav THREADS_ENABLED=true a aktualizuj THREADS_USER_ID + THREADS_ACCESS_TOKEN.
THREADS_ENABLED = os.getenv("THREADS_ENABLED", "false").lower() in ("1", "true", "yes")
THREADS_USER_ID = os.getenv("THREADS_USER_ID", "")
THREADS_ACCESS_TOKEN = os.getenv("THREADS_ACCESS_TOKEN", "")

# Social media dry-run (loguje, ale nepostuje)
SOCIAL_DRY_RUN = os.getenv("SOCIAL_DRY_RUN", "").lower() in ("1", "true", "yes")

# Denní limit social media postů (ochrana proti banu za spam)
SOCIAL_DAILY_LIMIT = _env_int("SOCIAL_DAILY_LIMIT", 3)

# Náhodný delay před social postem (sekundy) — aby to nevypadalo jako bot
SOCIAL_DELAY_MIN = _env_int("SOCIAL_DELAY_MIN", 60)
SOCIAL_DELAY_MAX = _env_int("SOCIAL_DELAY_MAX", 300)

def is_wp_configured():
    return bool(WP_URL and WP_USER and WP_APP_PASSWORD)

def is_twitter_configured():
    return bool(TWITTER_API_KEY and TWITTER_API_SECRET and TWITTER_ACCESS_TOKEN and TWITTER_ACCESS_TOKEN_SECRET)

def is_facebook_configured(lang='cs'):
    if lang == 'en':
        return bool(FACEBOOK_PAGE_ID_EN and FACEBOOK_PAGE_TOKEN_EN)
    return bool(FACEBOOK_PAGE_ID_CS and FACEBOOK_PAGE_TOKEN_CS)

def is_threads_configured():
    return bool(THREADS_ENABLED and THREADS_USER_ID and THREADS_ACCESS_TOKEN)

# SQLite databáze
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'gamefo.db')

# Nastavení agenta
MAX_ARTICLES_PER_SOURCE = _env_int("MAX_ARTICLES_PER_SOURCE", 10)
MIN_VIRALITY_SCORE = _env_int("MIN_VIRALITY_SCORE", 50)

# Model pro český článek — jediná fáze, kde se platí za porozumění zdroji.
# Měřeno 15. 8. 2026 na článku o S.T.A.L.K.E.R. 2: Sonnet 4.6 zaměnil příčinu
# a následek (vinil systém A-Life místo toho, že nefungoval), Opus 5 tutéž
# pasáž napsal správně a doplnil kontext, který ve zdroji nebyl.
ARTICLE_MODEL = os.getenv("ARTICLE_MODEL", "claude-opus-5")

# Model pro anglickou lokalizaci a EN metadata. Překlad hotového českého textu
# je mechanická práce — nemá smysl na ni platit sazbu Opusu.
TRANSLATION_MODEL = os.getenv("TRANSLATION_MODEL", "claude-sonnet-4-6")

# Model pro analýzu (přepisovatelný přes .env). Haiku 4.5 je 5× levnější než Sonnet
# a pro výběr top témat z RSS feedů plně dostačuje.
ANALYSIS_MODEL = os.getenv("ANALYSIS_MODEL", "claude-haiku-4-5-20251001")

# Model pro sémantický dedup (druhá vrstva po lexikálním filtru). Haiku stačí —
# rozhoduje jen ANO/NE, jestli jde o tutéž novinku i při přejmenované entitě.
DEDUP_MODEL = os.getenv("DEDUP_MODEL", "claude-haiku-4-5-20251001")

# Maximální délka summary při scrapování RSS (znaky)
SUMMARY_MAX_LENGTH = _env_int("SUMMARY_MAX_LENGTH", 500)

# Async RSS scraping
FEED_TIMEOUT = _env_int("FEED_TIMEOUT", 15)
MAX_CONCURRENT_FEEDS = _env_int("MAX_CONCURRENT_FEEDS", 8)
MAX_CONCURRENT_PER_DOMAIN = _env_int("MAX_CONCURRENT_PER_DOMAIN", 2)

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
