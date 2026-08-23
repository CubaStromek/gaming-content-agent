---
name: article-reel
description: Vygeneruje krátké vertikální video (Reel 1080×1920) z článku na gamefo.cz pomocí Remotion.
argument-hint: [název článku nebo URL]
allowed-tools: Bash, Read, Glob, Write, WebFetch, Edit
---

# Generátor Article Reel videa pro GAMEfo.cz

Vygeneruj krátké vertikální video (Reel 9:16, 1080×1920) z článku na gamefo.cz. Výstup je MP4 pro Facebook/Instagram Reels. Používá **Remotion** (`promo-video/` složka).

## Postup (7 kroků)

### 1. Najít článek

Pokud uživatel zadal argumenty `$ARGUMENTS`, použij je jako hledaný výraz.
Pokud ne, zeptej se na název článku nebo URL.

Vyhledej článek přes WP REST API:

```bash
curl -s "https://gamefo.cz/wp-json/wp/v2/posts?search=VYRAZ&_embed&per_page=10"
```

Z odpovědi získej:
- `title.rendered` — titulek
- `content.rendered` — HTML obsah
- `_embedded.wp:featuredmedia[0].source_url` — featured image URL
- `link` — URL článku
- `date` — datum publikace

Pokud je víc výsledků, ukaž uživateli seznam a nech ho vybrat.

### 2. Extrahovat H2 nadpisy

Z HTML obsahu (`content.rendered`) vytáhni všechny `<h2>` nadpisy. Každý H2 = jeden slide.

- **Max 8 sekcí** (limit 60s pro Reels)
- Zkrátit každý nadpis na ~60 znaků

### 3. Stáhnout video z RAWG (primárně) + obrázky (fallback)

**NIKDY nečíst obrázky/videa přes Read tool!** Používat jen `Glob` nebo `ls` pro kontrolu souborů.

1. Vyčistit složku: `rm -f /Users/openclaw/AI-Projects/gaming-content-agent/promo-video/public/article-reel/*`
2. Stáhnout featured image (pro intro slide) → `slide-featured.jpg`
3. Najít hru a její trailer přes RAWG:

```bash
# Najít game ID
curl -s "https://api.rawg.io/api/games?key=$RAWG_API_KEY&search=NAZEV_HRY&page_size=1"

# Stáhnout movies (trailers/gameplay videa)
curl -s "https://api.rawg.io/api/games/GAME_ID/movies?key=$RAWG_API_KEY"
```

Z odpovědi vzít první video → `data.480` URL (rychlejší download, dostatečná kvalita pro Reel) a uložit do `slide-trailer.mp4`:

```bash
cd /Users/openclaw/AI-Projects/gaming-content-agent/promo-video/public/article-reel/
curl -sL "URL_FEATURED_IMAGE" -o slide-featured.jpg
curl -sL "TRAILER_480_URL" -o slide-trailer.mp4
```

**Strategie offsetů:** Trailer bývá 60–180s. Každá sekce dostane jiný start time:
- Zjistit délku traileru: `ffprobe -v error -show_entries format=duration -of default=nw=1:nk=1 slide-trailer.mp4`
- Rozdělit délku na N+2 částí (vynechat první/poslední 5s) a přiřadit sekcím rovnoměrně.
- Příklad pro 90s trailer a 4 sekce: starty 10s, 28s, 46s, 64s.

`RAWG_API_KEY` je v `.env` souboru projektu.

**Fallback (žádné video v RAWG):**
- Stáhnout screenshoty: `curl -s "https://api.rawg.io/api/games/GAME_ID/screenshots?key=$RAWG_API_KEY"`
- Uložit do `slide-01.jpg`, `slide-02.jpg`... a v datech naplnit pouze `imageFile` (bez `videoFile`).

**Mix:** Lze i kombinovat — některé sekce video (`videoFile` + `videoStartSec`), jiné statický obrázek (`imageFile`).

### 4. Vygenerovat data

Přepiš soubor `promo-video/src/articleReelData.ts`:

