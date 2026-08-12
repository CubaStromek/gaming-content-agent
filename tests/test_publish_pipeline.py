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
    monkeypatch.setattr(pp.youtube_embed, 'find_embeddable_video', lambda q, game_name=None: None)
    monkeypatch.setattr(pp.section_images, 'get_or_fetch_screenshots', lambda g: None)
    monkeypatch.setattr(pp.internal_linking, 'enrich_with_internal_links',
                        lambda html, tags, lang='cs': html)
    monkeypatch.setattr(pp.social_poster, 'post_to_all',
                        lambda **kw: (calls['social'].append(kw) or {'x': 'ok'}))
    monkeypatch.setattr(pp.publish_log, 'log_decision', lambda d: calls['log'].append(d))
    monkeypatch.setattr(pp, 'generate_fb_post', lambda **kw: calls['fb'].append(kw) or kw['output_path'])
    monkeypatch.setattr(pp, 'search_game_image', lambda g, **kw: 'https://images.igdb.com/img.jpg')
    return calls


class TestResolveFeaturedImage:
    def test_brand_topic_returns_defined_image_url(self, monkeypatch):
        """Původní kritický bug: brand větev nechávala image_url nedefinované."""
        monkeypatch.setattr(pp.brand_logos, 'resolve_brand_logo_strict', lambda g: 8905)
        fid, meta, image_url = pp.resolve_featured_image('Steam', 'Titulek')
        assert fid == 8905
        assert meta is None
        assert image_url is None  # definované, žádný UnboundLocalError / stale hodnota

    def test_game_topic_returns_image_url(self, monkeypatch):
        monkeypatch.setattr(pp.brand_logos, 'resolve_brand_logo_strict', lambda g: None)
        monkeypatch.setattr(pp.brand_logos, 'resolve_brand_logo', lambda *a: None)
        monkeypatch.setattr(pp.section_images, 'get_or_fetch_screenshots', lambda g: {'imgs': 1})
        monkeypatch.setattr(pp, 'search_game_image', lambda g, **kw: 'https://images.igdb.com/x.jpg')
        monkeypatch.setattr(pp.wp_publisher, 'upload_media', lambda url, title='': (42, 'src', None))
        fid, meta, image_url = pp.resolve_featured_image(
            'Elden Ring', 'Titulek', {'game_name': 'Elden Ring'})
        assert fid == 42
        assert image_url == 'https://images.igdb.com/x.jpg'

    def test_brand_news_no_real_game_uses_logo_not_search(self, monkeypatch):
        """Regrese: game_name=N/A + brand v titulku → brand logo, NE herní DB.

        Reálný bug: 'Petice za záchranu disků na PlayStation' dostala náhodný
        screenshot hry, protože strict gate spadl na celé české větě a brand
        fallback pod hledáním se nikdy nespustil (fulltext vždy něco vrátí).
        """
        monkeypatch.setattr(pp.brand_logos, 'resolve_brand_logo_strict', lambda g: None)
        # Fulltext by (jako vždy) něco vrátil — nesmí se použít
        monkeypatch.setattr(pp, 'search_game_image',
                            lambda g, **kw: (_ for _ in ()).throw(AssertionError('IGDB nesmí běžet')))
        topic = {
            'game_name': 'N/A',
            'seo_keywords': 'PlayStation, Sony',
            'topic': 'Petice za záchranu fyzických her: 115 000 podpisů',
        }
        fid, meta, image_url = pp.resolve_featured_image(
            topic['topic'],
            'Petice proti zrušení disků na PlayStation překročila 115 tisíc podpisů',
            topic)
        assert fid == pp.brand_logos.BRAND_LOGOS['playstation']
        assert meta is None
        assert image_url is None


