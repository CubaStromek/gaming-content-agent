"""Feed Management API: /api/feeds/*."""

import re

from flask import Blueprint, request

from web.auth import require_auth
from web.helpers import json_response
import feed_manager

feeds_api_bp = Blueprint('feeds_api', __name__)


@feeds_api_bp.route('/api/feeds', methods=['GET'])
def api_get_feeds():
    feeds = feed_manager.load_feeds()
    return json_response({'feeds': feeds})


@feeds_api_bp.route('/api/feeds', methods=['POST'])
@require_auth
def api_add_feed():
    try:
        data = request.get_json(force=True)
    except Exception:
        return json_response({'error': 'Invalid JSON'}), 400
    name = data.get('name', '')
    url = data.get('url', '')
    lang = data.get('lang', 'en')

    feed, error = feed_manager.add_feed(name, url, lang)
    if error:
        return json_response({'error': error}), 400

    return json_response({'feed': feed})


@feeds_api_bp.route('/api/feeds/<feed_id>', methods=['PUT'])
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

    feed, error = feed_manager.update_feed(feed_id, **kwargs)
    if error:
        return json_response({'error': error}), 400

    return json_response({'feed': feed})


@feeds_api_bp.route('/api/feeds/<feed_id>', methods=['DELETE'])
@require_auth
def api_delete_feed(feed_id):
    deleted = feed_manager.delete_feed(feed_id)
    if not deleted:
        return json_response({'error': 'Feed not found'}), 404

    return json_response({'ok': True})


@feeds_api_bp.route('/api/feeds/validate', methods=['POST'])
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

    try:
        result = fp.parse(url)
        if result.bozo and not result.entries:
            return json_response({'valid': False, 'error': 'Not a valid RSS feed'})

        return json_response({
            'valid': True,
            'title': result.feed.get('title', ''),
            'entries': len(result.entries),
        })
    except Exception as e:
        return json_response({'valid': False, 'error': str(e)})
