---
name: dayreel
description: Vygeneruje denní souhrn Reel video (1080×1920, 9:16, ~45–55s) ze všech článků publikovaných na gamefo.cz daný den, s ElevenLabs narátorem. Vyrobí CZ i EN verzi do output/dayreels/.
argument-hint: "[YYYY-MM-DD volitelně, default dnes] [--no-narrator]"
allowed-tools: Bash, Read, Glob
---

# DayReel — denní souhrn Reel pro GAMEfo.cz

Vygeneruj 9:16 vertikální video shrnující články publikované daný den. Výstup je MP4 určený pro Facebook / Instagram Reels (manuální upload).

Pipeline orchestruje Python skript `dayreel.py` v kořeni projektu. On stáhne média, vygeneruje scénář přes Claude (Sonnet 4.6), vyrobí ElevenLabs narátora (CZ + EN), přepíše Remotion data soubory a spustí render přes `npm run render:dayreel{,-en}`.

**Narátor je defaultně zapnutý.** Při běhu se hudba pod narací úplně ztiší (na 0); v silent módu (`--no-narrator`) hraje pod celým reelem.

**NIKDY neuploaduj výstup automaticky na FB.** MVP končí soubory v `output/dayreels/`.

## Postup (9 kroků)

### 1. Parse argumentů

`$ARGUMENTS` může obsahovat ISO datum (`2026-05-03`). Pokud chybí, použij dnešek:

```bash
DATE="${1:-$(date +%Y-%m-%d)}"
PY=/Users/openclaw/AI-Projects/gaming-content-agent/venv/bin/python
```

`PY` je projektové venv (kde je `dotenv`, `requests`, `yt-dlp`). Použij ho místo systémového `python`/`python3` ve všech krocích.

### 2. Dry-run — vypsat dnešní články

```bash
cd /Users/openclaw/AI-Projects/gaming-content-agent
"$PY" dayreel.py --date "$DATE" --dry-run
```

Skript vypíše počet článků a tituly. Pokud je počet 0:

> Žádné články dnes nepublikovány. Konec, nic se neudělá.

…a v dalších krocích nepokračuj.

### 3. Konfirmace s uživatelem

Stručně potvrď:
- datum,
- počet sekcí (max 6, sortováno podle viralityScore desc),
- jazykové verze (`cs` + `en`, EN se přeskočí pokud žádný článek nemá `en_url`),
- výstupní cesty `output/dayreels/<DATE>_CZ.mp4` a `_EN.mp4`,
- **narátor**: zapnut (default) → CZ voice `XOgpjkYNnVH5W7ZAlLYg` (ženský), EN voice `DXFkLCBUTmvXpp2QwZjA`,
- **odhad nákladů**: Claude scénář ~$0.01/lang, ElevenLabs ~6 KB znaků/lang ≈ $0.20–0.30/lang,
- info: render bere ~4–6 min (yt-dlp + ElevenLabs TTS + Remotion).

Pokud uživatel chce silent verzi bez narátora, použij `--no-narrator` a přeskoč kroky 4–5 (rovnou na krok 6).

Pokračuj jen po `OK` od uživatele.

### 4. Generování scénáře narátora (Claude only, žádné TTS)

```bash
cd /Users/openclaw/AI-Projects/gaming-content-agent
"$PY" dayreel.py --date "$DATE" --lang both --narrator-plan-only
```

Skript zavolá Claude (Sonnet 4.6) pro každý jazyk a zapíše JSON do:

- `output/dayreel-scripts/<DATE>-cs.json`
- `output/dayreel-scripts/<DATE>-en.json` (pokud aspoň 1 článek má `en_url`)

Žádné TTS, žádné stahování médií, žádný render. Trvá ~10–20 sekund.

### 5. Schválení textu uživatelem (POVINNÉ)

Přečti oba JSON soubory a **zobraz uživateli plný text** (intro, všechny sekce, outro) — CZ verzi i EN, pokud existuje. Použij např.:

```bash
cat /Users/openclaw/AI-Projects/gaming-content-agent/output/dayreel-scripts/${DATE}-cs.json
cat /Users/openclaw/AI-Projects/gaming-content-agent/output/dayreel-scripts/${DATE}-en.json
```

Pak ve zprávě uživateli pěkně zformátuj (intro / sections očíslované / outro) a zeptej se, jestli text schvaluje nebo chce úpravy.

**Možnosti uživatele:**
- **OK / schválit** → pokračuj krokem 6.
- **úpravy přímo** → ručně edituj JSON soubory (zachovej strukturu `{intro, sections[], outro}`), pak pokračuj krokem 6. Synthesize fáze JSON automaticky reuse.
- **přegenerovat** → smaž JSON a opakuj krok 4 (volitelně `--narrator-plan-only` po smazání).

**Nepokračuj bez explicitního souhlasu nebo úpravy.**

### 6. Spuštění orchestrátoru

```bash
cd /Users/openclaw/AI-Projects/gaming-content-agent
"$PY" dayreel.py --date "$DATE" --lang both
# pro silent verzi:
# "$PY" dayreel.py --date "$DATE" --lang both --no-narrator
```