class TestEntityDrivenSearch:
    """ENTITA z article_writeru: kanonický anglický název subjektu.

    Bez ní se do IGDB posílal `game_name`, což je u témat s game_name=N/A
    celá česká věta ('Roblox v krizi: Podíl akcií padá o 70 %'). IGDB na to
    nic nenajde → článek vyšel s generickým GAMEfo logem (10 ze 13 srpnových
    placeholderů).
    """

    @pytest.fixture(autouse=True)
    def _no_brand_gate(self, monkeypatch):
        monkeypatch.setattr(pp.brand_logos, 'resolve_brand_logo_strict', lambda g: None)

    NA_TOPIC = {'game_name': 'N/A', 'seo_keywords': '', 'topic': 'České téma bez hry'}

    def test_no_entity_skips_search_entirely(self, monkeypatch):
        """Chybí ENTITA → radši placeholder než náhodná hra z české věty."""
        monkeypatch.setattr(pp, 'search_game_image',
                            lambda g, **kw: (_ for _ in ()).throw(AssertionError('IGDB nesmí běžet')))
        monkeypatch.setattr(pp.section_images, 'get_or_fetch_screenshots',
                            lambda g: (_ for _ in ()).throw(AssertionError('screenshoty nesmí běžet')))

        fid, meta, image_url = pp.resolve_featured_image(
            'Herní průmysl propouští, krize pokračuje',
            'Propouštění pokračuje i letos', self.NA_TOPIC)

        assert fid == pp.brand_logos.GAMEFO_LOGO
        assert image_url is None

    def test_entity_game_is_searched_instead_of_czech_sentence(self, monkeypatch):
        queried = []
        monkeypatch.setattr(pp, 'search_game_image',
                            lambda g, **kw: queried.append(g) or 'https://igdb/x.jpg')
        monkeypatch.setattr(pp.section_images, 'get_or_fetch_screenshots', lambda g: None)
        monkeypatch.setattr(pp.wp_publisher, 'upload_media', lambda url, **kw: (55, url, None))

        article = {'entity_name': 'The Witcher', 'entity_type': 'hra'}
        fid, meta, image_url = pp.resolve_featured_image(
            'Witcher seriál na Netflixu – finální sezona se posouvá na 2027',
            'Witcher se posouvá', self.NA_TOPIC, article)

        assert queried == ['The Witcher']  # ne celá česká věta
        assert fid == 55

    def test_entity_brand_prefers_logo_over_igdb(self, monkeypatch):
        monkeypatch.setattr(pp, 'search_game_image',
                            lambda g, **kw: (_ for _ in ()).throw(AssertionError('IGDB nesmí běžet')))

        article = {'entity_name': 'Devolver Digital', 'entity_type': 'znacka'}
        fid, meta, image_url = pp.resolve_featured_image(
            'Devolver Digital chce z burzy', 'Devolver mizí z burzy',
            self.NA_TOPIC, article)

        assert fid == pp.brand_logos.BRAND_LOGOS['devolver']

    def test_brand_without_logo_uses_exact_match_gate(self, monkeypatch):
        """Značka bez loga smí do IGDB, ale jen na přesnou shodu názvu.

        Brand match je vypnutý schválně — test ověřuje mechanismus, ne to,
        která loga zrovna v media library jsou.
        """
        seen = {}
        monkeypatch.setattr(pp.brand_logos, 'resolve_brand_logo', lambda *a: None)
        monkeypatch.setattr(pp, 'search_game_image',
                            lambda g, **kw: seen.update(kw, name=g) or None)

        article = {'entity_name': 'Pokémon', 'entity_type': 'znacka'}
        fid, meta, image_url = pp.resolve_featured_image(
            'Bezpečnostní krize v Pokémon Company', 'Krize v Pokémon Company',
            self.NA_TOPIC, article)

        assert seen == {'exact_only': True, 'name': 'Pokémon'}
        assert fid == pp.brand_logos.GAMEFO_LOGO  # neshoda → placeholder, ne cizí hra

    def test_game_entity_with_brand_token_skips_brand_shortcut(self, monkeypatch):
        """'Pokémon Pokopia' je hra, ne značka — musí dostat vlastní artwork.

        Regrese: po doplnění Pokémon loga přebíral brand match i konkrétní hry,
        které mají značku v názvu, a článek dostal obecné logo místo artworku.
        """
        queried = []
        monkeypatch.setattr(pp, 'search_game_image',
                            lambda g, **kw: queried.append(g) or 'https://igdb/x.jpg')
        monkeypatch.setattr(pp.section_images, 'get_or_fetch_screenshots', lambda g: None)
        monkeypatch.setattr(pp.wp_publisher, 'upload_media', lambda url, **kw: (77, url, None))

        article = {'entity_name': 'Pokémon Pokopia', 'entity_type': 'hra'}
        fid, meta, image_url = pp.resolve_featured_image(
            'Pokémon Pokopia 2.0.0 mění ukládání', 'Pokopia 2.0.0 mění ukládání',
            self.NA_TOPIC, article)

        assert queried == ['Pokémon Pokopia']
        assert fid == 77
        assert fid != pp.brand_logos.BRAND_LOGOS['pokemon']

    def test_game_entity_falls_back_to_brand_logo(self, monkeypatch):
        """Když IGDB na hru nic nenajde, brand logo entity ji pořád zachytí."""
        monkeypatch.setattr(pp, 'search_game_image', lambda g, **kw: None)
        monkeypatch.setattr(pp.section_images, 'get_or_fetch_screenshots', lambda g: None)

        article = {'entity_name': 'Pokémon Pokopia', 'entity_type': 'hra'}
        fid, meta, image_url = pp.resolve_featured_image(
            'Pokémon Pokopia 2.0.0 mění ukládání', 'Pokopia 2.0.0 mění ukládání',
            self.NA_TOPIC, article)

        assert fid == pp.brand_logos.BRAND_LOGOS['pokemon']

    def test_real_game_ignores_entity(self, monkeypatch):
        """Když analyzer hru zná, ENTITA do toho nemluví."""
        queried = []
        monkeypatch.setattr(pp, 'search_game_image',
                            lambda g, **kw: queried.append((g, kw)) or None)
        monkeypatch.setattr(pp.section_images, 'get_or_fetch_screenshots', lambda g: None)
        monkeypatch.setattr(pp.brand_logos, 'resolve_brand_logo', lambda *a: None)

        article = {'entity_name': 'Nintendo', 'entity_type': 'znacka'}
        pp.resolve_featured_image('Elden Ring', 'Titulek',
                                  {'game_name': 'Elden Ring'}, article)

        assert queried == [('Elden Ring', {'exact_only': False})]


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
        # brand téma → žádný stažený obrázek → žádné FB obrázky (a žádný crash)
        assert wired['fb'] == []
        assert wired['social'][0]['image_path'] is None

    def test_image_path_generates_fb_images(self, wired, topic, article, monkeypatch):
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


