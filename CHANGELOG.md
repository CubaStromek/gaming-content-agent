# Changelog — Gaming Content Agent

## 2026-08-18 — Český článek na `effort: low`

Kontrola nákladů po přechodu na Opus 5: cena za článek vyskočila z **$0,067 na $0,21** (3,1×), denní burn z ~$0,79 na ~$1,66. Sazba Opusu za tím stojí jen z části (výstup $25 vs $15/MTok) — zbytek dělá **objem výstupu**. Sonnet 4.6 psal CZ+EN dohromady za ~3 200 výstupních tokenů, Opus 5 vydává na samotnou češtinu ~5 000. Opus 5 má totiž adaptivní thinking zapnutý defaultně na `effort: high` a thinking se účtuje jako výstup — platilo se za dlouhé rozmýšlení nad přepisem herní novinky ze tří scrapnutých zdrojů.

- **`config`** — nový `ARTICLE_EFFORT` (default `low`, přepsatelné přes env). Hloubka přemýšlení jen pro české volání; EN lokalizace (Sonnet 4.6) i analýza (Haiku 4.5) beze změny.
- **`article_writer._call_api`** — volitelný parametr `effort`, posílaný jen moderním modelům (starší na `output_config` vracejí chybu). Nainstalované SDK 0.76 nezná `output_config` jako pojmenovaný argument, jde tedy přes `extra_body` syrově v těle requestu — API ho bere bez beta hlavičky.
- **Pojistka** — odmítne-li API `output_config`, `_call_api` volání jednou zopakuje bez něj a jen zaloguje varování. Důvod: doprava parametru je ověřená zachycením odchozího requestu, ale **ne proti živému API** — 18. 8. ve 20:00 byl vyčerpaný kredit klíče GAME AGENT, takže se nedalo zavolat vůbec nic. Bez pojistky by případné odmítnutí shodilo každý článek.
- Testy: 4 nové (effort v těle requestu, bez effortu se `output_config` neposílá, starému modelu se neposílá, fallback po odmítnutí), celkem **358**.
- **Ověřeno proti živému API** (po dobití kreditu ve 20:10): nesmyslná hodnota vrací `400 output_config.effort`, čímž je doloženo, že pole dorazí až na validaci API — a že pojistka na odmítnutí skutečně zabírá. Platný `low` prošel.
- **Změřeno na běhu ve 20:15** (článek Control Resonant): výstup české fáze **5 342 → 2 673 tokenů** (−50 %), cena CZ volání **$0,190 → $0,119**, celý článek **$0,21 → $0,15** (−28 %). Denní burn ~$1,66 → **~$1,36**, měsíčně ~$50 → ~$41. Článek má 759 slov, tedy nad povinným minimem 600.
- **`article_writer`** — zrušeno `cache_control` u českého promptu (19. 8.). Cache se nikdy netrefila: běhy jsou 105 minut od sebe, ephemeral TTL je 5 minut, takže v logu stálo pokaždé `cache read=0, write=7360`. Platil se jen 25% příplatek za zápis, ze kterého nikdo nečetl — u Opusu $6,25 místo $5,00 za MTok, tj. ~$0,009 na článek (~$2,2/měsíc). Po zkrácení výstupu na `effort: low` šlo přitom o 39 % ceny českého volání. EN prompt značku ponechává — je kratší než minimum 1024 tokenů pro cache, takže ho API tiše ignoruje (`write=0`) a nic nestojí. Analýza (Haiku) má `write=0` ze stejného důvodu. Test hlídá, že se značka u CZ nevrátí; celkem **359**.
- ⏳ **Otevřené:** kvalita na jednom vzorku nejde posoudit. Přečíst články z dalších pár běhů, jestli `low` nezhoršil pochopení zdroje — což byl původní důvod přechodu na Opus.


## 2026-08-16 — Český článek na Opus 5, anglická verze zvlášť

Podnět: ve vydaném článku o S.T.A.L.K.E.R. 2 stálo, že *„A-Life byl označován za hlavní příčinu toho, proč se Zóna cítila spíš jako střelnice"*. Dvě vady v jedné větě — kalk („Zóna se cítila") a hlavně obrácená kauzalita: za mrtvý svět nemohl systém A-Life, ale to, že po vydání nefungoval.