Před spuštěním ověř, že je nastaveno `ELEVENLABS_API_KEY` v prostředí (jinak skript dropne do silent módu a vypíše warning). `DAYREEL_VOICE_ID_CS` / `DAYREEL_VOICE_ID_EN` mají defaulty (viz výše); přepíšou se přes env, když je potřeba jiný hlas.

Skript:
1. Smaže `promo-video/public/dayreel/`, `public/audio/` a `public/narration/` (NE `output/dayreel-scripts/` — schválené scénáře přežijí).
2. Pro každý článek zkusí stáhnout 5–12s úsek YouTube traileru (`yt-dlp --download-sections`). Když selže, zkusí WP featured image, pak RAWG `background_image`. Když selže vše, sekci přeskočí.
3. Zkopíruje vybranou hudbu do `public/audio/`.
4. **Narátor:** Načte schválený scénář z `output/dayreel-scripts/<DATE>-{cs,en}.json` (přeskočí Claude call, scénář už existuje), ElevenLabs generuje MP3 pro každý segment. Délky se zapíší do `public/narration/durations-{cs,en}.json`. Při selhání kterékoliv části → silent mode pro daný jazyk, pipeline pokračuje.
5. Zapíše `promo-video/src/dayReelData.ts` a `dayReelDataEN.ts` (včetně narration polí).
6. Spustí `npm run render:dayreel` a `npm run render:dayreel-en`.
7. Přesune MP4 z `promo-video/out/` do `output/dayreels/`.

Pozoruj stdout/stderr — chyby v yt-dlp jsou očekávatelné (region-block, age-gate), fallback na image je normální. ElevenLabs HTTP chyby zaloguje skript a spadne do silent módu pro daný jazyk.

### 7. Verifikace médií

```bash
ls -lh /Users/openclaw/AI-Projects/gaming-content-agent/promo-video/public/dayreel/
ls -lh /Users/openclaw/AI-Projects/gaming-content-agent/promo-video/public/audio/
ls -lh /Users/openclaw/AI-Projects/gaming-content-agent/promo-video/public/narration/
```

Každá sekce má buď `aNN-trailer.mp4` (>50KB) nebo `aNN-image.jpg`. V audio musí být právě jeden MP3. V narration: `dayreel-{cs,en}-intro.mp3`, `aNN.mp3` per sekci, `outro.mp3` + `durations-{cs,en}.json`.

Pokud orchestrátor zalogoval `žádná média — sekce přeskočena`, upozorni uživatele kolik sekcí finálně reelu má. Pokud `narátor přeskočen` / `narátor selhal`, video se vyrenderuje bez naratora (silent mode, hudba na 0.6).

### 8. Render check

Render se spouští sám v kroku 4. Pokud render selhal, spusť ručně pro debug:

```bash
cd /Users/openclaw/AI-Projects/gaming-content-agent/promo-video
npm run render:dayreel
```

Pro vizuální preview v Remotion Studiu:

```bash
cd /Users/openclaw/AI-Projects/gaming-content-agent/promo-video
npm run studio
```

→ otevři `DayReel` / `DayReelEN`.

### 9. Report

```bash
ls -lh /Users/openclaw/AI-Projects/gaming-content-agent/output/dayreels/${DATE}_*.mp4
ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 \
  /Users/openclaw/AI-Projects/gaming-content-agent/output/dayreels/${DATE}_CZ.mp4
```

Vypiš uživateli:
- cesty k MP4 souborům,
- velikost a délku,
- **upozornění**: žádný auto-upload, postuje se ručně přes FB Page → Vytvořit příspěvek → Reels.

## Edge cases

| Případ | Chování |
|---|---|
| 0 článků v daný den | Krok 2 zachytí, skript exit 0, nic dalšího. |
| Všechny sekce bez médií (yt-dlp i RAWG selžou) | Orchestrátor exit 1 před renderem, žádný prázdný Reel. |
| Žádný článek nemá `en_url` | EN render přeskočen, zůstane jen CZ. |
| yt-dlp není v PATH ani v venv | Krok 4 zaloguje `yt-dlp není nainstalován`, pokračuje s RAWG image fallbackem. |
| Hudba chybí v `promo-video/out/` | Orchestrátor `FileNotFoundError`, oprav cestu k MP3. |
| `ELEVENLABS_API_KEY` chybí | Skript warning a silent mode pro daný jazyk (hudba na 0.6, žádná narace). |
| Claude scénář / ElevenLabs HTTP error | Silent mode pro daný jazyk, druhý jazyk se zkusí dál. |
| Uživatel chce silent mode | `--no-narrator` přeskočí Claude/ElevenLabs úplně (přeskoč i kroky 4–5). |
| Uživatel chce přegenerovat scénář | Smaž `output/dayreel-scripts/<DATE>-{cs,en}.json` a opakuj krok 4. Bez smazání skript JSON reuse. |
| Uživatel chce upravit text ručně | Edituj JSON soubor přímo, zachovej `{intro, sections[], outro}` strukturu; krok 6 ho použije bez Claude regenerace. |

## Co skill **neudělá** (záměrně mimo MVP)

- Nepostne na Facebook ani jinam — uživatel uploaduje ručně.
- Nestahuje data z RAWG `/movies` endpointu (článek-reel skill ano, dayreel ne — yt-dlp dává konzistentnější starty).

Pro budoucí rozšíření viz plán: `~/.claude/plans/ja-bych-potreboval-abys-structured-sutherland.md`.
