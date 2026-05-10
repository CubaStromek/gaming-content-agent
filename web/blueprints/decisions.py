"""Decision Transparency API: /api/decisions/*.

Read-only endpointy pro dashboard, který ukazuje, jaká témata pipeline navrhla
a proč byla některá zahozena. Kombinuje data z `publish_log` (rozhodnutí)
a `output/<run_id>/report.txt` (kompletní seznam navržených témat z Claude).
"""

import os
import re
from typing import Optional

from flask import Blueprint, request

from web.auth import require_auth
from web.helpers import json_response

import publish_log
from article_writer import parse_topics_from_report
from logger import setup_logger

log = setup_logger(__name__)

decisions_bp = Blueprint('decisions', __name__)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
OUTPUT_DIR = os.path.realpath(os.path.join(BASE_DIR, 'output'))


def _safe_run_dir(run_id: str) -> Optional[str]:
    if not re.match(r'^[\w\-]+$', run_id or ''):
        return None
    candidate = os.path.realpath(os.path.join(OUTPUT_DIR, run_id))
    if os.path.commonpath([candidate, OUTPUT_DIR]) != OUTPUT_DIR:
        return None
    return candidate


def _parse_int(name: str, default: int, min_val: int = 1, max_val: int = 365) -> int:
    raw = request.args.get(name)
    if raw is None:
        return default
    try:
        v = int(raw)
    except ValueError:
        return default
    return max(min_val, min(max_val, v))


@decisions_bp.route('/api/decisions/runs')
@require_auth
def api_recent_runs():
    """Posledních N běhů (distinct run_id) s agregáty."""
    limit = _parse_int('limit', 20, min_val=1, max_val=200)
    return json_response({'runs': publish_log.query_recent_runs(limit=limit)})


@decisions_bp.route('/api/decisions/run/<run_id>')
@require_auth
def api_decisions_for_run(run_id):
    """Detail jednoho běhu: log entries + parsed topics z report.txt.

    Vrací: {
      run_id, decisions: [...publish_log entries], proposed_topics: [...],
      report_text, articles_count
    }
    """
    run_dir = _safe_run_dir(run_id)
    if run_dir is None:
        return json_response({'error': 'Invalid run_id'}), 400

    decisions = publish_log.query_by_run(run_id)

    proposed_topics = []
    report_text = None
    report_path = os.path.join(run_dir, 'report.txt')
    if os.path.exists(report_path):
        try:
            with open(report_path, 'r', encoding='utf-8') as f:
                report_text = f.read()
            proposed_topics = parse_topics_from_report(report_text)
        except Exception:
            log.exception("Selhalo čtení report.txt pro run %s", run_id)

    # Articles count z articles.json (rss_scraper formát).
    articles_count = 0
    articles_path = os.path.join(run_dir, 'articles.json')
    if os.path.exists(articles_path):
        try:
            import json
            with open(articles_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            if isinstance(data, dict):
                articles_count = data.get('total_articles', len(data.get('articles', [])))
        except Exception:
            log.exception("Selhalo čtení articles.json pro run %s", run_id)

    return json_response({
        'run_id': run_id,
        'decisions': decisions,
        'proposed_topics': proposed_topics,
        'report_text': report_text,
        'articles_count': articles_count,
    })


@decisions_bp.route('/api/decisions/timeline')
@require_auth
def api_timeline():
    """Per-day buckets za posledních N dní."""
    days = _parse_int('days', 14, min_val=1, max_val=90)
    return json_response({
        'days': days,
        'buckets': publish_log.query_timeline(days=days),
    })


@decisions_bp.route('/api/decisions/skip-reasons')
@require_auth
def api_skip_reasons():
    """Top skip reasons + příklady."""
    days = _parse_int('days', 30, min_val=1, max_val=180)
    limit = _parse_int('limit', 5, min_val=1, max_val=20)
    return json_response({
        'days': days,
        'reasons': publish_log.query_skip_reasons(days=days, limit=limit),
    })


@decisions_bp.route('/api/decisions/scoring')
@require_auth
def api_scoring():
    """Scatter datapoints virality × verdikt."""
    days = _parse_int('days', 30, min_val=1, max_val=180)
    return json_response({
        'days': days,
        'points': publish_log.query_scoring(days=days),
    })
