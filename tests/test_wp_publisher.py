"""Tests for wp_publisher module."""

import pytest
from unittest.mock import patch, MagicMock

import wp_publisher


class TestToGutenbergBlocks:
    def test_wraps_paragraphs(self):
        html = "<p>Hello world</p>"
        result = wp_publisher._to_gutenberg_blocks(html)
        assert "<!-- wp:paragraph -->" in result
        assert "<!-- /wp:paragraph -->" in result

    def test_wraps_headings_h2(self):
        html = "<h2>Title</h2>"
        result = wp_publisher._to_gutenberg_blocks(html)
        assert "<!-- wp:heading -->" in result
        assert "<!-- /wp:heading -->" in result

    def test_wraps_headings_h3(self):
        html = "<h3>Subtitle</h3>"
        result = wp_publisher._to_gutenberg_blocks(html)
        assert '<!-- wp:heading {"level":3} -->' in result

    def test_wraps_blockquotes(self):
        html = '<blockquote class="wp-block-quote"><p>Quote</p></blockquote>'
        result = wp_publisher._to_gutenberg_blocks(html)
        assert "<!-- wp:quote -->" in result

    def test_wraps_unordered_lists(self):
        html = "<ul><li>Item 1</li><li>Item 2</li></ul>"
        result = wp_publisher._to_gutenberg_blocks(html)
        assert "<!-- wp:list -->" in result

    def test_wraps_ordered_lists(self):
        html = "<ol><li>First</li><li>Second</li></ol>"
        result = wp_publisher._to_gutenberg_blocks(html)
        assert '<!-- wp:list {"ordered":true} -->' in result

    def test_wraps_separators(self):
        html = '<hr class="wp-block-separator has-alpha-channel-opacity"/>'
        result = wp_publisher._to_gutenberg_blocks(html)
        assert "<!-- wp:separator -->" in result

    def test_complex_html(self):
        html = "<h2>Heading</h2><p>Text</p><ul><li>A</li></ul><p>More</p>"
        result = wp_publisher._to_gutenberg_blocks(html)
        assert result.count("<!-- wp:heading -->") == 1
        assert result.count("<!-- wp:paragraph -->") == 2
        assert result.count("<!-- wp:list -->") == 1


class TestStripFirstHeading:
    def test_strips_h1(self):
        html = "<h1>Title</h1><p>Content</p>"
        result = wp_publisher.strip_first_heading(html)
        assert "<h1>" not in result
        assert "<p>Content</p>" in result

    def test_strips_h2(self):
        html = "<h2>Title</h2><p>Content</p>"
        result = wp_publisher.strip_first_heading(html)
        assert "<h2>Title</h2>" not in result

    def test_strips_markdown_heading(self):
        html = "# Markdown Title\n<p>Content</p>"
        result = wp_publisher.strip_first_heading(html)
        assert "# Markdown Title" not in result
        assert "<p>Content</p>" in result

    def test_strips_code_fence_heading(self):
        html = "```html\n<h1>Title</h1><p>Content</p>\n```"
        result = wp_publisher.strip_first_heading(html)
        assert "```" not in result

    def test_no_heading(self):
        html = "<p>Just content</p>"
        result = wp_publisher.strip_first_heading(html)
        assert "<p>Just content</p>" in result


class TestAuthHeaders:
    @patch('wp_publisher.config')
    def test_returns_basic_auth(self, mock_config):
        mock_config.WP_USER = "testuser"
        mock_config.WP_APP_PASSWORD = "testpass"
        headers = wp_publisher._auth_headers()
        assert 'Authorization' in headers
        assert headers['Authorization'].startswith('Basic ')

    @patch('wp_publisher.config')
    def test_encodes_credentials(self, mock_config):
        import base64
        mock_config.WP_USER = "user"
        mock_config.WP_APP_PASSWORD = "pass"
        headers = wp_publisher._auth_headers()
        encoded = headers['Authorization'].split(' ')[1]
        decoded = base64.b64decode(encoded).decode()
        assert decoded == "user:pass"


class TestApiUrl:
    @patch('wp_publisher.config')
    def test_builds_url(self, mock_config):
        mock_config.WP_URL = "https://blog.example.com"
        result = wp_publisher._api_url("posts")
        assert result == "https://blog.example.com/wp-json/wp/v2/posts"

    @patch('wp_publisher.config')
    def test_strips_trailing_slash(self, mock_config):
        mock_config.WP_URL = "https://blog.example.com/"
        result = wp_publisher._api_url("/posts")
        assert result == "https://blog.example.com/wp-json/wp/v2/posts"


