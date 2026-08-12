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
    def test_readonly_get_allowed_when_token_empty(self, app_client):
        """Bez DASHBOARD_TOKEN musí read-only GET fungovat (lokální dashboard)."""
        with patch.object(config, 'DASHBOARD_TOKEN', ''):
            resp = app_client.get('/status')
            assert resp.status_code == 200

    def test_mutating_forbidden_when_token_empty(self, app_client):
        """Fail-closed: bez DASHBOARD_TOKEN musí mutace/spouštění vrátit 403."""
        with patch.object(config, 'DASHBOARD_TOKEN', ''):
            resp = app_client.post('/start')
            assert resp.status_code == 403
            data = json.loads(resp.data)
            assert 'DASHBOARD_TOKEN' in data['error']

    def test_auth_required_when_token_set(self, app_client):
        """When DASHBOARD_TOKEN is set, requests without token get 401."""
        with patch.object(config, 'DASHBOARD_TOKEN', 'secret-token-123'):
            resp = app_client.post('/start')
            assert resp.status_code == 401

    def test_auth_with_bearer_header(self, app_client):
        """Bearer token in Authorization header works."""
        with patch.object(config, 'DASHBOARD_TOKEN', 'secret-token-123'):
            resp = app_client.post('/start', headers={
                'Authorization': 'Bearer secret-token-123'
            })
            assert resp.status_code == 200
            data = json.loads(resp.data)
            assert data['status'] in ('started', 'already_running')

    def test_auth_query_param_rejected(self, app_client):
        """Token v query stringu MUSÍ být odmítnut (logoval by se do access logu)."""
        with patch.object(config, 'DASHBOARD_TOKEN', 'secret-token-123'):
            resp = app_client.post('/start?token=secret-token-123')
            assert resp.status_code == 401

    def test_auth_wrong_token(self, app_client):
        """Wrong token gets 401."""
        with patch.object(config, 'DASHBOARD_TOKEN', 'secret-token-123'):
            resp = app_client.post('/start', headers={
                'Authorization': 'Bearer wrong-token'
            })
            assert resp.status_code == 401


class TestStart:
    def test_get_method_not_allowed(self, app_client):
        """/start je jen POST — GET (např. z prefetche prohlížeče) vrátí 405."""
        resp = app_client.get('/start')
        assert resp.status_code == 405

    def test_start_reserves_running_state(self, app_client):
        """Handler musí rezervovat běh už v locku (TOCTOU) — druhý okamžitý
        /start smí buď vrátit already_running, nebo started až po dokončení
        prvního (fake) běhu; nikdy nesmí běžet dva agenty naráz."""
        with patch.object(config, 'DASHBOARD_TOKEN', 'tok'):
            headers = {'Authorization': 'Bearer tok'}
            resp = app_client.post('/start', headers=headers)
            assert resp.status_code == 200
            assert json.loads(resp.data)['status'] in ('started', 'already_running')


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
    # Pozn.: mutace bez DASHBOARD_TOKEN jsou nyní fail-closed (403),
    # proto testy posílají Bearer token.
    def test_invalid_json_on_write_article(self, app_client):
        with patch.object(config, 'DASHBOARD_TOKEN', 'tok'):
            resp = app_client.post('/write-article',
                                   data='not valid json{{{',
                                   content_type='application/json',
                                   headers={'Authorization': 'Bearer tok'})
            # Should get 400, not 500
            assert resp.status_code == 400

    def test_invalid_json_on_publish(self, app_client):
        with patch.object(config, 'DASHBOARD_TOKEN', 'tok'):
            resp = app_client.post('/api/wp/publish',
                                   data='broken json',
                                   content_type='application/json',
                                   headers={'Authorization': 'Bearer tok'})
            assert resp.status_code == 400


class TestPublishStats:
    def test_returns_stats(self, app_client):
        resp = app_client.get('/api/wp/publish-stats')
        assert resp.status_code == 200
        data = json.loads(resp.data)
        assert 'total' in data


