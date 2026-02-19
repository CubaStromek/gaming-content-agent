"""Tests for publish_log module (SQLite backend)."""

import pytest
from unittest.mock import patch

import database
import publish_log


@pytest.fixture(autouse=True)
def use_tmp_db(tmp_path):
    """Použije dočasnou SQLite databázi pro každý test."""
    db_path = str(tmp_path / 'test.db')
    database.init_db(db_path)
    with patch.object(database, 'DB_PATH', db_path):
        yield


class TestLogDecision:
    def test_logs_entry(self):
        publish_log.log_decision({
            'action': 'published',
            'score': 4,
            'topic': 'GTA 6',
        })

        conn = database.get_db()
        row = conn.execute("SELECT * FROM publish_log").fetchone()
        conn.close()
        assert row is not None
        assert row['action'] == 'published'
        assert row['score'] == 4
        assert row['timestamp'] is not None

    def test_appends_multiple(self):
        publish_log.log_decision({'action': 'published', 'score': 3})
        publish_log.log_decision({'action': 'skipped', 'score': 0})

        conn = database.get_db()
        count = conn.execute("SELECT COUNT(*) FROM publish_log").fetchone()[0]
        conn.close()
        assert count == 2


class TestGetStats:
    def test_empty_db(self):
        stats = publish_log.get_stats()
        assert stats['total'] == 0
        assert stats['published'] == 0
        assert stats['skipped'] == 0

    def test_counts_actions(self):
        publish_log.log_decision({'action': 'published', 'score': 4})
        publish_log.log_decision({'action': 'published', 'score': 5})
        publish_log.log_decision({'action': 'skipped', 'score': 0})

        stats = publish_log.get_stats()
        assert stats['total'] == 3
        assert stats['published'] == 2
        assert stats['skipped'] == 1

    def test_avg_score(self):
        publish_log.log_decision({'action': 'published', 'score': 4})
        publish_log.log_decision({'action': 'published', 'score': 6})

        stats = publish_log.get_stats()
        assert stats['avg_score'] == 5.0

    def test_top_sources(self):
        publish_log.log_decision({
            'action': 'published',
            'score': 4,
            'sources': ['https://ign.com/article1', 'https://ign.com/article2', 'https://pcgamer.com/article1']
        })

        stats = publish_log.get_stats()
        assert len(stats['top_sources']) > 0
        domains = {s['domain'] for s in stats['top_sources']}
        assert 'ign.com' in domains
