# Gaming Content Agent - Poznámky pro Claude

## PRAVIDLA

- **NIKDY neprovádět `git commit`, `git push`, ani `eas build` bez výslovného souhlasu uživatele.** Vždy se nejdřív zeptej, než commitneš, pushneš nebo spustíš EAS build (preview/production).

---

## Přehled projektu

**Účel:** Automatizovaný systém pro objevování herního obsahu pro české gaming bloggery. Monitoruje herní weby, analyzuje trendy pomocí Claude AI a poskytuje denní reporty s návrhy článků.

### Architektura

```
RSS Feeds → Scraper → Claude AI Analyzer → Email/Report
                ↓
         JSON/CSV Storage → Web Dashboard
```

### Klíčové moduly

| Modul | Funkce |
|-------|--------|
| `main.py` | Hlavní vstupní bod, orchestrace celého pipeline |
| `config.py` | Konfigurace, RSS zdroje (9 feedů), env proměnné |
| `rss_scraper.py` | Stahování a parsování článků z RSS |
| `claude_analyzer.py` | AI analýza pomocí Claude API (model: claude-3-haiku) |
| `email_sender.py` | Odesílání reportů emailem (Gmail SMTP) |
| `file_manager.py` | Správa výstupních složek (output/YYYYMMDD_HHMMSS) |
| `article_history.py` | Deduplikace - pamatuje si zpracované články |
| `web_app.py` | Flask webové rozhraní na localhost:5000 |

### RSS zdroje
- **Mezinárodní (EN):** IGN, GameSpot, PC Gamer, Rock Paper Shotgun, Kotaku, Polygon
- **České (CS):** Hrej.cz, Zing.cz, Jiří Bigas (Substack)

### Výstupy Claude analýzy
- **TOP 5 témat** s návrhy titulků a úhlů pohledu
- **Virality score** (1-100)
- **SEO klíčová slova**
- **Vizuální návrhy** pro bannery
- **Zdroje** s přesnými URL

### Výstupní soubory (v output/YYYYMMDD_HHMMSS/)
- `articles.json` - stažené články s metadaty
- `articles.csv` - Excel-kompatibilní tabulka
- `report.txt` - Claude analýza + statistiky

### Spuštění
- **Přímo:** `python main.py`
- **Web UI:** `python web_app.py` → http://localhost:5000
- **Automatizace:** GitHub Actions (denní cron) nebo Windows Task Scheduler

### Náklady
~$0.50 za běh (~$15/měsíc při denním spouštění) - používá Haiku model

### Deduplikace článků
Agent si pamatuje již zpracované články v `processed_articles.json`:
- Při každém běhu filtruje pouze **nové** články
- Pokud nejsou žádné nové → ukončí se bez volání Claude API (šetří peníze)
- Historie se automaticky čistí po 30 dnech
- Soubor `processed_articles.json` je v kořenové složce

---

## WordPress šablona (wp-theme-gameinfo)

- **Repo:** https://github.com/CubaStromek/gamefo-wordpress-theme (private)
- **Lokální složka:** `wp-theme-gameinfo/`
- **Verze:** 1.13.8
- **WP:** 5.0+, PHP 7.4+
- **Text Domain:** gamefo
- **Textdomain soubor:** gameinfo-terminal (v languages/)

### Struktura souborů

```
wp-theme-gameinfo/
├── assets/
│   └── js/main.js                  (JS: theme toggle, AJAX load more, dropdown, search)
├── languages/
│   ├── gameinfo-terminal.pot        (překlad šablona)
│   ├── cs_CZ.po / .mo              (české překlady)
├── mu-plugins/
│   ├── gamefo-game-posts.php        (shortcode [game_posts] v2.0.0)
│   └── gamefo-game-import.php       (import herních profilů z JSON)
├── template-parts/
│   ├── category-tabs.php            (kategorie navigace s ikonami)
│   ├── content-news-item.php        (news item v seznamu)
│   └── content-news-item-compact.php (kompaktní news item pro game page shortcode)
├── style.css          (2 068 ř.) - všechny styly, CSS proměnné, dark/light mode
├── functions.php      (2 479 ř.) - funkce, walker, meta boxy, AJAX, REST API, customizer, status tags
├── header.php         - terminálová hlavička, navigace, search, theme toggle, lang switcher
├── footer.php         - patička s verzí z style.css, UTF-8 info, post/category count
├── front-page.php     - úvodní stránka s category tabs a stránkováním
├── index.php          - blog index s AJAX load more
├── single.php         - detail článku (featured image, tagy, navigace, komentáře)
├── archive.php        - archiv/kategorie (dynamické titulky ve stylu terminálu)
├── search.php         - výsledky hledání
├── 404.php            - chybová stránka
├── page.php           - standardní stránka s [DOC] prefixem
├── page-about-game.php - herní profil (two-column layout, timeline, game info sidebar)
├── home.php           - homepage
├── comments.php       - komentáře (terminálový styl, custom callback)
├── sidebar.php        - widget area
├── readme.txt
└── MULTILINGUAL-SETUP.md
```

