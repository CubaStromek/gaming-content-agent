"""Tests for feed_manager module."""

import json
import os
import pytest
from unittest.mock import patch

import feed_manager


@pytest.fixture
def feeds_file(tmp_path, sample_feeds):
    """Create a temp feeds file and patch FEEDS_FILE."""
    fpath = tmp_path / "custom_feeds.json"
    data = {"last_updated": "2025-01-15T10:00:00", "feeds": sample_feeds}
    fpath.write_text(json.dumps(data), encoding='utf-8')
    return str(fpath)


class TestGenerateId:
    def test_simple_name(self):
        assert feed_manager._generate_id("IGN") == "ign"

    def test_spaces(self):
        assert feed_manager._generate_id("PC Gamer") == "pc-gamer"

    def test_special_chars(self):
        assert feed_manager._generate_id("Hrej.cz") == "hrej-cz"

    def test_empty_name(self):
        assert feed_manager._generate_id("") == "feed"


class TestEnsureUniqueId:
    def test_unique(self):
        assert feed_manager._ensure_unique_id("ign", {"pcgamer"}) == "ign"

    def test_duplicate(self):
        assert feed_manager._ensure_unique_id("ign", {"ign"}) == "ign-2"

    def test_multiple_duplicates(self):
        assert feed_manager._ensure_unique_id("ign", {"ign", "ign-2"}) == "ign-3"


class TestLoadFeeds:
    def test_loads_from_file(self, feeds_file, sample_feeds):
        with patch.object(feed_manager, 'FEEDS_FILE', feeds_file):
            feeds = feed_manager.load_feeds()
            assert len(feeds) == 3
            assert feeds[0]["name"] == "IGN"

    def test_seeds_from_config_if_missing(self, tmp_path):
        fpath = str(tmp_path / "nonexistent.json")
        with patch.object(feed_manager, 'FEEDS_FILE', fpath):
            feeds = feed_manager.load_feeds()
            assert len(feeds) > 0
            assert os.path.exists(fpath)


class TestGetEnabledFeeds:
    def test_filters_disabled(self, feeds_file):
        with patch.object(feed_manager, 'FEEDS_FILE', feeds_file):
            enabled = feed_manager.get_enabled_feeds()
            assert len(enabled) == 2
            names = {f["name"] for f in enabled}
            assert "Disabled" not in names


class TestValidateFeed:
    def test_valid(self):
        assert feed_manager._validate_feed("Test", "https://example.com/rss", "en") is None

    def test_empty_name(self):
        assert feed_manager._validate_feed("", "https://example.com", "en") is not None

    def test_invalid_url(self):
        assert feed_manager._validate_feed("Test", "ftp://bad", "en") is not None

    def test_invalid_lang(self):
        assert feed_manager._validate_feed("Test", "https://ok.com", "de") is not None

    def test_duplicate_url(self, sample_feeds):
        err = feed_manager._validate_feed("New", "https://feeds.ign.com/ign/all", "en", sample_feeds)
        assert err is not None


class TestAddFeed:
    def test_adds_new_feed(self, feeds_file):
        with patch.object(feed_manager, 'FEEDS_FILE', feeds_file):
            feed, error = feed_manager.add_feed("New Feed", "https://new.com/rss", "en")
            assert error is None
            assert feed["name"] == "New Feed"
            assert feed["id"] == "new-feed"

    def test_rejects_duplicate_url(self, feeds_file):
        with patch.object(feed_manager, 'FEEDS_FILE', feeds_file):
            feed, error = feed_manager.add_feed("Dupe", "https://feeds.ign.com/ign/all", "en")
            assert feed is None
            assert error is not None


class TestUpdateFeed:
    def test_updates_name(self, feeds_file):
        with patch.object(feed_manager, 'FEEDS_FILE', feeds_file):
            feed, error = feed_manager.update_feed("ign", name="IGN Updated")
            assert error is None
            assert feed["name"] == "IGN Updated"

    def test_not_found(self, feeds_file):
        with patch.object(feed_manager, 'FEEDS_FILE', feeds_file):
            feed, error = feed_manager.update_feed("nonexistent", name="Test")
            assert feed is None
            assert error == "Feed not found"

    def test_toggle_enabled(self, feeds_file):
        with patch.object(feed_manager, 'FEEDS_FILE', feeds_file):
            feed, error = feed_manager.update_feed("ign", enabled=False)
            assert error is None
            assert feed["enabled"] is False


class TestDeleteFeed:
    def test_deletes_existing(self, feeds_file):
        with patch.object(feed_manager, 'FEEDS_FILE', feeds_file):
            assert feed_manager.delete_feed("ign") is True
            feeds = feed_manager.load_feeds()
            assert all(f["id"] != "ign" for f in feeds)

    def test_returns_false_for_missing(self, feeds_file):
        with patch.object(feed_manager, 'FEEDS_FILE', feeds_file):
            assert feed_manager.delete_feed("nonexistent") is False
