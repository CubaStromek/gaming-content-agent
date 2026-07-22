"""
Auto Publish Pipeline
Automaticky stahne RSS, analyzuje, napise clanky a publikuje na GAMEfo.cz
Spousteno 5x denne pres launchd (8:00, 11:00, 14:00, 17:00, 20:00)
"""

import os
import sys
import time
from datetime import datetime

# Zajisti spravny working directory (dulezite pro launchd)
os.chdir(os.path.dirname(os.path.abspath(__file__)))

import config
import rss_scraper
import claude_analyzer
import article_writer
import article_history
import file_manager
import wp_publisher
import publish_log
import publish_pipeline
import topic_dedup
import telegram_alert
from logger import setup_logger

log = setup_logger('auto_publish')

# Zpětně kompatibilní aliasy — logika žije v publish_pipeline (sdílená
# s manual_article.py).
_publish_lock = publish_pipeline.publish_lock
search_rawg_image = publish_pipeline.search_rawg_image
_extract_excerpt = publish_pipeline.extract_excerpt

# Publish limit na běh. Analyzátor vrací až 5 kandidátů seřazených podle
# důležitosti (claude_analyzer.CANDIDATE_TOPICS) — dedup je profiltruje a
# publikují se první 2 přeživší. Níže seřazení kandidáti slouží jako záloha,
# když nejvirálnější témata už vyšla dřív (jinak běh nepublikoval nic).
MAX_TOPICS_PER_RUN = 2


def _pick_topics(articles, run_dir, run_id):
    """Etapa 1: Claude analýza → seznam témat po deduplikaci.

    Loguje do publish_log:
    - `proposed`: kompletní seznam témat, co Claude navrhl (decision-transparency)
    - `skipped` s reason=duplicate_topic: každé téma odfiltrované dedup, vč. detailu shody
    Vrací list(topic) nebo None pokud nelze pokračovat.
    """
    articles_text = rss_scraper.format_articles_for_analysis(articles)

    # Retry strategie: pokud Claude API spadne, je obvykle dole desítky minut.
    # Krátké retry žere input tokeny na promptu bez šance uspět — proto raději
    # 30 min sleep a max 3 pokusy (=1h). Schválně dlouhé.
    MAX_ANALYSIS_RETRIES = 3
    RETRY_WAIT_MINUTES = 30
    analysis = None
    topics = None

    for attempt in range(1, MAX_ANALYSIS_RETRIES + 1):
        structured = claude_analyzer.analyze_articles_structured(articles_text, article_count=len(articles))
        if structured:
            analysis = structured["text"]
            topics = structured["topics"]
            log.info("Strukturovaná analýza: %d témat", len(topics))
            break

        log.info("Fallback na textovou analýzu + regex parsování")
        analysis = claude_analyzer.analyze_gaming_articles(articles_text)
        if analysis:
            topics = article_writer.parse_topics_from_report(analysis)
            break

        if attempt < MAX_ANALYSIS_RETRIES:
            log.warning("⏳ Claude API nedostupná (pokus %d/%d). Čekám %d minut před dalším pokusem...",
                        attempt, MAX_ANALYSIS_RETRIES, RETRY_WAIT_MINUTES)
            time.sleep(RETRY_WAIT_MINUTES * 60)
        else:
            log.error("❌ Claude analýza selhala po %d pokusech. Končím.", MAX_ANALYSIS_RETRIES)
            return None

    file_manager.save_report(analysis, claude_analyzer.extract_key_insights(articles), run_dir, articles)

    if not topics:
        log.error("Zadna temata k publikaci")
        return None

    log.info("Nalezeno %d temat", len(topics))

    # Decision transparency: zaloguj VŠECHNA navržená témata, než cokoli skipneme.
    publish_log.log_decision({
        'action': 'proposed',
        'run_id': run_id,
        'rss_articles_count': len(articles),
        'topics': [
            {
                'topic': t.get('topic', ''),
                'title': t.get('title', ''),
                'virality_score': t.get('virality_score', 0),
                'status_tag': t.get('status_tag', ''),
                'game_name': t.get('game_name', ''),
                'sources_count': len(t.get('sources', [])),
            }
            for t in topics
        ],
    })

    topics, dup_topics = topic_dedup.filter_duplicate_topics(topics)
    # Sémantická druhá vrstva: chytí přejmenované entity (ráno bezejmenná hra,
    # odpoledne s oficiálním názvem), na které lexikální shoda nestačí.
    # `needed`: jakmile přežije MAX_TOPICS_PER_RUN témat, zbytek se nekontroluje.
    topics, llm_dups = topic_dedup.llm_filter_duplicate_topics(topics, needed=MAX_TOPICS_PER_RUN)
    dup_topics.extend(llm_dups)
    for dup in dup_topics:
        publish_log.log_decision({
            'action': 'skipped',
            'reason': 'duplicate_topic',
            'run_id': run_id,
            'topic': dup.get('topic', ''),
            'score': dup.get('virality_score', 0),
            'dedup_match': dup.get('_dedup_match'),
        })

    if not topics:
        log.info("Všechna témata jsou duplicitní. Končím.")
        return None

    if len(topics) > MAX_TOPICS_PER_RUN:
        log.info("Po dedupu zbývá %d kandidátů, publikuji top %d", len(topics), MAX_TOPICS_PER_RUN)
        topics = topics[:MAX_TOPICS_PER_RUN]

    log.info("Po deduplikaci: %d témat k publikaci", len(topics))
    return topics


