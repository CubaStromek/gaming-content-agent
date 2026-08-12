"""Testy pro brand_logos — výběr featured image pro brand/platform témata."""
import pytest

import brand_logos as bl


class TestResolveBrandLogoStrict:
    """Brand-first gate: logo jen když je game_name samotný brand/platforma."""

    @pytest.mark.parametrize('name,expected_brand', [
        ('Steam', 'steam'),
        ('Steam Deck', 'steam'),
        ('Valve', 'steam'),
        ('PlayStation', 'playstation'),
        ('PlayStation 5 Pro', 'playstation'),
        ('PS5', 'playstation'),
        ('Sony', 'playstation'),
        ('PS Plus', 'ps plus'),
        ('PlayStation Plus', 'ps plus'),
        ('Xbox', 'xbox'),
        ('Xbox Series X', 'xbox'),
        ('Xbox Game Pass', 'xbox'),
        ('Game Pass', 'xbox'),
        ('Microsoft', 'xbox'),
    ])
    def test_brand_topics_return_logo(self, name, expected_brand):
        assert bl.resolve_brand_logo_strict(name) == bl.BRAND_LOGOS[expected_brand]

    @pytest.mark.parametrize('name', [
        # skutečné hry obsahující brand token nesmí dostat logo (jdou do IGDB)
        'Microsoft Flight Simulator',
        'EA Sports FC 26',
        'Steamworld Dig',
        # běžné hry
        'Gothic',
        'GTA 6',
        'Elden Ring',
        'S.T.A.L.K.E.R. 2',
        'Half-Life 3',
    ])
    def test_real_games_return_none(self, name):
        assert bl.resolve_brand_logo_strict(name) is None

    def test_empty_and_none_safe(self):
        assert bl.resolve_brand_logo_strict('') is None
        assert bl.resolve_brand_logo_strict(None) is None


class TestResolveBrandLogoFallback:
    """Původní volná shoda (fallback po hledání obrázku) zůstává funkční."""

    def test_substring_match_in_title(self):
        assert bl.resolve_brand_logo('Gothic', 'Gothic míří na Xbox Game Pass') \
            == bl.BRAND_LOGOS['xbox']

    def test_multi_word_wins_over_single(self):
        # "PS Plus v květnu" → PS Plus logo, ne obecné PlayStation
        assert bl.resolve_brand_logo('PS Plus v květnu') == bl.BRAND_LOGOS['ps plus']

    def test_ea_token_does_not_match_inside_word(self):
        assert bl.resolve_brand_logo('Team Fortress') is None

    def test_no_match(self):
        assert bl.resolve_brand_logo('Hollow Knight Silksong') is None
