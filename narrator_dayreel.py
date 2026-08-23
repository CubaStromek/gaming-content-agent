"""DayReel narátor — Claude scénář + ElevenLabs TTS pro denní souhrn.

Generuje 3 typy MP3 do `promo-video/public/narration/`:
  - dayreel-{lang}-intro.mp3 (~4–5s)
  - dayreel-{lang}-a01.mp3 .. aNN.mp3 (~5–7s per článek)
  - dayreel-{lang}-outro.mp3 (~3–4s)

Vrací list dictů: [{file, durationSec, role, index?}]. Caller (dayreel.py)
napojí na Remotion data. Při chybě (chybí API key, Claude/EL down) vrátí None
a caller spadne do silent módu.

Env:
  ELEVENLABS_API_KEY — povinný
  DAYREEL_VOICE_ID_CS — default OAAjJsQDvpg3sVjiLgyl
  DAYREEL_VOICE_ID_EN — default DXFkLCBUTmvXpp2QwZjA
"""

import json
import os
import re
import subprocess
import sys
from typing import Optional
from urllib import error as urlerror
from urllib import request as urlrequest

import anthropic

import config
from logger import setup_logger

log = setup_logger('narrator_dayreel')

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NARRATION_DIR = os.path.join(BASE_DIR, 'promo-video', 'public', 'narration')
# Stabilní úložiště mimo cleanup_workdirs() — JSON scénáře přežijí mezi dvěma
# fázemi (plan → user approval → synthesize+render).
SCRIPT_DIR = os.path.join(BASE_DIR, 'output', 'dayreel-scripts')

ELEVENLABS_MODEL = "eleven_v3"
VOICE_SETTINGS = {
    "stability": 0.7,
    "similarity_boost": 0.5,
    "style": 0.0,
    "use_speaker_boost": False,
    "speed": 0.9,
}

DEFAULT_VOICE_IDS = {
    "cs": "XOgpjkYNnVH5W7ZAlLYg",
    "en": "DXFkLCBUTmvXpp2QwZjA",
}


def _clean_text(text: str) -> str:
    """Odebere em-dashes (ElevenLabs lesson — spouští dramatický nádech)."""
    return (text
            .replace(" — ", ", ")
            .replace("—", ",")
            .replace(" – ", ", ")
            .replace("–", ","))


def _strip_json_fence(s: str) -> str:
    s = s.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s)
        s = re.sub(r"\s*```$", "", s)
    return s.strip()


def _build_prompt(articles: list, lang: str, date: str) -> str:
    """Vytvoří prompt pro Claude — vrací JSON se scénářem."""
    if lang == "cs":
        return _prompt_cs(articles, date)
    return _prompt_en(articles, date)


def _prompt_cs(articles: list, date: str) -> str:
    items = "\n".join(
        f"{i + 1}. {a['game_name']} — {a['title']}"
        for i, a in enumerate(articles)
    )
    return f"""Jsi český sportovní herní moderátor pro GAMEfo.cz. Tvým úkolem je napsat krátký mluvený scénář pro Reel video shrnující dnešní herní novinky ({date}).

ARTIKLY DNES ({len(articles)}):
{items}

Napiš scénář pro narátora ve **formátu JSON** (nic jiného):

{{
  "intro": "krátký úvod (1 věta, ~3–4 sekundy, ~12 slov, energický)",
  "sections": [
    "věta o článku 1 (~5–7s, ~18–22 slov, zaměř se na fakt/hook)",
    "věta o článku 2",
    ...
  ],
  "outro": "krátké zavření (1 věta, ~3s, ~10 slov, výzva ke kliknutí)"
}}

PRAVIDLA:
- Mluvený jazyk, ne článkový (žádné "Společnost X oznámila..."; spíš "X přichází s...")
- Bez em-dash a pomlček, pouze tečka a čárka
- Žádné anglicismy navíc; názvy her nech v originále
- Každá section věta = jeden hook (proč fanouška zajímá)
- Intro nezačínej "Vítejte"; rovnou do věci
- Outro vybídne ke gamefo.cz

Vrať jen JSON, nic jiného."""


