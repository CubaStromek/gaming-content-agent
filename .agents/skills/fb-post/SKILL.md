---
name: fb-post
description: Vygeneruje Facebook post obrázek pro GAMEfo.cz z náhledového obrázku, názvu hry a titulku článku.
argument-hint: [cesta-k-obrazku] [nazev-hry] [titulek]
allowed-tools: Bash, Read, Glob
---

# Generátor Facebook post obrázku pro GAMEfo.cz

Vygeneruj Facebook post obrázek pomocí skriptu `fb_generator/generate_fb_post.py`.

## Postup

1. **Zjisti parametry od uživatele.** Potřebuješ:
   - **Náhledový obrázek** (cesta k souboru — .jpg/.png)
   - **Název hry** (bílý text nahoře, např. "Pokémon Pokopia")
   - **Titulek článku** (žlutý text dole, např. "Animal Crossing & Minecraft?")

2. Pokud uživatel zadal argumenty: `$ARGUMENTS`, parsuj je jako: `[cesta] [název hry] [titulek]`.

3. Pokud některý parametr chybí, zeptej se uživatele.

4. **Spusť generátor:**

```bash
cd /Users/openclaw/AI-Projects/gaming-content-agent && python3 -c "
from fb_generator.generate_fb_post import generate_fb_post
generate_fb_post(
    thumbnail_path='CESTA_K_OBRAZKU',
    title='NAZEV_HRY',
    subtitle='TITULEK',
    output_path='output/fb-posts/NAZEV_SOUBORU.png',
)
"
```

5. Název výstupního souboru: `output/fb-posts/YYYY-MM-DD_NazevHry.png`

6. **Ukaž výsledek** — přečti vygenerovaný obrázek pomocí Read tool a zobraz uživateli.

7. Pokud uživatel chce úpravy (jiný text, jiný obrázek), vygeneruj znovu.

## Vrstvy obrázku (940x788 px)

1. Pozadí (`FB_LAYOUT_pozadi.png`)
2. Náhledový obrázek hry (cover fit)
3. Logo GAMEfo (`gamefo_logo_transparent.png`) — překrývá horní část
4. Oddělovací čára (`FB_LAYOUT_cara.png`) — na spodní hraně obrázku
5. Text: název hry (bílý) + titulek (žlutý) — font Digitalt