Audit 50 vydaných článků (34 323 slov) ukázal, že **kalky nejsou systémový problém** — neživé „cítí se" má jediný skutečný výskyt v celém vzorku a em-dash drží 3,6/1000 slov proti 15–25 u nepromptovaného AI textu. Velký seznam zakázaných anglicismů by tedy léčil nemoc, která se skoro nevyskytuje. Problém je jeden odlehlý případ na článek, a ten vzniká **špatným pochopením zdroje**, ne stylem.

A/B na totožném zadání (téma + scrapnutý zdroj z ostrého běhu 15. 8. ve 14:00): Sonnet 4.6 kauzalitu zaměnil, Sonnet 5 se tématu vyhnul a napsal 551 slov (pod povinným minimem 600), **Opus 5 pasáž napsal správně** a doplnil kontext, který ve zdroji nebyl.

- **`config`** — `ARTICLE_MODEL` nově `claude-opus-5` a přepsatelný přes env (dřív natvrdo Sonnet 4.6). Přibyl `TRANSLATION_MODEL` (default `claude-sonnet-4-6`).
- **`article_writer`** — generování rozděleno na dvě volání: český článek + CZ metadata na `ARTICLE_MODEL`, anglická lokalizace + EN metadata na `TRANSLATION_MODEL`. Půlka výstupních tokenů byl překlad, na který nemá smysl platit sazbu Opusu. Selhání EN fáze článek nezabije — publikuje se jen česky.
- **`article_writer._call_api`** — u moderních modelů (`-opus-5`, `-sonnet-5`, `-opus-4-7/8`, `fable`, `mythos`) se vynechává `temperature` (jinak HTTP 400) a zvyšuje `max_tokens`, protože strop platí na přemýšlení i text dohromady.
- **`article_writer._response_text`** — nová funkce. Dřív se četlo `content[0].text`, což u modelů s přemýšlením padá na `'ThinkingBlock' object has no attribute 'text'`. Opraveno i v generátoru podcastů.
- **Prompt** — přibyly dvě jazykové poznámky (neživá věc se necítí; nezačínat větu příslovcem z anglické stavby) a sekce o směru příčiny a následku s tou konkrétní A-Life chybou jako příkladem. Vyhozeno protiřečení u EN verze (prompt zároveň chtěl „ne doslovný překlad" i „přesný překlad"). Opraveny zdvojené složené závorky v STORY_CARDS (pozůstatek po f-stringu).
- **`_MODEL_PRICING`** — Opus byl na 15/75 $ z éry Opusu 3; Opus 5 stojí 5/25 $, takže cost logy u něj nadsazovaly trojnásobně.
- **`.env.example`** — `ANALYSIS_MODEL=claude-sonnet-4-20250514` odstraněno, ten model API vrací 404. Kdo si example zkopíroval, rozbil si analýzu.
- Testy: 4 nové (přeskočení thinking bloku, detekce moderních modelů, dvoufázový tok, přežití pádu EN fáze), celkem 354. U regrese s thinking blokem ověřeno, že na starém kódu skutečně padá.
- **Objem a rozvrh** — z 10 článků denně na 8. Dřív 2 články × 5 běhů (8/11/14/17/20), nově **1 článek × 8 běhů po 105 minutách: 8:00, 9:45, 11:30, 13:15, 15:00, 16:45, 18:30, 20:15**. Objem tak nese rozvrh, ne `MAX_TOPICS_PER_RUN` (nově 1, přepsatelné přes env) — a hlavně nevycházejí dva články ve stejnou minutu. Rozvrh je v `~/Library/LaunchAgents/com.gamefo.autopublish.plist`, po úpravě znovu načten přes `launchctl unload/load` a ověřen v `launchctl print`.

- Ověřeno ostrým během na stejném zadání: CZ 697 slov, EN 905 slov, správná kauzalita, nula kalků, kompletní metadata, **$0,20 za článek** (při teplé cache ~$0,16).

## 2026-08-12 — RAWG.io vyhozeno z pipeline

Po výpadku 8/2026 se RAWG nezvedlo — každé volání v srpnu skončilo `Read timed out (10 s)`. Jako fallback pod IGDB přidávalo ~20 s na článek (2 volání: screenshoty + featured) a nezachránilo ani jeden obrázek. IGDB ho plně nahradilo.

