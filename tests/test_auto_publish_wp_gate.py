"""Chování běhu, když WordPress spadne uprostřed pipeline.

Regrese k 23. 8. 2026 (běh 20260823_130001): gamefo.cz přestal odpovídat
během ~2 minut generování článku. Gate po generování tehdy jen `continue`-l,
takže se běh dokončil jako úspěšný, uložil historii — a zdroje zaplaceného,
ale nepublikovaného článku (Diablo 4: Lord of Hatred) se spálily na 30 dní
v dedup okně. Navíc bez Telegram alertu.
"""

import pytest
from unittest.mock import MagicMock, patch

import auto_publish


@pytest.fixture
def pipeline(monkeypatch, tmp_path):
    """Naruby vyvěšená pipeline: jediná živá logika je gate v `run()`."""
    calls = {'saved_history': [], 'alerts': [], 'decisions': [], 'published': []}

    monkeypatch.setattr(auto_publish.config, 'validate_config', lambda: True)
    monkeypatch.setattr(auto_publish.config, 'is_wp_configured', lambda: True)
    monkeypatch.setattr(auto_publish.file_manager, 'create_run_directory',
                        lambda: str(tmp_path / '20260823_130001'))

    articles = [{'title': 'Diablo 4 review', 'link': 'https://vg247.com/d4'}]
    monkeypatch.setattr(auto_publish.article_history, 'load_history', lambda: {'articles': {}})
    monkeypatch.setattr(auto_publish.article_history, 'get_processed_urls', lambda h: set())
    monkeypatch.setattr(auto_publish.article_history, 'mark_as_processed', lambda a, h: h)
    monkeypatch.setattr(auto_publish.article_history, 'cleanup_old_entries', lambda h: h)
    monkeypatch.setattr(auto_publish.article_history, 'save_history',
                        lambda h: calls['saved_history'].append(h) or True)

    monkeypatch.setattr(auto_publish.rss_scraper, 'scrape_all_feeds', lambda skip_urls: articles)
    monkeypatch.setattr(auto_publish.rss_scraper, 'save_articles_to_json', lambda a, d: None)

    monkeypatch.setattr(auto_publish, '_pick_topics', lambda a, d, r: [
        {'topic': 'Diablo 4: Lord of Hatred', 'title': 'Recenze', 'virality_score': 68},
    ])
    monkeypatch.setattr(auto_publish, '_collect_source_texts',
                        lambda t, a: (['zdrojovy text'], ['https://vg247.com/d4'], []))
    monkeypatch.setattr(auto_publish.article_writer, 'write_article',
                        lambda t, s: {'content_cs': 'text', 'cost': '$0.1419'})

    monkeypatch.setattr(auto_publish.publish_log, 'log_decision',
                        lambda d: calls['decisions'].append(d))
    monkeypatch.setattr(auto_publish.telegram_alert, 'send_alert',
                        lambda msg: calls['alerts'].append(msg))
    def _fake_publish(**kw):
        calls['published'].append(kw)
        return {'cz_url': 'https://gamefo.cz/x'}, None

    monkeypatch.setattr(auto_publish.publish_pipeline, 'publish_article', _fake_publish)
    return calls


def test_wp_drops_after_generation_does_not_burn_history(pipeline, monkeypatch):
    """WP nahoře u preflightu, dole až po vygenerování → historie se NEuloží."""
    monkeypatch.setattr(auto_publish.wp_publisher, 'check_wp_available',
                        MagicMock(side_effect=[True, True, False]))

    auto_publish.run()

    assert pipeline['saved_history'] == [], \
        "historie uložena i přes zahozený článek — zdroje spálené na 30 dní"
    assert pipeline['published'] == []


def test_wp_drops_after_generation_sends_alert(pipeline, monkeypatch):
    monkeypatch.setattr(auto_publish.wp_publisher, 'check_wp_available',
                        MagicMock(side_effect=[True, True, False]))

    auto_publish.run()

    assert len(pipeline['alerts']) == 1, "uživatel se o výpadku nedozvěděl"
    assert 'ZASTAVEN' in pipeline['alerts'][0]
    assert 'Diablo 4: Lord of Hatred' in pipeline['alerts'][0]


def test_wp_drops_after_generation_logs_aborted(pipeline, monkeypatch):
    monkeypatch.setattr(auto_publish.wp_publisher, 'check_wp_available',
                        MagicMock(side_effect=[True, True, False]))

    auto_publish.run()

    aborts = [d for d in pipeline['decisions'] if d.get('action') == 'aborted']
    assert len(aborts) == 1
    assert aborts[0]['reason'] == 'wp_unavailable'


def test_happy_path_still_saves_history(pipeline, monkeypatch):
    """Kontrolní vzorek: bez výpadku se historie uložit MUSÍ."""
    monkeypatch.setattr(auto_publish.wp_publisher, 'check_wp_available', lambda: True)

    auto_publish.run()

    assert len(pipeline['saved_history']) == 1
    assert pipeline['alerts'] == []
