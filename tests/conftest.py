"""
Shared fixtures for Gaming Content Agent tests.
"""

import os
import sys
import json
import pytest
import tempfile

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture
def sample_articles():
    """Sample articles for testing."""
    return [
        {
            'source': 'IGN',
            'language': 'en',
            'title': 'GTA 6 Trailer Breaks Records',
            'link': 'https://ign.com/gta6',
            'summary': 'Rockstar Games released the second trailer...',
            'published': '2025-01-15T10:00:00Z',
        },
        {
            'source': 'Hrej.cz',
            'language': 'cs',
            'title': 'Nový trailer na Mafia 4',
            'link': 'https://hrej.cz/mafia4',
            'summary': 'Hangar 13 odhalilo nový trailer...',
            'published': '2025-01-15T12:00:00Z',
        },
        {
            'source': 'PC Gamer',
            'language': 'en',
            'title': 'Palworld hits 2 million',
            'link': 'https://pcgamer.com/palworld',
            'summary': 'The survival game is a massive hit...',
            'published': '2025-01-14T08:00:00Z',
        },
    ]


@pytest.fixture
def empty_history():
    """Empty article history."""
    return {
        "last_updated": None,
        "articles": {}
    }


@pytest.fixture
def populated_history():
    """History with some processed articles."""
    return {
        "last_updated": "2025-01-15T10:00:00",
        "articles": {
            "https://ign.com/gta6": "2025-01-15",
            "https://pcgamer.com/old-article": "2024-12-01",
            "https://hrej.cz/stary-clanek": "2024-11-01",
        }
    }


@pytest.fixture
def tmp_history_file(tmp_path):
    """Temporary history file path."""
    return str(tmp_path / "test_processed_articles.json")


@pytest.fixture
def tmp_feeds_file(tmp_path):
    """Temporary feeds file path."""
    return str(tmp_path / "test_custom_feeds.json")


@pytest.fixture
def sample_feeds():
    """Sample feed list."""
    return [
        {"id": "ign", "name": "IGN", "url": "https://feeds.ign.com/ign/all", "lang": "en", "enabled": True},
        {"id": "hrej-cz", "name": "Hrej.cz", "url": "https://hrej.cz/rss/all", "lang": "cs", "enabled": True},
        {"id": "disabled-feed", "name": "Disabled", "url": "https://example.com/rss", "lang": "en", "enabled": False},
    ]


@pytest.fixture
def sample_report_text():
    """Sample report text with topics."""
    return """Gaming Content Agent - Report
Datum: 15.01.2025 10:00

STATISTIKY:
Analyzováno článků: 50
Zdroje: IGN, Hrej.cz, PC Gamer

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏆 TOP TÉMATA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎮 TÉMA 1: GTA 6 Trailer
📰 NAVRŽENÝ TITULEK: GTA 6: Nový trailer překonává rekordy
🎯 ÚHEL POHLEDU: Detailní analýza
📝 KONTEXT: Rockstar Games vydal nový trailer.
💬 HLAVNÍ HOOK: Nejvíce sledovaný trailer v historii
🖼️ VIZUÁLNÍ NÁVRH: Vice City, neonové barvy
🔥 VIRALITA: 95/100
💡 PROČ TEĎKA: Trailer právě vyšel
🔗 ZDROJE:
https://ign.com/gta6
https://pcgamer.com/gta6
🏷️ SEO KLÍČOVÁ SLOVA: GTA 6, trailer, Rockstar, Vice City

🎮 TÉMA 2: Palworld fenomén
📰 NAVRŽENÝ TITULEK: Palworld: Proč je tahle hra všude?
🎯 ÚHEL POHLEDU: Analýza fenoménu
📝 KONTEXT: Palworld překonalo 2 miliony hráčů.
💬 HLAVNÍ HOOK: 2 miliony současných hráčů
🖼️ VIZUÁLNÍ NÁVRH: Pal creatures, colorful world
🔥 VIRALITA: 80/100
💡 PROČ TEĎKA: Právě překonáno milník
🔗 ZDROJE:
https://pcgamer.com/palworld
🏷️ SEO KLÍČOVÁ SLOVA: Palworld, survival, Pokemon
"""


@pytest.fixture
def app_client():
    """Flask test client."""
    from web_app import app
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client