def _collect_source_texts(topic, articles):
    """Stáhne plné texty zdrojů (max 3 + fallback z RSS).

    Vrací (texts, valid_urls, failed_sources) — failed_sources je list dictů
    `{url, reason}` (reason = error message z scrape_full_article), pro
    decision-transparency log.
    """
    topic_name = topic.get('topic', 'Neznámé')
    source_urls_in = topic.get('sources', [])
    source_texts = []
    valid_source_urls = []
    failed_sources = []
    for url in source_urls_in[:3]:
        text = article_writer.scrape_full_article(url)
        if not text.startswith('[Chyba'):
            source_texts.append(text)
            valid_source_urls.append(url)
        else:
            log.warning("Zdroj nedostupný, nebude v odkazech: %s", url[:80])
            failed_sources.append({'url': url, 'reason': text[:120]})

    if source_texts:
        return source_texts, valid_source_urls, failed_sources

    log.warning("Všechny zdroje selhaly pro '%s', hledám alternativní URL z RSS...", topic_name)
    topic_keywords = set(topic_name.lower().split())
    topic_keywords -= {'a', 'the', 'of', 'in', 'for', 'on', 'to', 'is', '-', '–', 'and', 'pro',
                       'nový', 'nová', 'nové', 'že', 'se', 'na', 'je', 'z', 'do', 'od', 'při', 'za'}
    fallback_urls = []
    for art in articles:
        art_text = f"{art.get('title', '')} {art.get('summary', '')}".lower()
        matches = sum(1 for kw in topic_keywords if kw in art_text)
        if matches >= min(2, len(topic_keywords)) and art['link'] not in valid_source_urls:
            fallback_urls.append(art['link'])

    if fallback_urls:
        log.info("Nalezeno %d alternativních URL, zkouším stáhnout...", len(fallback_urls))
        for url in fallback_urls[:5]:
            text = article_writer.scrape_full_article(url)
            if not text.startswith('[Chyba'):
                source_texts.append(text)
                valid_source_urls.append(url)
                log.info("Fallback zdroj OK: %s", url[:80])
                if len(source_texts) >= 2:
                    break
            else:
                log.warning("Fallback zdroj nedostupný: %s", url[:80])
                failed_sources.append({'url': url, 'reason': text[:120], 'fallback': True})

    return source_texts, valid_source_urls, failed_sources