- **`publish_pipeline`** — smazáno `search_rawg_image`, `search_game_image` je nově tenký wrapper nad IGDB. Alias v `auto_publish` zrušen.
- **`section_images`** — smazáno `fetch_rawg_screenshots`, Story Mode screenshoty bere jen z IGDB.
- **`dayreel`** — smazána inline kopie `search_rawg_image`; obrázkový fallback (3. v pořadí za yt-dlp trailerem a WP featured image) jede na IGDB.
- **Dashboard** — `/api/rawg/search` → **`/api/games/search`** (`web/blueprints/game_search_api.py`, starý blueprint smazán). Vyhledávání obrázků v ručním publikování bylo kvůli mrtvému RAWG nefunkční. Nová `igdb_client.search_games()` vrací stejný tvar `{id, name, background, screenshots}`, takže JS se změnil jen v URL. Ověřeno živě.
- **`config.RAWG_API_KEY`** ponechán a označen LEGACY — používá ho už jen archivní `scripts/oneoff/publish_crimson_desert.py`.
- Testy: `TestGameSearchApi` (3 nové), RAWG mocky v `test_publish_pipeline` přepsané na `search_game_image`. Celkem 350.

## 2026-08-12 — Oprava: IGDB vracelo 400 u KAŽDÉHO názvu s diakritikou

Od nasazení IGDB (3. 8.) padal každý dotaz na hru s ne-ASCII znakem — v logu 20× `IGDB API error 400: Syntax Error: Missing ';' at end of query`, ačkoliv dotaz `;` na konci má. Postižené: Pokémon Pokopia, Pokémon TCG Pocket, Ghost of Yōtei a všechna N/A témata s českým titulkem. Důsledek: žádný featured image ani Story Mode screenshoty → článek vyšel s generickým GAMEfo logem (RAWG fallback nezabral, viz níže).

Příčina je v `requests` 2.31.0: `super_len()` počítá `Content-Length` jako `len(str)` = počet **znaků**, ale urllib3 tělo odešle v **UTF-8**. U `Ghost of Yōtei` je hlavička 46 a tělo 47 bajtů → server request ořízne o poslední bajt, tedy přesně o koncový `;`. ASCII názvy (Kingdom Come: Deliverance II) proto fungovaly a chyba vypadala náhodně.

- **`igdb_client._query`** — tělo se posílá jako `body.encode('utf-8')`, ne `str`. Ověřeno živě proti IGDB: `Ghost of Yōtei` → 200 + artwork.
- Testy: `tests/test_igdb_client.py::TestNonAsciiBody` (2 nové) — kontroluje typ `bytes` i shodu `Content-Length` s délkou v bajtech; ověřeno, že na starém kódu oba padají (`assert 107 == 108`). Celkem 327 testů.

**RAWG je mrtvý fallback:** ve všech srpnových případech skončil `Read timed out (timeout=10)` — přidává ~20 s na článek a nezachránil nic.

## 2026-08-12 — ENTITA: do IGDB se přestala posílat česká věta

