"""Tests for article_history module (SQLite backend)."""

import os
import pytest
from unittest.mock import patch
from datetime import datetime, timedelta

import database
import article_history


@pytest.fixture(autouse=True)
def use_tmp_db(tmp_path):
    """Použije dočasnou SQLite databázi pro každý test."""
    db_path = str(tmp_path / 'test.db')
    database.init_db(db_path)
    with patch.object(database, 'DB_PATH', db_path):
        yield


class TestLoadHistory:
    def test_returns_empty_when_db_empty(self):
        result = article_history.load_history()
        assert result == {"last_updated": None, "articles": {}}

    def test_loads_existing_data(self):
        conn = database.get_db()
        conn.execute("INSERT INTO processed_articles (url, date_added) VALUES (?, ?)",
                     ("https://test.com", "2025-01-15"))
        conn.execute("INSERT OR REPLACE INTO meta (key, value) VALUES ('history_last_updated', '2025-01-15T10:00:00')")
        conn.commit()
        conn.close()

        result = article_history.load_history()
        assert result["articles"]["https://test.com"] == "2025-01-15"
        assert result["last_updated"] == "2025-01-15T10:00:00"


class TestSaveHistory:
    def test_saves_and_updates_timestamp(self):
        history = {"last_updated": None, "articles": {"https://test.com": "2025-01-15"}}
        result = article_history.save_history(history)
        assert result is True
        assert history["last_updated"] is not None

        loaded = article_history.load_history()
        assert "https://test.com" in loaded["articles"]


class TestGetProcessedUrls:
    def test_returns_urls(self, populated_history):
        urls = article_history.get_processed_urls(populated_history)
        assert "https://ign.com/gta6" in urls
        assert len(urls) == 3

    def test_returns_empty_set_for_empty_history(self, empty_history):
        urls = article_history.get_processed_urls(empty_history)
        assert urls == set()

    def test_returns_urls_from_db(self):
        conn = database.get_db()
        conn.execute("INSERT INTO processed_articles (url, date_added) VALUES (?, ?)",
                     ("https://test.com", "2025-01-15"))
        conn.commit()
        conn.close()

        urls = article_history.get_processed_urls()
        assert "https://test.com" in urls


class TestFilterNewArticles:
    def test_filters_processed(self, sample_articles, populated_history):
        new = article_history.filter_new_articles(sample_articles, populated_history)
        assert len(new) == 2
        assert all(a['link'] != 'https://ign.com/gta6' for a in new)

    def test_all_new_when_empty_history(self, sample_articles, empty_history):
        new = article_history.filter_new_articles(sample_articles, empty_history)
        assert len(new) == 3


class TestMarkAsProcessed:
    def test_marks_articles(self, sample_articles, empty_history):
        updated = article_history.mark_as_processed(sample_articles, empty_history)
        assert "https://ign.com/gta6" in updated["articles"]
        assert "https://hrej.cz/mafia4" in updated["articles"]
        assert len(updated["articles"]) == 3


class TestCleanupOldEntries:
    def test_removes_old_entries(self):
        today = datetime.now().strftime("%Y-%m-%d")
        old_date = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")
        very_old_date = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")
        history = {
            "last_updated": None,
            "articles": {
                "https://new.com": today,
                "https://old.com": old_date,
                "https://very-old.com": very_old_date,
            }
        }
        cleaned = article_history.cleanup_old_entries(history, expiry_days=30)
        assert len(cleaned["articles"]) == 1
        assert "https://new.com" in cleaned["articles"]

    def test_keeps_recent_entries(self, empty_history):
        today = datetime.now().strftime("%Y-%m-%d")
        empty_history["articles"] = {"https://test.com": today}
        cleaned = article_history.cleanup_old_entries(empty_history, expiry_days=30)
        assert len(cleaned["articles"]) == 1

    def test_handles_empty_articles(self, empty_history):
        cleaned = article_history.cleanup_old_entries(empty_history)
        assert cleaned["articles"] == {}


class TestGetStats:
    def test_stats_populated(self, populated_history):
        stats = article_history.get_stats(populated_history)
        assert stats["total_processed"] == 3
        assert stats["last_updated"] == "2025-01-15T10:00:00"

    def test_stats_empty(self, empty_history):
        stats = article_history.get_stats(empty_history)
        assert stats["total_processed"] == 0
        assert stats["last_updated"] is None
