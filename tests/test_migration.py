"""Tests for migrate_to_sqlite script."""

import json
import os
import pytest
from unittest.mock import patch

import database


@pytest.fixture
def setup_migration(tmp_path):
    """Vytvoří dočasné JSON/JSONL soubory a dočasnou DB."""
    db_path = str(tmp_path / 'test.db')
    database.init_db(db_path)

    # processed_articles.json
    articles_json = {
        "last_updated": "2025-01-15T10:00:00",
        "articles": {
            "https://ign.com/gta6": "2025-01-15",
            "https://pcgamer.com/palworld": "2025-01-14",
        }
    }
    articles_path = tmp_path / 'processed_articles.json'
    articles_path.write_text(json.dumps(articles_json), encoding='utf-8')

    # publish_log.jsonl
    log_entries = [
        {"timestamp": "2025-01-15T10:00:00", "action": "published", "topic": "GTA 6", "score": 4, "sources": ["https://ign.com/gta6"]},
        {"timestamp": "2025-01-15T11:00:00", "action": "skipped", "topic": "Palworld", "score": 0},
    ]
    log_path = tmp_path / 'publish_log.jsonl'
    log_path.write_text('\n'.join(json.dumps(e) for e in log_entries), encoding='utf-8')

    # feed_health.json
    health_data = {
        "IGN": {"consecutive_failures": 0, "total_success": 10, "total_failure": 1, "last_success": "2025-01-15T10:00:00", "last_failure": None},
        "Broken": {"consecutive_failures": 5, "total_success": 0, "total_failure": 5, "last_success": None, "last_failure": "2025-01-15T10:00:00"},
    }
    health_path = tmp_path / 'feed_health.json'
    health_path.write_text(json.dumps(health_data), encoding='utf-8')

    return tmp_path, db_path


class TestMigration:
    def test_migrates_articles(self, setup_migration):
        tmp_path, db_path = setup_migration

        with patch.object(database, 'DB_PATH', db_path):
            import migrate_to_sqlite
            with patch.object(migrate_to_sqlite, 'BASE_DIR', str(tmp_path)):
                count = migrate_to_sqlite.migrate_processed_articles()

        assert count == 2

        conn = database.get_db(db_path)
        rows = conn.execute("SELECT * FROM processed_articles").fetchall()
        conn.close()
        assert len(rows) == 2

    def test_migrates_publish_log(self, setup_migration):
        tmp_path, db_path = setup_migration

        with patch.object(database, 'DB_PATH', db_path):
            import migrate_to_sqlite
            with patch.object(migrate_to_sqlite, 'BASE_DIR', str(tmp_path)):
                count = migrate_to_sqlite.migrate_publish_log()

        assert count == 2

        conn = database.get_db(db_path)
        rows = conn.execute("SELECT * FROM publish_log").fetchall()
        conn.close()
        assert len(rows) == 2

    def test_migrates_feed_health(self, setup_migration):
        tmp_path, db_path = setup_migration

        with patch.object(database, 'DB_PATH', db_path):
            import migrate_to_sqlite
            with patch.object(migrate_to_sqlite, 'BASE_DIR', str(tmp_path)):
                count = migrate_to_sqlite.migrate_feed_health()

        assert count == 2

        conn = database.get_db(db_path)
        rows = conn.execute("SELECT * FROM feed_health").fetchall()
        assert len(rows) == 2
        ign = conn.execute("SELECT * FROM feed_health WHERE feed_name = 'IGN'").fetchone()
        conn.close()
        assert ign['total_success'] == 10
