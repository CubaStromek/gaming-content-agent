"""
Konfigurace pro Gaming Content Agent
Načítá nastavení z .env souboru
"""

import os
from dotenv import load_dotenv

# Načti .env soubor
load_dotenv()

# Claude API
CLAUDE_API_KEY = os.getenv("CLAUDE_API_KEY")
if not CLAUDE_API_KEY:
    raise ValueError("❌ CLAUDE_API_KEY není nastavený v .env souboru!")

# Email konfigurace
EMAIL_TO = os.getenv("EMAIL_TO", "")
EMAIL_FROM = os.getenv("EMAIL_FROM", "content-agent@gaming.cz")

# SMTP nastavení
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")

# Nastavení agenta
MAX_ARTICLES_PER_SOURCE = int(os.getenv("MAX_ARTICLES_PER_SOURCE", "10"))
MIN_VIRALITY_SCORE = int(os.getenv("MIN_VIRALITY_SCORE", "50"))

# RSS Feedy herních webů
RSS_FEEDS = [
    # Mezinárodní weby
    {"name": "IGN", "url": "https://feeds.ign.com/ign/all", "lang": "en"},
    {"name": "GameSpot", "url": "https://www.gamespot.com/feeds/news/", "lang": "en"},
    {"name": "PC Gamer", "url": "https://www.pcgamer.com/rss/", "lang": "en"},
    {"name": "Rock Paper Shotgun", "url": "https://www.rockpapershotgun.com/feed", "lang": "en"},
    {"name": "Kotaku", "url": "https://kotaku.com/rss", "lang": "en"},
    {"name": "Polygon", "url": "https://www.polygon.com/rss/index.xml", "lang": "en"},

    # České weby
    {"name": "Hrej.cz", "url": "https://hrej.cz/rss/all", "lang": "cs"},
    {"name": "Zing.cz", "url": "https://zing.cz/rss/clanky", "lang": "cs"},
    {"name": "Jiří Bigas", "url": "https://jiribigas.substack.com/feed", "lang": "cs"},
    {"name": "Games.cz", "url": "https://games.tiscali.cz/rss.xml", "lang": "cs"},
]

def validate_config():
    """Zkontroluje, že všechny důležité proměnné jsou nastavené"""
    errors = []

    if not CLAUDE_API_KEY or CLAUDE_API_KEY == "sk-ant-api03-your-api-key-here":
        errors.append("CLAUDE_API_KEY")

    if errors:
        print("⚠️  Chybí následující nastavení v .env:")
        for err in errors:
            print(f"   - {err}")
        return False

    return True
