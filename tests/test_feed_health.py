"""Tests for feed_health module (SQLite backend)."""

import pytest
from unittest.mock import patch

import database
import feed_health


@pytest.fixture(autouse=True)
def use_tmp_db(tmp_path):
    """Použije dočasnou SQLite databázi pro každý test."""
    db_path = str(tmp_path / 'test.db')
    database.init_db(db_path)
    with patch.object(database, 'DB_PATH', db_path):
        yield


class TestRecordSuccess:
    def test_records_success(self):
        feed_health.record_success("IGN")
        health = feed_health.get_feed_health("IGN")
        assert health["total_success"] == 1
        assert health["consecutive_failures"] == 0
        assert health["last_success"] is not None

    def test_resets_consecutive_failures(self):
        feed_health.record_failure("IGN")
        feed_health.record_failure("IGN")
        feed_health.record_success("IGN")
        health = feed_health.get_feed_health("IGN")
        assert health["consecutive_failures"] == 0
        assert health["total_failure"] == 2


class TestRecordFailure:
    def test_records_failure(self):
        feed_health.record_failure("IGN")
        health = feed_health.get_feed_health("IGN")
        assert health["total_failure"] == 1
        assert health["consecutive_failures"] == 1

    def test_increments_consecutive(self):
        for _ in range(3):
            feed_health.record_failure("IGN")
        health = feed_health.get_feed_health("IGN")
        assert health["consecutive_failures"] == 3

    def test_returns_true_at_threshold(self):
        for i in range(feed_health.MAX_CONSECUTIVE_FAILURES - 1):
            result = feed_health.record_failure("IGN")
            assert result is False
        result = feed_health.record_failure("IGN")
        assert result is True

    def test_returns_true_above_threshold(self):
        for _ in range(feed_health.MAX_CONSECUTIVE_FAILURES + 2):
            feed_health.record_failure("IGN")
        result = feed_health.record_failure("IGN")
        assert result is True


class TestShouldDisable:
    def test_false_for_healthy_feed(self):
        feed_health.record_success("IGN")
        assert feed_health.should_disable("IGN") is False

    def test_false_for_unknown_feed(self):
        assert feed_health.should_disable("Unknown") is False

    def test_true_at_threshold(self):
        for _ in range(feed_health.MAX_CONSECUTIVE_FAILURES):
            feed_health.record_failure("Broken")
        assert feed_health.should_disable("Broken") is True


class TestGetAllHealth:
    def test_empty_initially(self):
        assert feed_health.get_all_health() == {}

    def test_returns_all_feeds(self):
        feed_health.record_success("IGN")
        feed_health.record_failure("Broken")
        health = feed_health.get_all_health()
        assert "IGN" in health
        assert "Broken" in health


class TestResetFeed:
    def test_resets_failures(self):
        for _ in range(3):
            feed_health.record_failure("IGN")
        feed_health.reset_feed("IGN")
        health = feed_health.get_feed_health("IGN")
        assert health["consecutive_failures"] == 0
        assert health["total_failure"] == 3

    def test_reset_unknown_feed(self):
        feed_health.reset_feed("Unknown")
