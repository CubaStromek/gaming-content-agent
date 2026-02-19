"""
SQLite databáze pro Gaming Content Agent.
WAL mode, connection factory, schema init.
"""

import os
import sqlite3
from logger import setup_logger

log = setup_logger(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, 'data', 'gamefo.db')

SCHEMA = """
CREATE TABLE IF NOT EXISTS processed_articles (
    url TEXT UNIQUE NOT NULL,
    date_added TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS publish_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    action TEXT,
    topic TEXT,
    title TEXT,
    score REAL,
    data_json TEXT
);

CREATE TABLE IF NOT EXISTS feed_health (
    feed_name TEXT UNIQUE NOT NULL,
    consecutive_failures INTEGER DEFAULT 0,
    total_success INTEGER DEFAULT 0,
    total_failure INTEGER DEFAULT 0,
    last_success TEXT,
    last_failure TEXT
);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT
);
"""


def get_db(path=None):
    """Vrátí SQLite connection s WAL mode a foreign keys."""
    db_path = path or DB_PATH
    os.makedirs(os.path.dirname(db_path), exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(path=None):
    """Inicializuje schéma databáze."""
    conn = get_db(path)
    conn.executescript(SCHEMA)
    conn.commit()
    conn.close()
    log.info("SQLite databáze inicializována: %s", path or DB_PATH)


# Auto-init při prvním importu
if not os.path.exists(DB_PATH):
    init_db()
