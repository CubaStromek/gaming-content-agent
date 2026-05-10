"""Feed Management API: /api/feeds/*."""

import ipaddress
import re
import socket
from urllib.parse import urlparse

import requests
from flask import Blueprint, request

from web.auth import require_auth, require_safe_origin
from web.helpers import json_response
import feed_manager


_FEED_MAX_BYTES = 5 * 1024 * 1024  # 5 MB
_FEED_TIMEOUT = 10  # s
_FEED_MAX_REDIRECTS = 3


def _is_safe_feed_url(url: str) -> bool:
    """Stejné SSRF pravidlo jako u WP upload — http(s) only, žádné privátní IP."""
    try:
        parsed = urlparse(url)
    except Exception:
        return False
    if parsed.scheme not in ('http', 'https'):
        return False
    if not parsed.hostname:
        return False
    try:
        infos = socket.getaddrinfo(parsed.hostname, None)
    except socket.gaierror:
        return False
    for info in infos:
        try:
            ip = ipaddress.ip_address(info[4][0])
        except ValueError:
            return False
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_multicast or ip.is_reserved or ip.is_unspecified):
            return False
    return True

feeds_api_bp = Blueprint('feeds_api', __name__)


@feeds_api_bp.route('/api/feeds', methods=['GET'])
@require_auth
def api_get_feeds():
    feeds = feed_manager.load_feeds()
    return json_response({'feeds': feeds})


@feeds_api_bp.route('/api/feeds', methods=['POST'])
@require_safe_origin
@require_auth
def api_add_feed():
    try:
        data = request.get_json(force=True)
    except Exception:
        return json_response({'error': 'Invalid JSON'}), 400
    name = data.get('name', '')
    url = data.get('url', '')
    lang = data.get('lang', 'en')

    if not url or not re.match(r'^https?://', url):
        return json_response({'error': 'Invalid URL'}), 400
    if not _is_safe_feed_url(url):
        return json_response({'error': 'URL must resolve to a public address'}), 400

    feed, error = feed_manager.add_feed(name, url, lang)
    if error:
        return json_response({'error': error}), 400

    return json_response({'feed': feed})


@feeds_api_bp.route('/api/feeds/<feed_id>', methods=['PUT'])
@require_safe_origin
@require_auth
def api_update_feed(feed_id):
    try:
        data = request.get_json(force=True)
    except Exception:
        return json_response({'error': 'Invalid JSON'}), 400
    kwargs = {}
    for key in ('name', 'url', 'lang', 'enabled'):
        if key in data:
            kwargs[key] = data[key]

    # Validuj URL i při PUT — bez toho lze obejít kontrolu změnou existujícího záznamu.
    if 'url' in kwargs:
        new_url = kwargs['url']
        if not new_url or not re.match(r'^https?://', new_url):
            return json_response({'error': 'Invalid URL'}), 400
        if not _is_safe_feed_url(new_url):
            return json_response({'error': 'URL must resolve to a public address'}), 400

    feed, error = feed_manager.update_feed(feed_id, **kwargs)
    if error:
        return json_response({'error': error}), 400

    return json_response({'feed': feed})


@feeds_api_bp.route('/api/feeds/<feed_id>', methods=['DELETE'])
@require_safe_origin
@require_auth
def api_delete_feed(feed_id):
    deleted = feed_manager.delete_feed(feed_id)
    if not deleted:
        return json_response({'error': 'Feed not found'}), 404

    return json_response({'ok': True})


@feeds_api_bp.route('/api/feeds/validate', methods=['POST'])
@require_safe_origin
@require_auth
def api_validate_feed():
    import feedparser as fp
    try:
        data = request.get_json(force=True)
    except Exception:
        return json_response({'error': 'Invalid JSON'}), 400
    url = data.get('url', '')

    if not url or not re.match(r'^https?://', url):
        return json_response({'valid': False, 'error': 'Invalid URL'})

    # Stáhneme sami s timeoutem + size limitem + manuálním follow redirectů,
    # protože `allow_redirects=True` by obešel _is_safe_feed_url (veřejná URL
    # by mohla přesměrovat na 127.0.0.1 nebo cloud metadata endpoint).
    current_url = url
    buf = bytearray()
    try:
        for _ in range(_FEED_MAX_REDIRECTS + 1):
            if not _is_safe_feed_url(current_url):
                return json_response({'valid': False, 'error': 'URL must resolve to a public address'})
            with requests.get(current_url, timeout=_FEED_TIMEOUT, stream=True, allow_redirects=False) as resp:
                if resp.status_code in (301, 302, 303, 307, 308):
                    next_url = resp.headers.get('Location')
                    if not next_url:
                        return json_response({'valid': False, 'error': 'Redirect without Location'})
                    # Relativní redirect → absolutizuj
                    from urllib.parse import urljoin
                    current_url = urljoin(current_url, next_url)
                    continue
                if resp.status_code != 200:
                    return json_response({'valid': False, 'error': f'HTTP {resp.status_code}'})
                for chunk in resp.iter_content(chunk_size=64 * 1024):
                    if chunk:
                        buf.extend(chunk)
                    if len(buf) > _FEED_MAX_BYTES:
                        return json_response({'valid': False, 'error': 'Feed exceeds 5 MB limit'})
                break
        else:
            return json_response({'valid': False, 'error': 'Too many redirects'})
    except requests.RequestException as e:
        return json_response({'valid': False, 'error': str(e)})

    try:
        result = fp.parse(bytes(buf))
        if result.bozo and not result.entries:
            return json_response({'valid': False, 'error': 'Not a valid RSS feed'})

        return json_response({
            'valid': True,
            'title': result.feed.get('title', ''),
            'entries': len(result.entries),
        })
    except Exception as e:
        return json_response({'valid': False, 'error': str(e)})