def run():
    """Hlavni pipeline: RSS -> analyza -> clanky -> publish."""
    start_time = datetime.now()
    log.info("=" * 60)
    log.info("AUTO PUBLISH - %s", start_time.strftime('%d.%m.%Y %H:%M'))
    log.info("=" * 60)

    # 1. Validace
    if not config.validate_config():
        log.error("Chybi konfigurace (CLAUDE_API_KEY)")
        return

    if not config.is_wp_configured():
        log.error("WordPress neni nakonfigurovan (WP_URL, WP_USER, WP_APP_PASSWORD)")
        return

    # 2. Vytvoreni output slozky
    run_dir = file_manager.create_run_directory()
    run_id = os.path.basename(run_dir.rstrip(os.sep))
    log.info("Output: %s (run_id=%s)", run_dir, run_id)

    # 3. Nacteni historie a stahnuti novych clanku
    history = article_history.load_history()
    processed_urls = article_history.get_processed_urls(history)

    articles = rss_scraper.scrape_all_feeds(skip_urls=processed_urls)
    if not articles:
        log.info("Zadne nove clanky k analyze. Koncim.")
        return

    log.info("Stazeno %d novych clanku", len(articles))
    rss_scraper.save_articles_to_json(articles, run_dir)

    # Rané pre-flight gate: když je WP dole už teď, nemá smysl ani platit za
    # Claude analýzu (Haiku). Zastav před jakoukoliv útratou. Záruka: WP dole =>
    # nulová útrata za API. (Scraping je zdarma; per-téma gate níž řeší mid-run pád.)
    if not wp_publisher.check_wp_available():
        log.error("WP nedostupný před analýzou — končím běh (nulová útrata za API).")
        telegram_alert.send_alert(
            "⚠️ <b>GAMEfo autopublish ZASTAVEN</b>\n\n"
            "WordPress (gamefo.cz) je nedostupný — běh ukončen ještě před analýzou, "
            "žádná útrata za API.\n\n"
            "🔧 Nejpravděpodobnější příčina: <b>spadlá NordVPN</b> "
            "(Starlink IP na Webglobe blacklistu).\n"
            "➡️ Zapni VPN; další běh proběhne v plánovaný čas."
        )
        return

    # 4. Etapa „pick_topics": Claude analýza + dedup
    topics = _pick_topics(articles, run_dir, run_id)
    if not topics:
        return

    # 5. Etapa „produce_articles + publish_and_promote": pro každé téma napsat + publikovat
    published_count = 0
    aborted_mid_run = False
    for i, topic in enumerate(topics, 1):
        topic_name = topic.get('topic', 'Neznámé')
        title = topic.get('title', topic_name)
        virality = topic.get('virality_score', 0)

        log.info("-" * 40)
        log.info("TEMA %d/%d: %s (viralita: %d)", i, len(topics), topic_name, virality)

        # Pre-flight: WP musí být dostupný PŘED drahým generováním. Jinak bychom
        # zaplatili Claude za článek, který nejde publikovat (spadlá VPN / Webglobe
        # blacklist). Když je WP dole, je dole pro všechna témata → zastav celý běh
        # a pošli alert na telefon, ať uživatel zapne VPN.
        if not wp_publisher.check_wp_available():
            log.error(
                "WP nedostupný PŘED generováním — zastavuji běh (prevence placeného "
                "generování do koše). Pravděpodobně spadlá VPN / Webglobe blacklist."
            )
            publish_log.log_decision({
                'action': 'aborted',
                'reason': 'wp_unavailable_preflight',
                'run_id': run_id,
                'topic': topic_name,
                'score': virality,
            })
            telegram_alert.send_alert(
                "⚠️ <b>GAMEfo autopublish ZASTAVEN</b>\n\n"
                "WordPress (gamefo.cz) je nedostupný — běh zastaven PŘED generováním, "
                "aby se neplatilo za nepublikovatelné články.\n\n"
                "🔧 Nejpravděpodobnější příčina: <b>spadlá NordVPN</b> "
                "(Starlink IP je na Webglobe blacklistu).\n"
                "➡️ Zapni VPN; další běh proběhne v plánovaný čas."
            )
            aborted_mid_run = True
            break

        source_texts, source_urls, failed_sources = _collect_source_texts(topic, articles)

        if not source_texts:
            log.warning("Zadne zdrojove texty pro '%s' (ani po fallbacku), preskakuji", topic_name)
            publish_log.log_decision({
                'action': 'skipped',
                'reason': 'no_source_texts',
                'run_id': run_id,
                'topic': topic_name,
                'score': virality,
                'failed_sources': failed_sources,
            })
            continue

        # Generovani clanku (CZ + EN)
        log.info("Generuji clanek...")
        article = article_writer.write_article(topic, source_texts)
        if 'error' in article:
            log.error("Chyba pri generovani: %s", article['error'])
            publish_log.log_decision({
                'action': 'skipped',
                'reason': 'write_error',
                'run_id': run_id,
                'topic': topic_name,
                'score': virality,
                'error': article['error'],
                'failed_sources': failed_sources,
            })
            continue

        # Pouzij opraveny titulek pokud existuje
        if article.get('corrected_title'):
            title = article['corrected_title']
            log.info("Titulek opraven na: %s", title)

        log.info("Clanek vygenerovan (%s)", article.get('cost', '?'))

        # Rychlý test dostupnosti WP před jakýmkoliv odesíláním
        if not wp_publisher.check_wp_available():
            log.error("WP nedostupný — přeskakuji článek '%s' (prevence Fail2Ban)", topic_name)
            publish_log.log_decision({
                'action': 'skipped',
                'reason': 'wp_unavailable',
                'run_id': run_id,
                'topic': topic_name,
                'score': virality,
            })
            continue

        # Sdílená publish pipeline: YouTube embed, featured image, WP CZ+EN,
        # FB obrázky, social media, publish_log
        result, publish_err = publish_pipeline.publish_article(
            topic=topic,
            article=article,
            title=title,
            run_id=run_id,
            source='auto',
            source_urls=source_urls,
            extra_log={'failed_sources': failed_sources},
        )

        if publish_err:
            log.error("CZ publish selhal: %s", publish_err)
            publish_log.log_decision({
                'action': 'skipped',
                'reason': 'wp_error_cs',
                'run_id': run_id,
                'topic': topic_name,
                'score': virality,
                'error': publish_err,
            })
            continue

        published_count += 1

    # 8. Aktualizace historie — POUZE pokud běh nebyl přerušen výpadkem WP.
    # Při mid-run abortu se nepublikovaná témata NESMÍ označit za zpracovaná
    # (byla by nenávratně ztracená v 30denním dedup okně). Publikovaná témata
    # opakované publikaci zabrání topic_dedup (čte publish_log).
    if aborted_mid_run:
        log.warning("Běh přerušen výpadkem WP — historie se neukládá, "
                    "témata se zkusí znovu v dalším slotu.")
    else:
        history = article_history.mark_as_processed(articles, history)
        history = article_history.cleanup_old_entries(history)
        article_history.save_history(history)

    # 9. Shrnutí
    elapsed = (datetime.now() - start_time).total_seconds()
    log.info("=" * 60)
    log.info("HOTOVO! Publikovano %d/%d clanku za %.0f sekund", published_count, len(topics), elapsed)
    log.info("=" * 60)


if __name__ == '__main__':
    try:
        with _publish_lock():
            run()
    except KeyboardInterrupt:
        log.warning("Preruseno uzivatelem")
        sys.exit(0)
    except SystemExit:
        raise
    except Exception:
        log.exception("Neocekavana chyba")
        sys.exit(1)
