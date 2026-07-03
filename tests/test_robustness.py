"""Testy robustnostního refactoru core pipeline.

Pokrývá:
- feed_manager: atomický zápis, žádný přepis souboru defaulty při parse chybě,
  auto_disable_feed matching podle URL
- article_history: inkrementální save_history (žádný DELETE celé tabulky)
- rss_scraper: strip HTML ze summary před ořezem
- logger: maskování Telegram bot tokenu vč. tracebacků z exc_info
- claude_analyzer: format_topics_as_report přežije chybějící klíče
- topic_dedup: shoda podle game_name z data_json
"""

import io
import json
import logging
import os
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

import database
import feed_manager
import article_history
import rss_scraper
import topic_dedup
import claude_analyzer
import logger as logger_module


@pytest.fixture
def feeds_file(tmp_path, sample_feeds):
    fpath = tmp_path / "custom_feeds.json"
    data = {"last_updated": "2025-01-15T10:00:00", "feeds": sample_feeds}
    fpath.write_text(json.dumps(data), encoding='utf-8')
    return str(fpath)


class TestLoadFeedsCorruptFile:
    def test_raises_and_does_not_overwrite(self, tmp_path):
        fpath = tmp_path / "custom_feeds.json"
        fpath.write_text("{ not valid json", encoding='utf-8')
        original = fpath.read_text(encoding='utf-8')

        with patch.object(feed_manager, 'FEEDS_FILE', str(fpath)):
            with pytest.raises(feed_manager.FeedsFileError):
                feed_manager.load_feeds()

        # Soubor NESMÍ být přepsán defaulty
        assert fpath.read_text(encoding='utf-8') == original

    def test_seeds_only_when_file_missing(self, tmp_path):
        fpath = str(tmp_path / "nonexistent.json")
        with patch.object(feed_manager, 'FEEDS_FILE', fpath):
            feeds = feed_manager.load_feeds()
            assert len(feeds) > 0
            assert os.path.exists(fpath)


class TestSaveFeedsAtomic:
    def test_writes_valid_json(self, tmp_path, sample_feeds):
        fpath = str(tmp_path / "custom_feeds.json")
        with patch.object(feed_manager, 'FEEDS_FILE', fpath):
            assert feed_manager.save_feeds(sample_feeds) is True

        with open(fpath, encoding='utf-8') as f:
            data = json.load(f)
        assert len(data["feeds"]) == 3

    def test_no_temp_files_left(self, tmp_path, sample_feeds):
        fpath = str(tmp_path / "custom_feeds.json")
        with patch.object(feed_manager, 'FEEDS_FILE', fpath):
            feed_manager.save_feeds(sample_feeds)
        leftovers = [p for p in os.listdir(tmp_path) if p.endswith('.tmp')]
        assert leftovers == []


class TestAutoDisableFeed:
    def test_matches_by_url(self, feeds_file):
        with patch.object(feed_manager, 'FEEDS_FILE', feeds_file):
            # Jméno schválně špatně — URL musí vyhrát
            result = feed_manager.auto_disable_feed(
                "Wrong Name", feed_url="https://feeds.ign.com/ign/all")
            assert result is True
            feeds = feed_manager.load_feeds()
            ign = next(f for f in feeds if f["id"] == "ign")
            assert ign["enabled"] is False
            assert ign["auto_disabled"] is True

    def test_fallback_to_name(self, feeds_file):
        with patch.object(feed_manager, 'FEEDS_FILE', feeds_file):
            result = feed_manager.auto_disable_feed("Hrej.cz")
            assert result is True
            feeds = feed_manager.load_feeds()
            hrej = next(f for f in feeds if f["id"] == "hrej-cz")
            assert hrej["enabled"] is False

    def test_unknown_feed_returns_false(self, feeds_file):
        with patch.object(feed_manager, 'FEEDS_FILE', feeds_file):
            assert feed_manager.auto_disable_feed("Nope", feed_url="https://nope.example/rss") is False


@pytest.fixture
def tmp_db(tmp_path):
    db_path = str(tmp_path / 'test.db')
    database.init_db(db_path)
    with patch.object(database, 'DB_PATH', db_path):
        yield


