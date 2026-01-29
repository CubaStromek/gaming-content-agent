# GameFo - Release na Google Play (Open Testing cesta)

## Stav: Připraveno k zahájení

### Co je hotové

- [x] Google Developer Account (Jakub Romek)
- [x] Privacy Policy stránka (WP šablona `page-privacy-policy.php`, nasadit na `gamefo.cz/privacy-policy`)
- [x] Push token cleanup - server-side (`DeviceNotRegistered` auto-mazání)
- [x] Push token cleanup - client-side (AsyncStorage fix pro unregister)
- [x] App Views reset v admin

---

## Zbývající kroky

### 1. Nasadit Privacy Policy na web

- [ ] Ve WordPress vytvořit stránku, slug `privacy-policy`, šablona "Privacy Protocol"
- [ ] Ověřit, že je veřejně přístupná na `https://gamefo.cz/privacy-policy/`

### 2. Připravit grafiku pro Store listing

- [ ] **Ikona** — 512x512 PNG, 32-bit, bez průhlednosti (alfa kanál)
- [ ] **Feature graphic** — 1024x500 JPG/PNG (banner v Play Store)
- [ ] **Screenshoty** — min. 2, doporučeně 4-8 (z emulátoru nebo reálného zařízení, phone size)

### 3. Napsat Store listing texty

- [ ] **Název** — max 30 znaků (např. "GameFo - Herní novinky")
- [ ] **Krátký popis** — max 80 znaků
- [ ] **Plný popis** — max 4000 znaků
- [ ] Připravit CZ jako primární jazyk, EN jako překlad

### 4. Vytvořit production build

```bash
eas build --platform android --profile production
```

- [ ] Ověřit, že v `eas.json` existuje `production` profil generující `.aab`
- [ ] Rozhodnout keystore: EAS-managed (doporučeno) nebo vlastní
- [ ] `versionCode` a `version` v `app.config.ts` zkontrolovat/aktualizovat
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