class TestSubcategory:
    """Podrubriky Zpráv/News — LLM klasifikace z article_writer + ruční override."""

    @pytest.fixture(autouse=True)
    def _brand_logo(self, monkeypatch):
        monkeypatch.setattr(pp.brand_logos, 'resolve_brand_logo_strict', lambda g: 8905)

    def test_subcategory_appended_to_both_langs(self, wired, topic, article):
        article['subcategory'] = 'valve'
        pp.publish_article(topic, article, title='T')
        cs, en = wired['create_draft']
        assert cs['category_ids'] == [9, 4166]
        assert en['category_ids'] == [12, 607]
        published = [l for l in wired['log'] if l['action'] == 'published']
        assert published[0]['subcategory'] == 'valve'

    def test_no_subcategory_keeps_parent_only(self, wired, topic, article):
        pp.publish_article(topic, article, title='T')
        cs, en = wired['create_draft']
        assert cs['category_ids'] == [9]
        assert en['category_ids'] == [12]

    def test_subcategory_without_en_equivalent(self, wired, topic, article):
        article['subcategory'] = 'cesko-slovensko'
        pp.publish_article(topic, article, title='T')
        cs, en = wired['create_draft']
        assert cs['category_ids'] == [9, 33]
        assert en['category_ids'] == [12]  # EN ekvivalent neexistuje

    def test_unknown_subcategory_ignored(self, wired, topic, article):
        article['subcategory'] = 'nesmysl'
        pp.publish_article(topic, article, title='T')
        cs, en = wired['create_draft']
        assert cs['category_ids'] == [9]
        assert en['category_ids'] == [12]
        published = [l for l in wired['log'] if l['action'] == 'published']
        assert published[0]['subcategory'] is None

    def test_topic_override_beats_article(self, wired, topic, article):
        """manual_article --category má přednost před LLM klasifikací."""
        topic['subcategory'] = 'indie'
        article['subcategory'] = 'valve'
        pp.publish_article(topic, article, title='T')
        assert wired['create_draft'][0]['category_ids'] == [9, 66]

    def test_category_ids_constant_not_mutated(self, wired, topic, article):
        article['subcategory'] = 'aaa'
        pp.publish_article(topic, article, title='T')
        assert pp.CATEGORY_IDS == {'cs': [9], 'en': [12]}