class TestSaveHistoryIncremental:
    def test_does_not_delete_rows_missing_from_snapshot(self, tmp_db):
        """Simulace souběhu: jiný proces zapsal URL, které náš snapshot nemá."""
        today = datetime.now().strftime("%Y-%m-%d")

        conn = database.get_db()
        conn.execute(
            "INSERT INTO processed_articles (url, date_added) VALUES (?, ?)",
            ("https://other-process.com/article", today),
        )
        conn.commit()
        conn.close()

        history = {"last_updated": None, "articles": {"https://mine.com/a": today}}
        assert article_history.save_history(history) is True

        urls = article_history.get_processed_urls()
        assert "https://other-process.com/article" in urls  # NESMÍ zmizet
        assert "https://mine.com/a" in urls

    def test_deletes_expired_rows(self, tmp_db):
        today = datetime.now().strftime("%Y-%m-%d")
        old = (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d")

        conn = database.get_db()
        conn.execute("INSERT INTO processed_articles (url, date_added) VALUES (?, ?)",
                     ("https://old.com/x", old))
        conn.commit()
        conn.close()

        history = {"last_updated": None, "articles": {"https://new.com/y": today}}
        article_history.save_history(history)

        urls = article_history.get_processed_urls()
        assert "https://old.com/x" not in urls
        assert "https://new.com/y" in urls

    def test_does_not_overwrite_existing_date(self, tmp_db):
        conn = database.get_db()
        conn.execute("INSERT INTO processed_articles (url, date_added) VALUES (?, ?)",
                     ("https://a.com", datetime.now().strftime("%Y-%m-%d")))
        conn.commit()
        conn.close()

        # Snapshot má jiné (starší) datum — INSERT OR IGNORE ho nesmí přepsat
        history = {"last_updated": None, "articles": {"https://a.com": "2020-01-01"}}
        article_history.save_history(history)

        loaded = article_history.load_history()
        assert loaded["articles"]["https://a.com"] != "2020-01-01"


class TestStripHtml:
    def test_removes_tags(self):
        assert rss_scraper._strip_html("<p>Hello <b>world</b></p>") == "Hello world"

    def test_unescapes_entities(self):
        assert rss_scraper._strip_html("Rock &amp; Roll &lt;3") == "Rock & Roll <3"

    def test_collapses_whitespace(self):
        assert rss_scraper._strip_html("<div>a</div>\n\n<div>b</div>") == "a b"

    def test_empty(self):
        assert rss_scraper._strip_html("") == ""
        assert rss_scraper._strip_html(None) == ""


class TestLoggerSanitization:
    def _make_logger(self):
        lg = logging.getLogger(f"test-sanitize-{id(self)}")
        lg.handlers.clear()
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        handler.setFormatter(logger_module.SanitizingFormatter("%(message)s"))
        lg.addHandler(handler)
        lg.setLevel(logging.DEBUG)
        lg.propagate = False
        return lg, stream

    def test_masks_telegram_bot_token(self):
        lg, stream = self._make_logger()
        lg.info("POST https://api.telegram.org/bot123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw/sendMessage")
        out = stream.getvalue()
        assert "AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw" not in out
        assert "bot***" in out

    def test_masks_token_in_exception_traceback(self):
        lg, stream = self._make_logger()
        try:
            raise ValueError("failed for https://api.telegram.org/bot987654321:AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx/x")
        except ValueError:
            lg.exception("boom")
        out = stream.getvalue()
        assert "AAHxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" not in out
        assert "bot***" in out

    def test_masks_anthropic_key_in_exc_info(self):
        lg, stream = self._make_logger()
        try:
            raise RuntimeError("bad key sk-ant-api03-abcdefghijklmnop")
        except RuntimeError:
            lg.exception("fail")
        out = stream.getvalue()
        assert "sk-ant-api03-abcdefghijklmnop" not in out
        assert "sk-ant-***" in out


class TestFormatTopicsAsReport:
    def test_survives_missing_keys(self):
        # Raw data po selhání Pydantic validace — nesmí spadnout na KeyError
        topics = [{"topic": "GTA 6"}]
        report = claude_analyzer.format_topics_as_report(topics)
        assert "GTA 6" in report
        assert "STATUS TAG: news" in report

    def test_full_topic(self):
        topics = [{
            "topic": "T", "title": "Ti", "angle": "A", "context": "C",
            "hook": "H", "visual": "V", "virality_score": 90, "why_now": "W",
            "sources": ["https://a.com"], "seo_keywords": "x, y",
            "game_name": "G", "status_tag": "leak",
        }]
        report = claude_analyzer.format_topics_as_report(topics)
        assert "VIRALITA: 90/100" in report
        assert "https://a.com" in report
        assert "STATUS TAG: leak" in report

    def test_skips_non_dict(self):
        report = claude_analyzer.format_topics_as_report(["not-a-dict", {"topic": "X"}])
        assert "X" in report


class TestCheckTopicDuplicateGameName:
    def test_matches_on_game_name_field(self):
        """Hra jen v game_name (z data_json), ne v topic/title textu."""
        new_topic = {
            "topic": "Velké odhalení závodní novinky",
            "title": "Nová závodní hra odhalena, datum vydání 2027",
            "game_name": "Clutch",
        }
        recent = [{
            "topic": "Závodní novinka od Maverick Games má datum",
            "title": "Odhalení nové závodní hry, vyjde 2027",
            "game_name": "Clutch",
            "timestamp": datetime.now().isoformat(),
        }]
        is_dup, match = topic_dedup.check_topic_duplicate(new_topic, recent)
        assert is_dup is True
        assert match["match_type"] == "game_name"

    def test_no_match_for_different_game(self):
        new_topic = {"topic": "Zpráva A o něčem", "title": "Titulek A", "game_name": "Half-Life 3"}
        recent = [{
            "topic": "Úplně jiné téma o konzolích",
            "title": "Jiný titulek o hardwaru",
            "game_name": "Portal 3",
            "timestamp": datetime.now().isoformat(),
        }]
        is_dup, _ = topic_dedup.check_topic_duplicate(new_topic, recent)
        assert is_dup is False
