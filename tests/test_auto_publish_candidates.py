"""Výběr kandidátů v `run()`: limit běhu počítá placená generování, ne témata.

Regrese k 22. 9. 2026 (běh 20260922_130002): LLM dedup oříznul 5 kandidátů na
1 ještě před stahováním zdrojů. Jediné vybrané téma (Minecraft Live) mělo jen
zdroj z GameSpotu, který skriptu vrací 403, fallback z RSS našel tutéž URL —
a běh skončil `Publikovano 0/1`, přestože 4 další kandidáti čekali nevyzkoušení.
"""

import pytest

import auto_publish

# Fixture `_pick_topics` podvrhuje; regresní test si vrací tu skutečnou.
_REAL_PICK_TOPICS = auto_publish._pick_topics

GAMESPOT = 'https://www.gamespot.com/articles/minecrafts-next-update-could-be-its-biggest-in-15-years/'


def _topic(name, sources=None):
    return {'topic': name, 'title': name, 'virality_score': 70, 'sources': sources or []}


@pytest.fixture
def pipeline(monkeypatch, tmp_path):
    """Pipeline s živou smyčkou kandidátů v `run()`, vše kolem je podvržené."""
    calls = {'saved_history': [], 'alerts': [], 'decisions': [], 'published': [],
             'written': [], 'pulled': []}
    state = {'candidates': [], 'unfetchable': set(), 'write_error': set()}

    monkeypatch.setattr(auto_publish.config, 'validate_config', lambda: True)
    monkeypatch.setattr(auto_publish.config, 'is_wp_configured', lambda: True)
    monkeypatch.setattr(auto_publish.file_manager, 'create_run_directory',
                        lambda: str(tmp_path / '20260922_130002'))
    monkeypatch.setattr(auto_publish.wp_publisher, 'check_wp_available', lambda: True)

    articles = [{'title': 'Minecraft update', 'link': GAMESPOT}]
    monkeypatch.setattr(auto_publish.article_history, 'load_history', lambda: {'articles': {}})
    monkeypatch.setattr(auto_publish.article_history, 'get_processed_urls', lambda h: set())
    monkeypatch.setattr(auto_publish.article_history, 'mark_as_processed', lambda a, h: h)
    monkeypatch.setattr(auto_publish.article_history, 'cleanup_old_entries', lambda h: h)
    monkeypatch.setattr(auto_publish.article_history, 'save_history',
                        lambda h: calls['saved_history'].append(h) or True)
    monkeypatch.setattr(auto_publish.rss_scraper, 'scrape_all_feeds', lambda skip_urls: articles)
    monkeypatch.setattr(auto_publish.rss_scraper, 'save_articles_to_json', lambda a, d: None)

    def _lazy_candidates(a, d, r):
        # Stejně líné jako topic_dedup.iter_llm_unique_topics: co se nevytáhne,
        # to se ani nededupuje.
        for topic in state['candidates']:
            calls['pulled'].append(topic['topic'])
            yield topic

    def _sources(topic, arts):
        if topic['topic'] in state['unfetchable']:
            return [], [], [{'url': GAMESPOT, 'reason': '[Chyba: 403]'}]
        return ['zdrojovy text'], ['https://ign.com/x'], []

    def _write(topic, texts):
        calls['written'].append(topic['topic'])
        if topic['topic'] in state['write_error']:
            return {'error': 'API 529 overloaded'}
        return {'content_cs': 'text', 'cost': '$0.15'}

    def _publish(**kw):
        calls['published'].append(kw['topic']['topic'])
        return {'cz_url': 'https://gamefo.cz/x'}, None

    monkeypatch.setattr(auto_publish, '_pick_topics', _lazy_candidates)
    monkeypatch.setattr(auto_publish, '_collect_source_texts', _sources)
    monkeypatch.setattr(auto_publish.article_writer, 'write_article', _write)
    monkeypatch.setattr(auto_publish.publish_pipeline, 'publish_article', _publish)
    monkeypatch.setattr(auto_publish.publish_log, 'log_decision',
                        lambda d: calls['decisions'].append(d))
    monkeypatch.setattr(auto_publish.telegram_alert, 'send_alert',
                        lambda msg: calls['alerts'].append(msg))
    monkeypatch.setattr(auto_publish, 'MAX_TOPICS_PER_RUN', 1)
    return calls, state


