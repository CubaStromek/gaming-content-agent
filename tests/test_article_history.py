"""Tests for article_history module."""

import json
import os
import pytest
from unittest.mock import patch
from datetime import datetime, timedelta

import article_history


class TestLoadHistory:
    def test_returns_empty_when_file_missing(self, tmp_path):
        with patch.object(article_history, 'HISTORY_FILE', str(tmp_path / 'nonexistent.json')):
            result = article_history.load_history()
            assert result == {"last_updated": None, "articles": {}}

    def test_loads_existing_file(self, tmp_path):
        history_file = tmp_path / 'history.json'
        data = {"last_updated": "2025-01-15T10:00:00", "articles": {"https://test.com": "2025-01-15"}}
        history_file.write_text(json.dumps(data), encoding='utf-8')

        with patch.object(article_history, 'HISTORY_FILE', str(history_file)):
            result = article_history.load_history()
            assert result["articles"]["https://test.com"] == "2025-01-15"

    def test_returns_empty_on_corrupt_json(self, tmp_path):
        history_file = tmp_path / 'history.json'
        history_file.write_text("not valid json{{{", encoding='utf-8')

        with patch.object(article_history, 'HISTORY_FILE', str(history_file)):
            result = article_history.load_history()
            assert result == {"last_updated": None, "articles": {}}


class TestSaveHistory:
    def test_saves_and_updates_timestamp(self, tmp_path):
        history_file = tmp_path / 'history.json'
        with patch.object(article_history, 'HISTORY_FILE', str(history_file)):
            history = {"last_updated": None, "articles": {"https://test.com": "2025-01-15"}}
            result = article_history.save_history(history)
            assert result is True
            assert history_file.exists()

            saved = json.loads(history_file.read_text(encoding='utf-8'))
            assert saved["last_updated"] is not None
            assert "https://test.com" in saved["articles"]


class TestGetProcessedUrls:
    def test_returns_urls(self, populated_history):
        urls = article_history.get_processed_urls(populated_history)
        assert "https://ign.com/gta6" in urls
        assert len(urls) == 3

    def test_returns_empty_set_for_empty_history(self, empty_history):
        urls = article_history.get_processed_urls(empty_history)
        assert urls == set()


class TestFilterNewArticles:
    def test_filters_processed(self, sample_articles, populated_history):
        new = article_history.filter_new_articles(sample_articles, populated_history)
        # https://ign.com/gta6 is already processed
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
