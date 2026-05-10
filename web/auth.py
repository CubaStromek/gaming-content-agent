"""Autentizace pro web dashboard."""

import hmac
from functools import wraps
from urllib.parse import urlparse

from flask import request
import config


ALLOWED_ORIGINS = {
    'http://127.0.0.1:5000',
    'http://localhost:5000',
}


def _token_matches(provided: str, expected: str) -> bool:
    if not provided or not expected:
        return False
    return hmac.compare_digest(provided, expected)


def require_auth(f):
    """Vyžaduje Bearer token pokud je DASHBOARD_TOKEN nastaven nebo v production mode.

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
            allowed = set(ALLOWED_ORIGINS)
            host_header = request.headers.get('Host', '')
            if host_header:
                allowed.add(f"http://{host_header}")
                allowed.add(f"https://{host_header}")
            if base not in allowed:
                return json_response({'error': 'Forbidden origin'}), 403
        return f(*args, **kwargs)
    return decorated
