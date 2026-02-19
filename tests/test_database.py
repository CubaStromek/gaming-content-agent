"""Tests for database module."""

import os
import pytest
from unittest.mock import patch

import database


class TestGetDb:
    def test_creates_db_file(self, tmp_path):
        db_path = str(tmp_path / 'subdir' / 'test.db')
        conn = database.get_db(db_path)
        conn.close()
        assert os.path.exists(db_path)

    def test_wal_mode(self, tmp_path):
        db_path = str(tmp_path / 'test.db')
        conn = database.get_db(db_path)
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
        conn.close()
        assert mode == 'wal'

    def test_row_factory(self, tmp_path):
        db_path = str(tmp_path / 'test.db')
        conn = database.get_db(db_path)
        database.init_db(db_path)
        conn.execute("INSERT INTO meta (key, value) VALUES ('test', 'value')")
        row = conn.execute("SELECT * FROM meta WHERE key = 'test'").fetchone()
        conn.close()
        assert row['key'] == 'test'
        assert row['value'] == 'value'


class TestInitDb:
    def test_creates_all_tables(self, tmp_path):
        db_path = str(tmp_path / 'test.db')
        database.init_db(db_path)

        conn = database.get_db(db_path)
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        conn.close()

        table_names = {t['name'] for t in tables}
        assert 'processed_articles' in table_names
        assert 'publish_log' in table_names
        assert 'feed_health' in table_names
        assert 'meta' in table_names

    def test_idempotent(self, tmp_path):
        db_path = str(tmp_path / 'test.db')
        database.init_db(db_path)
        database.init_db(db_path)  # Should not raise
