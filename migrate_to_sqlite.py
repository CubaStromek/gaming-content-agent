#!/usr/bin/env python3
"""
Jednorázový migrační skript: JSON/JSONL → SQLite.
Migruje processed_articles.json, publish_log.jsonl a feed_health.json.
"""

import json
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

from database import get_db, init_db, DB_PATH
from logger import setup_logger

log = setup_logger('migration')


def migrate_processed_articles():
    """Migruje processed_articles.json → processed_articles tabulka."""
    json_path = os.path.join(BASE_DIR, 'processed_articles.json')
    if not os.path.exists(json_path):
        log.info("processed_articles.json neexistuje, přeskakuji")
        return 0

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    articles = data.get('articles', {})
    last_updated = data.get('last_updated')

    conn = get_db()
    try:
        count = 0
        for url, date_added in articles.items():
            conn.execute(
                "INSERT OR IGNORE INTO processed_articles (url, date_added) VALUES (?, ?)",
                (url, date_added),
            )
            count += 1

        if last_updated:
            conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES ('history_last_updated', ?)",
                (last_updated,),
            )

        conn.commit()
        log.info("Migrováno %d zpracovaných článků", count)
        return count
    finally:
        conn.close()


def migrate_publish_log():
    """Migruje publish_log.jsonl → publish_log tabulka."""
    jsonl_path = os.path.join(BASE_DIR, 'publish_log.jsonl')
    if not os.path.exists(jsonl_path):
        log.info("publish_log.jsonl neexistuje, přeskakuji")
        return 0

    conn = get_db()
    try:
        count = 0
        with open(jsonl_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    entry = json.loads(line)
                except json.JSONDecodeError:
                    continue

                timestamp = entry.get('timestamp', '')
                action = entry.get('action', '')
                topic = entry.get('topic', '')
                title = entry.get('title', entry.get('published_title', ''))
                score = entry.get('score')

                conn.execute(
                    "INSERT INTO publish_log (timestamp, action, topic, title, score, data_json) VALUES (?, ?, ?, ?, ?, ?)",
                    (timestamp, action, topic, title, score, json.dumps(entry, ensure_ascii=False)),
                )
                count += 1

        conn.commit()
        log.info("Migrováno %d záznamů publish_log", count)
        return count
    finally:
        conn.close()


def migrate_feed_health():
    """Migruje feed_health.json → feed_health tabulka."""
    json_path = os.path.join(BASE_DIR, 'feed_health.json')
    if not os.path.exists(json_path):
        log.info("feed_health.json neexistuje, přeskakuji")
        return 0

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    conn = get_db()
    try:
        count = 0
        for feed_name, entry in data.items():
            conn.execute(
                """INSERT OR REPLACE INTO feed_health
                   (feed_name, consecutive_failures, total_success, total_failure, last_success, last_failure)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (
                    feed_name,
                    entry.get('consecutive_failures', 0),
                    entry.get('total_success', 0),
                    entry.get('total_failure', 0),
                    entry.get('last_success'),
                    entry.get('last_failure'),
                ),
            )
            count += 1

        conn.commit()
        log.info("Migrováno %d feedů do feed_health", count)
        return count
    finally:
        conn.close()


def main():
    log.info("=" * 60)
    log.info("MIGRACE JSON → SQLite")
    log.info("Databáze: %s", DB_PATH)
    log.info("=" * 60)

    # Inicializuj schéma
    init_db()

    # Migrace
    articles = migrate_processed_articles()
    logs = migrate_publish_log()
    feeds = migrate_feed_health()

    log.info("=" * 60)
    log.info("HOTOVO! Celkem migrováno:")
    log.info("  - %d zpracovaných článků", articles)
    log.info("  - %d záznamů publish logu", logs)
    log.info("  - %d feed health záznamů", feeds)
    log.info("")
    log.info("Původní JSON soubory zůstávají jako záloha.")
    log.info("=" * 60)


if __name__ == '__main__':
    main()
