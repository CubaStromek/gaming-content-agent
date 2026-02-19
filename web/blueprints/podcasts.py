"""Podcast routes: /generate-podcast, /generate-podcast/output, /podcast/<run_id>/<topic_index>/<lang>."""

import os
import re
import threading

from flask import Blueprint, request

from web.auth import require_auth
from web.helpers import json_response
import web.helpers as state
from article_writer import generate_podcast_script

podcasts_bp = Blueprint('podcasts', __name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')


@podcasts_bp.route('/generate-podcast', methods=['POST'])
@require_auth
def generate_podcast_endpoint():
    try:
        data = request.get_json(force=True)
    except Exception:
        return json_response({'error': 'Invalid JSON'}), 400
    run_id = data.get('run_id', '')
    topic_index = data.get('topic_index', 0)
    lang = data.get('lang', 'cs')

    if not re.match(r'^[\w\-]+$', run_id):
        return json_response({'error': 'Invalid run_id'}), 400

    if lang not in ['cs', 'en']:
        return json_response({'error': 'Invalid lang'}), 400

    with state.podcast_writer_lock:
        if state.podcast_writer_state['running']:
            return json_response({'error': 'Already generating podcast'}), 409

    run_dir = os.path.join(OUTPUT_DIR, run_id)
    article_path = os.path.join(run_dir, f'article_{topic_index}_{lang}.html')

    if not os.path.exists(article_path):
        return json_response({'error': 'Article not found. Generate article first.'}), 404

    try:
        with open(article_path, 'r', encoding='utf-8') as f:
            article_html = f.read()
    except Exception as e:
        return json_response({'error': str(e)}), 500

    with state.podcast_writer_lock:
        state.podcast_writer_state = {
            'running': True,
            'result': None,
            'error': None,
        }

    def generate():
        try:
            result = generate_podcast_script(article_html, lang)

            if 'error' in result:
                with state.podcast_writer_lock:
                    state.podcast_writer_state['running'] = False
                    state.podcast_writer_state['error'] = result['error']
                return

            script_path = os.path.join(run_dir, f'podcast_{topic_index}_{lang}.txt')
            with open(script_path, 'w', encoding='utf-8') as f:
                f.write(result['script'])

            with state.podcast_writer_lock:
                state.podcast_writer_state['running'] = False
                state.podcast_writer_state['result'] = result

        except Exception as e:
            with state.podcast_writer_lock:
                state.podcast_writer_state['running'] = False
                state.podcast_writer_state['error'] = str(e)

    thread = threading.Thread(target=generate)
    thread.start()

    return json_response({'status': 'started'})


@podcasts_bp.route('/generate-podcast/output')
def generate_podcast_output():
    with state.podcast_writer_lock:
        s = dict(state.podcast_writer_state)
    return json_response(s)


@podcasts_bp.route('/podcast/<run_id>/<int:topic_index>/<lang>')
def get_saved_podcast(run_id, topic_index, lang):
    if not re.match(r'^[\w\-]+$', run_id):
        return json_response({'error': 'Invalid run_id'}), 400

    if lang not in ['cs', 'en']:
        return json_response({'error': 'Invalid lang'}), 400

    script_path = os.path.join(OUTPUT_DIR, run_id, f'podcast_{topic_index}_{lang}.txt')

    if not os.path.exists(script_path):
        return json_response({'error': 'Podcast script not found'}), 404

    with open(script_path, 'r', encoding='utf-8') as f:
        script = f.read()

    return json_response({'script': script})
