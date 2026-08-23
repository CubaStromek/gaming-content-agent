"""
DayReel orchestrátor — vyrábí denní souhrn Reel video (1080×1920, 9:16, ~30s)
ze všech článků publikovaných daný den.

Pipeline:
  publish_log → fetch_today_published → per article: yt-dlp trailer (5–8s) /
  IGDB image fallback → write dayReelData.ts → npm run render:dayreel(-en) →
  output/dayreels/<date>_<LANG>.mp4

CLI:
  python dayreel.py [--date YYYY-MM-DD] [--lang cs|en|both] [--dry-run]
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.request
from datetime import datetime
from typing import Optional

import requests

import config
import narrator_dayreel
from database import get_db
from logger import setup_logger
from youtube_embed import search_youtube

log = setup_logger('dayreel')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROMO_DIR = os.path.join(BASE_DIR, 'promo-video')
PUBLIC_DAYREEL = os.path.join(PROMO_DIR, 'public', 'dayreel')
PUBLIC_AUDIO = os.path.join(PROMO_DIR, 'public', 'audio')
PUBLIC_NARRATION = os.path.join(PROMO_DIR, 'public', 'narration')
OUT_DIR = os.path.join(BASE_DIR, 'output', 'dayreels')
PROMO_OUT = os.path.join(PROMO_DIR, 'out')

MAX_SECTIONS = 6
TRAILER_START = 5
TRAILER_END = 12
MIN_CLIP_BYTES = 50_000

# Hudba k dispozici v promo-video/out/
MUSIC_TRACKS = {
    'short': 'podcast-intro-159123.mp3',          # 1–3 článků
    'long': 'Dynamic Scroll Pulse.mp3',           # 4–6 článků
}



def _strip_topic_suffix(topic: str) -> str:
    """Z 'Crimson Desert news' nebo 'Game – review' udělá 'Crimson Desert' / 'Game'."""
    if not topic:
        return topic
    cleaned = re.sub(r'\s*[–—-]\s*(news|update|review|leak|preview|trailer|rumor)\s*$',
                     '', topic, flags=re.IGNORECASE)
    cleaned = re.sub(r'\s+(news|update|review|leak|preview|trailer|rumor)\s*$',
                     '', cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def fetch_today_published(date_str: str) -> list:
    """Vrátí seznam článků publikovaných v daný den (max MAX_SECTIONS, sort dle skóre desc).
    Každý záznam: {title, cs_url, en_url, topic, game_name, score, en_title}.
    """
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT timestamp, topic, title, score, data_json FROM publish_log "
            "WHERE action='published' AND timestamp LIKE ? "
            "ORDER BY score DESC, timestamp ASC LIMIT ?",
            (date_str + '%', MAX_SECTIONS),
        ).fetchall()
    finally:
        conn.close()

    articles = []
    for row in rows:
        try:
            data = json.loads(row['data_json']) if row['data_json'] else {}
        except json.JSONDecodeError:
            data = {}

        topic = row['topic'] or data.get('topic', '')
        title = row['title'] or data.get('title', '')
        game_name = _extract_game_name(title) or _strip_topic_suffix(topic) or title or 'gamefo'

        articles.append({
            'timestamp': row['timestamp'],
            'topic': topic,
            'game_name': game_name,
            'title': title,
            'score': row['score'] or 0,
            'cs_post_id': data.get('cs_post_id'),
            'en_post_id': data.get('en_post_id'),
            'cs_url': data.get('cs_url') or data.get('view_url') or '',
            'en_url': data.get('en_url') or '',
            'en_title': data.get('en_title') or '',
        })
    return articles


def _extract_game_name(title: str) -> Optional[str]:
    """Z titulku se snaží vytáhnout název hry — sekvenci kapitalizovaných slov
    od začátku (do první malé/funkční částice). Vrací None, pokud kandidát
    nevypadá jako herní název (čisté firemní jméno, news titulek atd)."""
    if not title:
        return None
    # Tokenize zachovávající interpunkci k oddělovačům
    tokens = re.split(r'[\s:–—\-]+', title.strip())
    capitalized = []
    for tok in tokens:
        # Roman numerals (II, III, IV) i čísla (6, 2039) i kapitálky (GTA, AAA, RPG)
        if not tok:
            continue
        is_cap = (tok[0].isupper() or tok[0].isdigit()) and tok.lower() not in {
            'a', 'i', 'v', 'na', 'po', 'za', 'se', 'do', 'od', 'ke', 'ku',
        }
        if is_cap:
            capitalized.append(tok)
        else:
            break
    if not capitalized:
        return None
    candidate = ' '.join(capitalized).rstrip(',.')
    # Když kandidát skončí na typicky firemní/non-game slovo, vrať None
    blocklist_tail = {'Games', 'Studios', 'Studio', 'Bank', 'Software'}
    if capitalized[-1] in blocklist_tail and len(capitalized) <= 2:
        return None
    return candidate if len(candidate) >= 2 else None


def fetch_wp_featured_image(post_id: int, size: str = 'large') -> Optional[str]:
    """Stáhne URL featured image článku z WP REST API.
    `size` může být: thumbnail, medium, medium_large, large, 1536x1536, full.
    """
    if not post_id:
        return None
    try:
        resp = requests.get(
            f"https://gamefo.cz/wp-json/wp/v2/posts/{post_id}",
            params={'_embed': '1'},
            timeout=15,
        )
        if resp.status_code != 200:
            return None
        media = (resp.json().get('_embedded', {}).get('wp:featuredmedia') or [{}])[0]
        sizes = media.get('media_details', {}).get('sizes', {})
        # Preferuj požadovaný size, jinak největší dostupný
        for try_size in (size, 'large', 'medium_large', 'full', 'medium'):
            if try_size in sizes and sizes[try_size].get('source_url'):
                return sizes[try_size]['source_url']
        return media.get('source_url')
    except Exception as e:
        log.warning("WP featured image error pro post %s: %s", post_id, e)
        return None


def _ytdlp_bin() -> str:
    """yt-dlp v env venv (jinak PATH)."""
    bin_path = os.path.join(os.path.dirname(sys.executable), 'yt-dlp')
    return bin_path if os.path.isfile(bin_path) else 'yt-dlp'


def download_clip(query: str, out_path: str) -> bool:
    """Stáhne 5–12s úsek YouTube videa pro daný query.
    Vrací True při úspěchu (soubor existuje a má > MIN_CLIP_BYTES)."""
    videos = search_youtube(f"{query} official trailer", max_results=1)
    if not videos:
        log.info("Trailer nenalezen pro '%s'", query)
        return False

    url = videos[0].get('url') or f"https://www.youtube.com/watch?v={videos[0].get('id')}"
    if not url:
        return False

    # Pokud yt-dlp napíše s extension, přepíšeme — zaručíme .mp4 výstup
    out_dir = os.path.dirname(out_path)
    base = os.path.splitext(os.path.basename(out_path))[0]
    out_template = os.path.join(out_dir, base + '.%(ext)s')

    try:
        result = subprocess.run(
            [
                _ytdlp_bin(),
                url,
                '--download-sections', f'*{TRAILER_START}-{TRAILER_END}',
                '--force-keyframes-at-cuts',
                '-f', 'bestvideo[height<=720]+bestaudio/best[height<=720]/best',
                '--merge-output-format', 'mp4',
                '-o', out_template,
                '--no-playlist',
                '--quiet',
                '--no-warnings',
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0:
            log.warning("yt-dlp clip selhal pro '%s': %s", query, result.stderr[:200])
            return False
    except subprocess.TimeoutExpired:
        log.warning("yt-dlp clip timeout pro '%s'", query)
        return False
    except FileNotFoundError:
        log.error("yt-dlp není nainstalován. pip install yt-dlp")
        return False

    # yt-dlp někdy pojmenuje výstup jinak (např. .mkv při fallbacku) — najít skutečný soubor
    candidates = [p for p in os.listdir(out_dir) if p.startswith(base + '.')]
    if not candidates:
        return False
    actual = os.path.join(out_dir, candidates[0])
    if actual != out_path:
        os.rename(actual, out_path)

    if not os.path.exists(out_path) or os.path.getsize(out_path) < MIN_CLIP_BYTES:
        log.warning("yt-dlp clip příliš malý/chybí pro '%s' (%s B)",
                    query, os.path.getsize(out_path) if os.path.exists(out_path) else 0)
        return False
    return True


def download_image(game_name: str, out_path: str) -> bool:
    """Stáhne background image hry z IGDB. Vrací True při úspěchu."""
    import igdb_client
    url = igdb_client.search_game_image(game_name)
    if not url:
        log.info("Game image nenalezen pro '%s' (IGDB)", game_name)
        return False
    try:
        urllib.request.urlretrieve(url, out_path)
        if os.path.exists(out_path) and os.path.getsize(out_path) > 1000:
            return True
    except Exception as e:
        log.warning("Image download selhal pro '%s': %s", game_name, e)
    return False


def _download_url(url: str, out_path: str) -> bool:
    """Stáhne URL na disk. Vrací True když výsledek > 1 KB."""
    try:
        urllib.request.urlretrieve(url, out_path)
        return os.path.exists(out_path) and os.path.getsize(out_path) > 1000
    except Exception as e:
        log.warning("Download selhal (%s): %s", url, e)
        return False


def build_section(article: dict, idx: int) -> Optional[dict]:
    """Stáhne média pro článek a vrátí Remotion sekci, nebo None když média selžou.

    Priorita médií:
      1. yt-dlp trailer — jen když máme vyextrahovaný čistý game_name
      2. WordPress featured image (preferovaný — vždy sedí k článku)
      3. IGDB artwork (poslední záchrana)
    """
    base = f"a{idx + 1:02d}"
    clip_path = os.path.join(PUBLIC_DAYREEL, f"{base}-trailer.mp4")
    img_path = os.path.join(PUBLIC_DAYREEL, f"{base}-image.jpg")
    extracted = _extract_game_name(article['title'])

    # 1) yt-dlp trailer — jen když je game_name jasně extrahovaný z title
    if extracted and download_clip(extracted, clip_path):
        log.info("[%s] trailer OK (query=%r)", article['title'][:50], extracted)
        return {
            'heading': article['title'][:90],
            'gameName': extracted,
            'mediaFile': os.path.basename(clip_path),
            'isVideo': True,
            'videoStartSec': 0,
        }

    # 2) WordPress featured image — primární obrázkový zdroj
    wp_url = fetch_wp_featured_image(article.get('cs_post_id'))
    if wp_url and _download_url(wp_url, img_path):
        log.info("[%s] WP featured image OK", article['title'][:50])
        return {
            'heading': article['title'][:90],
            'gameName': extracted or '',
            'mediaFile': os.path.basename(img_path),
            'isVideo': False,
            'videoStartSec': 0,
        }

    # 3) IGDB fallback — pokud máme kandidáta game name
    if extracted and download_image(extracted, img_path):
        log.info("[%s] IGDB image fallback OK", article['title'][:50])
        return {
            'heading': article['title'][:90],
            'gameName': extracted,
            'mediaFile': os.path.basename(img_path),
            'isVideo': False,
            'videoStartSec': 0,
        }

    log.warning("[%s] žádná média — sekce přeskočena", article['title'][:50])
    return None


def pick_music(article_count: int) -> str:
    return MUSIC_TRACKS['long'] if article_count >= 4 else MUSIC_TRACKS['short']


def copy_music_to_public(music_filename: str) -> None:
    src = os.path.join(PROMO_OUT, music_filename)
    dst = os.path.join(PUBLIC_AUDIO, music_filename)
    if not os.path.exists(src):
        raise FileNotFoundError(f"Hudba chybí: {src}")
    os.makedirs(PUBLIC_AUDIO, exist_ok=True)
    shutil.copy2(src, dst)


def _ts_string_literal(s: str) -> str:
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


def _narration_field(value) -> str:
    """Vrací TS literal pro narration soubor (string) nebo null."""
    return _ts_string_literal(value) if value else 'null'


def write_data_ts(
    lang: str,
    sections: list,
    music_file: str,
    date: str,
    narration: Optional[dict] = None,
) -> None:
    """Zapíše promo-video/src/dayReelData.ts (cs) nebo dayReelDataEN.ts (en).

    `narration` (volitelně) je výstup z narrator_dayreel.generate(); když je None,
    composition se vyrenderuje bez narátora (silent mode, stará timing logika).
    """
    filename = 'dayReelData.ts' if lang == 'cs' else 'dayReelDataEN.ts'
    var_name = 'dayReelData' if lang == 'cs' else 'dayReelDataEN'
    out_path = os.path.join(PROMO_DIR, 'src', filename)

    narr_sections = (narration or {}).get('sections') or []

    sections_lines = []
    for i, s in enumerate(sections):
        n = narr_sections[i] if i < len(narr_sections) else None
        narration_file = n['file'] if n else None
        narration_dur = (n['duration'] if n else 0) or 0
        sections_lines.append(
            "  { "
            f"heading: {_ts_string_literal(s['heading'])}, "
            f"gameName: {_ts_string_literal(s['gameName'])}, "
            f"position: {i + 1}, "
            f"total: {len(sections)}, "
            f"mediaFile: {_ts_string_literal(s['mediaFile'])}, "
            f"isVideo: {'true' if s['isVideo'] else 'false'}, "
            f"videoStartSec: {s.get('videoStartSec', 0)}, "
            f"narrationFile: {_narration_field(narration_file)}, "
            f"narrationDurationSec: {narration_dur:.3f} "
            "},"
        )

    intro = (narration or {}).get('intro')
    outro = (narration or {}).get('outro')
    intro_file = _narration_field(intro['file'] if intro else None)
    intro_dur = (intro['duration'] if intro else 0) or 0
    outro_file = _narration_field(outro['file'] if outro else None)
    outro_dur = (outro['duration'] if outro else 0) or 0

    content = (
        "import { DayReelData } from './DayReel';\n\n"
        f"export const {var_name}: DayReelData = {{\n"
        f"  date: {_ts_string_literal(date)},\n"
        f'  lang: "{lang}",\n'
        f"  musicFile: {_ts_string_literal(music_file)},\n"
        f"  introNarrationFile: {intro_file},\n"
        f"  introNarrationDurationSec: {intro_dur:.3f},\n"
        f"  outroNarrationFile: {outro_file},\n"
        f"  outroNarrationDurationSec: {outro_dur:.3f},\n"
        "  sections: [\n"
        + "\n".join(sections_lines)
        + "\n  ],\n"
        "};\n"
    )

    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(content)
    log.info("Zapsáno %s (%d sekcí, narrator=%s)",
             filename, len(sections), "ano" if narration else "ne")


def render(lang: str, date: str) -> Optional[str]:
    """Spustí `npm run render:dayreel{,-en}` a přesune MP4 do output/dayreels/."""
    script = 'render:dayreel-en' if lang == 'en' else 'render:dayreel'
    log.info("Spouštím Remotion render (%s)...", script)
    result = subprocess.run(
        ['npm', 'run', script],
        cwd=PROMO_DIR,
        capture_output=False,
    )
    if result.returncode != 0:
        log.error("Render selhal pro %s (exit %d)", lang, result.returncode)
        return None

    src = os.path.join(PROMO_OUT, 'dayreel-en.mp4' if lang == 'en' else 'dayreel.mp4')
    if not os.path.exists(src):
        log.error("Renderovaný soubor chybí: %s", src)
        return None

    os.makedirs(OUT_DIR, exist_ok=True)
    lang_tag = 'EN' if lang == 'en' else 'CZ'
    dst = os.path.join(OUT_DIR, f"{date}_{lang_tag}.mp4")
    shutil.move(src, dst)
    log.info("Hotovo → %s", dst)
    return dst


def cleanup_workdirs() -> None:
    for d in (PUBLIC_DAYREEL, PUBLIC_AUDIO, PUBLIC_NARRATION):
        if os.path.exists(d):
            shutil.rmtree(d)
        os.makedirs(d, exist_ok=True)


def _gen_narration(articles_for_lang: list, lang: str, date: str, enabled: bool) -> Optional[dict]:
    """Vrátí narration dict nebo None. Při enabled=False vrátí None bez API volání."""
    if not enabled or not articles_for_lang:
        return None
    narration = narrator_dayreel.generate(articles_for_lang, lang, date)
    if not narration:
        log.warning("[%s] narátor selhal — pokračuju silent módem.", lang)
    return narration


def _plan_narration_only(date: str, lang_choice: str) -> int:
    """Vygeneruje jen Claude scénáře (CZ/EN) do output/dayreel-scripts/, žádné TTS / render."""
    articles = fetch_today_published(date)
    if not articles:
        log.warning("Žádné články publikované %s. Konec.", date)
        return 0
    log.info("Plánuji scénář pro %d článků...", len(articles))

    paths = []
    if lang_choice in ('cs', 'both'):
        s = narrator_dayreel.plan(articles, 'cs', date)
        if not s:
            log.error("CZ scénář selhal.")
            return 1
        paths.append(narrator_dayreel._script_path(date, 'cs'))

    if lang_choice in ('en', 'both'):
        en_articles = [a for a in articles if a.get('en_url')]
        if en_articles:
            s = narrator_dayreel.plan(en_articles, 'en', date)
            if not s:
                log.error("EN scénář selhal.")
                return 1
            paths.append(narrator_dayreel._script_path(date, 'en'))
        else:
            log.warning("EN: žádný článek nemá en_url, EN scénář přeskočen.")

    log.info("Scénáře hotovy. Otevři a uprav před renderem:")
    for p in paths:
        log.info("  → %s", p)
    log.info("Po schválení spusť: python dayreel.py --date %s --lang %s",
             date, lang_choice)
    return 0


def run(date: str, lang_choice: str, dry_run: bool, narrator_enabled: bool = True,
        narrator_plan_only: bool = False) -> int:
    log.info("DayReel: datum=%s, lang=%s, dry_run=%s, narrator=%s, plan_only=%s",
             date, lang_choice, dry_run, narrator_enabled, narrator_plan_only)

    if narrator_plan_only:
        if not narrator_enabled:
            log.error("--narrator-plan-only a --no-narrator se vylučují.")
            return 2
        return _plan_narration_only(date, lang_choice)

    articles = fetch_today_published(date)
    if not articles:
        log.warning("Žádné články publikované %s. Konec.", date)
        return 0
    log.info("Nalezeno %d článků (limit %d):", len(articles), MAX_SECTIONS)
    for a in articles:
        log.info("  • [%.0f] %s — %s", a['score'], a['game_name'], a['title'])

    if dry_run:
        log.info("--dry-run, končím bez stahování / renderu.")
        return 0

    cleanup_workdirs()
    music_file = pick_music(len(articles))
    copy_music_to_public(music_file)

    cs_sections = []
    en_sections = []
    cs_articles = []
    en_articles = []
    for idx, article in enumerate(articles):
        section = build_section(article, idx)
        if not section:
            continue
        cs_sections.append(section)
        cs_articles.append(article)
        if article.get('en_url'):
            en_section = dict(section)
            en_section['heading'] = (article.get('en_title') or section['heading'])[:90]
            en_sections.append(en_section)
            en_articles.append(article)

    if not cs_sections:
        log.error("Žádná CZ sekce s médii — abort. Nic nerenderuju.")
        return 1

    # Narrator (volitelný) — generuje se jen pro jazyky, které se budou renderovat
    cs_narration = None
    en_narration = None
    if lang_choice in ('cs', 'both'):
        cs_narration = _gen_narration(cs_articles, 'cs', date, narrator_enabled)
    if lang_choice in ('en', 'both') and en_sections:
        en_narration = _gen_narration(en_articles, 'en', date, narrator_enabled)

    # Vždycky zapsat oba TS soubory (Root.tsx je oba importuje při startu).
    # Pro variantu, kterou nerenderujeme, zapíšeme s prázdnými/CZ sections jako placeholder.
    write_data_ts('cs', cs_sections, music_file, date, cs_narration)
    write_data_ts(
        'en',
        en_sections if en_sections else cs_sections,
        music_file, date,
        en_narration if en_sections else None,
    )

    rendered = []
    if lang_choice in ('cs', 'both'):
        path = render('cs', date)
        if path:
            rendered.append(path)
    if lang_choice in ('en', 'both'):
        if not en_sections:
            log.warning("EN: žádný článek nemá en_url, EN render přeskočen.")
        else:
            path = render('en', date)
            if path:
                rendered.append(path)

    if not rendered:
        return 1
    log.info("Vyrobeno: %s", ', '.join(rendered))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Generuje denní souhrn Reel video.")
    parser.add_argument('--date', default=datetime.now().strftime('%Y-%m-%d'),
                        help='ISO datum (default dnes)')
    parser.add_argument('--lang', default='both', choices=['cs', 'en', 'both'])
    parser.add_argument('--dry-run', action='store_true',
                        help='Jen vypíše plán, nestahuje, nerenderuje.')
    parser.add_argument('--no-narrator', action='store_true',
                        help='Vypnout ElevenLabs narátor (silent mode, jen hudba).')
    parser.add_argument('--narrator-plan-only', action='store_true',
                        help='Jen vygenerovat Claude scénář do output/dayreel-scripts/. '
                             'Žádné TTS, žádný render. Pro schvalovací krok před plným během.')
    args = parser.parse_args()
    sys.exit(run(
        args.date, args.lang, args.dry_run,
        narrator_enabled=not args.no_narrator,
        narrator_plan_only=args.narrator_plan_only,
    ))


if __name__ == '__main__':
    main()
