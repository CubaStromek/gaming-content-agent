"""Tests for Pydantic models (models.py)."""

import pytest
from models import Topic, AnalysisResult


class TestTopic:
    def test_valid_topic(self):
        topic = Topic(
            topic="GTA 6",
            title="GTA 6: Nový trailer",
            angle="Analýza",
            context="Rockstar vydal trailer.",
            hook="10M zhlédnutí",
            visual="Vice City neon",
            virality_score=90,
            why_now="Právě vyšel",
            sources=["https://ign.com/gta6"],
            seo_keywords="GTA 6, trailer",
            game_name="Grand Theft Auto VI",
        )
        assert topic.topic == "GTA 6"
        assert topic.virality_score == 90

    def test_virality_score_bounds(self):
        with pytest.raises(Exception):
            Topic(
                topic="Test", title="T", angle="A", context="C",
                hook="H", visual="V", virality_score=0,
                why_now="W", sources=[], seo_keywords="K",
            )

    def test_default_game_name(self):
        topic = Topic(
            topic="Test", title="T", angle="A", context="C",
            hook="H", visual="V", virality_score=50,
            why_now="W", sources=[], seo_keywords="K",
        )
        assert topic.game_name == "N/A"

    def test_model_dump(self):
        topic = Topic(
            topic="Test", title="T", angle="A", context="C",
            hook="H", visual="V", virality_score=50,
            why_now="W", sources=["https://example.com"], seo_keywords="K",
            game_name="Test Game",
        )
        d = topic.model_dump()
        assert isinstance(d, dict)
        assert d["topic"] == "Test"
        assert d["sources"] == ["https://example.com"]


class TestAnalysisResult:
    def test_valid_result(self):
        result = AnalysisResult(topics=[
            Topic(
                topic="Test", title="T", angle="A", context="C",
                hook="H", visual="V", virality_score=50,
                why_now="W", sources=[], seo_keywords="K",
            )
        ])
        assert len(result.topics) == 1

    def test_empty_topics(self):
        result = AnalysisResult(topics=[])
        assert len(result.topics) == 0

    def test_model_validate_from_dict(self):
        data = {
            "topics": [{
                "topic": "GTA 6", "title": "T", "angle": "A",
                "context": "C", "hook": "H", "visual": "V",
                "virality_score": 85, "why_now": "W",
                "sources": ["https://ign.com"], "seo_keywords": "K",
                "game_name": "Grand Theft Auto VI",
            }]
        }
        result = AnalysisResult.model_validate(data)
        assert result.topics[0].topic == "GTA 6"
        assert result.topics[0].virality_score == 85