def _prompt_en(articles: list, date: str) -> str:
    items = "\n".join(
        f"{i + 1}. {a['game_name']} — {a.get('en_title') or a['title']}"
        for i, a in enumerate(articles)
    )
    return f"""You are an English-speaking gaming news host for GAMEfo. Write a short voiceover script for a Reel video summarizing today's gaming news ({date}).

TODAY'S ARTICLES ({len(articles)}):
{items}

Return the script as **JSON only** (nothing else):

{{
  "intro": "short opener (1 sentence, ~3–4 seconds, ~12 words, energetic)",
  "sections": [
    "sentence about article 1 (~5–7s, ~18–22 words, lead with the hook)",
    "sentence about article 2",
    ...
  ],
  "outro": "short closer (1 sentence, ~3s, ~10 words, CTA to gamefo.cz)"
}}

RULES:
- Spoken style, not written ("X is coming with..." not "Company X announced...")
- No em-dashes; only periods and commas
- Keep game titles as-is
- Each section sentence = one hook
- Don't open with "Welcome"; jump straight in
- Outro nudges toward gamefo.cz

Return JSON only."""


def generate_script(articles: list, lang: str, date: str) -> Optional[dict]:
    """Zavolá Claude a vrátí parsed JSON {intro, sections[], outro} nebo None."""
    if not config.CLAUDE_API_KEY:
        log.error("CLAUDE_API_KEY chybí — scénář vygenerovat nelze.")
        return None

    client = anthropic.Anthropic(api_key=config.CLAUDE_API_KEY)
    prompt = _build_prompt(articles, lang, date)

    try:
        resp = client.messages.create(
            model=config.ANALYSIS_MODEL,
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )
    except Exception as e:
        log.error("Claude script API selhalo: %s", e)
        return None

    raw = resp.content[0].text if resp.content else ""
    cleaned = _strip_json_fence(raw)
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        log.error("Claude script JSON parse selhal: %s\nRaw: %s", e, raw[:400])
        return None

    if not isinstance(data.get("sections"), list) or len(data["sections"]) != len(articles):
        log.error("Claude script: počet sekcí (%d) neodpovídá článkům (%d)",
                  len(data.get("sections") or []), len(articles))
        return None
    if not data.get("intro") or not data.get("outro"):
        log.error("Claude script: chybí intro/outro")
        return None

    log.info("[%s] scénář OK — intro+%d sekcí+outro", lang, len(articles))
    return data


def _voice_id(lang: str) -> str:
    env_key = f"DAYREEL_VOICE_ID_{lang.upper()}"
    return os.getenv(env_key) or DEFAULT_VOICE_IDS[lang]


def _tts(text: str, voice_id: str, out_path: str) -> bool:
    """ElevenLabs TTS jednoho segmentu. True při úspěchu."""
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        log.error("ELEVENLABS_API_KEY chybí.")
        return False

    payload = json.dumps({
        "text": _clean_text(text),
        "model_id": ELEVENLABS_MODEL,
        "voice_settings": VOICE_SETTINGS,
    }).encode("utf-8")

    url = f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}?output_format=mp3_44100_128"
    req = urlrequest.Request(
        url, data=payload,
        headers={
            "xi-api-key": api_key,
            "Content-Type": "application/json",
            "Accept": "audio/mpeg",
        },
        method="POST",
    )
    try:
        with urlrequest.urlopen(req, timeout=120) as resp:
            data = resp.read()
    except urlerror.HTTPError as e:
        body = e.read().decode(errors='replace')[:300]
        log.error("ElevenLabs HTTP %d: %s", e.code, body)
        return False
    except Exception as e:
        log.error("ElevenLabs request selhal: %s", e)
        return False

    with open(out_path, "wb") as f:
        f.write(data)
    return os.path.exists(out_path) and os.path.getsize(out_path) > 1000


def _duration(path: str) -> float:
    try:
        result = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, check=True,
        )
        return float(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError, ValueError) as e:
        log.warning("ffprobe selhal pro %s: %s", path, e)
        return 0.0


def _script_path(date: str, lang: str) -> str:
    return os.path.join(SCRIPT_DIR, f"{date}-{lang}.json")


