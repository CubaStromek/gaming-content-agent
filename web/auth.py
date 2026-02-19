"""Autentizace pro web dashboard."""

from functools import wraps
from flask import request
import config


def require_auth(f):
    """Vyžaduje Bearer token pokud je DASHBOARD_TOKEN nastaven nebo v production mode."""
    @wraps(f)
    def decorated(*args, **kwargs):
        from web.helpers import json_response
        token = config.DASHBOARD_TOKEN
        if not token:
            if config.PRODUCTION_MODE:
                return json_response({'error': 'DASHBOARD_TOKEN is required in production mode'}), 503
            return f(*args, **kwargs)

        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer ') and auth_header[7:] == token:
            return f(*args, **kwargs)

        if request.args.get('token') == token:
            return f(*args, **kwargs)

        return json_response({'error': 'Unauthorized'}), 401
    return decorated
