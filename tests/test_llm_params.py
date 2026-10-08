"""Testy parametrů volání podle generace modelu (migrace na Haiku 5.5)."""

from types import SimpleNamespace

import llm_params


class TestIsModern:
    def test_haiku_55_is_modern(self):
        assert llm_params.is_modern("claude-haiku-5-5")

    def test_haiku_45_is_legacy(self):
        assert not llm_params.is_modern("claude-haiku-4-5-20251001")
        assert not llm_params.is_modern("claude-haiku-4-5")

    def test_other_models(self):
        assert llm_params.is_modern("claude-opus-5")
        assert llm_params.is_modern("claude-sonnet-5-5")
        assert not llm_params.is_modern("claude-sonnet-4-6")


class TestSamplingKwargs:
    def test_modern_drops_temperature_and_sends_effort(self):
        """Haiku 5.5 vrací na temperature=0/0.7 HTTP 400."""
        kw = llm_params.sampling_kwargs("claude-haiku-5-5", 0, effort="low")
        assert "temperature" not in kw
        assert kw == {"extra_body": {"output_config": {"effort": "low"}}}

    def test_modern_without_effort_is_empty(self):
        assert llm_params.sampling_kwargs("claude-haiku-5-5", 0.7) == {}

    def test_legacy_keeps_temperature_and_no_effort(self):
        """Haiku 4.5 effort odmítá — posílá se jen temperature jako dřív."""
        kw = llm_params.sampling_kwargs("claude-haiku-4-5-20251001", 0, effort="low")
        assert kw == {"temperature": 0}


class TestMaxTokens:
    def test_modern_gets_room_for_thinking(self):
        assert llm_params.max_tokens_for("claude-haiku-5-5", 250, 2000) == 2000

    def test_legacy_unchanged(self):
        assert llm_params.max_tokens_for("claude-haiku-4-5", 250, 2000) == 250


class TestResponseText:
    def test_skips_thinking_blocks(self):
        """Odpověď moderního modelu začíná blokem thinking — content[0].text by spadlo."""
        msg = SimpleNamespace(content=[
            SimpleNamespace(type="thinking", thinking="", signature="x"),
            SimpleNamespace(type="text", text="VÝROK: OK"),
        ])
        assert llm_params.response_text(msg) == "VÝROK: OK"

    def test_empty_content(self):
        assert llm_params.response_text(SimpleNamespace(content=[])) == ""
