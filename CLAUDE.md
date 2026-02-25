# Gaming Content Agent - Poznámky pro Claude

## PRAVIDLA

- **NIKDY neprovádět `git commit`, `git push`, `eas build`, ani `eas submit` bez výslovného souhlasu uživatele.** Platí i pro amend, force-push, tag push a jakýkoliv deploy na Expo/EAS. Vždy počkat na explicitní pokyn.
- **Verzování:** Při každé změně kódu (WP šablona, appka, skripty) vždy zvýšit číslo verze a zapsat changelog. U WP šablony: `Version` v `style.css` + záznam v `readme.txt` sekci Changelog. U appky: `version` v `app.config.ts`. Nikdy nevytvářet build/ZIP bez aktualizace verze.

---

## Přehled projektu

Automatizovaný systém pro české gaming bloggery. Monitoruje herní weby (12 RSS feedů), analyzuje trendy Claude AI (Sonnet 4), posílá denní reporty emailem.

```
RSS Feeds → rss_scraper.py → claude_analyzer.py → email_sender.py
                  ↓
           JSON/CSV (output/) → web_app.py (Flask :5000)
```

- **Spuštění:** `python main.py` (pipeline) nebo `python web_app.py` (web UI)
- **Deduplikace:** `processed_articles.json` — filtruje nové články, čistí po 30 dnech
- **Náklady:** ~$0.02–0.06/běh analýzy (Sonnet 4, ~5 800 tokenů), ~$0.05–0.20 navíc za vygenerovaný článek

---

## WordPress šablona (wp-theme-gameinfo)

- **Repo:** https://github.com/CubaStromek/gamefo-wordpress-theme (private)
- **Lokální složka:** `wp-theme-gameinfo/`
- **Verze:** 1.15.6 | WP 5.0+, PHP 7.4+
- **Text Domain:** gamefo | Textdomain soubor: gameinfo-terminal
- **Terminálový design:** dark/light mode, Inter + Fira Code fonty, Material Symbols ikony

Klíčové soubory: `style.css` (2 068 ř.), `functions.php` (2 479 ř.), `assets/js/main.js` (257 ř.). Detaily vždy číst přímo ze zdrojáků.

### Šablony a MU-Plugins

- `page-about-game.php` — herní profil (two-column layout, timeline, game info sidebar)
- `mu-plugins/gamefo-game-posts.php` — shortcode `[game_posts]` (v2.0.0, Polylang filtering)
- `mu-plugins/gamefo-game-import.php` — admin Pages > Import Game (JSON, CZ/EN)
- `template-parts/content-news-item-compact.php` — kompaktní news item pro game page shortcode

### Export ZIP souborů

**NEPOUŽÍVEJ PowerShell `Compress-Archive`** — backslash cesty nefungují na Linux serverech.

Složka v ZIPu musí = Theme Name (`GAMEfo/`, ne `wp-theme-gameinfo/`). Použij Python:
```python
import zipfile, os
with zipfile.ZipFile('GAMEfo_x_x_x.zip', 'w', zipfile.ZIP_DEFLATED) as zipf:
    for root, dirs, files in os.walk('wp-theme-gameinfo'):
        for file in files:
            file_path = os.path.join(root, file)
            arcname = file_path.replace(os.sep, '/').replace('wp-theme-gameinfo', 'GAMEfo', 1)
            zipf.write(file_path, arcname)
```

---

## Ruční publikace článku (manual_article.py)

Skript pro publikaci článku na vlastní téma — přeskočí RSS/analýzu a rovnou generuje + publikuje.

**Voláno z Telegram bota** přes `/task napiš článek na GAMEfo o <téma>`.

### Postup při použití

1. **Najdi 2–3 zdrojové články** k tématu (URL anglických herních webů — IGN, PC Gamer, Kotaku atd.)
2. Spusť skript:

```bash
python /Users/openclaw/AI-Projects/gaming-content-agent/manual_article.py \
  --topic "Gothic remake" \
  --game-name "Gothic" \
  --sources "https://ign.com/article1,https://pcgamer.com/article2" \
  --seo-keywords "gothic,remake,rpg" \
  --status-tag news
```

### Parametry

| Parametr | Povinný | Popis |
|----------|---------|-------|
| `--topic` | ano | Popis tématu článku |
| `--sources` | ano | Zdrojové URL oddělené čárkou (min 1, max 5) |
| `--game-name` | ne | Název hry (default = topic). Použito pro RAWG obrázek, SEO, social media |
| `--title` | ne | Vlastní CZ titulek (jinak vygeneruje Claude) |
| `--seo-keywords` | ne | SEO klíčová slova oddělená čárkou |
| `--status-tag` | ne | news, update, leak, critical, success, indie, review, trailer, rumor, info, finance, tema, preview |

### Pipeline

`Zdroje → article_writer (CZ+EN) → YouTube embed → RAWG obrázek → WordPress publish → FB post obrázky → Social media (X.com, FB, Threads)`

### Příklad z Telegramu

Uživatel: `/task napiš článek na GAMEfo o tom, že GTA 6 bylo odloženo na 2027`

Claude Code CLI by měl:
1. Vyhledat 2-3 zdrojové články na webu (WebSearch)
2. Spustit `python manual_article.py --topic "GTA 6 odloženo na 2027" --game-name "GTA 6" --sources "url1,url2" --status-tag critical`

---

## Android appka (APP/)

**Package:** `com.cubastromek.gamefo` | **Config:** `APP/app.config.ts`

### Spuštění na emulátoru (jediný spolehlivý způsob)

```bash
cd "C:\AI\gaming-content-agent\APP"
JAVA_HOME="C:/Program Files/Android/Android Studio/jbr" npx expo run:android --port 8081
```

**JAVA_HOME není v PATH** — musí se nastavit ručně. Appka je custom dev build (ne Expo Go) — `npx expo start` sám o sobě nefunguje, potřebuje deep link od `expo run:android`.

Port konflikt: `netstat -ano | findstr :8081 | findstr LISTENING` → `taskkill //PID <pid> //F` (v Git Bash `//PID`).

---

## Push notifikace: WordPress → Expo → FCM → Android

```
WP publish → gamefo-push-notifications.php → Expo Push API → FCM → zařízení
```

### Credentials (3 kusy)

| Credential | Kde | K čemu |
|------------|-----|--------|
| FCM V1 service account key | expo.dev → Credentials → Android | Expo odesílá přes Firebase |
| Expo access token | WP admin → Settings → Push Notifications | WP → Expo API auth |
| google-services.json | `APP/google-services.json` | Firebase config v appce |

### Gotchas

- **`channelId: "default"` je povinný** v payloadu — bez něj Android 8+ notifikaci tiše zahodí
- **Firebase Cloud Messaging API (V1)** musí být zapnutá v Google Cloud Console
- Push log: WP admin → Settings → Push Notifications → Push Log (posledních 50)
- `InvalidCredentials` = chybí FCM V1 key na expo.dev
- `DeviceNotRegistered` = expirovaný push token

### Klientská strana (APP/)

- `APP/src/services/pushNotifications.ts` — registrace tokenu
- `APP/src/api/gamefo.ts` — POST/DELETE na `/gamefo/v1/devices`
- `APP/src/hooks/usePushNotifications.ts` — hook
- `App.tsx` — notification handler