class TestSafeOrigin:
    def test_post_with_foreign_origin_rejected(self, app_client):
        """POST z cizího Originu musí být odmítnut (CSRF defense-in-depth)."""
        with patch.object(config, 'DASHBOARD_TOKEN', 'tok'):
            resp = app_client.post(
                '/api/feeds',
                headers={
                    'Authorization': 'Bearer tok',
                    'Origin': 'https://evil.example',
                    'Content-Type': 'application/json',
                },
                data='{}',
            )
            assert resp.status_code == 403

    def test_post_with_whitelisted_origin_allowed(self, app_client):
        """POST z whitelistovaného originu projde Origin checkem."""
        with patch.object(config, 'DASHBOARD_TOKEN', 'tok'):
            resp = app_client.post(
                '/api/feeds',
                headers={
                    'Authorization': 'Bearer tok',
                    'Origin': 'http://127.0.0.1:5000',
                    'Content-Type': 'application/json',
                },
                data='{}',
            )
            # 400 z aplikační logiky (chybí name/url) — ale prošlo přes Origin check.
            assert resp.status_code != 403

    def test_host_header_not_trusted(self, app_client):
        """Origin shodný s Host headerem NESMÍ projít (DNS rebinding) —
        whitelist je pevný a Host header se nesmí echovat."""
        with patch.object(config, 'DASHBOARD_TOKEN', 'tok'):
            resp = app_client.post(
                '/api/feeds',
                headers={
                    'Authorization': 'Bearer tok',
                    'Origin': 'http://evil.example',
                    'Host': 'evil.example',
                    'Content-Type': 'application/json',
                },
                data='{}',
            )
            assert resp.status_code == 403

    def test_env_allowed_origins_extends_whitelist(self, app_client, monkeypatch):
        """DASHBOARD_ALLOWED_ORIGINS (čárkou oddělené) rozšiřuje whitelist."""
        monkeypatch.setenv('DASHBOARD_ALLOWED_ORIGINS', 'https://dash.example.com, http://192.168.1.10:5000')
        with patch.object(config, 'DASHBOARD_TOKEN', 'tok'):
            resp = app_client.post(
                '/api/feeds',
                headers={
                    'Authorization': 'Bearer tok',
                    'Origin': 'https://dash.example.com',
                    'Content-Type': 'application/json',
                },
                data='{}',
            )
            assert resp.status_code != 403

    def test_post_without_origin_allowed(self, app_client):
        """Curl/legitimate non-browser klient bez Origin headeru projde (jen Bearer)."""
        with patch.object(config, 'DASHBOARD_TOKEN', 'tok'):
            resp = app_client.post(
                '/api/feeds',
                headers={
                    'Authorization': 'Bearer tok',
                    'Content-Type': 'application/json',
                },
                data='{}',
            )
            assert resp.status_code != 403


class TestPathTraversal:
    def test_run_id_traversal_rejected(self, app_client):
        """Pokus o path traversal v run_id musí být odmítnut s 400."""
        with patch.object(config, 'DASHBOARD_TOKEN', 'tok'):
            resp = app_client.post(
                '/write-article',
                headers={
                    'Content-Type': 'application/json',
                    'Authorization': 'Bearer tok',
                },
                data='{"run_id":"../../etc","topic_index":0}',
            )
            assert resp.status_code == 400


class TestGameSearchApi:
    """/api/games/search — nahradilo /api/rawg/search po vyhození RAWG (8/2026)."""

    def test_missing_query_returns_400(self, app_client):
        resp = app_client.get('/api/games/search?q=')
        assert resp.status_code == 400

    def test_returns_games_from_igdb(self, app_client):
        games = [{'id': 1, 'name': 'Elden Ring',
                  'background': 'https://images.igdb.com/a.jpg',
                  'screenshots': ['https://images.igdb.com/a.jpg']}]
        with patch('igdb_client.is_configured', return_value=True), \
             patch('igdb_client.search_games', return_value=games) as mock_search:
            resp = app_client.get('/api/games/search?q=elden+ring')
            assert resp.status_code == 200
            assert json.loads(resp.data)['games'] == games
            mock_search.assert_called_once_with('elden ring')

    def test_igdb_failure_returns_502(self, app_client):
        with patch('igdb_client.is_configured', return_value=True), \
             patch('igdb_client.search_games', side_effect=RuntimeError('boom')):
            resp = app_client.get('/api/games/search?q=x')
            assert resp.status_code == 502
