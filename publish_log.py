"""
Publish Decision Log — zaznamenává publish/skip rozhodnutí do SQLite.
"""

import json
from datetime import datetime
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
    """Vrátí statistiky z publish_log tabulky."""
    conn = get_db()
    try:
        published = conn.execute("SELECT COUNT(*) FROM publish_log WHERE action = 'published'").fetchone()[0]
        skipped = conn.execute("SELECT COUNT(*) FROM publish_log WHERE action = 'skipped'").fetchone()[0]

        row = conn.execute("SELECT AVG(score) FROM publish_log WHERE score > 0").fetchone()
        avg_score = round(row[0], 1) if row[0] else 0

        # Top sources z data_json
        source_counts = {}
        rows = conn.execute("SELECT data_json FROM publish_log WHERE data_json IS NOT NULL").fetchall()
        for row in rows:
            try:
                entry = json.loads(row[0])
            except (json.JSONDecodeError, TypeError):
                continue
            for src in entry.get('sources', []):
                try:
                    domain = urlparse(src).netloc
                    if domain:
                        source_counts[domain] = source_counts.get(domain, 0) + 1
                except Exception:
                    pass

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
