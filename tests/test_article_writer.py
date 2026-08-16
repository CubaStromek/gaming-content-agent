"""Tests for article_writer module."""

import pytest
from unittest.mock import patch, MagicMock

import article_writer
import config


class TestParseTopicsFromReport:
    """Testy pro regex parsování témat z reportu."""

    def test_parses_two_topics(self, sample_report_text):
        topics = article_writer.parse_topics_from_report(sample_report_text)
        assert len(topics) == 2

    def test_first_topic_fields(self, sample_report_text):
        topics = article_writer.parse_topics_from_report(sample_report_text)
        topic = topics[0]
        assert topic['topic'] == 'GTA 6 Trailer'
        assert topic['title'] == 'GTA 6: Nový trailer překonává rekordy'
        assert topic['angle'] == 'Detailní analýza'
        assert topic['context'] == 'Rockstar Games vydal nový trailer.'
        assert topic['hook'] == 'Nejvíce sledovaný trailer v historii'
        assert topic['virality_score'] == 95

    def test_sources_parsed(self, sample_report_text):
        topics = article_writer.parse_topics_from_report(sample_report_text)
        assert 'https://ign.com/gta6' in topics[0]['sources']
        assert 'https://pcgamer.com/gta6' in topics[0]['sources']

    def test_seo_keywords(self, sample_report_text):
        topics = article_writer.parse_topics_from_report(sample_report_text)
        assert 'GTA 6' in topics[0]['seo_keywords']

    def test_second_topic(self, sample_report_text):
        topics = article_writer.parse_topics_from_report(sample_report_text)
        topic = topics[1]
        assert 'Palworld' in topic['topic']
        assert topic['virality_score'] == 80

    def test_empty_report(self):
        topics = article_writer.parse_topics_from_report("")
        assert topics == []

    def test_no_topics_in_text(self):
        topics = article_writer.parse_topics_from_report("Nějaký náhodný text bez témat.")
        assert topics == []

    def test_bold_markdown_format(self):
        """Testuje parsování s markdown bold formátováním."""
        text = """**🎮 TÉMA 1:** Test Topic
**📰 NAVRŽENÝ TITULEK:** Test Titulek
**🎯 ÚHEL POHLEDU:** Test Úhel
**📝 KONTEXT:** Test Kontext
**💬 HLAVNÍ HOOK:** Test Hook
**🖼️ VIZUÁLNÍ NÁVRH:** Test Visual
**🔥 VIRALITA:** 75/100
**💡 PROČ TEĎKA:** Test Why
**🔗 ZDROJE:**
https://example.com/article1
**🏷️ SEO KLÍČOVÁ SLOVA:** keyword1, keyword2
**🕹️ NÁZEV HRY:** Test Game"""
        topics = article_writer.parse_topics_from_report(text)
        assert len(topics) == 1
        assert topics[0]['topic'] == 'Test Topic'
        assert topics[0]['virality_score'] == 75


class TestStripMarkdownArtifacts:
    def test_removes_code_fences(self):
        html = "```html\n<p>Hello</p>\n```"
        result = article_writer._strip_markdown_artifacts(html)
        assert "```" not in result
        assert "<p>Hello</p>" in result

    def test_converts_markdown_headings(self):
        html = "## Nadpis"
        result = article_writer._strip_markdown_artifacts(html)
        assert "<h2>Nadpis</h2>" in result

    def test_converts_bold(self):
        html = "**important text**"
        result = article_writer._strip_markdown_artifacts(html)
        assert "<strong>important text</strong>" in result

    def test_converts_hr(self):
        html = "---"
        result = article_writer._strip_markdown_artifacts(html)
        assert "<hr>" in result


class TestMakeFirstParagraphQuote:
    def test_wraps_first_paragraph(self):
        html = "<p>First paragraph</p><p>Second paragraph</p>"
        result = article_writer._make_first_paragraph_quote(html)
        assert '<blockquote class="wp-block-quote"><p>First paragraph</p></blockquote>' in result
        # Druhý odstavec zůstává nezměněn
        assert "<p>Second paragraph</p>" in result

    def test_no_paragraphs(self):
        html = "<h2>Just a heading</h2>"
        result = article_writer._make_first_paragraph_quote(html)
        assert result == html


