"""
YouTube Embed - detekce video referencí v článku a vložení YouTube embedu.
Používá yt-dlp pro vyhledávání na YouTube (žádný API klíč).
"""

import os
import re
import subprocess
import json
import sys

from logger import setup_logger

log = setup_logger(__name__)

# Klíčová slova signalizující odkaz na video
_VIDEO_KEYWORDS_CS = re.compile(
    r'\b(trailer|video|ukázk[auy]|záběr[yů]|gameplay|teaser|reveal)\b',
    re.IGNORECASE,
)
_VIDEO_KEYWORDS_EN = re.compile(
    r'\b(trailer|video|footage|gameplay|teaser|reveal|announcement)\b',
    re.IGNORECASE,
)

_YOUTUBE_EMBED_TEMPLATE = (
    '<!-- wp:embed {{"url":"https://www.youtube.com/watch?v={video_id}",'
    '"type":"video","providerNameSlug":"youtube","responsive":true,'
    '"className":"wp-embed-aspect-16-9 wp-has-aspect-ratio"}} -->\n'
    '<figure class="wp-block-embed is-type-video is-provider-youtube '
    'wp-block-embed-youtube wp-embed-aspect-16-9 wp-has-aspect-ratio">'
    '<div class="wp-block-embed__wrapper">\n'
    'https://www.youtube.com/watch?v={video_id}\n'
    '</div></figure>\n'
    '<!-- /wp:embed -->'
)


def has_video_reference(html: str, lang: str = 'cs') -> bool:
    """Zjistí, jestli článek zmiňuje video/trailer."""
    pattern = _VIDEO_KEYWORDS_CS if lang == 'cs' else _VIDEO_KEYWORDS_EN
    return bool(pattern.search(html))


# Kolik kandidátů z vyhledávání zkoušet, než to vzdáme
_SEARCH_CANDIDATES = 5


def _yt_dlp_bin() -> str:
    """yt-dlp ze stejného adresáře jako Python interpreter (venv/bin/), jinak PATH."""
    path = os.path.join(os.path.dirname(sys.executable), 'yt-dlp')
    return path if os.path.isfile(path) else 'yt-dlp'


