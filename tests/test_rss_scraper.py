"""Tests for rss_scraper module."""

import pytest
import rss_scraper


class TestFormatArticlesForAnalysis:
    def test_formats_articles(self, sample_articles):
        result = rss_scraper.format_articles_for_analysis(sample_articles)
        assert "ČLÁNEK 1:" in result
        assert "ČLÁNEK 2:" in result
        assert "ČLÁNEK 3:" in result
        assert "GTA 6 Trailer Breaks Records" in result
        assert "Zdroj: IGN (en)" in result

    def test_empty_list(self):
        result = rss_scraper.format_articles_for_analysis([])
        assert result == ""

    def test_single_article(self):
        articles = [{'source': 'Test', 'language': 'en', 'title': 'Title', 'summary': 'Desc', 'link': 'https://test.com'}]
        result = rss_scraper.format_articles_for_analysis(articles)
        assert "ČLÁNEK 1:" in result
        assert "ČLÁNEK 2:" not in result


class TestSaveArticlesToJson:
    def test_saves_json(self, tmp_path, sample_articles):
        run_dir = str(tmp_path)
        filepath = rss_scraper.save_articles_to_json(sample_articles, run_dir)
        assert filepath is not None

        import json
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        assert data["total_articles"] == 3
        assert len(data["articles"]) == 3


class TestSaveArticlesToCsv:
    def test_saves_csv(self, tmp_path, sample_articles):
        run_dir = str(tmp_path)
        filepath = rss_scraper.save_articles_to_csv(sample_articles, run_dir)
        assert filepath is not None

        with open(filepath, 'r', encoding='utf-8-sig') as f:
            lines = f.readlines()
        # Header + 3 articles
        assert len(lines) == 4
