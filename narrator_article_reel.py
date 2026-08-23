"""Narátor pro ArticleReel — ženský CZ hlas (ElevenLabs) pro shrnutí článku.

Texty jsou definované inline (SCRIPT). Generuje MP3 do
`promo-video/public/narration/` jako article-intro.mp3, article-a01..aNN.mp3,
article-outro.mp3 a zapíše durations-article.json.

Hlas: XOgpjkYNnVH5W7ZAlLYg = "dayreel CZ female voice".
Spuštění: python narrator_article_reel.py
"""

import json
import os
import subprocess
import sys
from urllib import error as urlerror
from urllib import request as urlrequest

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
NARRATION_DIR = os.path.join(BASE_DIR, "promo-video", "public", "narration")

VOICE_ID = "XOgpjkYNnVH5W7ZAlLYg"  # dayreel CZ female voice
ELEVENLABS_MODEL = "eleven_v3"
VOICE_SETTINGS = {
    "stability": 0.7,
    "similarity_boost": 0.5,
    "style": 0.0,
    "use_speaker_boost": False,
    "speed": 0.9,
}

SCRIPT = {
    "intro": "Playground Games konečně ukázal, jak se hraje nový Fable. Třicet minut z Albionu, který žije vlastním životem a nic nezapomíná.",
    "sections": [
        "Albion obývá přes tisíc ručně vytvořených postav. Každá má vlastní jméno, domov, práci i denní rozvrh. A svět běží dál, i když se zrovna nedíváš.",
        "Postavy si pamatují, co jsi jim provedl. Žebrák, kterému pomůžeš, se stane spojencem. Partner, kterého podvedeš, ti možná nikdy neodpustí.",
        "Ukázka provedla hráče městečkem Silverbrook. Hned v úvodu rozhoduješ o osudu mluvícího prasete jménem Colin, kterého chce řezník porazit. Typicky britský humor.",
        "Pověst si buduješ v každé osadě zvlášť. Můžeš být pronajímatel, manžel, hrdina i padouch zároveň. A když vyhladíš celé město, svět se s tím vyrovná po svém.",
        "Došlo i na akci. Hrdina umí teleportovat, šermovat mečem, a nepřátele klidně promění ve slepice. Boj vypadá stejně hravě jako zbytek hry.",
        "O příběhu víme zatím málo. Záporačkou je Isabel v podání Hayley Atwell a vrací se i Jack of Blades. Fable vyjde třiadvacátého února dva tisíce dvacet sedm.",
    ],
    "outro": "Celý článek najdeš na GAMEfo tečka cé zet.",
}


def _clean_text(text: str) -> str:
    return (text.replace(" — ", ", ").replace("—", ",")
                .replace(" – ", ", ").replace("–", ","))


def _tts(text: str, out_path: str) -> bool:
    api_key = os.getenv("ELEVENLABS_API_KEY")
    if not api_key:
        print("ELEVENLABS_API_KEY chybí.", file=sys.stderr)
        return False
    payload = json.dumps({
        "text": _clean_text(text),
        "model_id": ELEVENLABS_MODEL,
        "voice_settings": VOICE_SETTINGS,
    }).encode("utf-8")
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{VOICE_ID}?output_format=mp3_44100_128"
    req = urlrequest.Request(url, data=payload, headers={
        "xi-api-key": api_key,
        "Content-Type": "application/json",
        "Accept": "audio/mpeg",
    }, method="POST")
    try:
        with urlrequest.urlopen(req, timeout=120) as resp:
            data = resp.read()
    except urlerror.HTTPError as e:
        print(f"ElevenLabs HTTP {e.code}: {e.read().decode(errors='replace')[:300]}", file=sys.stderr)
        return False
    except Exception as e:
        print(f"ElevenLabs request selhal: {e}", file=sys.stderr)
        return False
    with open(out_path, "wb") as f:
        f.write(data)
    return os.path.exists(out_path) and os.path.getsize(out_path) > 1000


def _duration(path: str) -> float:
    try:
        r = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", path],
            capture_output=True, text=True, check=True)
        return float(r.stdout.strip())
    except Exception as e:
        print(f"ffprobe selhal pro {path}: {e}", file=sys.stderr)
        return 0.0


def main() -> int:
    os.makedirs(NARRATION_DIR, exist_ok=True)
    segments = [("intro", SCRIPT["intro"], "article-intro.mp3")]
    for i, text in enumerate(SCRIPT["sections"]):
        segments.append((f"a{i + 1:02d}", text, f"article-a{i + 1:02d}.mp3"))
    segments.append(("outro", SCRIPT["outro"], "article-outro.mp3"))

    result = {"intro": None, "sections": [], "outro": None}
    for role, text, filename in segments:
        out_path = os.path.join(NARRATION_DIR, filename)
        if not _tts(text, out_path):
            print(f"TTS selhalo pro {role} — abort.", file=sys.stderr)
            return 1
        dur = _duration(out_path)
        entry = {"file": filename, "duration": dur, "text": text}
        if role == "intro":
            result["intro"] = entry
        elif role == "outro":
            result["outro"] = entry
        else:
            result["sections"].append(entry)
        print(f"  ✓ {filename} — {dur:.2f}s")

    with open(os.path.join(NARRATION_DIR, "durations-article.json"), "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    total = (result["intro"]["duration"]
             + sum(s["duration"] for s in result["sections"])
             + result["outro"]["duration"])
    print(f"Narátor OK — celkem {total:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
