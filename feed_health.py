"""
Feed Health Monitor - sledování úspěšnosti RSS feedů.
Auto-deaktivace feedů po opakovaných selháních. SQLite backend.
"""

from datetime import datetime
from database import get_db
from logger import setup_logger

log = setup_logger(__name__)

MAX_CONSECUTIVE_FAILURES = 5


def _ensure_entry(conn, feed_name):
    """Zajistí existenci záznamu pro feed."""
    conn.execute(
        "INSERT OR IGNORE INTO feed_health (feed_name) VALUES (?)",
        (feed_name,),
    )


def record_success(feed_name):
    """Zaznamená úspěšné stažení feedu."""
    conn = get_db()
    try:
        _ensure_entry(conn, feed_name)
        conn.execute(
            """UPDATE feed_health
               SET consecutive_failures = 0,
                   total_success = total_success + 1,
                   last_success = ?
               WHERE feed_name = ?""",
            (datetime.now().isoformat(), feed_name),
        )
        conn.commit()
    finally:
        conn.close()


def record_failure(feed_name):
    """
    Zaznamená selhání feedu.

    Returns:
        True pokud feed překročil limit po sobě jdoucích selhání
    """
    conn = get_db()
    try:
        _ensure_entry(conn, feed_name)
        conn.execute(
            """UPDATE feed_health
               SET consecutive_failures = consecutive_failures + 1,
                   total_failure = total_failure + 1,
                   last_failure = ?
               WHERE feed_name = ?""",
            (datetime.now().isoformat(), feed_name),
        )
        conn.commit()

        row = conn.execute(
            "SELECT consecutive_failures FROM feed_health WHERE feed_name = ?",
            (feed_name,),
        ).fetchone()
        return row["consecutive_failures"] >= MAX_CONSECUTIVE_FAILURES
    finally:
        conn.close()


def should_disable(feed_name):
    """Zkontroluje, zda feed překročil limit selhání."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT consecutive_failures FROM feed_health WHERE feed_name = ?",
            (feed_name,),
        ).fetchone()
        if not row:
            return False
        return row["consecutive_failures"] >= MAX_CONSECUTIVE_FAILURES
    finally:
        conn.close()


def get_all_health():
    """Vrátí health status všech feedů jako dict."""
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM feed_health").fetchall()
        result = {}
        for row in rows:
            result[row["feed_name"]] = {
                "consecutive_failures": row["consecutive_failures"],
                "total_success": row["total_success"],
                "total_failure": row["total_failure"],
                "last_success": row["last_success"],
                "last_failure": row["last_failure"],
            }
        return result
    finally:
        conn.close()


def get_feed_health(feed_name):
    """Vrátí health data pro konkrétní feed."""
    conn = get_db()
    try:
        row = conn.execute(
            "SELECT * FROM feed_health WHERE feed_name = ?",
            (feed_name,),
        ).fetchone()
        if not row:
            return {
                "consecutive_failures": 0,
                "total_success": 0,
                "total_failure": 0,
            }
        return {
            "consecutive_failures": row["consecutive_failures"],
            "total_success": row["total_success"],
            "total_failure": row["total_failure"],
            "last_success": row["last_success"],
            "last_failure": row["last_failure"],
        }
    finally:
        conn.close()


def reset_feed(feed_name):
    """Resetuje health záznam pro feed (po ruční reaktivaci)."""
    conn = get_db()
    try:
        conn.execute(
            "UPDATE feed_health SET consecutive_failures = 0 WHERE feed_name = ?",
            (feed_name,),
        )
        conn.commit()
    finally:
        conn.close()
