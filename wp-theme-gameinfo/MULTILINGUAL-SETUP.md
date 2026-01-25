# Nastavení dvojjazyčného webu (CZ/EN)

Šablona GameInfo Terminal je připravena na dvojjazyčný provoz pomocí pluginu **Polylang**.

## Krok 1: Instalace Polylang

1. V administraci WordPress jdi na **Pluginy → Přidat nový**
2. Vyhledej **"Polylang"**
3. Klikni na **Instalovat** a poté **Aktivovat**

## Krok 2: Konfigurace jazyků

1. Jdi na **Jazyky → Jazyky**
2. Přidej **Čeština (cs_CZ)** - nastav jako výchozí
3. Přidej **English (en_US)**
4. V **Nastavení** (záložka) vyber:
   - Typ URL: `Jazyk v doméně (cs.example.com)` nebo `Adresář (example.com/cs/)`
   - Detekce jazyka prohlížeče: Ano

## Krok 3: Překlad obsahu

### Články
- Při vytváření článku se vpravo zobrazí sekce **Jazyky**
- Napiš článek v jednom jazyce, ulož
- Klikni na **+** u druhého jazyka pro vytvoření překladu

### Menu
1. Jdi na **Vzhled → Menu**
2. Vytvoř samostatné menu pro každý jazyk
3. Přiřaď menu k lokaci podle jazyka

### Widgety
- V **Vzhled → Widgety** můžeš nastavit různé widgety pro různé jazyky

## Struktura souborů

```
wp-theme-gameinfo/
├── languages/
│   ├── gameinfo-terminal.pot   # Šablona pro překlady
│   └── cs_CZ.po                # České překlady statických textů
```

## Přepínač jazyka

Přepínač jazyka je automaticky zobrazen v headeru vedle vyhledávání.
Zobrazí se pouze když je Polylang aktivní a máte nastaveny alespoň 2 jazyky.

## Kompilace překladů (.po → .mo)

Pro funkčnost překladů statických textů je potřeba zkompilovat `.po` soubory:

### Možnost A: Plugin Loco Translate
1. Nainstaluj plugin **Loco Translate**
2. Jdi na **Loco Translate → Themes → GameInfo Terminal**
3. Překladatel automaticky zkompiluje soubory

### Možnost B: Příkazová řádka (pokud máš gettext)
```bash
cd wp-content/themes/gameinfo-terminal/languages
msgfmt -o cs_CZ.mo cs_CZ.po
```

### Možnost C: Online nástroj
- Nahraj `cs_CZ.po` na https://localise.biz/free/poeditor
- Stáhni zkompilovaný `.mo` soubor

## Poznámky

- Polylang je zdarma, pro pokročilé funkce existuje PRO verze
- Pro automatické překlady můžeš použít DeepL nebo Google Translate integraci (PRO)
- Každý jazyk může mít vlastní homepage a kategorii strukturu
