# Gaming Content Agent - Poznámky pro Claude

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
- **Verze:** 1.7.3
- **WP:** 5.0+, PHP 7.4+, testováno na WP 6.4

### Struktura souborů

```
wp-theme-gameinfo/
├── assets/
│   ├── css/
│   ├── fonts/
│   └── js/main.js                  (JS: theme toggle, AJAX load more, dropdown, search)
├── languages/
│   ├── gameinfo-terminal.pot        (překlad šablona)
│   ├── cs_CZ.po / .mo              (české překlady)
├── mu-plugins/
│   └── gamefo-game-posts.php        (shortcode [game_posts tag="slug" limit="10"])
├── template-parts/
│   ├── category-tabs.php            (kategorie navigace s ikonami)
│   └── content-news-item.php        (news item v seznamu)
├── style.css          (1 470 ř.) - všechny styly, CSS proměnné, dark/light mode
├── functions.php      (1 266 ř.) - funkce, walker, meta boxy, AJAX, REST API, customizer
├── header.php         - terminálová hlavička, navigace, search, theme toggle, lang switcher
├── footer.php         - patička s verzí z style.css
├── front-page.php     - úvodní stránka s category tabs a stránkováním
├── index.php          - blog index s AJAX load more
├── single.php         - detail článku (featured image, tagy, navigace, komentáře)
├── archive.php        - archiv/kategorie (dynamické titulky ve stylu terminálu)
├── search.php         - výsledky hledání
├── 404.php            - chybová stránka
├── page.php           - standardní stránka
├── home.php           - homepage
├── comments.php       - komentáře (terminálový styl)
├── sidebar.php        - widget area
├── readme.txt
├── debug-posts.php    - debug utilita (podmíněné vložení)
└── MULTILINGUAL-SETUP.md
```

### Design systém

**Barvy (CSS proměnné):**
| Proměnná | Dark mode | Light mode |
|----------|-----------|------------|
| Primary | `#13a4ec` | `#0284c7` |
| Background | `#101c22` | — |
| Console BG | `#1e1e1e` | `#ffffff` |
| Header BG | `#181818` | `#f0f2f4` |
| Input BG | `#282828` | `#e5e7eb` |
| Terminal green | `#4ade80` | — |
| Text primary | `#d1d5db` | — |
| Text secondary | `#9ca3af` | — |

**Status tag barvy:** leak=#f97316, critical=#ef4444, success=#4ade80, indie=#a78bfa, review=#38bdf8, trailer=#fbbf24, rumor=#fb923c, update=#2dd4bf, news=#13a4ec, info=#6b7280

**Fonty:** Inter (body), Fira Code (terminal/monospace), Material Symbols Outlined (ikony)

### Klíčové funkce (functions.php)

| Funkce | Popis |
|--------|-------|
| `gameinfo_get_post_status_data()` | Mapuje kategorie/tagy → status štítky (LEAK, REVIEW, TRAILER...) |
| `gameinfo_language_switcher()` | Polylang přepínač jazyků, fallback na CZ/EN |
| `gameinfo_load_more_posts()` | AJAX endpoint pro stránkování (wp_ajax) |
| `gameinfo_include_subcategory_posts()` | Automaticky zahrnuje podkategorie v archivech |
| `GameInfo_Walker_Nav_Menu` | Custom walker pro dropdown navigaci |
| `GameInfo_Walker_Category_Tabs` | Walker pro kategorie taby s ikonami |

**3 menu lokace:** primary (hlavní + dropdown), category-tabs (herní kategorie), footer
**2 widget areas:** primary-sidebar, footer-widget-area

### Vlastní pole (Custom Fields)
- `gameinfo_source` - zdroj článku (zobrazí se jako doména)
- `gameinfo_audio_url` - URL na audio verzi článku
- Obě pole registrována v REST API

### Customizer nastavení
- **Terminal Title** (default: "game_info")
- **Terminal Path** (default: "~/news")
- **Build Version** (default: "2.4.0-stable")
- **Facebook URL** (volitelné)

### JavaScript (main.js)
- Theme toggle (localStorage + prefers-color-scheme)
- AJAX Load More s category filtrováním
- Dropdown menu (hover desktop / click mobile)
- Search focus: Ctrl/Cmd+K, Escape pro blur
- Terminálové efekty (cursor animace)

### Kategorie → ikony mapování
indie→token, triple/aaa→rocket_launch, hardware/tech→memory, news/zprávy→newspaper, review/recenze→rate_review, default→database

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
