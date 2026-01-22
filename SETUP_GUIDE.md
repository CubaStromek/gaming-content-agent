# Setup Guide - Gaming Content Agent

Tento soubor obsahuje kompletní návod pro Claude, jak nainstalovat a spustit Gaming Content Agent na novém počítači.

---

## 📋 PROMPT PRO CLAUDE

Zkopíruj následující text a pošli Claudovi:

```
Ahoj Claude! Potřebuji tvou pomoc s nastavením projektu Gaming Content Agent na tomto počítači.

PROJECT INFO:
- GitHub repo: https://github.com/CubaStromek/gaming-content-agent
- Účel: Automatický agent pro content discovery z herních webů pomocí Claude API
- Jazyk: Python 3.10+
- Výstup: Denní reporty s návrhy článků v JSON, CSV a TXT formátu

DŮLEŽITÉ INFORMACE:
- Mám Claude API klíč: [VLOŽ SVŮJ KLÍČ Z .env SOUBORU NA PRVNÍM PC]
- Můj email: jakub.romek@gmail.com
- Pracuji na Windows

ÚKOLY:
1. Zkontroluj, jestli mám nainstalovaný Python (pokud ne, řekni mi odkud ho stáhnout)
2. Zkontroluj, jestli mám Git (pokud ne, řekni mi jak ho nainstalovat)
3. Pomoz mi naklonovat repozitář z GitHubu
4. Vytvoř virtuální prostředí a nainstaluj závislosti
5. Nastav konfiguraci (.env soubor) s mým API klíčem
6. Spusť první test agenta
7. Pokud bude nějaká chyba, pomoz mi ji opravit

INSTRUKCE:
- Používej Windows příkazy (PowerShell nebo CMD)
- Vysvětli mi každý krok, co dělá
- Pokud se něco pokazí, diagnostikuj problém a navrhni řešení
- Na konci mi řekni, jak agenta spustit příště (bez celého setupu)

Můžeme začít?
```

---

## 🔑 DŮLEŽITÉ - API KLÍČ

**Tvůj Claude API klíč najdeš:**
1. Na prvním PC v souboru `C:\Users\jakub\gaming-content-agent\.env`
2. Nebo na console.anthropic.com v sekci "API Keys"

Formát: `sk-ant-api03-...` (dlouhý string)

**Poznámka:** Tento klíč je uložený v souboru `.env` a NIKDY se neposílá na GitHub (je v `.gitignore`).

---

## 📝 MANUÁLNÍ INSTRUKCE (pokud chceš dělat ručně)

### 1. Nainstaluj Python
- Stáhni z https://www.python.org/downloads/
- **DŮLEŽITÉ:** Zaškrtni "Add Python to PATH" při instalaci

### 2. Nainstaluj Git (pokud nemáš)
- Stáhni z https://git-scm.com/download/win

### 3. Naklonuj projekt
```bash
cd C:\Users\[tvoje_jmeno]
git clone https://github.com/CubaStromek/gaming-content-agent.git
cd gaming-content-agent
```

### 4. Vytvoř virtuální prostředí
```bash
python -m venv venv
venv\Scripts\activate
```

### 5. Nainstaluj závislosti
```bash
pip install -r requirements.txt
```

### 6. Nastav konfiguraci
```bash
copy .env.example .env
notepad .env
```

Do `.env` vlož:
```
CLAUDE_API_KEY=tvůj-api-klíč-z-prvního-pc-nebo-z-console.anthropic.com
EMAIL_TO=jakub.romek@gmail.com
```

### 7. Spusť agenta
```bash
python main.py
```

---

## ⚡ RYCHLÉ SPUŠTĚNÍ (příště)

Po dokončení setupu stačí:

```bash
cd gaming-content-agent
venv\Scripts\activate
python main.py
```

---

## 🐛 Časté problémy

### "python není rozpoznán jako příkaz"
- Python není v PATH → přeinstaluj Python se zaškrtnutým "Add to PATH"

### "pip není rozpoznán jako příkaz"
- Python není správně nainstalovaný → reinstalace

### "ModuleNotFoundError"
- Zapomněl jsi aktivovat venv → `venv\Scripts\activate`
- Nebo neinstaloval jsi závislosti → `pip install -r requirements.txt`

### "CLAUDE_API_KEY není nastavený"
- Soubor `.env` neexistuje → `copy .env.example .env`
- API klíč není správně v `.env` → zkontroluj formát

---

## 📊 Očekávaný výstup

Po úspěšném běhu najdeš:
```
output/
└── YYYYMMDD_HHMMSS/
    ├── articles.json    # 50-60 článků z herních webů
    ├── articles.csv     # Tabulka pro Excel
    └── report.txt       # Top 5 návrhů článků s URL odkazy
```

---

## 💰 Náklady

Jeden běh agenta: **~$0.05** (cca 1.25 Kč)
Denní běh po měsíc: **~$1.50** (35 Kč/měsíc)

---

## 📚 Další informace

- **GitHub repo:** https://github.com/CubaStromek/gaming-content-agent
- **README:** Kompletní dokumentace v README.md
- **Podpora:** Issues na GitHubu