class TestIsConfigured:
    @patch('wp_publisher.config')
    def test_true_when_all_set(self, mock_config):
        mock_config.is_wp_configured.return_value = True
        assert wp_publisher.is_configured() is True

    @patch('wp_publisher.config')
    def test_false_when_missing(self, mock_config):
        mock_config.is_wp_configured.return_value = False
        assert wp_publisher.is_configured() is False


class TestCreateDraft:
    @patch('wp_publisher.requests.post')
    @patch('wp_publisher._auth_headers')
    @patch('wp_publisher.config')
    def test_creates_draft_success(self, mock_config, mock_auth, mock_post):
        mock_config.WP_URL = "https://blog.example.com"
        mock_auth.return_value = {'Authorization': 'Basic dGVzdDp0ZXN0'}

        mock_resp = MagicMock()
        mock_resp.status_code = 201
        mock_resp.json.return_value = {
            'id': 42,
            'link': 'https://blog.example.com/?p=42',
            'categories': [9],
        }
        mock_post.return_value = mock_resp

        result, error = wp_publisher.create_draft(
            title="Test Post",
            content="<p>Content</p>",
            category_ids=[9],
            lang='cs',
        )

        assert error is None
        assert result['id'] == 42
        assert 'edit_url' in result
        assert 'view_url' in result

    @patch('wp_publisher.requests.post')
    @patch('wp_publisher._auth_headers')
    @patch('wp_publisher.config')
    def test_handles_api_error(self, mock_config, mock_auth, mock_post):
        mock_config.WP_URL = "https://blog.example.com"
        mock_auth.return_value = {'Authorization': 'Basic dGVzdDp0ZXN0'}

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Internal Server Error"
        mock_post.return_value = mock_resp

        result, error = wp_publisher.create_draft(
            title="Test Post",
            content="<p>Content</p>",
        )

        assert result is None
        assert "500" in error

    @patch('wp_publisher.requests.post')
    @patch('wp_publisher._auth_headers')
    @patch('wp_publisher.config')
    def test_handles_connection_error(self, mock_config, mock_auth, mock_post):
        mock_config.WP_URL = "https://blog.example.com"
        mock_auth.return_value = {'Authorization': 'Basic dGVzdDp0ZXN0'}
        mock_post.side_effect = Exception("Connection refused")

        result, error = wp_publisher.create_draft(
            title="Test Post",
            content="<p>Content</p>",
        )

        assert result is None
        assert error is not None


class TestUploadMedia:
    @patch('wp_publisher.requests.post')
    @patch('wp_publisher.requests.get')
    @patch('wp_publisher._auth_headers')
    @patch('wp_publisher.config')
    def test_upload_success(self, mock_config, mock_auth, mock_get, mock_post):
        mock_config.WP_URL = "https://blog.example.com"
        mock_auth.return_value = {'Authorization': 'Basic dGVzdDp0ZXN0'}

        # Mock image download
        mock_img_resp = MagicMock()
        mock_img_resp.status_code = 200
        mock_img_resp.content = b'\x89PNG\r\n\x1a\n'
        mock_img_resp.headers = {'Content-Type': 'image/png'}
        mock_get.return_value = mock_img_resp

        # Mock WP upload
        mock_upload_resp = MagicMock()
        mock_upload_resp.status_code = 201
        mock_upload_resp.json.return_value = {'id': 123}
        mock_post.return_value = mock_upload_resp

        media_id, error = wp_publisher.upload_media("https://example.com/image.png", title="Test")
        assert media_id == 123
        assert error is None

    @patch('wp_publisher.requests.get')
    def test_handles_download_failure(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 404
        mock_get.return_value = mock_resp

        media_id, error = wp_publisher.upload_media("https://example.com/missing.png")
        assert media_id is None
        assert "404" in error


class TestLinkTranslations:
    @patch('wp_publisher.requests.post')
    @patch('wp_publisher._auth_headers')
    @patch('wp_publisher.config')
    def test_link_success(self, mock_config, mock_auth, mock_post):
        mock_config.WP_URL = "https://blog.example.com"
        mock_auth.return_value = {'Authorization': 'Basic dGVzdDp0ZXN0'}

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_post.return_value = mock_resp

        result, error = wp_publisher.link_translations(42, 43)
        assert result is True
        assert error is None

    @patch('wp_publisher.requests.post')
    @patch('wp_publisher._auth_headers')
    @patch('wp_publisher.config')
    def test_link_failure(self, mock_config, mock_auth, mock_post):
        mock_config.WP_URL = "https://blog.example.com"
        mock_auth.return_value = {'Authorization': 'Basic dGVzdDp0ZXN0'}

        mock_resp = MagicMock()
        mock_resp.status_code = 500
        mock_resp.text = "Error"
        mock_post.return_value = mock_resp

        result, error = wp_publisher.link_translations(42, 43)
        assert result is None
        assert error is not None
