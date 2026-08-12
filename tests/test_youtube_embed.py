"""Testy youtube_embed — flat search, kontrola embedovatelnosti, výběr kandidáta.

Vše mockované, žádný yt-dlp subprocess. Reálný kontext: plná extrakce padala
na age-restricted výsledcích ("Sign in to confirm your age") a bot-checku,
takže embed v produkci nefungoval od 21. 7. 2026. Flat search + check_embeddable
navíc řeší, že age-restricted video by v embedu na webu stejně nehrálo.
"""

import json
import subprocess

import youtube_embed as ye


class FakeCompleted:
    def __init__(self, returncode=0, stdout='', stderr=''):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def _video_json(vid='abc', age_limit=0, playable=True):
    return json.dumps({
        'id': vid, 'title': 'T',
        'webpage_url': f'https://www.youtube.com/watch?v={vid}',
        'age_limit': age_limit, 'playable_in_embed': playable,
    })


class TestSearchYoutube:
    def test_parses_flat_results(self, monkeypatch):
        lines = '\n'.join(
            json.dumps({'id': f'v{i}', 'title': f't{i}', 'url': f'u{i}'})
            for i in range(3))
        monkeypatch.setattr(ye.subprocess, 'run', lambda *a, **kw: FakeCompleted(0, lines))
        videos = ye.search_youtube('q')
        assert [v['id'] for v in videos] == ['v0', 'v1', 'v2']

    def test_partial_results_despite_error(self, monkeypatch):
        """returncode != 0, ale stdout má výsledky → použijí se (dřív se zahodily)."""
        line = json.dumps({'id': 'v1', 'title': 't', 'url': 'u'})
        monkeypatch.setattr(ye.subprocess, 'run',
                            lambda *a, **kw: FakeCompleted(1, line, 'ERROR: neco'))
        assert len(ye.search_youtube('q')) == 1

    def test_url_fallback_from_id(self, monkeypatch):
        """Flat entry bez url/webpage_url → složí se z ID."""
        monkeypatch.setattr(ye.subprocess, 'run',
                            lambda *a, **kw: FakeCompleted(0, json.dumps({'id': 'xyz', 'title': 't'})))
        assert ye.search_youtube('q')[0]['url'] == 'https://www.youtube.com/watch?v=xyz'


class TestCheckEmbeddable:
    def test_ok_video(self, monkeypatch):
        monkeypatch.setattr(ye.subprocess, 'run', lambda *a, **kw: FakeCompleted(0, _video_json()))
        assert ye.check_embeddable('abc') is True

    def test_age_limit_from_json(self, monkeypatch):
        monkeypatch.setattr(ye.subprocess, 'run',
                            lambda *a, **kw: FakeCompleted(0, _video_json(age_limit=18)))
        assert ye.check_embeddable('abc') is False

    def test_embed_disabled(self, monkeypatch):
        monkeypatch.setattr(ye.subprocess, 'run',
                            lambda *a, **kw: FakeCompleted(0, _video_json(playable=False)))
        assert ye.check_embeddable('abc') is False

    def test_age_gate_error(self, monkeypatch):
        monkeypatch.setattr(ye.subprocess, 'run',
                            lambda *a, **kw: FakeCompleted(1, '', 'ERROR: Sign in to confirm your age.'))
        assert ye.check_embeddable('abc') is False

    def test_bot_check_is_unknown(self, monkeypatch):
        """Bot-check blokuje jen náš scraper, ne návštěvníky → None, ne False."""
        monkeypatch.setattr(ye.subprocess, 'run',
                            lambda *a, **kw: FakeCompleted(1, '', "ERROR: Sign in to confirm you're not a bot"))
        assert ye.check_embeddable('abc') is None

    def test_timeout_is_unknown(self, monkeypatch):
        def boom(*a, **kw):
            raise subprocess.TimeoutExpired(cmd='yt-dlp', timeout=30)
        monkeypatch.setattr(ye.subprocess, 'run', boom)
        assert ye.check_embeddable('abc') is None


