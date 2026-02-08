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

def is_wp_configured():
    return bool(WP_URL and WP_USER and WP_APP_PASSWORD)

# Nastavení agenta
MAX_ARTICLES_PER_SOURCE = int(os.getenv("MAX_ARTICLES_PER_SOURCE", "10"))
MIN_VIRALITY_SCORE = int(os.getenv("MIN_VIRALITY_SCORE", "50"))

# Model pro generování článků
ARTICLE_MODEL = "claude-sonnet-4-20250514"

# Model pro analýzu (přepisovatelný přes .env)
ANALYSIS_MODEL = os.getenv("ANALYSIS_MODEL", "claude-sonnet-4-20250514")

# Maximální délka summary při scrapování RSS (znaky)
SUMMARY_MAX_LENGTH = int(os.getenv("SUMMARY_MAX_LENGTH", "500"))

# Dashboard autentizace (volitelný bearer token)
DASHBOARD_TOKEN = os.getenv("DASHBOARD_TOKEN", "")

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

    return True
