"""Tests for web_app routes."""

import json
import pytest
from unittest.mock import patch

import config


class TestHealthcheck:
    def test_returns_ok(self, app_client):
        resp = app_client.get('/health')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert data['status'] == 'ok'
        assert 'uptime' in data
        assert data['version'] == '1.0'


class TestIndex:
    def test_returns_html(self, app_client):
        resp = app_client.get('/')
        assert resp.status_code == 200
        assert b'<!DOCTYPE html>' in resp.data


class TestStatus:
    def test_returns_running_status(self, app_client):
        resp = app_client.get('/status')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert 'running' in data


class TestHistory:
    def test_returns_runs(self, app_client):
        resp = app_client.get('/history')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert 'runs' in data


class TestAuth:
    def test_no_auth_required_when_token_empty(self, app_client):
        """When DASHBOARD_TOKEN is empty, auth is disabled."""
        with patch.object(config, 'DASHBOARD_TOKEN', ''):
            resp = app_client.get('/start')
            # Should not return 401 (might return started or already_running)
            assert resp.status_code != 401

    def test_auth_required_when_token_set(self, app_client):
        """When DASHBOARD_TOKEN is set, requests without token get 401."""
        with patch.object(config, 'DASHBOARD_TOKEN', 'secret-token-123'):
            resp = app_client.get('/start')
            assert resp.status_code == 401

    def test_auth_with_bearer_header(self, app_client):
        """Bearer token in Authorization header works."""
        with patch.object(config, 'DASHBOARD_TOKEN', 'secret-token-123'):
            resp = app_client.get('/start', headers={
                'Authorization': 'Bearer secret-token-123'
            })
            assert resp.status_code != 401

    def test_auth_with_query_param(self, app_client):
        """Token in query param works."""
        with patch.object(config, 'DASHBOARD_TOKEN', 'secret-token-123'):
            resp = app_client.get('/start?token=secret-token-123')
            assert resp.status_code != 401

    def test_auth_wrong_token(self, app_client):
        """Wrong token gets 401."""
        with patch.object(config, 'DASHBOARD_TOKEN', 'secret-token-123'):
            resp = app_client.get('/start', headers={
                'Authorization': 'Bearer wrong-token'
            })
            assert resp.status_code == 401


class TestHistoryRunId:
    def test_invalid_run_id_rejected(self, app_client):
        resp = app_client.get('/history/../../../etc/passwd')
        assert resp.status_code in (400, 404)

    def test_valid_run_id_format(self, app_client):
        resp = app_client.get('/history/20250115_100000')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert 'id' in data


class TestJsonSafety:
    def test_invalid_json_on_write_article(self, app_client):
        with patch.object(config, 'DASHBOARD_TOKEN', ''):
            resp = app_client.post('/write-article',
                                   data='not valid json{{{',
                                   content_type='application/json')
            # Should get 400, not 500
            assert resp.status_code == 400

    def test_invalid_json_on_publish(self, app_client):
        with patch.object(config, 'DASHBOARD_TOKEN', ''):
            resp = app_client.post('/api/wp/publish',
                                   data='broken json',
                                   content_type='application/json')
            assert resp.status_code == 400


class TestPublishStats:
    def test_returns_stats(self, app_client):
        resp = app_client.get('/api/wp/publish-stats')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert 'total' in data
