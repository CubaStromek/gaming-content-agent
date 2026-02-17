# GameFo - Release na Google Play (Open Testing cesta)

## Stav: Rozpracováno (kroky 2 a 3 hotové)

### Co je hotové

- [x] Google Developer Account (Jakub Romek)
- [x] Privacy Policy stránka (WP šablona `page-privacy-policy.php`, nasadit na `gamefo.cz/privacy-policy`)
- [x] Push token cleanup - server-side (`DeviceNotRegistered` auto-mazání)
- [x] Push token cleanup - client-side (AsyncStorage fix pro unregister)
- [x] App Views reset v admin

---

## Zbývající kroky

### 1. Nasadit Privacy Policy na web ✅

- [x] Ve WordPress vytvořit stránku, slug `privacy-policy`, šablona "Privacy Protocol"
- [x] Ověřit, že je veřejně přístupná na `https://gamefo.cz/privacy-policy/`

### 2. Připravit grafiku pro Store listing ✅

- [x] **Ikona** — 512x512 PNG, 32-bit, bez průhlednosti (alfa kanál)
- [x] **Feature graphic** — 1024x500 JPG/PNG (banner v Play Store)
- [x] **Screenshoty** — 7 ks (4 dark + 3 light, z tabletu 2560x1600)
- Grafika uložena v `store_graphics/`:
  - `icon_512x512.png` — Store ikona
  - `feature_graphic_1024x500.png` — Banner (logo + text + terminálový motiv)
  - `screenshot_01_feed.png` — Feed (dark)
  - `screenshot_02_article.png` — Detail článku (dark)
  - `screenshot_03_settings.png` — Nastavení (dark)
  - `screenshot_04_category.png` — Kategorie ZPRÁVY + sub-filtry (dark)
  - `screenshot_05_settings_light.png` — Nastavení (light)
  - `screenshot_06_feed_light.png` — Feed (light)
  - `screenshot_07_article_light.png` — Detail článku (light)
- ⚠️ Screenshoty jsou z tabletu — pokud Google Play vyžaduje phone-size, pořídit z phone emulátoru

### 3. Napsat Store listing texty ✅

- [x] **Název** — "GameFo – Herní novinky" (23 znaků)
- [x] **Krátký popis** — "Český herní zpravodaj. Novinky z 9 zdrojů, push notifikace, bez reklam." (72 znaků)
- [x] **Plný popis** — kompletní CZ + EN
- [x] Připravit CZ jako primární jazyk, EN jako překlad
- Texty uloženy v `store_listing_texts.md`

### 4. Vytvořit production build

```bash
eas build --platform android --profile production
```

- [x] Ověřeno: v `eas.json` existuje `production` profil s `autoIncrement: true`
- [ ] Rozhodnout keystore: EAS-managed (doporučeno) nebo vlastní
- [ ] `versionCode` a `version` v `app.config.ts` zkontrolovat/aktualizovat
  - ⚠️ Commit říká 1.3.0, ale working tree má 1.2.2 — vyřešit před buildem
- [ ] Spustit `eas build --platform android --profile production`
- [ ] Stáhnout `.aab` z Expo

### 5. Založit aplikaci v Google Play Console

- [ ] Vytvořit aplikaci (název, jazyk CZ, typ: app, free)
- [ ] Nahrát ikonu, feature graphic, screenshoty
- [ ] Vyplnit Store listing texty (CZ + EN)
- [ ] Zadat Privacy Policy URL (`https://gamefo.cz/privacy-policy/`)

### 6. Vyplnit povinné formuláře v Play Console

- [ ] **Content rating** — IARC dotazník (news/gaming obsah, žádné násilí ani gambling)
- [ ] **Data safety** — deklarovat:
  - Device identifiers: Ano (push token) — účel: app functionality
  - App activity: Ano (article views) — účel: analytics, anonymní
  - Data se nesdílí s třetími stranami
  - Data nejsou šifrována end-to-end (HTTPS/TLS, ne E2E)
  - Uživatel může požádat o smazání (disable notifikací / kontakt email)
- [ ] **Target audience** — věková skupina (ne děti pod 13)
- [ ] **Ads declaration** — appka neobsahuje reklamy
- [ ] **Government apps** — ne
- [ ] **Financial features** — ne

### 7. Nahrát build a spustit Open Testing

- [ ] V Play Console: Testing → Open testing → Create new release
- [ ] Nahrát `.aab` soubor
- [ ] Vyplnit release notes (CZ + EN)
- [ ] Odeslat k review

### 8. Google Review

- Review trvá typicky hodiny až pár dní
- Appka se po schválení objeví ve Store jako "Early Access"
- Kdokoliv ji může najít a nainstalovat

### 9. Production release

- [ ] Kdykoliv po schválení Open Testing: Production → Create new release
- [ ] Nahrát stejný (nebo novější) `.aab`
- [ ] Odeslat k production review
- [ ] Po schválení zmizí "Early Access" štítek

---

## Důležité poznámky

- **Keystore je trvalý** — ztráta = nemožnost updatovat appku. EAS-managed je bezpečnější volba.
- **Privacy Policy URL musí zůstat aktivní** — Google ji kontroluje průběžně
- **Data Safety musí odpovídat realitě** — nesouhlasí-li s tím co appka dělá, review zamítne
- **Open Testing nemá časový limit** — můžete přejít na production kdykoliv po schválení review
