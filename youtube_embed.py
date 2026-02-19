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


def search_youtube(query: str, max_results: int = 1) -> list:
    """
    Vyhledá videa na YouTube pomocí yt-dlp.
    Vrací seznam dict s 'id', 'title', 'url'.
    """
    # Najdi yt-dlp ve stejném adresáři jako aktuální Python interpreter (venv/bin/)
    yt_dlp_bin = os.path.join(os.path.dirname(sys.executable), 'yt-dlp')
    if not os.path.isfile(yt_dlp_bin):
        yt_dlp_bin = 'yt-dlp'  # fallback na PATH

    try:
        result = subprocess.run(
            [
                yt_dlp_bin,
                f'ytsearch{max_results}:{query}',
                '--dump-json',
                '--no-download',
                '--no-playlist',
                '--quiet',
            ],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode != 0:
            log.warning("yt-dlp search failed: %s", result.stderr[:200])
            return []

        videos = []
        for line in result.stdout.strip().split('\n'):
            if not line:
                continue
            try:
                data = json.loads(line)
                videos.append({
                    'id': data.get('id', ''),
                    'title': data.get('title', ''),
                    'url': data.get('webpage_url', ''),
                })
            except json.JSONDecodeError:
                continue

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

    # 2. Fallback: vlož za blockquote (po úvodu, před první sekcí)
    bq_match = re.search(r'</blockquote>', html)
    if bq_match:
        pos = bq_match.end()
        return html[:pos] + embed_block + html[pos:]

    # 3. Fallback: vlož po prvním <h2>...</h2>
    h2_match = re.search(r'</h2>', html)
    if h2_match:
        pos = h2_match.end()
        return html[:pos] + embed_block + html[pos:]

    # 4. Poslední fallback: přidej na konec
    return html + embed_block


def embed_youtube_in_html(html: str, game_name: str, lang: str = 'cs') -> str:
    """
    Hlavní funkce: detekuje video odkaz v článku, vyhledá na YouTube
    a vloží embed blok do HTML.

    Args:
        html: HTML obsah článku
        game_name: Název hry pro YouTube search query
        lang: 'cs' nebo 'en'

    Returns:
        Upravené HTML s YouTube embedem, nebo původní HTML pokud nic nenalezeno.
    """
    if not has_video_reference(html, lang):
        log.info("Žádná zmínka o videu v článku, přeskakuji YouTube embed")
        return html

    # Sestav search query
    query = f"{game_name} official trailer 2026"
    log.info("Hledám YouTube video: %s", query)

    videos = search_youtube(query)
    if not videos:
        log.warning("YouTube video nenalezeno pro: %s", query)
        return html

    video = videos[0]
    log.info("Nalezeno video: %s (%s)", video['title'], video['url'])

    embed_block = '\n' + build_youtube_gutenberg_block(video['id']) + '\n'
    return _insert_embed_block(html, embed_block, lang)


def force_embed_youtube(html: str, video_id: str, lang: str = 'cs') -> str:
    """
    Vloží YouTube embed do HTML bez kontroly klíčových slov.
    Používá se když video už bylo nalezeno pro jinou jazykovou verzi.
    """
    embed_block = '\n' + build_youtube_gutenberg_block(video_id) + '\n'
    return _insert_embed_block(html, embed_block, lang)
