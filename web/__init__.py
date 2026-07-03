"""
Gaming Content Agent — Web application factory.
"""

import os
from flask import Flask


def create_app():
    """Vytvoří a nakonfiguruje Flask aplikaci."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    app = Flask(
        __name__,
        template_folder=os.path.join(os.path.dirname(__file__), 'templates'),
        static_folder=os.path.join(os.path.dirname(__file__), 'static'),
    )

    # Register blueprints
    from web.blueprints.core import core_bp
    from web.blueprints.history import history_bp
    from web.blueprints.articles import articles_bp
    from web.blueprints.podcasts import podcasts_bp
    from web.blueprints.feeds_api import feeds_api_bp
    from web.blueprints.wp_api import wp_api_bp
    from web.blueprints.rawg_api import rawg_api_bp
    from web.blueprints.decisions import decisions_bp

    app.register_blueprint(core_bp)
    app.register_blueprint(history_bp)
    app.register_blueprint(articles_bp)
    app.register_blueprint(podcasts_bp)
    app.register_blueprint(feeds_api_bp)
    app.register_blueprint(wp_api_bp)
    app.register_blueprint(rawg_api_bp)
    app.register_blueprint(decisions_bp)

    return app