class TestInsertSeparatorsBeforeH2:
    def test_no_separator_before_first_h2(self):
        html = "<h2>First</h2><p>text</p>"
        result = article_writer._insert_separators_before_h2(html)
        assert '<hr class="wp-block-separator' not in result.split("<h2>First</h2>")[0]

    def test_separator_before_second_h2(self):
        html = "<h2>First</h2><p>text</p><h2>Second</h2><p>more text</p>"
        result = article_writer._insert_separators_before_h2(html)
        assert '<hr class="wp-block-separator' in result
        # Separator je před druhým h2, ne před prvním
        before_first = result.split("<h2>First</h2>")[0]
        assert "hr" not in before_first


class TestStripGeneratedSources:
    def test_strips_czech_sources(self):
        html = "<p>Content</p><h2>Zdroje</h2><ul><li>src1</li></ul>"
        result = article_writer._strip_generated_sources(html)
        assert "<h2>Zdroje</h2>" not in result
        assert "<p>Content</p>" in result

    def test_strips_english_sources(self):
        html = "<p>Content</p><h2>Sources</h2><ul><li>src1</li></ul>"
        result = article_writer._strip_generated_sources(html)
        assert "<h2>Sources</h2>" not in result

    def test_keeps_non_source_content(self):
        html = "<p>Content</p><h2>Other</h2><p>More</p>"
        result = article_writer._strip_generated_sources(html)
        assert result == html


class TestBuildSourcesHtml:
    def test_czech_heading(self):
        result = article_writer._build_sources_html(["https://ign.com/article"], lang='cs')
        assert "<h2>Zdroje</h2>" in result
        assert "ign.com" in result

    def test_english_heading(self):
        result = article_writer._build_sources_html(["https://ign.com/article"], lang='en')
        assert "<h2>Sources</h2>" in result

    def test_empty_urls(self):
        assert article_writer._build_sources_html([]) == ''

    def test_multiple_sources(self):
        urls = ["https://ign.com/a", "https://pcgamer.com/b"]
        result = article_writer._build_sources_html(urls)
        assert "ign.com" in result
        assert "pcgamer.com" in result


