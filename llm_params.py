"""Parametry Claude volání, které se liší podle generace modelu.

Moderní modely (Haiku 5.5, Sonnet/Opus 5, Opus 4.7+) vracejí na nedefaultní
temperature HTTP 400 a mají ve výchozím stavu zapnuté přemýšlení: odpověď pak
začíná blokem `thinking` (content[0] není text) a přemýšlení se počítá do
max_tokens. Hloubku přemýšlení řídí `output_config.effort`. Haiku 4.5 naopak
effort odmítá chybou, takže se mu posílá jen temperature jako dřív.

Stejnou logiku má article_writer (_is_modern, _call_api) — tady je vytažená
pro analýzu, dedup a dayreel, které volají Haiku.
"""

import re

_MODERN_MODEL = re.compile(r'-(?:opus|sonnet|haiku|fable|mythos)-5\b|-opus-4-[78]\b')


def is_modern(model: str) -> bool:
    return bool(_MODERN_MODEL.search(model or ''))


def sampling_kwargs(model: str, temperature: float, effort: str = None) -> dict:
    """kwargs pro messages.create/stream: temperature pro staré modely, effort pro moderní.

    Nainstalované SDK 0.76 nezná `output_config` jako pojmenovaný argument, posílá
    se proto syrově v těle requestu (stejně jako v article_writer._call_api).
    """
    if is_modern(model):
        return {"extra_body": {"output_config": {"effort": effort}}} if effort else {}
    return {"temperature": temperature}


def max_tokens_for(model: str, legacy: int, modern: int) -> int:
    """Strop výstupu. U moderních modelů zahrnuje i přemýšlení, proto vyšší."""
    return modern if is_modern(model) else legacy


def response_text(message) -> str:
    """Text odpovědi bez bloků přemýšlení (nesahat na content[0].text)."""
    return "".join(
        b.text for b in message.content if getattr(b, 'type', None) == 'text'
    )
