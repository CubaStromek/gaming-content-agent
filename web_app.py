"""Gaming Content Agent — Web server entry point."""

from web import create_app
from logger import setup_logger

log = setup_logger(__name__)

app = create_app()

if __name__ == '__main__':
    log.info("")
    log.info("=" * 70)
    log.info("          GAMING CONTENT AGENT - Web Frontend")
    log.info("=" * 70)
    log.info("")
    log.info("  Server bezi na: http://localhost:5000")
    log.info("")
    log.info("=" * 70)
    app.run(host='127.0.0.1', port=5000)