class TestScrapeFullArticle:
    @patch('article_writer.requests.get')
    def test_scrapes_article_content(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = """
        <html><body>
            <article><p>This is the article content about gaming.</p></article>
        </body></html>
        """
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = article_writer.scrape_full_article("https://example.com/article")
        assert "article content" in result

    @patch('article_writer.requests.get')
    def test_handles_timeout(self, mock_get):
        mock_get.side_effect = Exception("Connection timeout")
        result = article_writer.scrape_full_article("https://example.com/article")
        assert "[Chyba" in result

    @patch('article_writer.requests.get')
    def test_truncates_long_content(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.text = f"<html><body><article><p>{'A' * 5000}</p></article></body></html>"
        mock_resp.raise_for_status = MagicMock()
        mock_get.return_value = mock_resp

        result = article_writer.scrape_full_article("https://example.com/article")
        assert len(result) <= 3000


class TestWriteArticle:
    @patch('article_writer._call_api')
    def test_returns_cs_and_en(self, mock_api):
        mock_message = MagicMock()
        mock_message.content = [MagicMock(type="text", text="""TITULEK CZ: Testovací titulek
TITULEK EN: Test Title

=== ČESKY ===
<p>Český článek o hře.</p>
<h2>Detaily</h2>
<p>Více informací.</p>

=== ENGLISH ===
<p>English article about the game.</p>
<h2>Details</h2>
<p>More information.</p>""")]
        mock_message.usage = MagicMock(input_tokens=1000, output_tokens=500)
        mock_api.return_value = mock_message

        topic = {
            'topic': 'Test Game',
            'title': 'Původní titulek',
            'angle': 'Analýza',
            'context': 'Kontext',
            'seo_keywords': 'test, game',
            'sources': ['https://example.com'],
        }

        result = article_writer.write_article(topic, ["Source text about the game"])
        assert 'cs' in result
        assert 'en' in result
        assert 'error' not in result
        assert 'Český článek' in result['cs']
        assert 'English article' in result['en']
        assert result['corrected_title'] == 'Testovací titulek'
        assert result['en_title'] == 'Test Title'

    def test_response_text_skips_thinking_blocks(self):
        """U modelů s přemýšlením není content[0] textový blok. Dřív se četlo
        content[0].text a padalo to na 'ThinkingBlock' object has no attribute
        'text' — tenhle test tu regresi hlídá."""
        thinking = MagicMock(type="thinking")
        del thinking.text  # ThinkingBlock .text opravdu nemá
        text_block = MagicMock(type="text", text="<p>Článek.</p>")
        message = MagicMock(content=[thinking, text_block])
        assert article_writer._response_text(message) == "<p>Článek.</p>"

    def test_modern_models_skip_temperature(self):
        """Sonnet 5 / Opus 5 / Opus 4.7+ vracejí na nedefaultní temperature 400."""
        assert article_writer._is_modern("claude-opus-5")
        assert article_writer._is_modern("claude-sonnet-5")
        assert article_writer._is_modern("claude-opus-4-8")
        assert not article_writer._is_modern("claude-sonnet-4-6")
        assert not article_writer._is_modern("claude-haiku-4-5-20251001")

    @patch('article_writer._call_api')
    def test_english_comes_from_second_call(self, mock_api):
        """Český článek a anglická lokalizace jsou dvě volání, každé na svém
        modelu. EN text musí pocházet z druhého volání, ne z prvního."""
        def response(text):
            m = MagicMock()
            m.content = [MagicMock(type="text", text=text)]
            m.usage = MagicMock(input_tokens=1000, output_tokens=500)
            m.stop_reason = 'end_turn'
            return m

        mock_api.side_effect = [
            response("TITULEK CZ: Český titulek\n\n=== ČESKY ===\n<p>Český článek.</p>"),
            response("TITULEK EN: English title\nKEYWORD EN: test\n\n=== ENGLISH ===\n<p>English article.</p>"),
        ]

        topic = {'topic': 'T', 'title': 'T', 'angle': '', 'context': '', 'seo_keywords': '', 'sources': []}
        result = article_writer.write_article(topic, ["source"])

        assert 'Český článek' in result['cs']
        assert 'English article' in result['en']
        assert result['en_title'] == 'English title'
        assert result['focus_keyword_en'] == 'test'
        # dvě volání, každé na svém modelu
        models = [c.args[1] for c in mock_api.call_args_list]
        assert models == [config.ARTICLE_MODEL, config.TRANSLATION_MODEL]
        # náklady i tokeny se sčítají přes obě fáze
        assert result['tokens_out'] == 1000

    @patch('article_writer._call_api')
    def test_failed_localization_still_publishes_czech(self, mock_api):
        """Když spadne EN fáze, český článek se musí vrátit — ne celý spadnout."""
        ok = MagicMock()
        ok.content = [MagicMock(type="text", text="TITULEK CZ: T\n\n=== ČESKY ===\n<p>Český text.</p>")]
        ok.usage = MagicMock(input_tokens=100, output_tokens=200)
        ok.stop_reason = 'end_turn'
        mock_api.side_effect = [ok, Exception("EN model spadl")]

        topic = {'topic': 'T', 'title': 'T', 'angle': '', 'context': '', 'seo_keywords': '', 'sources': []}
        result = article_writer.write_article(topic, ["source"])

        assert 'error' not in result
        assert 'Český text' in result['cs']
        assert result['en'] == ''

    @patch('article_writer._call_api')
    def test_handles_api_error(self, mock_api):
        mock_api.side_effect = Exception("API Error")

        topic = {'topic': 'Test', 'title': 'Test', 'angle': '', 'context': '', 'seo_keywords': '', 'sources': []}
        result = article_writer.write_article(topic, ["text"])
        assert 'error' in result

    def _write_with_output(self, mock_api, text):
        mock_message = MagicMock()
        mock_message.content = [MagicMock(type="text", text=text)]
        mock_message.usage = MagicMock(input_tokens=1000, output_tokens=500)
        mock_message.stop_reason = 'end_turn'
        mock_api.return_value = mock_message
        topic = {'topic': 'Test', 'title': 'Test', 'angle': '', 'context': '', 'seo_keywords': '', 'sources': []}
        return article_writer.write_article(topic, ["text"])

    @patch('article_writer._call_api')
    def test_parses_rubrika_and_strips_line(self, mock_api):
        result = self._write_with_output(mock_api, """TITULEK CZ: Titulek
RUBRIKA: valve

=== ČESKY ===
<p>Článek o Steamu.</p>""")
        assert result['subcategory'] == 'valve'
        assert 'RUBRIKA' not in result['cs']

    @patch('article_writer._call_api')
    def test_rubrika_zadna_means_no_subcategory(self, mock_api):
        result = self._write_with_output(mock_api, """TITULEK CZ: Titulek
RUBRIKA: zadna

=== ČESKY ===
<p>Článek.</p>""")
        assert 'subcategory' not in result
        assert 'RUBRIKA' not in result['cs']

    @patch('article_writer._call_api')
    def test_invalid_rubrika_ignored(self, mock_api):
        result = self._write_with_output(mock_api, """TITULEK CZ: Titulek
RUBRIKA: sega

=== ČESKY ===
<p>Článek.</p>""")
        assert 'subcategory' not in result
