"""History routes: /history, /history/<run_id>, /topics/<run_id>."""

import os
import re
import json

from flask import Blueprint

from web.helpers import json_response
from article_writer import parse_topics_from_report

history_bp = Blueprint('history', __name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_DIR = os.path.join(BASE_DIR, 'output')


@history_bp.route('/history')
def get_history():
    runs = []

    if os.path.exists(OUTPUT_DIR):
        for folder in sorted(os.listdir(OUTPUT_DIR), reverse=True):
            folder_path = os.path.join(OUTPUT_DIR, folder)
            if os.path.isdir(folder_path) and re.match(r'^[\w\-]+$', folder):
                try:
                    date_str = folder[:8]
                    time_str = folder[9:]
                    formatted_date = f"{date_str[6:8]}.{date_str[4:6]}.{date_str[:4]}"
                    formatted_time = f"{time_str[:2]}:{time_str[2:4]}"
                    article_count = len([f for f in os.listdir(folder_path) if f.startswith('article_') and f.endswith('_cs.html')])
                    runs.append({'id': folder, 'date': formatted_date, 'time': formatted_time, 'articles': article_count})
                except Exception:
                    runs.append({'id': folder, 'date': folder, 'time': '', 'articles': 0})

    return json_response({'runs': runs})


@history_bp.route('/history/<run_id>')
def get_run(run_id):
    if not re.match(r'^[\w\-]+$', run_id):
        return json_response({'error': 'Invalid run_id'}), 400
    run_path = os.path.join(OUTPUT_DIR, run_id)
    result = {'id': run_id, 'report': None, 'articles_count': 0}

    report_path = os.path.join(run_path, 'report.txt')
    no_articles_path = os.path.join(run_path, 'no_new_articles.txt')
    if os.path.exists(report_path):
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                result['report'] = f.read()
        except Exception:
            result['report'] = 'Chyba pri cteni reportu'
    elif os.path.exists(no_articles_path):
        try:
            with open(no_articles_path, 'r', encoding='utf-8') as f:
                result['report'] = f.read()
        except Exception:
            result['report'] = 'Chyba pri cteni info souboru'

    articles_path = os.path.join(run_path, 'articles.json')
    if os.path.exists(articles_path):
        try:
            with open(articles_path, 'r', encoding='utf-8') as f:
                articles = json.load(f)
                result['articles_count'] = len(articles)
        except Exception:
            pass

    return json_response(result)


@history_bp.route('/topics/<run_id>')
def get_topics(run_id):
    if not re.match(r'^[\w\-]+$', run_id):
        return json_response({'error': 'Invalid run_id'}), 400

    report_path = os.path.join(OUTPUT_DIR, run_id, 'report.txt')
    if not os.path.exists(report_path):
        return json_response({'error': 'Report not found'}), 404

    try:
        with open(report_path, 'r', encoding='utf-8') as f:
            report_text = f.read()

        topics = parse_topics_from_report(report_text)

        topics_out = []
        run_dir = os.path.join(OUTPUT_DIR, run_id)
        for i, t in enumerate(topics):
            has_article = os.path.exists(os.path.join(run_dir, f'article_{i}_cs.html'))
            topics_out.append({
                'index': i,
                'topic': t.get('topic', ''),
                'title': t.get('title', ''),
                'angle': t.get('angle', ''),
                'context': t.get('context', ''),
                'hook': t.get('hook', ''),
                'virality': t.get('virality', ''),
                'virality_score': t.get('virality_score', 0),
                'seo_keywords': t.get('seo_keywords', ''),
                'sources': t.get('sources', []),
                'has_article': has_article,
            })

        return json_response({'topics': topics_out, 'run_id': run_id})
    except Exception as e:
        return json_response({'error': str(e)}), 500
