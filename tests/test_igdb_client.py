"""Testy pro igdb_client — mockované HTTP, žádná živá síť."""

import pytest
import requests

import config
import igdb_client


@pytest.fixture(autouse=True)
def igdb_env(monkeypatch):
    """Testovací credentials + čistý token cache pro každý test."""
    monkeypatch.setattr(config, 'IGDB_CLIENT_ID', 'test-id')
    monkeypatch.setattr(config, 'IGDB_CLIENT_SECRET', 'test-secret')
    monkeypatch.setattr(igdb_client, '_token', None)
    monkeypatch.setattr(igdb_client, '_token_expires_at', 0.0)


class FakeResponse:
    def __init__(self, status_code=200, payload=None, text=''):
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        return self._payload


def wire_post(monkeypatch, games_responses, token_calls=None):
    """Mock requests.post: token endpoint → access_token, games → postupně z listu."""
    counters = {'token': 0, 'games': 0}

    def fake_post(url, **kwargs):
        if url.startswith(igdb_client._TOKEN_URL):
            counters['token'] += 1
            return FakeResponse(payload={'access_token': f"tok{counters['token']}",
                                         'expires_in': 3600})
        counters['games'] += 1
        resp = games_responses[min(counters['games'], len(games_responses)) - 1]
        return resp

    monkeypatch.setattr(igdb_client.requests, 'post', fake_post)
    return counters


GAME_FULL = {
    'name': 'Elden Ring',
    'cover': {'image_id': 'cov1'},
    'artworks': [{'image_id': 'art1'}, {'image_id': 'art2'}],
    'screenshots': [{'image_id': f'sc{i}'} for i in range(1, 8)],
}


class TestSearchGameImage:
    def test_not_configured_skips_http(self, monkeypatch):
        monkeypatch.setattr(config, 'IGDB_CLIENT_ID', '')
        monkeypatch.setattr(igdb_client.requests, 'post',
                            lambda *a, **kw: (_ for _ in ()).throw(AssertionError('HTTP nesmí běžet')))
        assert igdb_client.search_game_image('Elden Ring') is None
        assert igdb_client.fetch_screenshots('Elden Ring') == []

    def test_prefers_artwork_over_screenshot_and_cover(self, monkeypatch):
        wire_post(monkeypatch, [FakeResponse(payload=[GAME_FULL])])
        url = igdb_client.search_game_image('Elden Ring')
        assert url == 'https://images.igdb.com/igdb/image/upload/t_1080p/art1.jpg'

    def test_falls_back_to_screenshot_then_cover(self, monkeypatch):
        game = {'name': 'X', 'cover': {'image_id': 'cov1'},
                'screenshots': [{'image_id': 'sc1'}]}
        wire_post(monkeypatch, [FakeResponse(payload=[game])])
        assert 'sc1' in igdb_client.search_game_image('X')

        igdb_client._token = None  # nový „test“ v rámci téhož mocku
        cover_only = {'name': 'Y', 'cover': {'image_id': 'cov9'}}
        wire_post(monkeypatch, [FakeResponse(payload=[cover_only])])
        assert 'cov9' in igdb_client.search_game_image('Y')

    def test_skips_first_result_without_images(self, monkeypatch):
        dlc = {'name': 'Elden Ring DLC'}  # fulltext hit bez obrázků
        wire_post(monkeypatch, [FakeResponse(payload=[dlc, GAME_FULL])])
        url = igdb_client.search_game_image('Elden Ring')
        assert 'art1' in url

    def test_empty_results_returns_none(self, monkeypatch):
        wire_post(monkeypatch, [FakeResponse(payload=[])])
        assert igdb_client.search_game_image('Neexistuje') is None

    def test_network_error_returns_none(self, monkeypatch):
        def boom(url, **kwargs):
            raise requests.exceptions.Timeout('timeout')
        monkeypatch.setattr(igdb_client.requests, 'post', boom)
        assert igdb_client.search_game_image('Elden Ring') is None
        assert igdb_client.fetch_screenshots('Elden Ring') == []

    def test_na_game_skips_http(self, monkeypatch):
        monkeypatch.setattr(igdb_client.requests, 'post',
                            lambda *a, **kw: (_ for _ in ()).throw(AssertionError('HTTP nesmí běžet')))
        assert igdb_client.search_game_image('N/A') is None
        assert igdb_client.search_game_image('') is None


