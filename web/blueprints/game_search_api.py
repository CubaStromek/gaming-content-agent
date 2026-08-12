"""Vyhledávání herních obrázků pro ruční výběr v dashboardu: /api/games/search.

Do 2026-08-12 běželo na RAWG.io (`/api/rawg/search`). RAWG po výpadku 8/2026
nenaběhl — každé volání končilo timeoutem, takže vyhledávání v dashboardu
nefungovalo. Nahrazeno IGDB; tvar odpovědi zůstal stejný.
"""

from flask import Blueprint, request

from web.auth import require_auth
from web.helpers import json_response
import igdb_client

game_search_api_bp = Blueprint('game_search_api', __name__)


@game_search_api_bp.route('/api/games/search', methods=['GET'])
@require_auth
def api_game_search():
    query = request.args.get('q', '').strip()
    if not query:
        return json_response({'error': 'Missing query'}), 400
    if not igdb_client.is_configured():
        return json_response({'error': 'IGDB API not configured'}), 400

    try:
        games = igdb_client.search_games(query)
    except Exception:
        return json_response({'error': 'IGDB API request failed'}), 502

    return json_response({'games': games})
