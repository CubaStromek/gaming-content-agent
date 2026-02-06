"""Tests for publish_log module."""

import json
import os
import pytest
from unittest.mock import patch

import publish_log


@pytest.fixture
def log_file(tmp_path):
    """Temporary log file."""
    return str(tmp_path / "test_publish_log.jsonl")


class TestLogDecision:
    def test_logs_entry(self, log_file):
        with patch.object(publish_log, 'LOG_FILE', log_file):
            publish_log.log_decision({
                'action': 'published',
                'score': 4,
                'topic': 'GTA 6',
            })

            assert os.path.exists(log_file)
            with open(log_file, 'r', encoding='utf-8') as f:
                line = f.readline()
            entry = json.loads(line)
            assert entry['action'] == 'published'
            assert entry['score'] == 4
            assert 'timestamp' in entry

    def test_appends_multiple(self, log_file):
        with patch.object(publish_log, 'LOG_FILE', log_file):
            publish_log.log_decision({'action': 'published', 'score': 3})
            publish_log.log_decision({'action': 'skipped', 'score': 0})

            with open(log_file, 'r', encoding='utf-8') as f:
                lines = [l for l in f if l.strip()]
            assert len(lines) == 2


class TestGetStats:
    def test_empty_file(self, log_file):
        with patch.object(publish_log, 'LOG_FILE', log_file):
            stats = publish_log.get_stats()
            assert stats['total'] == 0
            assert stats['published'] == 0
            assert stats['skipped'] == 0

    def test_counts_actions(self, log_file):
        with patch.object(publish_log, 'LOG_FILE', log_file):
            publish_log.log_decision({'action': 'published', 'score': 4})
            publish_log.log_decision({'action': 'published', 'score': 5})
            publish_log.log_decision({'action': 'skipped', 'score': 0})

            stats = publish_log.get_stats()
            assert stats['total'] == 3
            assert stats['published'] == 2
            assert stats['skipped'] == 1

    def test_avg_score(self, log_file):
        with patch.object(publish_log, 'LOG_FILE', log_file):
            publish_log.log_decision({'action': 'published', 'score': 4})
            publish_log.log_decision({'action': 'published', 'score': 6})

            stats = publish_log.get_stats()
            assert stats['avg_score'] == 5.0

    def test_top_sources(self, log_file):
        with patch.object(publish_log, 'LOG_FILE', log_file):
            publish_log.log_decision({
                'action': 'published',
                'score': 4,
                'sources': ['https://ign.com/article1', 'https://ign.com/article2', 'https://pcgamer.com/article1']
            })

            stats = publish_log.get_stats()
            assert len(stats['top_sources']) > 0
            domains = {s['domain'] for s in stats['top_sources']}
            assert 'ign.com' in domains
