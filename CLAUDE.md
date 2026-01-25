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

### Struktura šablony
- `style.css` - hlavní styly (terminal design)
- `functions.php` - PHP funkce, meta boxy, AJAX
- `header.php` - hlavička s language switcherem
- `front-page.php` - úvodní stránka
- `template-parts/content-news-item.php` - šablona článku v seznamu

### Vlastní pole (Custom Fields)
- `gameinfo_source` - zdroj článku
- `gameinfo_audio_url` - URL na audio verzi článku

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