```typescript
import { ArticleReelData } from './ArticleReel';

export const articleReelData: ArticleReelData = {
  articleTitle: "PLNY TITULEK CLANKU",
  shortTitle: "KRATKY POUTAVY TITULEK UPPERCASE",  // max ~40 znaků, UPPERCASE
  gameName: "NAZEV HRY",
  date: "DD.MM.YYYY",
  articleUrl: "https://gamefo.cz/...",
  featuredImage: "slide-featured.jpg",
  sections: [
    // Video varianta (preferované): imageFile slouží jako fallback poster
    { heading: "H2 nadpis 1", imageFile: "slide-featured.jpg", videoFile: "slide-trailer.mp4", videoStartSec: 10 },
    { heading: "H2 nadpis 2", imageFile: "slide-featured.jpg", videoFile: "slide-trailer.mp4", videoStartSec: 28 },
    // Statická varianta (když video není k dispozici):
    // { heading: "H2 nadpis 3", imageFile: "slide-03.jpg" },
  ],
};
```

**shortTitle** musí být UPPERCASE a poutavý — ne doslovný překlad H1.

**Pole `videoFile`** je volitelné — když je vyplněné, slide použije `<OffthreadVideo>` (muted, startuje na `videoStartSec`). Když chybí, použije se `<Img>` z `imageFile`.

### 5. Ověřit délku

Vzorec: `3 + (N × 3.5) + 4` sekund, kde N = počet sekcí.

- Max 8 sekcí = 35s
- Musí být pod 60s

### 6. Zobrazit souhrn

Ukaž uživateli:
- Název článku
- Počet sekcí a jejich nadpisy
- Celková délka videa
- Počet stažených obrázků
- Nabídni: **Preview** (`npm run studio`) nebo **Render** (`npm run render:article`)

### 7. Render

```bash
cd /Users/openclaw/AI-Projects/gaming-content-agent/promo-video && npm run render:article
```

Výstup: `promo-video/out/article-reel.mp4`

## Struktura videa

| Slide | Délka | Obsah |
|-------|-------|-------|
| Intro | 3s | Featured image, název hry, titulek, datum, logo |
| Sekce 1–N | 3.5s každá | Screenshot + Ken Burns zoom, H2 nadpis přes gradient |
| Outro | 4s | CTA "Celý článek na gamefo.cz", logo |

## Vizuální styl

- Tmavý terminálový design (#1a1c1e)
- Fonty: JetBrains Mono, Share Tech Mono
- Scanline overlay, glitch efekt na logu
- Ken Burns zoom (1.0 → 1.15), spring animace textu, crossfade 15 framů
- Dekorativní rohy (teal/green), progress bar

## Klíčové soubory

```
promo-video/src/
├── ArticleReel.tsx              # Hlavní kompozice
├── articleReelData.ts           # Data pro konkrétní článek
└── scenes/article/
    ├── ArticleIntroSlide.tsx
    ├── ArticleSectionSlide.tsx
    └── ArticleOutroSlide.tsx
```

## Gotchas

- **NIKDY nečíst obrázky/videa přes Read tool!** WebP a mp4 → 400 error.
- **Safe zones:** FB/IG UI překrývá spodní ~300-350px a horní ~100-150px — řeší komponenty automaticky.
- **Media lokálně:** Trailer i obrázky se stahují do `public/article-reel/` aby render nebyl závislý na síti.
- **RAWG `/movies`:** Vrací typicky 1–2 trailery; pro novější/indie hry často nic. Vždy mít fallback na screenshoty.
- **Audio:** `<OffthreadVideo>` se renderuje s `muted` — trailer audio by se sekalo mezi klipy.
- **`videoStartSec`:** Musí být uvnitř délky traileru (zjisti přes `ffprobe`). Sekce trvá 3.5s, takže start nesmí být blíž než 3.5s ke konci.
- **Před každým novým článkem vyčistit** složku `public/article-reel/`.
- Existuje i EN varianta (`ArticleReelEN`, `articleReelDataEN.ts`) — sdílí stejný `ArticleSection` typ, takže videa fungují i tam.