class TestTokenHandling:
    def test_token_cached_between_calls(self, monkeypatch):
        counters = wire_post(monkeypatch, [FakeResponse(payload=[GAME_FULL]),
                                           FakeResponse(payload=[GAME_FULL])])
        igdb_client.search_game_image('Elden Ring')
        igdb_client.fetch_screenshots('Elden Ring')
        assert counters['token'] == 1

    def test_401_refreshes_token_once(self, monkeypatch):
        counters = wire_post(monkeypatch, [FakeResponse(status_code=401, text='expired'),
                                           FakeResponse(payload=[GAME_FULL])])
        url = igdb_client.search_game_image('Elden Ring')
        assert 'art1' in url
        assert counters['token'] == 2


class TestFetchScreenshots:
    def test_caps_at_max_count(self, monkeypatch):
        wire_post(monkeypatch, [FakeResponse(payload=[GAME_FULL])])
        urls = igdb_client.fetch_screenshots('Elden Ring', max_count=5)
        assert len(urls) == 5
        assert all('t_screenshot_huge' in u for u in urls)

    def test_no_screenshots_returns_empty(self, monkeypatch):
        cover_only = {'name': 'Y', 'cover': {'image_id': 'cov9'}}
        wire_post(monkeypatch, [FakeResponse(payload=[cover_only])])
        assert igdb_client.fetch_screenshots('Y') == []


class TestExactOnly:
    """Značka bez vlastního loga: IGDB smí odpovědět jen na přesnou shodu."""

    def test_name_matches_accepts_exact_and_prefix(self):
        assert igdb_client.name_matches('Roblox', 'Roblox')
        assert igdb_client.name_matches('Roblox', 'Roblox Studio')
        assert igdb_client.name_matches('Pokémon', 'Pokemon Legends')  # bez diakritiky

    def test_name_matches_rejects_incidental_hit(self):
        assert not igdb_client.name_matches('Pokémon', 'Name That Pokemon')
        assert not igdb_client.name_matches(
            'Nintendo', 'Animal Crossing: New Horizons - Nintendo Switch 2 Edition')

    def test_exact_only_discards_mismatch(self, monkeypatch):
        junk = {'name': 'Name That Pokemon', 'artworks': [{'image_id': 'a1'}]}
        wire_post(monkeypatch, [FakeResponse(payload=[junk])])
        assert igdb_client.search_game_image('Pokémon', exact_only=True) is None

    def test_exact_only_keeps_match(self, monkeypatch):
        hit = {'name': 'Roblox', 'artworks': [{'image_id': 'a1'}]}
        wire_post(monkeypatch, [FakeResponse(payload=[hit])])
        assert 'a1' in igdb_client.search_game_image('Roblox', exact_only=True)

    def test_default_is_unrestricted(self, monkeypatch):
        """Reálná hra: fulltext smí vrátit i edici/pokračování."""
        wire_post(monkeypatch, [FakeResponse(payload=[{'name': 'The Witcher IV',
                                                       'artworks': [{'image_id': 'a1'}]}])])
        assert 'a1' in igdb_client.search_game_image('The Witcher')


class TestNonAsciiBody:
    """Regrese: názvy s diakritikou (Pokémon, Ghost of Yōtei) vracely 400.

    `requests` počítá Content-Length jako `len(str)` = počet ZNAKŮ, ale tělo
    odešle v UTF-8 → hlavička kratší než data, server ořízne koncový `;`
    a IGDB odpoví „Syntax Error: Missing `;` at end of query".
    """

    def test_body_is_utf8_bytes(self, monkeypatch):
        sent = {}

        def fake_post(url, **kwargs):
            if url.startswith(igdb_client._TOKEN_URL):
                return FakeResponse(payload={'access_token': 'tok', 'expires_in': 3600})
            sent['data'] = kwargs['data']
            return FakeResponse(payload=[GAME_FULL])

        monkeypatch.setattr(igdb_client.requests, 'post', fake_post)
        igdb_client.search_game_image('Ghost of Yōtei')

        assert isinstance(sent['data'], bytes)
        assert 'Yōtei'.encode('utf-8') in sent['data']
        assert sent['data'].endswith(b';')

    def test_content_length_matches_byte_length(self, monkeypatch):
        """Skutečná příčina: hlavička se musí shodovat s délkou odeslaných dat."""
        sent = {}

        def fake_post(url, **kwargs):
            if url.startswith(igdb_client._TOKEN_URL):
                return FakeResponse(payload={'access_token': 'tok', 'expires_in': 3600})
            sent['prepared'] = requests.Request('POST', url, data=kwargs['data']).prepare()
            return FakeResponse(payload=[GAME_FULL])

        monkeypatch.setattr(igdb_client.requests, 'post', fake_post)
        igdb_client.fetch_screenshots('Pokémon TCG Pocket')

        prepared = sent['prepared']
        body = prepared.body
        if isinstance(body, str):  # str tělo → urllib3 ho pošle jako UTF-8
            body = body.encode('utf-8')
        assert int(prepared.headers['Content-Length']) == len(body)
