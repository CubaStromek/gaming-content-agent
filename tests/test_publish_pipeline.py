"""Testy sdílené publish pipeline — vše mockované, žádná síť/WP/Claude.

Kryje hlavně kritické cesty z code review:
- brand téma nesmí spadnout na nedefinovaný image_url (původní UnboundLocalError)
- image_url nesmí přežít mezi tématy (stale obrázek jiné hry)
- happy path publikace CZ+EN vrací kompletní výsledek
- selhání CZ publish vrací error, nic dalšího se neposílá
"""

import pytest

import publish_pipeline as pp


@pytest.fixture
def topic():
    return {
        'topic': 'Steam Deck 2 oznámen',
        'title': 'Steam Deck 2 přichází',
        'game_name': 'Steam',
        'seo_keywords': 'steam, valve',
        'status_tag': 'news',
        'virality_score': 80,
        'sources': ['https://example.com/a'],
    }


@pytest.fixture
def article():
    return {
        'cs': '<p>Český článek o Steamu, dost dlouhý na excerpt i všechno ostatní.</p>',
        'en': '<p>English article about Steam, long enough for the excerpt logic.</p>',
        'en_title': 'Steam Deck 2 is coming',
        'cost': '$0.05',
    }


@pytest.fixture
def wired(monkeypatch):
    """Zapojí mocky na všechny externí závislosti a sbírá volání."""
    calls = {'create_draft': [], 'social': [], 'log': [], 'fb': []}

    monkeypatch.setattr(pp.wp_publisher, 'create_draft',
                        lambda **kw: (calls['create_draft'].append(kw) or
                                      ({'id': 100 + len(calls['create_draft']),
                                        'edit_url': 'e', 'view_url': f"https://gamefo.cz/{kw['lang']}"}, None)))
    monkeypatch.setattr(pp.wp_publisher, 'link_translations', lambda a, b: (True, None))
    monkeypatch.setattr(pp.wp_publisher, 'upload_media', lambda url, title='': (555, 'https://wp/img.jpg', None))
    monkeypatch.setattr(pp.wp_publisher, 'strip_first_heading', lambda h: h)
    monkeypatch.setattr(pp.youtube_embed, 'has_video_reference', lambda h, lang='cs': False)
    monkeypatch.setattr(pp.section_images, 'get_or_fetch_screenshots', lambda g: None)
    monkeypatch.setattr(pp.internal_linking, 'enrich_with_internal_links',
                        lambda html, tags, lang='cs': html)
    monkeypatch.setattr(pp.social_poster, 'post_to_all',
                        lambda **kw: (calls['social'].append(kw) or {'x': 'ok'}))
    monkeypatch.setattr(pp.publish_log, 'log_decision', lambda d: calls['log'].append(d))
    monkeypatch.setattr(pp, 'generate_fb_post', lambda **kw: calls['fb'].append(kw) or kw['output_path'])
    monkeypatch.setattr(pp, 'search_rawg_image', lambda g: 'https://rawg.io/img.jpg')
    return calls


class TestResolveFeaturedImage:
    def test_brand_topic_returns_defined_image_url(self, monkeypatch):
        """Původní kritický bug: brand větev nechávala image_url nedefinované."""
        monkeypatch.setattr(pp.brand_logos, 'resolve_brand_logo_strict', lambda g: 8905)
        fid, meta, image_url = pp.resolve_featured_image('Steam', 'Titulek')
        assert fid == 8905
        assert meta is None
        assert image_url is None  # definované, žádný UnboundLocalError / stale hodnota

    def test_rawg_topic_returns_image_url(self, monkeypatch):
        monkeypatch.setattr(pp.brand_logos, 'resolve_brand_logo_strict', lambda g: None)
        monkeypatch.setattr(pp.brand_logos, 'resolve_brand_logo', lambda *a: None)
        monkeypatch.setattr(pp.section_images, 'get_or_fetch_screenshots', lambda g: {'imgs': 1})
        monkeypatch.setattr(pp, 'search_rawg_image', lambda g: 'https://rawg.io/x.jpg')
        monkeypatch.setattr(pp.wp_publisher, 'upload_media', lambda url, title='': (42, 'src', None))
        fid, meta, image_url = pp.resolve_featured_image('Elden Ring', 'Titulek')
        assert fid == 42
        assert image_url == 'https://rawg.io/x.jpg'


class TestPublishArticle:
    def test_happy_path_cz_en(self, wired, topic, article, monkeypatch):
        monkeypatch.setattr(pp.brand_logos, 'resolve_brand_logo_strict', lambda g: 8905)
        result, err = pp.publish_article(topic, article, title='Steam Deck 2 přichází',
                                         run_id='run1', source='auto')
        assert err is None
        assert result['cs_result']['view_url'] == 'https://gamefo.cz/cs'
        assert result['en_result']['view_url'] == 'https://gamefo.cz/en'
        assert result['en_title'] == 'Steam Deck 2 is coming'
        # publikovaly se přesně 2 posty (cs, en) a zalogoval se 1 published záznam
        assert [c['lang'] for c in wired['create_draft']] == ['cs', 'en']
        published = [l for l in wired['log'] if l['action'] == 'published']
        assert len(published) == 1
        assert published[0]['run_id'] == 'run1'
        # brand téma → žádný RAWG obrázek → žádné FB obrázky (a žádný crash)
        assert wired['fb'] == []
        assert wired['social'][0]['image_path'] is None

    def test_rawg_path_generates_fb_images(self, wired, topic, article, monkeypatch):
        monkeypatch.setattr(pp.brand_logos, 'resolve_brand_logo_strict', lambda g: None)
        monkeypatch.setattr(pp.brand_logos, 'resolve_brand_logo', lambda *a: None)

        class FakeResp:
            status_code = 200
            content = b'fake-jpg'
        monkeypatch.setattr(pp.requests, 'get', lambda *a, **kw: FakeResp())

        result, err = pp.publish_article(topic, article, title='Steam Deck 2 přichází')
        assert err is None
        assert len(wired['fb']) == 2  # CZ + EN obrázek

    def test_cs_publish_error_stops_pipeline(self, wired, topic, article, monkeypatch):
        monkeypatch.setattr(pp.brand_logos, 'resolve_brand_logo_strict', lambda g: 8905)
        monkeypatch.setattr(pp.wp_publisher, 'create_draft', lambda **kw: (None, 'WP down'))
        result, err = pp.publish_article(topic, article, title='T')
        assert result is None
        assert err == 'WP down'
        assert wired['social'] == []  # po selhání CZ se nic nepostuje
        assert all(l['action'] != 'published' for l in wired['log'])

    def test_sanitizes_llm_html(self, wired, topic, monkeypatch):
        monkeypatch.setattr(pp.brand_logos, 'resolve_brand_logo_strict', lambda g: 8905)
        evil = {'cs': '<p>ok</p><script>alert(1)</script>', 'en': '', 'cost': '$0'}
        result, err = pp.publish_article(topic, evil, title='T')
        assert err is None
        sent_content = wired['create_draft'][0]['content']
        assert '<script' not in sent_content and 'alert' not in sent_content

    def test_status_tag_fallback(self, wired, article, monkeypatch, topic):
        monkeypatch.setattr(pp.brand_logos, 'resolve_brand_logo_strict', lambda g: 8905)
        topic['status_tag'] = 'nesmysl'
        pp.publish_article(topic, article, title='T')
        assert wired['create_draft'][0]['status_tag'] == 'news'
