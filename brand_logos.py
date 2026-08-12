"""Brand logo resolver for featured images.

When IGDB (game database) finds no screenshot, fall back to a curated brand logo
from the WP media library if the article topic matches a known brand keyword.
"""
import re
import unicodedata
from typing import Optional

# Media IDs verified via WP REST API on 2026-05-17.
# Update if logos are replaced; values are wp_posts.ID of attachment.

# Generické GAMEfo logo (site icon, 511x459) — úplně poslední fallback featured
# image, když selže IGDB i brand match (výpadek RAWG.io 2026-08-02/03 nechal
# články úplně bez náhledu). Media ID ověřeno přes REST 2026-08-03.
GAMEFO_LOGO = 401

BRAND_LOGOS = {
    'playstation': 7070,
    'ps plus': 7458,
    'xbox': 6189,
    'ea': 6544,
    'fromsoftware': 7263,
    'steam': 8905,
    # Ověřeno přes WP REST 2026-08-12 (ROBLOX.jpeg 738×415, Devolver.png 600×600).
    'roblox': 11359,
    'devolver': 11242,
    # Nahráno 2026-08-12 jako brand-*.jpg, ověřeno HTTP 200 na source_url.
    # Průhlednost sloučena na bílou — černé logo na transparentu (Summer Game
    # Fest) by v dark mode zmizelo.
    'nintendo': 11489,
    'pokemon': 11490,
    'blizzard': 11491,
    'cd projekt': 11492,
    'ubisoft': 11493,
    'rockstar': 11494,
    'summer game fest': 11495,
}

# Značky bez loga v media library. Prázdné — každý keyword níž má své logo.
# Až přibude keyword pro značku bez ID, patří sem (resolve_brand_logo ji pak
# přeskočí místo pádu).
PENDING_BRAND_LOGOS = ()

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
    # Steam / Valve
    'steam': 'steam',
    'valve': 'steam',
    'steam deck': 'steam',
    # Publishers
    'electronic arts': 'ea',
    'ea sports': 'ea',
    'fromsoftware': 'fromsoftware',
    'from software': 'fromsoftware',
    'devolver': 'devolver',
    'devolver digital': 'devolver',
    # Roblox je zároveň hra i platforma; jako brand ho drží až ENTITA typu
    # `znacka` z article_writeru, jinak by ho přebil IGDB záznam hry.
    'roblox': 'roblox',
    # Platformy a vydavatelé — doplněno 2026-08-12 podle reálných témat, která
    # končila na generickém GAMEfo logu.
    'nintendo': 'nintendo',
    'switch': 'nintendo',
    'nintendo switch': 'nintendo',
    'pokemon': 'pokemon',
    'pokémon': 'pokemon',
    'pokemon company': 'pokemon',
    'blizzard': 'blizzard',
    'blizzard entertainment': 'blizzard',
    'cd projekt': 'cd projekt',
    'cd projekt red': 'cd projekt',
    'cdpr': 'cd projekt',
    'ubisoft': 'ubisoft',
    'rockstar': 'rockstar',
    'rockstar games': 'rockstar',
    'summer game fest': 'summer game fest',
}

_MULTI_WORD = [(kw, brand) for kw, brand in _KEYWORD_TO_BRAND.items() if ' ' in kw]
_SINGLE_WORD = {kw: brand for kw, brand in _KEYWORD_TO_BRAND.items() if ' ' not in kw}

# Tokens that may appear in a game_name that is *itself* a brand/platform topic
# ("PlayStation 5 Pro", "Xbox Series X", "Steam Deck") without disqualifying it
# from the strict brand-first match.
_BRAND_TOKENS = {tok for kw in _KEYWORD_TO_BRAND for tok in kw.split()}
_GENERIC_TOKENS = {
    'plus', 'pro', 'slim', 'series', 'x', 's', 'one', 'deck', 'game', 'pass',
    'store', 'network', 'direct', 'live', 'machine', 'frame', 'controller',
    'vr', 'vr2', 'portal', 'edition',
}


def _normalize(text: str) -> str:
    if not text:
        return ''
    text = unicodedata.normalize('NFKD', text)
    text = ''.join(c for c in text if not unicodedata.combining(c))
    return text.lower()


def resolve_brand_logo_strict(game_name: str) -> Optional[int]:
    """Return brand logo media ID only when game_name IS the brand/platform itself.

    Used as a brand-first gate before the IGDB search: "Steam", "PlayStation 5",
    "Xbox Game Pass" → logo; "Microsoft Flight Simulator" → None (a real game
    that merely contains a brand token must keep its IGDB image).
    """
    norm = _normalize(game_name)
    tokens = re.findall(r'[a-z0-9]+', norm)
    if not tokens:
        return None
    for tok in tokens:
        if tok.isdigit() or tok in _BRAND_TOKENS or tok in _GENERIC_TOKENS:
            continue
        return None
    return resolve_brand_logo(game_name)


def resolve_brand_logo(*texts) -> Optional[int]:
    """Return media ID of brand logo if any of the texts matches a brand keyword.

    Multi-word keywords (e.g. "ps plus") win over single-word ones so that
    "PS Plus v květnu" returns the PS Plus logo, not the generic PlayStation one.
    """
    haystack = _normalize(' '.join(t for t in texts if t))
    if not haystack:
        return None

    # .get(), ne [] — keyword pro značku bez nahraného loga (PENDING_BRAND_LOGOS)
    # nesmí shodit publikaci, jen se přeskočí na další shodu.
    for kw, brand in _MULTI_WORD:
        if kw in haystack and brand in BRAND_LOGOS:
            return BRAND_LOGOS[brand]

    for token in re.findall(r"[a-z0-9]+", haystack):
        brand = _SINGLE_WORD.get(token)
        if brand and brand in BRAND_LOGOS:
            return BRAND_LOGOS[brand]

    return None