Druhá, větší příčina placeholderů (10 ze 13 srpnových). U témat, kde analyzer neurčí konkrétní hru (`game_name = N/A`), dosazoval `resolve_game_name()` celé téma — českou větu („Roblox v krizi: Podíl akcií padá o 70 % kvůli poklesu počtu hráčů") — a ta šla do IGDB jako dotaz na název hry. Databáze her na to buď nenajde nic, nebo vrátí náhodný titul.

- **`article_writer`** — nový metadata řádek `ENTITA: <anglický název> | hra|znacka` vedle KEYWORD/TITULEK/RUBRIKA. Kanonický název hlavního subjektu článku, jen pro hledání obrázku (z textu se maže jako ostatní metadata). **Žádné API volání navíc** — jede v témže requestu jako článek, ~15 output tokenů.
- **`article_postprocess.parse_entity`** — parsování + brána proti tomu, když LLM formát ignoruje a napíše celou větu (dvojtečka/pomlčka v názvu, > 40 znaků, > 6 slov → zahodit). Radši nehledat než hádat.
- **`publish_pipeline.resolve_featured_image(…, article=None)`** — pořadí u témat bez hry: brand logo (nově se do shody posílá i `entity_name`, takže „Nintendo" se trefí i z českého skloňovaného titulku) → IGDB podle entity → GAMEfo logo. Bez použitelné entity se **IGDB ani RAWG nevolá vůbec**.
- **`igdb_client.name_matches` + `search_game_image(exact_only=)`** — u entit typu `znacka` se výsledek uzná jen při shodě názvu nebo prefixu („Roblox" → „Roblox" ✓, „Pokémon" → „Name That Pokemon" ✗, „Nintendo" → „Animal Crossing: New Horizons – Nintendo Switch 2 Edition" ✗). Bez téhle brány by značky bez loga dostávaly náhodné hry. Při `exact_only` se RAWG přeskočí — vrací jen URL bez názvu, kontrolu udělat nejde.
- **`brand_logos`** — 9 nových značek. Roblox (11359) a Devolver (11242) už v knihovně byly; **Nintendo (11489), Pokémon (11490), Blizzard (11491), CD Projekt Red (11492), Ubisoft (11493), Rockstar (11494) a Summer Game Fest (11495)** nahrány 2026-08-12 jako `brand-*.jpg`. Zdroje: Wikimedia Commons rastery přes jejich API (libovolné šířky náhledů už vracejí 400, povolené velikosti jen z jejich seznamu) + oficiální press assety (cdprojekt.com, staticctf.ubisoft.com). Průhlednost sloučena na bílou — černé logo Summer Game Fest by na transparentu v dark mode zmizelo; u CD Projektu ořezány prázdné okraje. `resolve_brand_logo` používá `BRAND_LOGOS.get()` místo `[]`, takže keyword značky bez loga nezhavaruje publikaci.
- **Brand-first zkratka neplatí pro `entity_type == 'hra'`** — „Pokémon Pokopia" obsahuje značku Pokémon, ale je to konkrétní hra a patří jí vlastní artwork. Odchyceno až koncovým měřením: po nahrání Pokémon loga začal brand match přebíjet i konkrétní hry. Brand logo je zachytí až ve fallbacku, když IGDB nic nenajde.
- Testy: `TestEntityDrivenSearch` (7), `TestParseEntity` (8), `TestExactOnly` (5). Celkem 347.

**Ověřeno na 13 reálných srpnových placeholderech:** Sonnet 4.6 vrátil 13/13 správných entit i typů (jediná vada — překlep „Pokémon Kopopia"). Proti živému IGDB má nově obrázek **13 z 13** (dřív 0) — 4× herní artwork, 9× brand logo.

## 2026-08-06 — YouTube embed do každého článku o konkrétní hře + oprava rozbitého yt-dlp hledání

Onimusha: Way of the Sword preview (6. 8.) vyšla bez traileru. Dvě nezávislé příčiny:

1. **Keyword brána**: embed se vkládal jen při zmínce trailer/video/gameplay/ukázka… v textu — vygenerovaný text žádné z těch slov nepoužil. Z principu křehké (regex `záběr[yů]` navíc nepokrýval ani všechny pády).
2. **yt-dlp hledání bylo v produkci MRTVÉ od 21. 7.** (poslední „Nalezeno video" v logu): plná extrakce výsledků padala na age-restricted videích („Sign in to confirm your age" — top 2 výsledky pro Onimushu jsou 18+) a bot-checku/POT. Log to maskoval — `stderr[:200]` ukázal jen urllib3 warning ze začátku, skutečný ERROR je na konci.

Změny:

- **`publish_pipeline.embed_youtube`** — článek s reálnou hrou (`game_name` ≠ N/A a není brand dle `brand_logos.resolve_brand_logo_strict`) dostává YouTube embed **vždy**, bez ohledu na text. Keyword brána zůstává jen pro témata bez hry (YouTube query by byla celá česká věta tématu → náhodné video, stejný problém jako dřív RAWG obrázky) a brand témata (PlayStation, Steam…).
- **`youtube_embed.search_youtube`** — přepnuto na `--flat-playlist` (bez plné extrakce → age-gate/bot-check pády se hledání netýkají, ~2 s na 5 kandidátů); stdout se parsuje i při returncode ≠ 0 (částečné výsledky); stderr se loguje od konce (`[-300:]`).
- **Nové `youtube_embed.check_embeddable` + `find_embeddable_video`** — age-restricted video by v embedu na webu stejně nehrálo (šedý box „Watch on YouTube"), takže se kandidáti ověřují plnou extrakcí: prokázaný age-gate/vypnutý embed → přeskočit dalšího kandidáta; bot-check/POT/síť → neznámo, video se použije (blokuje jen náš scraper, ne návštěvníky). Ověřeno živě: Onimusha → přeskočeny 2× 18+ trailer, vybrán embedovatelný Capcom Spotlight Overview Trailer.
- **`youtube_embed._insert_embed_block`** — když text video nezmiňuje (nově hlavní cesta), embed se vkládá **před první `<h2>`** = na konec úvodu; dřívější fallback za `</h2>` by video dal mezi nadpis a text sekce.
- **`youtube_embed.title_matches_game`** — relevanční filtr kandidátů: aspoň polovina významových tokenů názvu hry musí být v titulku videa + blacklist „concept/fan made". Reálné úlovky z backfill dry-runu: indie „Red Odyssey" by dostala trailer na film Jason Bourne 6, „Assassin's Creed Odyssey" Nolanův film The Odyssey. Filtr se používá jen u reálné hry (u N/A témat je game_name celá věta).
- **`youtube_embed.embed_youtube_in_html`** smazána — mrtvý kód (nikdo nevolal) s vlastní, nyní odlišnou rozhodovací logikou.
- **Nový skript `backfill_youtube.py`** — zpětné doplnění embedů do článků publikovaných od 21. 7. (období rozbitého hledání): čte publish_log, přeskakuje posty s existujícím YouTube, brand/N-A témata; jedno video pro CZ+EN pár. Idempotentní, `--since`, `--limit`, `--dry-run`. Ověřeno: update publikovaného postu NEspouští push notifikace (`gamefo-pwa.php` guard `old_status === 'publish'`).
- Testy: `tests/test_youtube_embed.py` (nový, 21 testů) + `tests/test_publish_pipeline.py` (TestEmbedYoutube, 4 testy; `find_embeddable_video` mock ve `wired` fixture). Celkem 323.

## 2026-08-03 — Migrace obrázků na IGDB + featured fallback řetěz (výpadek RAWG)

RAWG.io od 2. 8. ~20:00 kompletně nedostupné (origin infrastruktura vč. vlastní status stránky, Cloudflare 522/521; služba je dlouhodobě neudržovaná — celodenní výpadek už v 5/2024). Důsledek: 4 články vyšly bez featured image, Beast of Reincarnation navíc bez Story Mode screenshotů.

- **Nový modul `igdb_client.py`** — IGDB (databáze her od Twitche) jako **primární zdroj obrázků**: OAuth2 client credentials na id.twitch.tv (token cache v procesu, 1× refresh při 401), fulltext search s preferencí výsledku se screenshoty/artworky (fulltext často vrací DLC bez obrázků), featured = artwork → screenshot → cover, Story Mode screenshoty `t_screenshot_huge`. Config: `IGDB_CLIENT_ID` / `IGDB_CLIENT_SECRET` v .env; bez credentials se IGDB tiše přeskočí.
- **`publish_pipeline.search_game_image()`** — nový wrapper IGDB → RAWG fallback; volá ho `resolve_featured_image` i `backfill_featured.py`. `section_images.get_or_fetch_screenshots` a `dayreel.download_image` stejně.
- **Featured image fallback řetěz** (`resolve_featured_image`): po IGDB/RAWG a brand logu nově pokračuje → **první Story Mode screenshot z WP cache** → **generické GAMEfo logo** (`brand_logos.GAMEFO_LOGO = 401`). Článek už nikdy nevyjde bez náhledového obrázku.
- **Nový skript `backfill_featured.py`** — idempotentní zpětná oprava: čte poslední publish_log záznamy, přes WP REST doplní chybějící featured (0 nebo placeholder logo → povýší) i `gameinfo_section_images` meta (aktivuje Story Mode). `--limit`, `--dry-run`. Spuštěn 3. 8.: BG3, Wolverine EN, God of War doplněny ze screenshot cache; Beast of Reincarnation dočasně GAMEfo logo.
- Testy: `tests/test_igdb_client.py` (12, mockované HTTP) + autouse fixture v `conftest.py` vyprazdňující IGDB credentials (žádná živá volání z testů). Celkem 298 testů.

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
