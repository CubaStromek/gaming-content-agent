"""
Shared fixtures for Gaming Content Agent tests.
"""

import os
import sys
import json
import pytest
import tempfile
from unittest.mock import patch

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import config  # noqa: E402


@pytest.fixture(autouse=True)
def _no_live_igdb(monkeypatch):
    """Vyprázdní IGDB credentials — testy nesmí dělat živá volání na Twitch/IGDB.

    (igdb_client.is_configured() → False → celá IGDB větev se přeskočí; testy,
    které IGDB testují, si credentials nastaví vlastním monkeypatchem.)
    """
    monkeypatch.setattr(config, 'IGDB_CLIENT_ID', '', raising=False)
    monkeypatch.setattr(config, 'IGDB_CLIENT_SECRET', '', raising=False)


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
def app_client(tmp_path):
    """Flask test client s temp DB, temp OUTPUT_DIR a zamockovaným agentem.

    DŮLEŽITÉ: run_agent_process je VŽDY zamockovaný — testy NIKDY nesmí
    spustit reálný main.py (utrácel by API tokeny). OUTPUT_DIR je přesměrován
    do tmp_path, takže testy nezávisí na reálném output/ adresáři.
    """
    import database
    import web.helpers as web_state
    from web.blueprints import core as core_module
    from web.blueprints import history as history_module
    from web.blueprints import articles as articles_module
    from web.blueprints import podcasts as podcasts_module
    from web.blueprints import decisions as decisions_module

    db_path = str(tmp_path / 'test_web.db')
    database.init_db(db_path)

    output_dir = os.path.realpath(str(tmp_path / 'output'))
    os.makedirs(output_dir, exist_ok=True)

    def fake_run_agent_process():
        """Náhrada za spuštění main.py — okamžitě 'doběhne'."""
        with web_state.output_lock:
            web_state.output_lines.append('FAKE RUN (test) - main.py se nespoustí')
            web_state.run_success = True
            web_state.agent_running = False

    # Reset sdíleného modulového stavu (web.helpers je globální napříč testy)
    with web_state.output_lock:
        web_state.agent_running = False
        web_state.output_lines.clear()
        web_state.articles_count = 0
        web_state.sources_count = 0
        web_state.sent_line_index = 0
        web_state.run_success = False
    with web_state.article_writer_lock:
        web_state.article_writer_state = {'running': False, 'result': None, 'error': None}
    with web_state.podcast_writer_lock:
        web_state.podcast_writer_state = {'running': False, 'result': None, 'error': None}

    with patch.object(database, 'DB_PATH', db_path), \
         patch.object(core_module, 'run_agent_process', fake_run_agent_process), \
         patch.object(history_module, 'OUTPUT_DIR', output_dir), \
         patch.object(articles_module, 'OUTPUT_DIR', output_dir), \
         patch.object(podcasts_module, 'OUTPUT_DIR', output_dir), \
         patch.object(decisions_module, 'OUTPUT_DIR', output_dir):
        from web_app import app
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
