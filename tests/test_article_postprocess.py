"""Testy pro article_postprocess — čisté string transformace, žádná síť/Claude."""

import article_postprocess as pp


class TestBuildSourcesHtml:
    def test_empty_returns_empty(self):
        assert pp.build_sources_html([]) == ''

    def test_cz_uses_zdroje(self):
        out = pp.build_sources_html(['https://www.example.com/path'], lang='cs')
        assert '<h2>Zdroje</h2>' in out
        # Display text domény bez www.
        assert '>example.com</a>' in out

    def test_en_uses_sources(self):
        out = pp.build_sources_html(['https://ign.com/x'], lang='en')
        assert '<h2>Sources</h2>' in out


class TestStripGeneratedSources:
    def test_removes_zdroje_section(self):
        html = '<p>úvod</p><h2>Zdroje</h2><ul><li>x</li></ul>'
        assert '<h2>Zdroje</h2>' not in pp.strip_generated_sources(html)

    def test_removes_sources_section(self):
        html = '<p>intro</p>\n<h2>Sources</h2>\n<ul><li>y</li></ul>'
        assert '<h2>Sources</h2>' not in pp.strip_generated_sources(html)

    def test_keeps_other_h2(self):
        html = '<h2>Hra</h2><p>x</p>'
        assert '<h2>Hra</h2>' in pp.strip_generated_sources(html)


class TestStripMarkdownArtifacts:
    def test_removes_code_fence(self):
        out = pp.strip_markdown_artifacts('```html\n<p>x</p>\n```')
        assert '```' not in out

    def test_converts_bold(self):
        assert '<strong>x</strong>' in pp.strip_markdown_artifacts('**x**')

    def test_converts_h2(self):
        assert '<h2>Title</h2>' in pp.strip_markdown_artifacts('## Title')


class TestMakeFirstParagraphQuote:
    def test_wraps_first_paragraph_only(self):
        html = '<p>první</p><p>druhý</p>'
        out = pp.make_first_paragraph_quote(html)
        assert out.count('<blockquote') == 1
        assert '<blockquote class="wp-block-quote"><p>první</p></blockquote>' in out
        assert '<p>druhý</p>' in out


class TestInsertSeparatorsBeforeH2:
    def test_inserts_between_h2(self):
        html = '<p>úvod</p><h2>A</h2><p>x</p><h2>B</h2><p>y</p>'
        out = pp.insert_separators_before_h2(html)
        # Před prvním <h2> separátor není, před druhým ano.
        assert out.count('wp-block-separator') == 1

    def test_no_h2_unchanged(self):
        html = '<p>jen text</p>'
        assert pp.insert_separators_before_h2(html) == html


class TestExtractStoryCards:
    def test_returns_none_when_label_missing(self):
        assert pp.extract_story_cards('nic tu není', 'CZ') is None

    def test_parses_simple_array(self):
        text = 'STORY_CARDS CZ: [{"heading":"H","body":"B"},{"heading":"","body":"B2"}]'
        cards = pp.extract_story_cards(text, 'CZ')
        assert cards is not None
        assert len(cards) == 2
        assert cards[0]['heading'] == 'H'
        assert cards[1]['body'] == 'B2'

    def test_truncates_lengths(self):
        long_h = 'x' * 80
        long_b = 'y' * 300
        text = f'STORY_CARDS EN: [{{"heading":"{long_h}","body":"{long_b}"}}]'
        cards = pp.extract_story_cards(text, 'EN')
        assert cards is not None
        assert len(cards[0]['heading']) == 60
        assert len(cards[0]['body']) == 200

    def test_skips_empty_body(self):
        text = 'STORY_CARDS CZ: [{"heading":"H","body":""}]'
        assert pp.extract_story_cards(text, 'CZ') is None

    def test_unbalanced_brackets_returns_none(self):
        text = 'STORY_CARDS CZ: [{"heading":"H","body":"B"'
        assert pp.extract_story_cards(text, 'CZ') is None