class TestTitleMatchesGame:
    def test_unrelated_movie_rejected(self):
        """Reálný případ: indie 'Red Odyssey' dostala trailer na Jasona Bourna."""
        assert ye.title_matches_game(
            'Jason Bourne 6 (2026) - First Trailer | Matt Damon Returns',
            'Red Odyssey: Legacy of Man') is False

    def test_partial_title_match_passes(self):
        """Volnost: FF 14 vs XIV — stačí polovina tokenů."""
        assert ye.title_matches_game(
            'FINAL FANTASY XIV: Evercold Teaser Trailer', 'Final Fantasy 14') is True

    def test_concept_marker_rejected(self):
        """Fanouškovské 'concept' trailery neexistujících filmů."""
        assert ye.title_matches_game(
            'MECCHA CHAMELEON MOVIE Trailer (2026) Concept', 'Meccha Chameleon') is False

    def test_movie_with_shared_word_rejected(self):
        """Nolanův film The Odyssey ≠ Assassin's Creed Odyssey (1/3 tokenů)."""
        assert ye.title_matches_game(
            'The Odyssey | Official New Trailer', "Assassin's Creed Odyssey") is False

    def test_dotted_acronym_title_matches(self):
        """Tečkovaný akronym v titulku: 'stalker' musí matchnout 'S.T.A.L.K.E.R.'."""
        assert ye.title_matches_game(
            'S.T.A.L.K.E.R. 2: Cost of Hope — Release Date Reveal', 'Stalker 2') is True

    def test_acronym_only_game_name(self):
        """game_name samý akronym → porovnání celých zkolabovaných názvů."""
        assert ye.title_matches_game(
            'S.T.A.L.K.E.R. 2: Cost of Hope — Announcement Trailer', 'S.T.A.L.K.E.R. 2') is True
        assert ye.title_matches_game(
            'Jason Bourne 6 - First Trailer', 'S.T.A.L.K.E.R. 2') is False


class TestFindEmbeddableVideo:
    @staticmethod
    def _candidates():
        return [{'id': 'a', 'title': 'A', 'url': 'ua'},
                {'id': 'b', 'title': 'B', 'url': 'ub'},
                {'id': 'c', 'title': 'C', 'url': 'uc'}]

    def test_skips_age_restricted(self, monkeypatch):
        """Reálný případ Onimusha: první DVA kandidáti 18+ → bere se třetí."""
        monkeypatch.setattr(ye, 'search_youtube', lambda q: self._candidates())
        verdicts = {'a': False, 'b': False, 'c': None}
        monkeypatch.setattr(ye, 'check_embeddable', lambda vid: verdicts[vid])
        assert ye.find_embeddable_video('q')['id'] == 'c'

    def test_first_ok_wins(self, monkeypatch):
        monkeypatch.setattr(ye, 'search_youtube', lambda q: self._candidates())
        monkeypatch.setattr(ye, 'check_embeddable', lambda vid: True)
        assert ye.find_embeddable_video('q')['id'] == 'a'

    def test_all_blocked_returns_none(self, monkeypatch):
        monkeypatch.setattr(ye, 'search_youtube', lambda q: self._candidates())
        monkeypatch.setattr(ye, 'check_embeddable', lambda vid: False)
        assert ye.find_embeddable_video('q') is None

    def test_no_results(self, monkeypatch):
        monkeypatch.setattr(ye, 'search_youtube', lambda q: [])
        assert ye.find_embeddable_video('q') is None

    def test_title_filter_skips_mismatched(self, monkeypatch):
        candidates = [{'id': 'movie', 'title': 'Jason Bourne 6 - First Trailer', 'url': 'u1'},
                      {'id': 'game', 'title': 'Red Odyssey - Official Trailer', 'url': 'u2'}]
        monkeypatch.setattr(ye, 'search_youtube', lambda q: candidates)
        monkeypatch.setattr(ye, 'check_embeddable', lambda vid: True)
        found = ye.find_embeddable_video('q', game_name='Red Odyssey: Legacy of Man')
        assert found['id'] == 'game'

    def test_no_game_name_no_title_filter(self, monkeypatch):
        candidates = [{'id': 'movie', 'title': 'Jason Bourne 6 - First Trailer', 'url': 'u1'}]
        monkeypatch.setattr(ye, 'search_youtube', lambda q: candidates)
        monkeypatch.setattr(ye, 'check_embeddable', lambda vid: True)
        assert ye.find_embeddable_video('q')['id'] == 'movie'


class TestInsertPosition:
    def test_embed_before_first_h2_without_keyword(self):
        """Bez zmínky o videu jde embed na konec úvodu (PŘED <h2>, ne za něj)."""
        html = '<p>Úvod bez klíčových slov.</p><h2>Sekce</h2><p>Text.</p>'
        out = ye.force_embed_youtube(html, 'vidX')
        assert out.index('vidX') < out.index('<h2>')

    def test_embed_after_keyword_paragraph(self):
        html = '<p>Úvod.</p><p>Vyšel nový trailer.</p><h2>Sekce</h2>'
        out = ye.force_embed_youtube(html, 'vidX')
        assert out.index('trailer') < out.index('vidX') < out.index('<h2>')
