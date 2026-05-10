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


class TestQueryByRun:
    def test_returns_only_matching_run(self):
        publish_log.log_decision({'action': 'published', 'run_id': 'r1', 'topic': 'A', 'score': 80})
        publish_log.log_decision({'action': 'skipped', 'reason': 'duplicate_topic',
                                  'run_id': 'r1', 'topic': 'B', 'score': 60})
        publish_log.log_decision({'action': 'published', 'run_id': 'r2', 'topic': 'C', 'score': 70})

        r1 = publish_log.query_by_run('r1')
        r2 = publish_log.query_by_run('r2')

        assert len(r1) == 2
        assert len(r2) == 1
        topics = {d['topic'] for d in r1}
        assert topics == {'A', 'B'}
        assert r2[0]['topic'] == 'C'

    def test_empty_run_id_returns_empty(self):
        publish_log.log_decision({'action': 'published', 'run_id': 'r1', 'topic': 'A', 'score': 80})
        assert publish_log.query_by_run('') == []

    def test_unknown_run_id(self):
        publish_log.log_decision({'action': 'published', 'run_id': 'r1', 'topic': 'A', 'score': 80})
        assert publish_log.query_by_run('nonexistent') == []

    def test_data_includes_dedup_match(self):
        publish_log.log_decision({
            'action': 'skipped',
            'reason': 'duplicate_topic',
            'run_id': 'r1',
            'topic': 'GTA 6 trailer',
            'score': 90,
            'dedup_match': {'topic': 'GTA 6 reveal', 'sim_score': 0.78, 'match_type': 'jaccard'},
        })
        rows = publish_log.query_by_run('r1')
        assert rows[0]['data']['dedup_match']['sim_score'] == 0.78


class TestQueryTimeline:
    def test_buckets_by_day(self):
        publish_log.log_decision({'action': 'published', 'run_id': 'r1', 'topic': 'A', 'score': 80})
        publish_log.log_decision({'action': 'skipped', 'reason': 'no_source_texts',
                                  'run_id': 'r1', 'topic': 'B', 'score': 60})

        buckets = publish_log.query_timeline(days=1)
        assert len(buckets) == 1
        b = buckets[0]
        assert b['published'] == 1
        assert b['skipped'] == 1
        assert b['skipped_by_reason']['no_source_texts'] == 1
        assert b['avg_virality'] == 80.0

    def test_filters_proposed_action(self):
        # action=proposed se v timeline neagregae (jen published/skipped)
        publish_log.log_decision({'action': 'proposed', 'run_id': 'r1', 'topics': []})
        publish_log.log_decision({'action': 'published', 'run_id': 'r1', 'topic': 'A', 'score': 50})
        buckets = publish_log.query_timeline(days=1)
        assert buckets[0]['published'] == 1
        assert buckets[0]['skipped'] == 0


class TestQuerySkipReasons:
    def test_groups_by_reason_with_examples(self):
        for i in range(7):
            publish_log.log_decision({
                'action': 'skipped',
                'reason': 'duplicate_topic',
                'run_id': f'r{i}',
                'topic': f'Topic {i}',
                'score': 50 + i,
            })
        publish_log.log_decision({'action': 'skipped', 'reason': 'no_source_texts',
                                  'run_id': 'rx', 'topic': 'X', 'score': 30})

        result = publish_log.query_skip_reasons(days=30, limit=3)
        assert 'duplicate_topic' in result
        assert result['duplicate_topic']['count'] == 7
        # limit=3 — examples cap
        assert len(result['duplicate_topic']['examples']) == 3
        assert result['no_source_texts']['count'] == 1


class TestQueryScoring:
    def test_only_scored_entries(self):
        publish_log.log_decision({'action': 'published', 'run_id': 'r1', 'topic': 'A', 'score': 80})
        publish_log.log_decision({'action': 'skipped', 'reason': 'duplicate_topic',
                                  'run_id': 'r1', 'topic': 'B', 'score': 60})
        publish_log.log_decision({'action': 'published', 'run_id': 'r1', 'topic': 'C', 'score': 0})  # ignore
        publish_log.log_decision({'action': 'proposed', 'run_id': 'r1', 'topics': []})  # ignore

        points = publish_log.query_scoring(days=30)
        assert len(points) == 2
        topics = {p['topic'] for p in points}
        assert topics == {'A', 'B'}
        skipped = next(p for p in points if p['action'] == 'skipped')
        assert skipped['reason'] == 'duplicate_topic'


class TestQueryRecentRuns:
    def test_groups_by_run_id(self):
        publish_log.log_decision({'action': 'proposed', 'run_id': 'r1', 'topics': []})
        publish_log.log_decision({'action': 'published', 'run_id': 'r1', 'topic': 'A', 'score': 80})
        publish_log.log_decision({'action': 'skipped', 'reason': 'duplicate_topic',
                                  'run_id': 'r1', 'topic': 'B', 'score': 60})
        publish_log.log_decision({'action': 'published', 'run_id': 'r2', 'topic': 'C', 'score': 70})

        runs = publish_log.query_recent_runs(limit=10)
        assert len(runs) == 2
        run_ids = [r['run_id'] for r in runs]
        assert 'r1' in run_ids
        assert 'r2' in run_ids
        r1 = next(r for r in runs if r['run_id'] == 'r1')
        assert r1['published'] == 1
        assert r1['skipped'] == 1
        assert r1['proposed'] == 1

    def test_skips_entries_without_run_id(self):
        publish_log.log_decision({'action': 'published', 'topic': 'NoRun', 'score': 40})
        publish_log.log_decision({'action': 'published', 'run_id': 'r1', 'topic': 'A', 'score': 80})

        runs = publish_log.query_recent_runs(limit=10)
        assert len(runs) == 1
        assert runs[0]['run_id'] == 'r1'
