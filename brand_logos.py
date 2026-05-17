"""Brand logo resolver for featured images.

When RAWG (game database) finds no screenshot, fall back to a curated brand logo
from the WP media library if the article topic matches a known brand keyword.
"""
import re
import unicodedata
from typing import Optional

# Media IDs verified via WP REST API on 2026-05-17.
# Update if logos are replaced; values are wp_posts.ID of attachment.
BRAND_LOGOS = {
    'playstation': 7070,
    'ps plus': 7458,
    'xbox': 6189,
    'ea': 6544,
    'fromsoftware': 7263,
}

# Keyword → brand key. Multi-word keys are checked as substrings; single-word
# keys are matched as whole tokens to avoid e.g. "ea" matching "team".
_KEYWORD_TO_BRAND = {
    # PlayStation family
    'playstation': 'playstation',
    'ps5': 'playstation',
    'ps6': 'playstation',
    'psn': 'playstation',
    'sony': 'playstation',
    'ps plus': 'ps plus',
    'playstation plus': 'ps plus',
    # Xbox family
    'xbox': 'xbox',
    'xbox series': 'xbox',
    'xbox series x': 'xbox',
    'xbox series s': 'xbox',
    'xbox game pass': 'xbox',
    'game pass': 'xbox',
    'microsoft': 'xbox',
    # Publishers
    'electronic arts': 'ea',
    'ea sports': 'ea',
    'fromsoftware': 'fromsoftware',
    'from software': 'fromsoftware',
}

_MULTI_WORD = [(kw, brand) for kw, brand in _KEYWORD_TO_BRAND.items() if ' ' in kw]
_SINGLE_WORD = {kw: brand for kw, brand in _KEYWORD_TO_BRAND.items() if ' ' not in kw}


def _normalize(text: str) -> str:
    if not text:
        return ''
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return text.lower()


def resolve_brand_logo(*texts) -> Optional[int]:
    """Return media ID of brand logo if any of the texts matches a brand keyword.

    Multi-word keywords (e.g. "ps plus") win over single-word ones so that
    "PS Plus v květnu" returns the PS Plus logo, not the generic PlayStation one.
    """
    haystack = _normalize(' '.join(t for t in texts if t))
    if not haystack:
        return None

    for kw, brand in _MULTI_WORD:
        if kw in haystack:
            return BRAND_LOGOS[brand]

    for token in re.findall(r"[a-z0-9]+", haystack):
        brand = _SINGLE_WORD.get(token)
        if brand:
            return BRAND_LOGOS[brand]

    return None
