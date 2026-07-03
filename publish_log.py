"""
Publish Decision Log — zaznamenává publish/skip rozhodnutí do SQLite.
"""

import json
from collections import defaultdict
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from urllib.parse import urlparse
from database import get_db


def log_decision(data: dict):
    """Uloží jedno publish/skip rozhodnutí do SQLite."""
    timestamp = datetime.now().strftime('%Y-%m-%dT%H:%M:%S')
    action = data.get('action', '')
    topic = data.get('topic', '')
    title = data.get('title', data.get('published_title', ''))
    score = data.get('score')

    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO publish_log (timestamp, action, topic, title, score, data_json) VALUES (?, ?, ?, ?, ?, ?)",
            (timestamp, action, topic, title, score, json.dumps(data, ensure_ascii=False)),
        )
        conn.commit()
    finally:
        conn.close()


def get_stats() -> dict:
    """Vrátí statistiky z publish_log tabulky (agregace v SQL, ne v Pythonu)."""
    conn = get_db()
    try:
        counts = conn.execute(
            "SELECT "
            "  SUM(CASE WHEN action = 'published' THEN 1 ELSE 0 END), "
            "  SUM(CASE WHEN action = 'skipped' THEN 1 ELSE 0 END), "
            "  AVG(CASE WHEN score > 0 THEN score END) "
            "FROM publish_log"
        ).fetchone()
        published = counts[0] or 0
        skipped = counts[1] or 0
        avg_score = round(counts[2], 1) if counts[2] else 0

        # Top sources: json_each rozbalí pole $.sources přímo v SQLite —
        # do Pythonu jdou jen agregované URL (ne celá tabulka JSONů).
        # Subquery s json_valid chrání json_each před malformed JSONem.
        try:
            rows = conn.execute(
                "SELECT je.value AS url, COUNT(*) AS cnt "
                "FROM (SELECT data_json FROM publish_log "
                "      WHERE data_json IS NOT NULL AND json_valid(data_json)) p, "
                "     json_each(p.data_json, '$.sources') AS je "
                "WHERE json_type(p.data_json, '$.sources') = 'array' "
                "GROUP BY je.value"
            ).fetchall()
        except Exception:
            rows = []

        source_counts: Dict[str, int] = {}
        for row in rows:
            try:
                domain = urlparse(row['url']).netloc
            except Exception:
                continue
            if domain:
                source_counts[domain] = source_counts.get(domain, 0) + row['cnt']

        top_sources = sorted(source_counts.items(), key=lambda x: x[1], reverse=True)[:10]

        return {
            'total': published + skipped,
            'published': published,
            'skipped': skipped,
            'avg_score': avg_score,
            'top_sources': [{'domain': d, 'count': c} for d, c in top_sources],
        }
    finally:
        conn.close()


def _row_to_dict(row) -> Dict:
    """Převede SQLite row na dict s parsed data_json."""
    try:
        data = json.loads(row['data_json']) if row['data_json'] else {}
    except (json.JSONDecodeError, TypeError):
        data = {}
    return {
        'id': row['id'] if 'id' in row.keys() else None,
        'timestamp': row['timestamp'],
        'action': row['action'],
        'topic': row['topic'],
        'title': row['title'],
        'score': row['score'],
        'data': data,
    }


def query_by_run(run_id: str) -> List[Dict]:
    """Vrátí všechna rozhodnutí pro daný run_id, seřazená podle timestamp."""
    if not run_id:
        return []
    conn = get_db()
    try:
        # data_json je JSON s polem run_id — používáme json_extract pro indexovaný lookup.
        rows = conn.execute(
            "SELECT id, timestamp, action, topic, title, score, data_json "
            "FROM publish_log "
            "WHERE json_extract(data_json, '$.run_id') = ? "
            "ORDER BY timestamp ASC",
            (run_id,),
        ).fetchall()
        return [_row_to_dict(r) for r in rows]
    finally:
        conn.close()