### Design systém

**Barvy (CSS proměnné):**
| Proměnná | Dark mode | Light mode |
|----------|-----------|------------|
| Primary | `#13a4ec` | `#0284c7` |
| Primary hover | `#0d8fd4` | `#0369a1` |
| Background | `#101c22` | — |
| Console BG | `#1e1e1e` | `#ffffff` |
| Header BG | `#181818` | `#d5d9e0` |
| Input BG | `#282828` | `#e5e7eb` |
| Terminal green | `#4ade80` | `#16a34a` |
| Text primary | `#d1d5db` | — |
| Text secondary | `#9ca3af` | — |
| Text muted | `#6b7280` | — |
| Text dim | `#4b5563` | — |
| Heading | `#fff` | — |

**Status tag barvy (10 výchozích):** leak=#f97316, critical=#ef4444, success=#4ade80, indie=#a78bfa, review=#38bdf8, trailer=#fbbf24, rumor=#fb923c, update=#2dd4bf, news=#13a4ec, info=#6b7280
- Spravovatelné přes admin: Theme > Status Tags (přidat/upravit/smazat)
- Dynamicky generované CSS styly pro status tagy

**Fonty:** Inter (4 řezy, body), Fira Code (3 řezy, terminal/monospace), Material Symbols Outlined (ikony)

### Klíčové funkce (functions.php)

| Funkce | Popis |
|--------|-------|
| `gameinfo_get_post_status_data()` | Mapuje kategorie/tagy → status štítky (LEAK, REVIEW, TRAILER...) |
| `gameinfo_get_post_tag_type()` | Klasifikace tagů: critical/normal |
| `gameinfo_get_status_tags()` | Vrací všechny status tagy s výchozími hodnotami |
| `gameinfo_language_switcher()` | Polylang přepínač jazyků |
| `gameinfo_language_switcher_fallback()` | CZ/EN tlačítka bez Polylangu |
| `gameinfo_load_more_posts()` | AJAX endpoint pro stránkování (6 postů/stránka) |
| `gameinfo_include_subcategory_posts()` | Automaticky zahrnuje podkategorie v archivech |
| `gameinfo_search_game_pages()` | AJAX endpoint pro vyhledávání herních stránek v meta boxu |
| `gameinfo_get_category_colors()` | 10 předdefinovaných barev pro kategorie |
| `gameinfo_get_type_color($type)` | Lookup barvy podle typu |
| `gameinfo_get_option($option, $default)` | Helper pro Customizer hodnoty |
| `gameinfo_get_facebook_button()` | Sociální odkaz pro header |
| `gameinfo_get_rss_button()` | RSS odkaz s Polylang podporou |
| `gameinfo_login_styles()` | Terminálový styl login stránky |
| `GameInfo_Walker_Nav_Menu` | Custom walker pro dropdown navigaci |
| `GameInfo_Walker_Category_Tabs` | Walker pro kategorie taby s ikonami |

**3 menu lokace:** primary (hlavní + dropdown), category-tabs (herní kategorie), footer
**2 widget areas:** sidebar-1 (Sidebar), footer-1 (Footer Widget Area)

### Meta boxy (4 celkem)

| Meta box | Popis |
|----------|-------|
| Source Information | Textové pole pro zdroj článku |
| Audio Version | URL pole pro audio verzi |
| Game Pages | Vyhledávání + multi-select herních stránek (AJAX) |
| Status Tag | Select dropdown s barvami (ruční přepsání auto-detekce) |