class TestEmbedYoutube:
    """Always-embed: článek o reálné hře dostane video VŽDY, keyword brána
    zůstává jen pro témata bez hry (N/A) a brand témata.

    Reálný případ: Onimusha preview 6. 8. 2026 vyšla bez traileru, protože
    text nepoužil žádné z klíčových slov (trailer/video/gameplay…)."""

    @pytest.fixture(autouse=True)
    def _no_brand(self, monkeypatch):
        monkeypatch.setattr(pp.brand_logos, 'resolve_brand_logo_strict', lambda g: None)

    def test_real_game_embeds_without_video_mention(self, monkeypatch):
        monkeypatch.setattr(pp.youtube_embed, 'find_embeddable_video',
                            lambda q, game_name=None: {'id': 'vid123', 'title': 'Trailer', 'url': 'u'})
        article = {'cs': '<p>Text bez klíčových slov o videu.</p><h2>Sekce</h2><p>Obsah.</p>',
                   'en': '<p>Plain text, no keywords.</p><h2>Section</h2><p>Body.</p>'}
        out = pp.embed_youtube(article, 'Onimusha: Way of the Sword',
                               {'game_name': 'Onimusha: Way of the Sword'})
        assert 'vid123' in out['cs'] and 'vid123' in out['en']
        # embed patří na konec úvodu (před první <h2>), ne mezi nadpis a text
        assert out['cs'].index('vid123') < out['cs'].index('<h2>')

    def test_na_game_without_mention_skips(self, monkeypatch):
        monkeypatch.setattr(pp.youtube_embed, 'find_embeddable_video',
                            lambda q, game_name=None: (_ for _ in ()).throw(
                                AssertionError('YouTube search nesmí běžet')))
        article = {'cs': '<p>Petice za záchranu fyzických her sbírá podpisy.</p>', 'en': ''}
        out = pp.embed_youtube(article, 'Petice za záchranu fyzických her', {'game_name': 'N/A'})
        assert 'wp:embed' not in out['cs']

    def test_na_game_with_mention_embeds(self, monkeypatch):
        monkeypatch.setattr(pp.youtube_embed, 'find_embeddable_video',
                            lambda q, game_name=None: {'id': 'vid456', 'title': 'T', 'url': 'u'})
        article = {'cs': '<p>Sony zveřejnila nový trailer k výročí.</p>', 'en': ''}
        out = pp.embed_youtube(article, 'PlayStation výročí', {'game_name': 'N/A'})
        assert 'vid456' in out['cs']

    def test_brand_game_without_mention_skips(self, monkeypatch):
        monkeypatch.setattr(pp.brand_logos, 'resolve_brand_logo_strict', lambda g: 8905)
        monkeypatch.setattr(pp.youtube_embed, 'find_embeddable_video',
                            lambda q, game_name=None: (_ for _ in ()).throw(
                                AssertionError('YouTube search nesmí běžet')))
        article = {'cs': '<p>Steam slaví výročí slevami.</p>', 'en': ''}
        out = pp.embed_youtube(article, 'Steam', {'game_name': 'Steam'})
        assert 'wp:embed' not in out['cs']