def plan(articles: list, lang: str, date: str, force: bool = False) -> Optional[dict]:
    """Vygeneruje (nebo načte) Claude scénář a zapíše ho do output/dayreel-scripts/.

    Když JSON už pro daný (date, lang) existuje a `force=False`, vrátí ho beze
    změny — to umožňuje uživateli upravit text mezi `plan` a `synthesize`.

    Vrací dict {"intro": str, "sections": [str, ...], "outro": str} nebo None.
    """
    path = _script_path(date, lang)
    if not force and os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if (isinstance(data.get("sections"), list) and data.get("intro")
                    and data.get("outro")):
                log.info("[%s] scénář načten z %s (existuje, nepřegeneruju)",
                         lang, path)
                return data
            log.warning("Existující scénář %s má neplatný formát, regeneruju.", path)
        except (OSError, json.JSONDecodeError) as e:
            log.warning("Existující scénář %s nečitelný (%s), regeneruju.", path, e)

    script = generate_script(articles, lang, date)
    if not script:
        return None

    os.makedirs(SCRIPT_DIR, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(script, f, ensure_ascii=False, indent=2)
    log.info("[%s] scénář zapsán do %s", lang, path)
    return script


def synthesize(script: dict, lang: str) -> Optional[dict]:
    """Z Claude scénáře vyrobí ElevenLabs MP3 a vrátí dict s file+duration."""
    if not os.getenv("ELEVENLABS_API_KEY"):
        log.warning("ELEVENLABS_API_KEY chybí — TTS přeskočen.")
        return None

    os.makedirs(NARRATION_DIR, exist_ok=True)
    voice_id = _voice_id(lang)
    log.info("[%s] TTS voice=%s, %d segmentů",
             lang, voice_id, len(script["sections"]) + 2)

    segments = [("intro", script["intro"], f"dayreel-{lang}-intro.mp3")]
    for i, text in enumerate(script["sections"]):
        segments.append((f"a{i + 1:02d}", text, f"dayreel-{lang}-a{i + 1:02d}.mp3"))
    segments.append(("outro", script["outro"], f"dayreel-{lang}-outro.mp3"))

    result = {"intro": None, "sections": [], "outro": None}
    for role, text, filename in segments:
        out_path = os.path.join(NARRATION_DIR, filename)
        if not _tts(text, voice_id, out_path):
            log.error("[%s] TTS selhalo pro %s — narátor abort.", lang, role)
            return None
        dur = _duration(out_path)
        entry = {"file": filename, "duration": dur, "text": text}
        if role == "intro":
            result["intro"] = entry
        elif role == "outro":
            result["outro"] = entry
        else:
            result["sections"].append(entry)
        log.info("  ✓ %s — %.2fs", filename, dur)

    durations_path = os.path.join(NARRATION_DIR, f"durations-{lang}.json")
    with open(durations_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    total = (result["intro"]["duration"] +
             sum(s["duration"] for s in result["sections"]) +
             result["outro"]["duration"])
    log.info("[%s] narátor OK — celkem %.1fs", lang, total)
    return result


def generate(articles: list, lang: str, date: str) -> Optional[dict]:
    """End-to-end: plan (Claude) + synthesize (ElevenLabs). Reuse JSON pokud existuje.

    Vrací dict:
      {
        "intro": {"file": "...", "duration": 4.2, "text": "..."},
        "sections": [{"file": "...", "duration": 6.1, "text": "..."}, ...],
        "outro": {"file": "...", "duration": 3.4, "text": "..."},
      }

    Vrací None, když cokoliv selže — caller dropne do silent módu.
    """
    if not os.getenv("ELEVENLABS_API_KEY"):
        log.warning("ELEVENLABS_API_KEY chybí — narátor přeskočen.")
        return None

    script = plan(articles, lang, date)
    if not script:
        return None
    return synthesize(script, lang)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Testovací generátor narátora (samostatně).")
    parser.add_argument("--date", required=True)
    parser.add_argument("--lang", default="cs", choices=["cs", "en"])
    parser.add_argument("--plan-only", action="store_true",
                        help="Jen Claude scénář, žádné TTS.")
    parser.add_argument("--force", action="store_true",
                        help="Přegenerovat scénář i když JSON existuje.")
    args = parser.parse_args()
    from dayreel import fetch_today_published
    arts = fetch_today_published(args.date)
    if not arts:
        print("Žádné články.")
        sys.exit(0)
    if args.plan_only:
        out = plan(arts, args.lang, args.date, force=args.force)
    else:
        if args.force and os.path.exists(_script_path(args.date, args.lang)):
            os.remove(_script_path(args.date, args.lang))
        out = generate(arts, args.lang, args.date)
    print(json.dumps(out, ensure_ascii=False, indent=2) if out else "FAIL")
