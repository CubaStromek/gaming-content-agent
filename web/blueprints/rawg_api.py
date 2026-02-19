"""RAWG API: /api/rawg/search."""

import requests as http_requests
from flask import Blueprint, request

from web.auth import require_auth
from web.helpers import json_response
import config

rawg_api_bp = Blueprint('rawg_api', __name__)


@rawg_api_bp.route('/api/rawg/search', methods=['GET'])
@require_auth
def api_rawg_search():
    query = request.args.get('q', '').strip()
    if not query:
        return json_response({'error': 'Missing query'}), 400
    if not config.RAWG_API_KEY:
        return json_response({'error': 'RAWG API not configured'}), 400

    resp = http_requests.get(
        'https://api.rawg.io/api/games',
        params={'key': config.RAWG_API_KEY, 'search': query, 'page_size': 6},
        timeout=10,
    )
    if resp.status_code != 200:
        return json_response({'error': f'RAWG API error {resp.status_code}'}), 502

    data = resp.json()
    results = []
    for game in data.get('results', []):
        screenshots = [s['image'] for s in (game.get('short_screenshots') or []) if s.get('image')]
        if not screenshots and game.get('background_image'):
            screenshots = [game['background_image']]
        if not screenshots:
            continue
        results.append({
            'id': game['id'],
            'name': game.get('name', ''),
            'background': game.get('background_image', ''),
            'screenshots': screenshots[:6],
        })

    return json_response({'games': results})
