# Changelog — Gaming Content Agent

## 2026-07-22 — Automatické zařazování do podrubrik Zpráv/News

Články šly dosud natvrdo jen do rubriky Zprávy (9) / News (12). Nově je Claude při psaní článku rovnou klasifikuje do podrubriky:

- **`models.SUBCATEGORY_IDS`** — jediný zdroj pravdy pro podrubriky a jejich WP category ID: aaa, indie, playstation, microsoft, nintendo, valve, technologie, ekonomika, mimoherni, cesko-slovensko (bez EN ekvivalentu). Zdroj: WP REST API gamefo.cz.
- **`article_writer`** — nový metadata řádek `RUBRIKA:` v promptu (stejné API volání jako KEYWORD/META/STORY_CARDS, žádné vícenáklady); pravidlo nejkonkrétnější rubriky (platforma/firma > obecná aaa/ekonomika), `zadna` = bez podrubriky. Validace proti `SUBCATEGORY_IDS`, neznámá hodnota → warning + jen Zprávy.
- **`publish_pipeline`** — publikuje do `[Zprávy, podrubrika]` CZ i EN (cesko-slovensko jen CZ); `topic['subcategory']` (ruční override) má přednost před LLM klasifikací; podrubrika se loguje do publish_log.
- **`manual_article`** — nový volitelný parametr `--category` (choices z `SUBCATEGORY_IDS`) pro ruční přebití z Telegramu.
- Testy: `tests/test_publish_pipeline.py` (TestSubcategory, 6 testů), `tests/test_article_writer.py` (3 testy na parsování RUBRIKA).

## 2026-07-10 — Fallback kandidáti: když jsou top témata duplicitní, publikuj další v pořadí

Běhy 10. 7. v 8:00 a 11:00 nepublikovaly nic — analyzátor vrátil jen 2 témata a LLM dedup obě zahodil (Palworld 1.0 launch, Xbox layoffs). Odteď:

- **`claude_analyzer`**: analyzátor vrací až **5 kandidátních témat** seřazených podle důležitosti (`CANDIDATE_TOPICS = 5`, dřív napevno 2); `max_tokens` analýzy 4000 → 8000, aby se 5 témat vešlo bez ořezu. Cena analýzy ~+$0.03/běh (více output tokenů).
- **`auto_publish`**: `MAX_TOPICS_PER_RUN = 2` je nyní explicitní publish limit — po dedupu se publikují první 2 přeživší kandidáti, zbytek je záloha. Objem publikace se nemění (max 2 články/běh jako dřív).
- **`topic_dedup.llm_filter_duplicate_topics`**: nový parametr `needed` — jakmile přežije `needed` témat, zbylí (níže seřazení) kandidáti se už LLM nekontrolují, aby se neplatila zbytečná Haiku volání.
- Testy: `tests/test_topic_dedup.py` (4 nové testy na `needed` limit).

Pozn.: dedup verdikt „vydání 1.0 = duplicita dřívějšího oznámení data vydání" (Palworld) tím vyřešen není — top téma zůstane blokované a místo něj vyjdou další kandidáti.

## 2026-07-06 — Brand logo pro témata bez konkrétní hry (fix RAWG garbage)

- **`publish_pipeline.resolve_featured_image`**: když analyzer nevrátí reálnou hru (`game_name = N/A`), zkusí se brand logo z titulku/tématu/SEO klíčových slov **před** RAWG — dřív šla do RAWG celá česká věta tématu a RAWG (databáze her) vždy vrátil náhodný screenshot cizí hry, takže brand fallback pod RAWG se nikdy nespustil. Reálný případ: „Petice proti zrušení disků na PlayStation" dostala screenshot náhodné hry místo PlayStation loga. Reálné hry (`game_name != N/A`) jdou beze změny na RAWG.
- Regresní test `test_brand_news_no_real_game_uses_logo_not_rawg` (tests/test_publish_pipeline.py).
- Manuální cesta (Telegram): pro brand/industry témata bez konkrétní hry předávat `--game-name "N/A"` nebo přímo brand (`--game-name "PlayStation"`) — viz CLAUDE.md.

## 2026-07-03 — Kompletní refactor podle code review