def search_youtube(query: str, max_results: int = _SEARCH_CANDIDATES) -> list:
    """
    Vyhledá videa na YouTube pomocí yt-dlp FLAT searchem (bez plné extrakce
    jednotlivých videí). Plná extrakce padala na age-restricted výsledcích
    ("Sign in to confirm your age") a bot-checku — kvůli tomu embed v produkci
    nefungoval od 21. 7. 2026. Flat search vrací id/title/url bez těchto pádů.

    Vrací seznam dict s 'id', 'title', 'url'.
    """
    try:
        result = subprocess.run(
            [
                _yt_dlp_bin(),
                f'ytsearch{max_results}:{query}',
                '--flat-playlist',
                '--dump-json',
                '--no-download',
                '--quiet',
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        # stdout parsovat i při returncode != 0 — částečné výsledky se počítají
        videos = []
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            try:
                data = json.loads(line)
                vid = data.get('id', '')
                videos.append({
                    'id': vid,
                    'title': data.get('title', ''),
                    'url': data.get('url') or data.get('webpage_url')
                        or f'https://www.youtube.com/watch?v={vid}',
                })
            except json.JSONDecodeError:
                continue

        if not videos and result.returncode != 0:
            # Konec stderr, ne začátek — začátek bývá jen urllib3 warning
            log.warning("yt-dlp search failed: %s", result.stderr[-300:])

        return videos

    except subprocess.TimeoutExpired:
        log.warning("yt-dlp search timeout for query: %s", query)
        return []
    except FileNotFoundError:
        log.error("yt-dlp not found. Install: pip install yt-dlp")
        return []
    except Exception as e:
        log.warning("YouTube search error: %s", e)
        return []


def check_embeddable(video_id: str):
    """
    Ověří plnou extrakcí, jestli video půjde přehrát v embedu na webu.

    Vrací:
        True  — extrakce OK, age_limit 0 a embed není zakázaný
        False — PROKÁZANĚ nehratelné: age-restricted (YouTube v embedu
                nepřehraje, jen šedý box "Watch on YouTube") nebo vypnutý embed
        None  — nelze zjistit (bot-check "confirm you're not a bot", POT
                provider, síť…) — to blokuje jen náš scraper, ne návštěvníky,
                video je pro embed pravděpodobně v pořádku
    """
    try:
        result = subprocess.run(
            [
                _yt_dlp_bin(),
                f'https://www.youtube.com/watch?v={video_id}',
                '--dump-json',
                '--no-download',
                '--no-playlist',
                '--quiet',
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception:
        return None

    if result.returncode == 0:
        try:
            data = json.loads(result.stdout.strip().splitlines()[-1])
        except (json.JSONDecodeError, IndexError):
            return None
        if (data.get('age_limit') or 0) > 0:
            return False
        if data.get('playable_in_embed') is False:
            return False
        return True

    if 'confirm your age' in result.stderr:
        return False
    return None


# Markery titulků, které skoro jistě nejsou oficiální video ke hře
# (fanouškovské "concept" trailery neexistujících filmů apod.)
_FAKE_TITLE_MARKERS = ('concept', 'fan made', 'fan-made')
_TITLE_STOPWORDS = {'the', 'of', 'and', 'for', 'a', 'an'}


def title_matches_game(title: str, game_name: str) -> bool:
    """
    Hrubá kontrola, že video patří ke hře: aspoň polovina významových tokenů
    z názvu hry je v titulku videa. Chrání před úplně cizími videi — reálné
    případy z backfillu 6. 8.: 'Red Odyssey' (indie) → trailer na film Jason
    Bourne 6, 'Assassin's Creed Odyssey' → Nolanův film The Odyssey.
    Záměrně volná (FF 14 vs XIV projde) — je to lapač nesmyslů, ne přesný match.
    """
    t = title.lower()
    if any(m in t for m in _FAKE_TITLE_MARKERS):
        return False
    # Interpunkci v titulku kolabovat — jinak token "stalker" nikdy nematchne
    # titulek "S.T.A.L.K.E.R. 2: ..." a filtr odmítne všechny oficiální trailery
    collapsed_title = re.sub(r'[^a-z0-9]+', '', t)
    g = game_name.lower()
    tokens = [tok for tok in re.findall(r'[a-z0-9]+', g)
              if len(tok) > 1 and tok not in _TITLE_STOPWORDS]
    if not tokens:
        # game_name je samý akronym/číslo ("S.T.A.L.K.E.R. 2") — porovnej
        # celé zkolabované názvy
        collapsed_game = re.sub(r'[^a-z0-9]+', '', g)
        return not collapsed_game or collapsed_game in collapsed_title
    hits = sum(1 for tok in tokens if tok in t or tok in collapsed_title)
    return hits * 2 >= len(tokens)


def find_embeddable_video(query: str, game_name: str = None):
    """
    Flat search + výběr prvního kandidáta, který (a) odpovídá hře podle
    titulku (jen když je game_name zadané) a (b) není prokazatelně
    nehratelný v embedu (přeskočí age-restricted videa — např. Onimusha
    trailery, kde jsou první DVA výsledky 18+).

    Vrací dict {'id', 'title', 'url'} nebo None.
    """
    candidates = search_youtube(query)
    for video in candidates:
        if game_name and not title_matches_game(video['title'], game_name):
            log.info("Kandidát '%s' neodpovídá hře '%s', zkouším další",
                     video['title'], game_name)
            continue
        verdict = check_embeddable(video['id'])
        if verdict is False:
            log.info("Kandidát '%s' je age-restricted/bez embedu, zkouším další",
                     video['title'])
            continue
        return video
    return None


def build_youtube_gutenberg_block(video_id: str) -> str:
    """Vrátí WordPress Gutenberg embed blok pro YouTube video."""
    return _YOUTUBE_EMBED_TEMPLATE.format(video_id=video_id)


def _find_video_paragraph_index(html: str, lang: str = 'cs') -> int:
    """
    Najde index konce <p> tagu, který obsahuje video klíčové slovo.
    Vrací pozici v HTML stringu (konec tagu) nebo -1.
    Přeskakuje <p> uvnitř <blockquote> — embed má být samostatný blok.
    """
    pattern = _VIDEO_KEYWORDS_CS if lang == 'cs' else _VIDEO_KEYWORDS_EN

    # Najdi všechny blockquote rozsahy, abychom je přeskočili
    blockquote_ranges = [
        (m.start(), m.end())
        for m in re.finditer(r'<blockquote[\s\S]*?</blockquote>', html, re.DOTALL)
    ]

    for match in re.finditer(r'<p[^>]*>.*?</p>', html, re.DOTALL):
        # Přeskoč <p> uvnitř blockquote
        inside_bq = any(start <= match.start() < end for start, end in blockquote_ranges)
        if inside_bq:
            continue
        if pattern.search(match.group()):
            return match.end()

    return -1


def _insert_embed_block(html: str, embed_block: str, lang: str = 'cs') -> str:
    """Vloží embed blok na nejlepší pozici v HTML."""
    # 1. Najdi odstavec s video klíčovým slovem (mimo blockquote)
    insert_pos = _find_video_paragraph_index(html, lang)

    if insert_pos > 0:
        return html[:insert_pos] + embed_block + html[insert_pos:]

    # 2. Fallback: konec úvodu — před první <h2> sekci. Od always-embed
    #    (články bez zmínky o videu) je tohle hlavní cesta; vložení AŽ ZA
    #    </h2> by video dalo mezi nadpis a text sekce.
    h2_match = re.search(r'<h2[\s>]', html)
    if h2_match:
        pos = h2_match.start()
        return html[:pos] + embed_block + html[pos:]

    # 3. Fallback: vlož za blockquote (po úvodu)
    bq_match = re.search(r'</blockquote>', html)
    if bq_match:
        pos = bq_match.end()
        return html[:pos] + embed_block + html[pos:]

    # 4. Poslední fallback: přidej na konec
    return html + embed_block


def force_embed_youtube(html: str, video_id: str, lang: str = 'cs') -> str:
    """
    Vloží YouTube embed do HTML bez kontroly klíčových slov.
    Jediný vstup z publish_pipeline — hledání i rozhodnutí, JESTLI embedovat,
    řeší publish_pipeline.embed_youtube (jedno video pro CZ i EN verzi).
    """
    embed_block = '\n' + build_youtube_gutenberg_block(video_id) + '\n'
    return _insert_embed_block(html, embed_block, lang)
