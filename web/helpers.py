"""Sdílený stav a utility pro web blueprinty."""

import json
import threading
from flask import make_response


# --- Agent state ---
agent_running = False
agent_thread = None
output_lines = []
output_lock = threading.Lock()
articles_count = 0
sources_count = 0
run_success = False
sent_line_index = 0

# --- Article writer state ---
article_writer_state = {
    'running': False,
    'result': None,
    'error': None,
}
article_writer_lock = threading.Lock()

# --- Podcast writer state ---
podcast_writer_state = {
    'running': False,
    'result': None,
    'error': None,
}
podcast_writer_lock = threading.Lock()


def json_response(data):
    """Vytvoří JSON response s UTF-8."""
    response = make_response(json.dumps(data, ensure_ascii=False))
    response.headers['Content-Type'] = 'application/json; charset=utf-8'
    return response
