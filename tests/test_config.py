"""Tests for config module."""

import os
import pytest
from unittest.mock import patch

import config


class TestValidateConfig:
    def test_valid_config(self):
        with patch.object(config, 'CLAUDE_API_KEY', 'sk-ant-real-key'):
            assert config.validate_config() is True

    def test_missing_api_key(self):
        with patch.object(config, 'CLAUDE_API_KEY', ''):
            assert config.validate_config() is False

    def test_placeholder_api_key(self):
        with patch.object(config, 'CLAUDE_API_KEY', 'sk-ant-api03-your-api-key-here'):
            assert config.validate_config() is False


class TestConfigValues:
    def test_defaults_exist(self):
        assert isinstance(config.MAX_ARTICLES_PER_SOURCE, int)
        assert isinstance(config.MIN_VIRALITY_SCORE, int)
        assert isinstance(config.SUMMARY_MAX_LENGTH, int)
        assert config.SUMMARY_MAX_LENGTH == 500

    def test_analysis_model_set(self):
        assert config.ANALYSIS_MODEL is not None
        assert "claude" in config.ANALYSIS_MODEL

    def test_article_model_set(self):
        assert config.ARTICLE_MODEL is not None
        assert "claude" in config.ARTICLE_MODEL

    def test_dashboard_token_defaults_empty(self):
        # Default je prázdný string (auth vypnuta)
        assert isinstance(config.DASHBOARD_TOKEN, str)


class TestIsWpConfigured:
    def test_configured(self):
        with patch.object(config, 'WP_URL', 'https://test.com'), \
             patch.object(config, 'WP_USER', 'user'), \
             patch.object(config, 'WP_APP_PASSWORD', 'pass'):
            assert config.is_wp_configured() is True

    def test_not_configured(self):
        with patch.object(config, 'WP_URL', ''), \
             patch.object(config, 'WP_USER', ''), \
             patch.object(config, 'WP_APP_PASSWORD', ''):
            assert config.is_wp_configured() is False
