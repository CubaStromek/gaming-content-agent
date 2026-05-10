"""Tests for /api/decisions/* endpoints."""

import json
from unittest.mock import patch

import config
import publish_log


class TestDecisionsRuns:
    def test_returns_runs(self, app_client):
        publish_log.log_decision({'action': 'published', 'run_id': 'r1', 'topic': 'A', 'score': 80})
        publish_log.log_decision({'action': 'published', 'run_id': 'r2', 'topic': 'B', 'score': 70})

        with patch.object(config, 'DASHBOARD_TOKEN', ''):
            resp = app_client.get('/api/decisions/runs')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert len(data['runs']) == 2

    def test_requires_auth_when_token_set(self, app_client):
        with patch.object(config, 'DASHBOARD_TOKEN', 'tok'):
            resp = app_client.get('/api/decisions/runs')
        assert resp.status_code == 401


class TestDecisionsRun:
    def test_invalid_run_id_rejected(self, app_client):
        # Mezera/slash nesplňuje [\w\-]+ regex → 400 (path traversal guard).
        with patch.object(config, 'DASHBOARD_TOKEN', ''):
            resp = app_client.get('/api/decisions/run/has spaces')
        assert resp.status_code == 400

    def test_returns_decisions_for_run(self, app_client):
        publish_log.log_decision({'action': 'published', 'run_id': 'r1', 'topic': 'A', 'score': 80})
        publish_log.log_decision({'action': 'skipped', 'reason': 'duplicate_topic',
                                  'run_id': 'r1', 'topic': 'B', 'score': 60})
        publish_log.log_decision({'action': 'published', 'run_id': 'other', 'topic': 'X', 'score': 90})

        with patch.object(config, 'DASHBOARD_TOKEN', ''):
            resp = app_client.get('/api/decisions/run/r1')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['run_id'] == 'r1'
        assert len(data['decisions']) == 2


class TestDecisionsTimeline:
    def test_returns_buckets(self, app_client):
        publish_log.log_decision({'action': 'published', 'run_id': 'r1', 'topic': 'A', 'score': 80})

        with patch.object(config, 'DASHBOARD_TOKEN', ''):
            resp = app_client.get('/api/decisions/timeline?days=7')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['days'] == 7
        assert len(data['buckets']) >= 1

    def test_invalid_days_clamped(self, app_client):
        with patch.object(config, 'DASHBOARD_TOKEN', ''):
            resp = app_client.get('/api/decisions/timeline?days=99999')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['days'] == 90  # clamped to max


class TestDecisionsScoring:
    def test_excludes_zero_scores(self, app_client):
        publish_log.log_decision({'action': 'published', 'run_id': 'r1', 'topic': 'A', 'score': 80})
        publish_log.log_decision({'action': 'skipped', 'reason': 'no_source_texts',
                                  'run_id': 'r1', 'topic': 'B', 'score': 0})

        with patch.object(config, 'DASHBOARD_TOKEN', ''):
            resp = app_client.get('/api/decisions/scoring?days=7')
        data = json.loads(resp.data)
        assert len(data['points']) == 1
        assert data['points'][0]['topic'] == 'A'
