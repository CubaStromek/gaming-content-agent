# Gaming Content Agent - Poznámky pro Claude

## PRAVIDLA

- **NIKDY neprovádět `git commit`, `git push`, `eas build`, ani `eas submit` bez výslovného souhlasu uživatele.** Platí i pro amend, force-push, tag push a jakýkoliv deploy na Expo/EAS. Vždy počkat na explicitní pokyn.

---

## Přehled projektu

Automatizovaný systém pro české gaming bloggery. Monitoruje herní weby (9 RSS feedů), analyzuje trendy Claude AI (Haiku), posílá denní reporty emailem.

```
RSS Feeds → rss_scraper.py → claude_analyzer.py → email_sender.py
                  ↓
           JSON/CSV (output/) → web_app.py (Flask :5000)
```

- **Spuštění:** `python main.py` (pipeline) nebo `python web_app.py` (web UI)
- **Deduplikace:** `processed_articles.json` — filtruje nové články, čistí po 30 dnech
- **Náklady:** ~$2.00/běh (Haiku 4.5 model)

---

## WordPress šablona (wp-theme-gameinfo)

- **Repo:** https://github.com/CubaStromek/gamefo-wordpress-theme (private)
- **Lokální složka:** `wp-theme-gameinfo/`
- **Verze:** 1.13.8 | WP 5.0+, PHP 7.4+
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