def query_timeline(days: int = 14) -> List[Dict]:
    """Vrátí denní agregát: published / skipped per reason / avg virality."""
    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%S')
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT timestamp, action, score, data_json "
            "FROM publish_log "
            "WHERE timestamp >= ? AND action IN ('published', 'skipped') "
            "ORDER BY timestamp ASC",
            (cutoff,),
        ).fetchall()

        buckets: Dict[str, Dict] = defaultdict(lambda: {
            'date': '',
            'published': 0,
            'skipped': 0,
            'skipped_by_reason': defaultdict(int),
            'virality_sum': 0,
            'virality_count': 0,
        })

        for row in rows:
            day = row['timestamp'][:10]  # YYYY-MM-DD
            bucket = buckets[day]
            bucket['date'] = day
            if row['action'] == 'published':
                bucket['published'] += 1
                if row['score']:
                    bucket['virality_sum'] += row['score']
                    bucket['virality_count'] += 1
            else:
                bucket['skipped'] += 1
                try:
                    data = json.loads(row['data_json']) if row['data_json'] else {}
                except (json.JSONDecodeError, TypeError):
                    data = {}
                reason = data.get('reason') or 'unknown'
                bucket['skipped_by_reason'][reason] += 1

        # Převedeme na seřazený list, defaultdicty na regular dicty.
        result = []
        for day in sorted(buckets.keys()):
            b = buckets[day]
            avg = (b['virality_sum'] / b['virality_count']) if b['virality_count'] else 0
            result.append({
                'date': b['date'],
                'published': b['published'],
                'skipped': b['skipped'],
                'skipped_by_reason': dict(b['skipped_by_reason']),
                'avg_virality': round(avg, 1),
            })
        return result
    finally:
        conn.close()


def query_skip_reasons(days: int = 30, limit: int = 5) -> Dict:
    """Vrátí top skip reasons + ukázky témat/match infa za posledních N dní."""
    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%S')
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT timestamp, topic, score, data_json "
            "FROM publish_log "
            "WHERE timestamp >= ? AND action = 'skipped' "
            "ORDER BY timestamp DESC",
            (cutoff,),
        ).fetchall()

        by_reason: Dict[str, Dict] = defaultdict(lambda: {'count': 0, 'examples': []})
        for row in rows:
            try:
                data = json.loads(row['data_json']) if row['data_json'] else {}
            except (json.JSONDecodeError, TypeError):
                data = {}
            reason = data.get('reason') or 'unknown'
            entry = by_reason[reason]
            entry['count'] += 1
            if len(entry['examples']) < limit:
                entry['examples'].append({
                    'timestamp': row['timestamp'],
                    'topic': row['topic'],
                    'score': row['score'],
                    'dedup_match': data.get('dedup_match'),
                    'failed_sources': data.get('failed_sources'),
                    'error': data.get('error'),
                })

        return {
            reason: {'count': info['count'], 'examples': info['examples']}
            for reason, info in sorted(by_reason.items(), key=lambda kv: kv[1]['count'], reverse=True)
        }
    finally:
        conn.close()


def query_scoring(days: int = 30) -> List[Dict]:
    """Vrátí raw scoring datapoints pro scatter — virality vs verdikt."""
    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%S')
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT timestamp, action, topic, score, data_json "
            "FROM publish_log "
            "WHERE timestamp >= ? AND action IN ('published', 'skipped') "
            "AND score IS NOT NULL AND score > 0 "
            "ORDER BY timestamp ASC",
            (cutoff,),
        ).fetchall()

        result = []
        for row in rows:
            try:
                data = json.loads(row['data_json']) if row['data_json'] else {}
            except (json.JSONDecodeError, TypeError):
                data = {}
            result.append({
                'timestamp': row['timestamp'],
                'topic': row['topic'],
                'virality_score': row['score'],
                'action': row['action'],
                'reason': data.get('reason') if row['action'] == 'skipped' else None,
            })
        return result
    finally:
        conn.close()


def query_recent_runs(limit: int = 20) -> List[Dict]:
    """Vrátí poslední N běhů (distinct run_id z data_json) s počty published/skipped/proposed."""
    conn = get_db()
    try:
        # Najdi distinct run_ids — řazeno dle nejnovějšího timestampu v daném runu.
        rows = conn.execute(
            "SELECT json_extract(data_json, '$.run_id') AS run_id, "
            "MAX(timestamp) AS last_ts, "
            "SUM(CASE WHEN action = 'published' THEN 1 ELSE 0 END) AS published, "
            "SUM(CASE WHEN action = 'skipped' THEN 1 ELSE 0 END) AS skipped, "
            "SUM(CASE WHEN action = 'proposed' THEN 1 ELSE 0 END) AS proposed "
            "FROM publish_log "
            "WHERE json_extract(data_json, '$.run_id') IS NOT NULL "
            "GROUP BY run_id "
            "ORDER BY last_ts DESC "
            "LIMIT ?",
            (limit,),
        ).fetchall()
        return [
            {
                'run_id': r['run_id'],
                'last_timestamp': r['last_ts'],
                'published': r['published'] or 0,
                'skipped': r['skipped'] or 0,
                'proposed': r['proposed'] or 0,
            }
            for r in rows
        ]
    finally:
        conn.close()
