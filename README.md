# 🎮 Gaming Content Agent

Automatický agent, který denně monitoruje herní weby a navrhuje témata článků pro tvůj blog.

## ✨ Funkce

- 📡 **Automatické stahování** z 8+ herních RSS feedů (IGN, GameSpot, Bonusweb...)
- 🧠 **AI analýza** pomocí Claude 3.5 Sonnet
- 🎯 **Navrhuje konkrétní články** včetně titulků, úhlu pohledu a SEO keywords
- 📧 **Denní email report** s top 5 tématy
- 🔥 **Viralita scoring** - prioritizuje hot témata
- 🇨🇿 **Zaměřeno na české publikum**

## 🚀 Rychlý start

### 1. Klonuj repozitář

```bash
git clone https://github.com/tvuj-github/gaming-content-agent.git
cd gaming-content-agent
```

### 2. Vytvoř virtuální prostředí

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Mac/Linux
python3 -m venv venv
source venv/bin/activate
```

### 3. Nainstaluj závislosti

```bash
pip install -r requirements.txt
```

### 4. Nastav konfiguraci

```bash
# Zkopíruj šablonu
copy .env.example .env

# Uprav .env a vyplň:
# - CLAUDE_API_KEY (z console.anthropic.com)
# - EMAIL_TO (tvůj email)
# - Volitelně SMTP pro odesílání emailů
```

### 5. Spusť agenta

```bash
python main.py
```

## ⚙️ Konfigurace

### Claude API Klíč

1. Jdi na [console.anthropic.com](https://console.anthropic.com)
2. Vytvoř účet a přidej platební metodu
3. Vytvoř API klíč v sekci "API Keys"
4. Zkopíruj klíč do `.env` souboru

**Odhadované náklady:** ~$0.50 za běh (15-30 Kč/den)

### Email nastavení (volitelné)

Pro Gmail použij **App Password** (ne tvé běžné heslo):

1. Jdi do Google Account → Security
2. Zapni 2-Step Verification
3. Vytvoř App Password
4. Použij tento password v `.env` jako `SMTP_PASSWORD`

Pokud nenastavíš SMTP, report se zobrazí jen v konzoli a uloží do souboru.

## 📁 Struktura projektu

```
gaming-content-agent/
├── main.py              # Hlavní spouštěcí skript
├── config.py            # Konfigurace a nastavení
├── rss_scraper.py       # Stahování článků z RSS
├── claude_analyzer.py   # AI analýza pomocí Claude
├── email_sender.py      # Odesílání email reportů
├── requirements.txt     # Python závislosti
├── .env.example         # Šablona pro nastavení
├── .env                 # Tvé nastavení (ignorováno Gitem)
├── .gitignore           # Co nejde na GitHub
└── README.md            # Dokumentace
```

## 🎯 Přidání dalších zdrojů

Uprav `RSS_FEEDS` v [config.py](config.py:23):

```python
RSS_FEEDS = [
    {"name": "Tvůj web", "url": "https://web.cz/rss", "lang": "cs"},
    # ... další
]
```

## 🤖 Automatizace

### GitHub Actions (doporučeno, zdarma)

1. Nahraj projekt na GitHub
2. Nastav Secrets v GitHub:
   - `CLAUDE_API_KEY`
   - `EMAIL_TO`
   - Volitelně `SMTP_USER` a `SMTP_PASSWORD`

3. Vytvoř `.github/workflows/daily-run.yml`:

```yaml
name: Daily Content Discovery

on:
  schedule:
    - cron: '0 8 * * *'  # Každý den v 8:00 UTC
  workflow_dispatch:

jobs:
  run-agent:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v4
        with:
          python-version: '3.11'
      - run: pip install -r requirements.txt
      - env:
          CLAUDE_API_KEY: ${{ secrets.CLAUDE_API_KEY }}
          EMAIL_TO: ${{ secrets.EMAIL_TO }}
          SMTP_USER: ${{ secrets.SMTP_USER }}
          SMTP_PASSWORD: ${{ secrets.SMTP_PASSWORD }}
        run: python main.py
```

### Windows Task Scheduler

1. Otevři Task Scheduler
2. Create Task → Trigger: Daily 8:00
3. Action: `C:\Users\jakub\gaming-content-agent\venv\Scripts\python.exe`
4. Add argument: `C:\Users\jakub\gaming-content-agent\main.py`

## 📊 Příklad výstupu

```
🎮 TÉMA 1: GTA 6 Nový Trailer
📰 NAVRŽENÝ TITULEK: GTA 6: Rozbor druhého traileru - co nás čeká v roce 2025?
🎯 ÚHEL POHLEDU: Detailní analýza traileru s easter eggy
🔥 VIRALITA: 95/100
💡 PROČ TEĎKA: Trailer vyšel dnes, obrovský zájem komunity
🔗 ZDROJE: https://ign.com/gta6-trailer, https://gamespot.com/...
🏷️ SEO: GTA 6, trailer, analýza, Rockstar Games, 2025

🎮 TÉMA 2: Palworld překonal 2M hráčů
📰 NAVRŽENÝ TITULEK: Palworld: Proč "Pokémon s puškami" dobyl herní svět?
🎯 ÚHEL POHLEDU: Analýza úspěchu, srovnání s Pokémonem
🔥 VIRALITA: 85/100
💡 PROČ TEĎKA: Hra právě explodovala na Steamu
🔗 ZDROJE: https://pcgamer.com/palworld...
🏷️ SEO: Palworld, survival, Steam, hit hry 2026
```

## 🔧 Testování

Každý modul můžeš testovat samostatně:

```bash
# Test RSS scraperu
python rss_scraper.py

# Test Claude API (spotřebuje tokeny!)
python claude_analyzer.py

# Test email senderu
python email_sender.py
```

## 💰 Náklady

- **Claude API:** ~$0.50/běh = ~$15/měsíc (denní běh)
- **GitHub Actions:** Zdarma (2000 min/měsíc)
- **Email (Gmail):** Zdarma
- **Celkem:** ~$15/měsíc

**Tip:** Použij Claude 3.5 Haiku místo Sonnet pro úsporu (~$5/měsíc).

## 🛠️ Troubleshooting

### "ModuleNotFoundError: No module named 'dotenv'"
```bash
pip install python-dotenv
```

### "CLAUDE_API_KEY není nastavený"
- Zkontroluj, že soubor `.env` existuje (ne `.env.example`)
- Ověř, že API klíč začíná `sk-ant-api03-`

### Email se neodesílá
- Pro Gmail použij App Password, ne běžné heslo
- Zkontroluj, že máš zapnuté "Less secure app access"
- Agent funguje i bez emailu - report se uloží do souboru

### "Feed parsing error"
- Některé weby mohou mít dočasně nedostupný RSS
- Agent pokračuje s dalšími zdroji

## 🚀 Další rozšíření

- [ ] Reddit integrace (r/gaming, r/pcgaming)
- [ ] YouTube trending videos analýza
- [ ] Steam API - nové hry a updaty
- [ ] Sentiment analýza komentářů
- [ ] Automatické vytváření draft článků v WordPress
- [ ] Dashboard s vizualizací trendů

## 📝 Licence

MIT License - použij jak chceš!

## 🤝 Přispívání

Pull requesty vítány! Máš nápad na vylepšení? Vytvoř issue.

## 📧 Kontakt

Máš dotaz nebo problém? Vytvoř issue na GitHubu.

---

**Made with ❤️ for Czech gaming bloggers**
