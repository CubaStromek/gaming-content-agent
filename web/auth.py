"""Autentizace pro web dashboard."""

import hmac
import os
from functools import wraps
from urllib.parse import urlparse

from flask import request
import config


# Pevný whitelist originů — NIKDY nedoplňovat z Host headeru (DNS rebinding:
# útočník nasměruje vlastní doménu na 127.0.0.1 a Host header by pak "povolil"
# jeho origin). Rozšíření jen přes env DASHBOARD_ALLOWED_ORIGINS.
ALLOWED_ORIGINS = {
    'http://127.0.0.1:5000',
    'http://localhost:5000',
}

MUTATING_METHODS = ('POST', 'PUT', 'PATCH', 'DELETE')


def _allowed_origins():
    """Whitelist originů: pevné hodnoty + volitelné z env (čárkou oddělené)."""
    allowed = set(ALLOWED_ORIGINS)
    extra = os.environ.get('DASHBOARD_ALLOWED_ORIGINS', '')
    for origin in extra.split(','):
        origin = origin.strip().rstrip('/')
        if origin:
            allowed.add(origin)
    return allowed


def _token_matches(provided: str, expected: str) -> bool:
    if not provided or not expected:
        return False
    return hmac.compare_digest(provided, expected)


def require_auth(f):
    """Vyžaduje Bearer token pokud je DASHBOARD_TOKEN nastaven.

    Bez nakonfigurovaného tokenu je auth fail-closed pro mutace:
    POST/PUT/PATCH/DELETE (tedy i spouštěcí endpointy jako /start) vrací 403,
    read-only GET/HEAD projde — lokální dashboard má fungovat pro čtení.

    Token musí být v Authorization: Bearer <token> headeru — query parametr
    `?token=` byl odstraněn (logoval se do access logu / browser history).
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        from web.helpers import json_response
        token = config.DASHBOARD_TOKEN
        if not token:
            if config.PRODUCTION_MODE:
                return json_response({'error': 'DASHBOARD_TOKEN is required in production mode'}), 503
            if request.method in MUTATING_METHODS:
                return json_response({
                    'error': 'DASHBOARD_TOKEN není nastaven — mutating endpointy jsou zakázané. '
                             'Nastav DASHBOARD_TOKEN v .env a restartuj server.'
                }), 403
            return f(*args, **kwargs)

        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer ') and _token_matches(auth_header[7:], token):
            return f(*args, **kwargs)

        return json_response({'error': 'Unauthorized'}), 401
    return decorated


def require_safe_origin(f):
    """Pro mutating endpointy — odmítne POST z cizího Originu.

    Bezpečnostní pojistka proti CSRF, kdyby útočník přiměl prohlížeč poslat
    request s validním tokenem (např. uloženým v service workeru). Bearer
    token sám o sobě není přístupný cizímu webu, takže primární ochranou je
    `require_auth`; tento dekorátor je defense-in-depth.

    Origin se porovnává POUZE proti pevnému whitelistu (+ env
    DASHBOARD_ALLOWED_ORIGINS) — Host header se záměrně nepoužívá, protože mu
    nelze věřit (DNS rebinding).
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        from web.helpers import json_response
        if request.method in ('GET', 'HEAD', 'OPTIONS'):
            return f(*args, **kwargs)

        origin = request.headers.get('Origin') or request.headers.get('Referer') or ''
        if origin:
            parsed = urlparse(origin)
            base = f"{parsed.scheme}://{parsed.netloc}"
            if base not in _allowed_origins():
                return json_response({'error': 'Forbidden origin'}), 403
        return f(*args, **kwargs)
    return decorated
