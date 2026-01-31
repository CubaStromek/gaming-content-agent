"""
Publish Decision Log — zaznamenává publish/skip rozhodnutí do JSONL.
"""

import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, 'publish_log.jsonl')


def log_decision(data: dict):
    """Append one JSON line to publish_log.jsonl."""
    entry = {
        'timestamp': datetime.now().strftime('%Y-%m-%dT%H:%M:%S'),
    }
    entry.update(data)

    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


def get_stats() -> dict:
    """Return basic stats from publish_log.jsonl."""
    if not os.path.exists(LOG_FILE):
        return {'total': 0, 'published': 0, 'skipped': 0, 'avg_score': 0, 'top_sources': []}

    published = 0
    skipped = 0
    scores = []
    source_counts = {}

    with open(LOG_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue

            action = entry.get('action', '')
            if action == 'published':
                published += 1
            elif action == 'skipped':
                skipped += 1

            score = entry.get('score')
            if score is not None and score > 0:
                scores.append(score)

            for src in entry.get('sources', []):
                # Extract domain from URL
                try:
                    from urllib.parse import urlparse
                    domain = urlparse(src).netloc
                    if domain:
                        source_counts[domain] = source_counts.get(domain, 0) + 1
                except Exception:
                    pass

    total = published + skipped
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0

    # Top 10 sources by frequency
    top_sources = sorted(source_counts.items(), key=lambda x: x[1], reverse=True)[:10]

    return {
        'total': total,
        'published': published,
        'skipped': skipped,
        'avg_score': avg_score,
        'top_sources': [{'domain': d, 'count': c} for d, c in top_sources],
    }