def test_unfetchable_top_candidate_falls_through_to_next(pipeline):
    """22. 9.: téma bez stažitelných zdrojů nesmí shodit celý slot."""
    calls, state = pipeline
    state['candidates'] = [_topic('Minecraft Live 2026', [GAMESPOT]), _topic('Hollow Knight Silksong DLC')]
    state['unfetchable'] = {'Minecraft Live 2026'}

    auto_publish.run()

    assert calls['published'] == ['Hollow Knight Silksong DLC']
    skips = [d for d in calls['decisions'] if d.get('reason') == 'no_source_texts']
    assert [d['topic'] for d in skips] == ['Minecraft Live 2026']


def test_regression_20260922_through_real_pick_topics(pipeline, monkeypatch):
    """Totéž přes skutečné `_pick_topics` + dedup: oříznutí nesmí proběhnout před zdroji."""
    calls, state = pipeline
    monkeypatch.setattr(auto_publish, '_pick_topics', _REAL_PICK_TOPICS)
    monkeypatch.setattr(auto_publish.rss_scraper, 'format_articles_for_analysis', lambda a: 'clanky')
    monkeypatch.setattr(auto_publish.claude_analyzer, 'analyze_articles_structured',
                        lambda text, article_count=None: {'text': 'report', 'topics': [
                            _topic('Minecraft Live 2026', [GAMESPOT]),
                            _topic('Hollow Knight Silksong DLC'),
                        ]})
    monkeypatch.setattr(auto_publish.claude_analyzer, 'extract_key_insights', lambda a: {})
    monkeypatch.setattr(auto_publish.file_manager, 'save_report', lambda *a, **kw: 'report.txt')
    monkeypatch.setattr(auto_publish.topic_dedup, 'get_recent_published_topics', lambda *a, **kw: [])
    state['unfetchable'] = {'Minecraft Live 2026'}

    auto_publish.run()

    assert calls['published'] == ['Hollow Knight Silksong DLC']


def test_stops_pulling_candidates_once_limit_is_used(pipeline):
    """Po vygenerování článku se další kandidát nevytáhne — a tedy ani neplatí LLM dedup."""
    calls, state = pipeline
    state['candidates'] = [_topic('T0'), _topic('T1'), _topic('T2')]

    auto_publish.run()

    assert calls['pulled'] == ['T0']
    assert calls['written'] == ['T0']


def test_failed_generation_counts_toward_limit(pipeline):
    """Selhané generování je zaplacené — další kandidát se už nezkouší (výpadek API)."""
    calls, state = pipeline
    state['candidates'] = [_topic('T0'), _topic('T1')]
    state['write_error'] = {'T0'}

    auto_publish.run()

    assert calls['written'] == ['T0']
    assert calls['published'] == []


def test_no_writable_candidate_still_saves_history(pipeline):
    """Když nejde napsat nic, běh doběhne normálně: bez generování, historie uložena."""
    calls, state = pipeline
    state['candidates'] = [_topic('T0'), _topic('T1')]
    state['unfetchable'] = {'T0', 'T1'}

    auto_publish.run()

    assert calls['written'] == []
    assert calls['pulled'] == ['T0', 'T1']
    assert len(calls['saved_history']) == 1
    assert calls['alerts'] == []


def test_fallback_does_not_retry_failed_source(monkeypatch):
    """Zdroj tématu je i v RSS; fallback ho nesmí zkusit podruhé, ale jiné shody ano."""
    other = 'https://www.ign.com/articles/minecraft-live-2026-biggest-update'
    articles = [
        {'title': 'Minecraft Live 2026 biggest update in 15 years', 'summary': '', 'link': GAMESPOT},
        {'title': 'Minecraft Live 2026: what to expect', 'summary': '', 'link': other},
    ]
    scraped = []

    def _scrape(url):
        scraped.append(url)
        return '[Chyba: 403 Forbidden]' if url == GAMESPOT else 'plny text'

    monkeypatch.setattr(auto_publish.article_writer, 'scrape_full_article', _scrape)

    texts, urls, failed = auto_publish._collect_source_texts(
        _topic('Minecraft Live 2026 - Největší update za 15 let', [GAMESPOT]), articles)

    assert scraped == [GAMESPOT, other]
    assert urls == [other]
    assert texts == ['plny text']
    assert [f['url'] for f in failed] == [GAMESPOT]
