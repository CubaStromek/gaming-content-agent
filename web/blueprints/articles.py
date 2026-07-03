"""Article routes: /write-article, /write-article/output, /articles/<run_id>/<topic_index>."""

import os
import re
import threading
from typing import Optional

from flask import Blueprint, request

from web.auth import require_auth, require_safe_origin
from web.helpers import json_response
import web.helpers as state
from article_writer import parse_topics_from_report, scrape_full_article, write_article

articles_bp = Blueprint('articles', __name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_DIR = os.path.realpath(os.path.join(BASE_DIR, 'output'))


def _safe_run_dir(run_id: str) -> Optional[str]:
    """Vrátí absolutní cestu k run_dir nebo None, pokud by ušla z OUTPUT_DIR."""
    if not re.match(r'^[\w\-]+$', run_id or ''):
        return None
    candidate = os.path.realpath(os.path.join(OUTPUT_DIR, run_id))
    if os.path.commonpath([candidate, OUTPUT_DIR]) != OUTPUT_DIR:
        return None
    return candidate


@articles_bp.route('/write-article', methods=['POST'])
@require_safe_origin
@require_auth
def write_article_endpoint():
    try:
        data = request.get_json(force=True)
    except Exception:
        return json_response({'error': 'Invalid JSON'}), 400
    run_id = data.get('run_id', '')
    try:
        topic_index = int(data.get('topic_index', 0))
    except (TypeError, ValueError):
        return json_response({'error': 'topic_index must be an integer'}), 400
    article_length = data.get('length', 'medium')

    run_dir = _safe_run_dir(run_id)
    if run_dir is None:
        return json_response({'error': 'Invalid run_id'}), 400

    # Check-then-act v JEDNÉ lock sekci — rezervace běhu hned, jinak TOCTOU
    # (dva souběžné requesty by oba prošly checkem a spustily dvě generování).
    with state.article_writer_lock:
        if state.article_writer_state['running']:
            return json_response({'error': 'Already generating'}), 409
        state.article_writer_state = {
            'running': True,
            'result': None,
            'error': None,
        }

    def _release():
        with state.article_writer_lock:
            state.article_writer_state['running'] = False

    report_path = os.path.join(run_dir, 'report.txt')
    if not os.path.exists(report_path):
        _release()
        return json_response({'error': 'Report not found'}), 404

    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            report_text = f.read()

        topics = parse_topics_from_report(report_text)
        if topic_index < 0 or topic_index >= len(topics):
            _release()
            return json_response({'error': 'Invalid topic_index'}), 400

        topic = topics[topic_index]
    except Exception as e:
        _release()
        return json_response({'error': str(e)}), 500

    def generate():
        try:
            source_texts = []
            for url in topic.get('sources', []):
                text = scrape_full_article(url)
                if text:
                    source_texts.append(text)

            result = write_article(topic, source_texts, length=article_length)

            if 'error' in result:
                with state.article_writer_lock:
                    state.article_writer_state['running'] = False
                    state.article_writer_state['error'] = result['error']
                return

            for lang in ['cs', 'en']:
                html = result.get(lang, '')
                if html:
                    filepath = os.path.join(run_dir, f'article_{topic_index}_{lang}.html')
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(html)

            with state.article_writer_lock:
                state.article_writer_state['running'] = False
                state.article_writer_state['result'] = result

        except Exception as e:
            with state.article_writer_lock:
                state.article_writer_state['running'] = False
                state.article_writer_state['error'] = str(e)

    thread = threading.Thread(target=generate)
    thread.start()

    return json_response({'status': 'started'})


@articles_bp.route('/write-article/output')
@require_auth
def write_article_output():
    with state.article_writer_lock:
        s = dict(state.article_writer_state)
    return json_response(s)


@articles_bp.route('/articles/<run_id>/<int:topic_index>')
@require_auth
def get_saved_article(run_id, topic_index):
    run_dir = _safe_run_dir(run_id)
    if run_dir is None:
        return json_response({'error': 'Invalid run_id'}), 400

    result = {}

    for lang in ['cs', 'en']:
        filepath = os.path.join(run_dir, f'article_{topic_index}_{lang}.html')
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                result[lang] = f.read()

    if not result:
        return json_response({'error': 'Article not found'}), 404

    return json_response(result)