### Kritické opravy
- **`image_url` unbound/stale u brand témat** (auto_publish, manual_article): u brand tématu (Steam, PlayStation…) běh padal na `UnboundLocalError` po publikaci na WP, u dalších témat ve smyčce se použil obrázek předchozí hry. Opraveno strukturálně extrakcí do `publish_pipeline.resolve_featured_image()`.
- **`article_cleanup` mazal sdílená WP média**: brand loga (media ID z `brand_logos.py`) jsou nyní whitelistovaná (`PROTECTED_MEDIA_IDS`), ostatní média se před smazáním ověřují přes `is_media_used_elsewhere()` (fail-safe: při síťové chybě se nemaže). Nedostupný detail překladu → přeskočení celého páru.
- **`feed_manager`**: poškozený `custom_feeds.json` už NEPŘEPÍŠE feedy defaulty (nová výjimka `FeedsFileError`, seed jen když soubor neexistuje); atomický zápis (temp + `os.replace`); `auto_disable_feed` matchuje podle URL.
- **`article_history.save_history`**: místo `DELETE` celé tabulky + reinsert nyní inkrementální `INSERT OR IGNORE` + expirace v DB — souběh dvou procesů už neztrácí zpracované URL (= žádné duplicitní analýzy/články).
- **Dashboard auth fail-closed**: bez `DASHBOARD_TOKEN` vrací mutating endpointy 403; `/start` je nyní POST s origin checkem (CSRF fix); origin whitelist nedůvěřuje Host headeru (DNS rebinding); LLM článek se v dashboardu renderuje přes sanitizer (XSS fix).

### Nový modul `publish_pipeline.py`
Sdílená publish pipeline pro `auto_publish.py` i `manual_article.py` (~300 duplicitních řádků odstraněno): YouTube embed (jedno hledání pro CZ+EN místo 2–3), featured image, focus keyword, WP publish CZ+EN + Polylang link, FB obrázky (tempfile místo predictable /tmp), social media, publish_log. Sdílený fcntl `publish_lock` — manuální publikace (Telegram) nyní čeká na scheduled slot místo kolize.

### Vysoké
- **Sanitizace LLM HTML před WP publikací** (`article_postprocess.sanitize_article_html`): allowlist tagů/atributů, zahazuje script/iframe/on*/javascript: — obrana proti prompt-injection ze scrapnutých zdrojů.
- **`article_writer`**: kontrola `stop_reason == 'max_tokens'` (dřív se tiše publikovala useknutá EN verze) + zvýšený token cap (8192/16384); ceník podle modelu (dřív hardcoded Sonnet).
- **`auto_publish`**: při mid-run výpadku WP se historie NEUKLÁDÁ (dřív se všechny RSS články označily za zpracované a témata byla ztracená); pojistka max 3 témata/běh.
- **`wp_publisher`**: timeout POSTu na /posts → ověření, zda post nevznikl (idempotence, prevence duplicitních článků); media dedup přes přesnou shodu slugu (dřív substring match vracel obrázky jiné hry); `print` → `log`.
- **Testy už nespouštějí ostrou pipeline** (`run_agent_process` mocknutý, OUTPUT_DIR do tmp).

### Střední / nízké
- `claude_analyzer`: deduplikace dvou ~100řádkových kopií analýzy (sdílená pravidla, retry, cost logger); `.get()` defaulty v report builderu (KeyError už nezahodí zaplacenou analýzu); optional `article_count`.
- `rss_scraper`: HTTP status check, strip HTML ze summary před ořezem (úspora tokenů), dávkové feed-health zápisy mimo event loop, `get_running_loop()`.
- `topic_dedup`: game match i proti uloženému `game_name`.
- `logger`: sanitizace tracebacků (SanitizingFormatter), maskování Telegram bot tokenů; `telegram_alert` neloguje URL s tokenem.
- `social_poster`: `LIKE '\_slot\_%' ESCAPE` fix, vynucení `SOCIAL_DAILY_LIMIT`, odstraněn mrtvý param `url`.
- `internal_linking`: tag detaily se čtou 1× (dřív 2×/tag), escapovaný alt.
- `fb_generator`: NameError při chybějícím fontu opraven + fallback na systémové fonty.
- `config`: `_env_int` helper — překlep v .env neshodí import.
- `email_sender`: SMTP timeout + context manager + TLS context + HTML escape.
- `publish_log.get_stats`: SQL agregace místo načítání celé tabulky.
- `migrate_to_sqlite`: idempotentní migrace publish_logu.
- `web`: flask-limiter (mrtvý) odstraněn, stdout po řádcích, RAWG JSON guard, TOCTOU fixy na /start a write-article/podcast.
- `requirements.txt`: +Pillow, +yt-dlp, requests>=2.32.4 (CVE); `test_api.py` → `scripts/check_api.py`.
- `models.py`: `VALID_STATUS_TAGS` jako jediný zdroj pravdy (dřív 3 kopie).

### Breaking changes / nutná akce po nasazení
1. `DASHBOARD_TOKEN` musí být v `.env`, jinak mutace v dashboardu vrací 403.
2. Přístup na dashboard přes jiný origin (Cloudflare Tunnel) vyžaduje `DASHBOARD_ALLOWED_ORIGINS` v env.
3. Restart Flask LaunchAgentu: `launchctl kickstart -k gui/$UID/com.gamefo.web`.
4. `pip install -r requirements.txt` do venv (nové/aktualizované závislosti se neinstalovaly).