### Vlastní pole (Custom Fields)

**Pole pro příspěvky:**
- `gameinfo_source` - zdroj článku (zobrazí se jako doména)
- `gameinfo_audio_url` - URL na audio verzi článku
- `gameinfo_status_tag` - ruční status tag (fallback na auto-detect z kategorií/tagů)
- `gameinfo_game_pages` - propojené herní stránky (pole ID)

**Pole pro herní profily (page-about-game.php):**
- `series` - herní série
- `part` - díl série
- `platforms` - platformy
- `publisher` - vydavatel
- `studio` - vývojářské studio
- `game_status` - stav hry (released, development, announced, early_access, cancelled)
- `timeline` - časová osa událostí (JSON)

**REST API registrace:** `gameinfo_source`, `gameinfo_audio_url`, `gameinfo_status_tag`, `gameinfo_game_pages` — všechna v show_in_rest. Navíc REST field `status_data` (label, type, color) na postech a `color` na kategoriích.

### Systém barev kategorií

- Každá kategorie může mít vlastní barvu: `gameinfo_category_color` (hex color picker v admin)
- 10 předdefinovaných barev v `gameinfo_get_category_colors()`
- Barva dostupná přes REST API field `color` na category responses
- Podpora EN + CZ názvů kategorií s fallback matchingem

### Customizer nastavení
- **Terminal Title** (default: "game_info")
- **Terminal Path** (default: "~/news")
- **Build Version** (default: "2.4.0-stable")
- **Facebook URL** (volitelné)

### JavaScript (main.js, 257 ř.)
- Theme toggle (localStorage + prefers-color-scheme, rotační animace)
- AJAX Load More s category filtrováním (FETCHING... stav, skrytí při max pages)
- Dropdown menu (hover desktop / click mobile, auto-close)
- Search focus: Ctrl/Cmd+K, Escape pro blur, placeholder management
- Terminálové efekty (cursor animace při hover)

### Kategorie → ikony mapování
indie→token, triple/aaa→rocket_launch, hardware/tech→memory, news/zprávy→newspaper, review/recenze→rate_review, default→database

### MU-Plugins

| Plugin | Popis |
|--------|-------|
| `gamefo-game-posts.php` (v2.0.0) | Shortcode `[game_posts]` — automaticky detekuje posty z aktuální stránky přes `gameinfo_game_pages` meta. Fallback: `[game_posts tag="slug" limit="10"]`. Polylang filtering. Template: content-news-item-compact.php |
| `gamefo-game-import.php` | Admin stránka Pages > Import Game. JSON import herních profilů s preview tabulkou. Polylang integrace pro CZ/EN. Status labels: released, development, announced, early_access, cancelled |

### Herní profil šablona (page-about-game.php)

Dedikovaná šablona pro herní stránky:
- **Game header:** série, díl, platformy
- **Two-column layout:** hlavní obsah + sidebar
- **System Summary:** přehledové informace
- **Related Log Entries:** propojené články (přes `gameinfo_game_pages`)
- **Game Info box:** publisher, studio, status
- **System Archive:** timeline událostí
- **Media Asset:** featured image

### Export ZIP souborů
**DŮLEŽITÉ:** Při vytváření ZIP archivu šablony:

1. **NEPOUŽÍVEJ PowerShell `Compress-Archive`** - vytváří cesty s backslash (`\`), které nefungují na FTP/Linux serverech
2. **Název složky v ZIPu = název šablony** - složka musí odpovídat Theme Name (např. `GAMEfo/`, ne `wp-theme-gameinfo/`)
3. **Theme Name, Text Domain a složka musí být konzistentní** - pokud je šablona "GAMEfo", pak:
   - Složka v ZIPu: `GAMEfo/`
   - Theme Name v style.css: `GAMEfo`
   - Text Domain v style.css: `gamefo`

**Správný způsob** - použij Python:
```python
import zipfile
import os

zip_path = 'GAMEfo_1_0_0.zip'
source_dir = 'wp-theme-gameinfo'  # lokální složka
target_folder = 'GAMEfo'  # název složky v ZIPu (= název šablony)

with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
    for root, dirs, files in os.walk(source_dir):
        for file in files:
            file_path = os.path.join(root, file)
            # DŮLEŽITÉ: Forward slashes + přejmenování složky
            arcname = file_path.replace(os.sep, '/').replace(source_dir, target_folder, 1)
            zipf.write(file_path, arcname)
```

---

## Budoucí integrace: Google NotebookLM (analýza leden 2026)

### Cíl
Automaticky posílat denní report do NotebookLM pro generování audio souhrnu.

### Aktuální stav API

| Varianta | API | Poznámka |
|----------|-----|----------|
| **NotebookLM (free)** | ❌ | Pouze manuální web UI |
| **NotebookLM Enterprise** | ✅ | Google Cloud, placené |
| **Gemini + NotebookLM** | ✅ | Integrace od 12/2025 |

### Možné cesty k automatizaci

#### 1. NotebookLM Enterprise API (Oficiální)
- **Endpointy:** `notebooks.create`, sources API
- **Auth:** OAuth 2.0 bearer token
- **Docs:** https://docs.cloud.google.com/gemini/enterprise/notebooklm-enterprise/docs/api-notebooks
- **Proti:** Enterprise pricing

#### 2. Google Drive + ruční import (Doporučeno pro teď)
- Agent nahraje report do Google Drive
- NotebookLM má složku jako zdroj
- Ruční klik na "Generate Audio Overview"
- **Pro:** Zdarma, jednoduché

#### 3. Browser automation (Playwright)
- Plná automatizace včetně audio generování
- **Proti:** Křehké při UI změnách

#### 4. AutoContent API (Neoficiální)
- URL: https://autocontentapi.com
- Generuje NotebookLM-like audio
- **Proti:** Třetí strana, placené

### Doporučený postup pro implementaci
1. Přidat Google Drive API upload do agenta
2. V NotebookLM vytvořit notebook se zdrojem z Drive složky
3. (Volitelně) Playwright skript pro automatické generování audia

---

## Spuštění Android appky na emulátoru (APP/)

### Prerekvizity
- Android emulátor běží (ověř: `adb devices`)
- ADB cesta: `C:\Users\jakub\AppData\Local\Android\Sdk\platform-tools\adb.exe`
- Java (JAVA_HOME): `C:\Program Files\Android\Android Studio\jbr` — **není v systémovém PATH**, musí se nastavit ručně

### Správný postup (jediný spolehlivý)

```bash
cd "C:\AI\gaming-content-agent\APP"
JAVA_HOME="C:/Program Files/Android/Android Studio/jbr" npx expo run:android --port 8081
```

Tento příkaz:
1. Sestaví native Android debug APK (Gradle)
2. Nainstaluje APK na emulátor
3. Spustí Metro bundler
4. Otevře appku přes deep link `gamefo://expo-development-client/?url=...`

### Co NEFUNGUJE

| Postup | Proč nefunguje |
|--------|---------------|
| `npx expo start` + ruční otevření appky | Appka je **custom dev build** (ne Expo Go). `isMetroRunning()` vrátí `false` i když Metro běží — native kód potřebuje deep link od `expo run:android` |
| `npx expo start --dev-client` | Stejný problém — Metro běží, ale appka ho nedetekuje bez správného deep linku |
| `adb reverse tcp:8081 tcp:8081` + restart appky | Nepomůže — problém není v síti, ale v tom, že dev client potřebuje být spuštěn přes `expo-development-client://` URL |
| `npx expo run:android` bez JAVA_HOME | Selže s `JAVA_HOME is not set` |

### Řešení port konfliktu
Pokud port 8081 je obsazený:
```bash
netstat -ano | findstr :8081 | findstr LISTENING
taskkill //PID <pid> //F
```
Pozor: v Git Bash se `/PID` interpretuje jako cesta — nutno `//PID`.

### Package info
- **Package name:** `com.cubastromek.gamefo`
- **Activity:** `com.cubastromek.gamefo.MainActivity`
- **Build type:** Debug (DEBUGGABLE)
- **App config:** `APP/app.config.ts`

---

## Push notifikace: WordPress + Android (Expo)

### Architektura

```
WP publish post → gamefo-push-notifications.php → Expo Push API → FCM (Firebase) → Android zařízení
                                                        ↑
                                                  Expo access token
                                                  + FCM V1 key (na expo.dev)
```

### Potřebné credentials (3 kusy)

| Credential | Kde se nastavuje | K čemu |
|------------|-----------------|--------|
| **FCM V1 service account key** | expo.dev → Credentials → Android | Expo ho potřebuje k odeslání přes Firebase |
| **Expo access token** | WP admin → Settings → Push Notifications | WP plugin ho posílá v Authorization hlavičce na Expo API |
| **google-services.json** | `APP/google-services.json` | Klientská konfigurace Firebase v appce |

### Postup nastavení od nuly

#### 1. Firebase projekt
- Vytvoř projekt na [console.firebase.google.com](https://console.firebase.google.com)
- Přidej Android appku s package name `com.cubastromek.gamefo`
- Stáhni `google-services.json` → do `APP/`
- **DŮLEŽITÉ:** Ověř, že **Firebase Cloud Messaging API (V1)** je zapnutá:
  - [console.cloud.google.com](https://console.cloud.google.com) → APIs & Services → Library → hledej "Firebase Cloud Messaging API" → Enable

#### 2. FCM V1 klíč → Expo
- Firebase Console → Project Settings → **Service accounts** → **Generate new private key** (stáhne JSON)
- expo.dev → projekt → **Credentials** → **Android** → sekce **FCM V1 service account key** → Upload JSON
- Alternativně CLI: `npx eas credentials -p android` → Push Notifications → Upload

#### 3. Expo access token → WordPress
- expo.dev → Settings → **Access Tokens** → Create (typ Robot nebo Personal)
- WP admin → Settings → **Push Notifications** → pole "Expo Access Token" → vložit a uložit

#### 4. WP plugin
- Soubor: `gamefo-push-notifications.php`
- Nahrát do `wp-content/plugins/` a aktivovat
- Plugin automaticky:
  - Vytvoří DB tabulku `wp_gamefo_devices` pro tokeny
  - Registruje REST endpointy (`/gamefo/v1/devices`)
  - Odesílá push při publikaci nového příspěvku (`transition_post_status` hook)

#### 5. Appka (klientská strana)
- `APP/src/services/pushNotifications.ts` — registrace Expo push tokenu
- `APP/src/api/gamefo.ts` — POST/DELETE na `/gamefo/v1/devices`
- `APP/src/hooks/usePushNotifications.ts` — hook reagující na nastavení
- `App.tsx` — notification handler (foreground/background/cold start)
- Notifikační kanál: `'default'` (Android 8+)

### Push payload (server → Expo API)

```json
{
  "to": "ExponentPushToken[xxx]",
  "title": "NOVY LOG PRIJAT",
  "body": "Titulek článku",
  "data": { "postId": 123, "url": "https://gamefo.cz/slug/", "type": "new_post" },
  "sound": "default",
  "priority": "high",
  "channelId": "default"
}
```

**`channelId: "default"` je povinný** — bez něj Android 8+ notifikaci tiše zahodí.

### Debugging

- WP admin → Settings → Push Notifications → **Push Log** (posledních 50 záznamů)
- Log ukazuje: payload, Expo API response (HTTP kód + body), chyby
- Tlačítko **Send Test Notification** pro ruční test
- Expo API odpovědi:
  - `"status":"ok"` + `"id":"xxx"` = doručeno
  - `"status":"error"` + `"InvalidCredentials"` = chybí FCM V1 klíč na expo.dev
  - `"status":"error"` + `"DeviceNotRegistered"` = neplatný/expirovaný push token

### Časté problémy

| Problém | Příčina | Řešení |
|---------|---------|--------|
| `InvalidCredentials` | Chybí FCM V1 key na expo.dev | Upload service account JSON na expo.dev → Credentials → Android |
| Nic na expo.dev dashboardu | Chybí Expo access token | Vytvořit na expo.dev → Settings → Access Tokens, vložit do WP |
| Notifikace nedorazí (ale Expo vrátí ok) | Chybí `channelId` v payloadu | Přidat `"channelId": "default"` |
| `debug.log` se nevytváří | `WP_DEBUG_LOG` není zapnutý | Použít vestavěný Push Log v admin stránce pluginu |
| FCM API disabled | Cloud Messaging API není zapnutá | Google Cloud Console → APIs → Enable Firebase Cloud Messaging API |
