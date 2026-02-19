"""
Správa historie zpracovaných článků — SQLite backend.
Zajišťuje, že se stejné články neanalyzují opakovaně.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Set
from database import get_db
from logger import setup_logger

log = setup_logger(__name__)

DEFAULT_EXPIRY_DAYS = 30


def load_history() -> Dict:
    """
    Načte historii zpracovaných článků z SQLite.

    Returns:
        Slovník s historií (kompatibilní s původním formátem)
    """
    conn = get_db()
    try:
        rows = conn.execute("SELECT url, date_added FROM processed_articles").fetchall()
        articles = {row["url"]: row["date_added"] for row in rows}

        last_updated = conn.execute(
            "SELECT value FROM meta WHERE key = 'history_last_updated'"
        ).fetchone()

        return {
            "last_updated": last_updated["value"] if last_updated else None,
            "articles": articles,
        }
    finally:
        conn.close()


def save_history(history: Dict) -> bool:
    """
    Uloží historii zpracovaných článků do SQLite.

    Args:
        history: Slovník s historií

    Returns:
        True pokud úspěšně uloženo
    """
    try:
        now = datetime.now().isoformat()
        history["last_updated"] = now

        conn = get_db()
        try:
            conn.execute("DELETE FROM processed_articles")
            for url, date_added in history.get("articles", {}).items():
                conn.execute(
                    "INSERT OR REPLACE INTO processed_articles (url, date_added) VALUES (?, ?)",
                    (url, date_added),
                )
            conn.execute(
                "INSERT OR REPLACE INTO meta (key, value) VALUES ('history_last_updated', ?)",
                (now,),
            )
            conn.commit()
        finally:
            conn.close()

        return True
    except Exception as e:
        log.error("Chyba při ukládání historie: %s", e)
        return False


def get_processed_urls(history: Dict = None) -> Set[str]:
    """
    Vrátí množinu již zpracovaných URL.

    Args:
        history: Volitelný slovník s historií (pro zpětnou kompatibilitu).
                 Pokud None, načte přímo z DB.

    Returns:
        Set URL adres
    """
    if history is not None:
        return set(history.get("articles", {}).keys())

    conn = get_db()
    try:
        rows = conn.execute("SELECT url FROM processed_articles").fetchall()
        return {row["url"] for row in rows}
    finally:
        conn.close()


def filter_new_articles(articles: List[Dict], history: Dict) -> List[Dict]:
    """
    Odfiltruje již zpracované články.

    Args:
        articles: Seznam všech stažených článků
        history: Historie zpracovaných článků

    Returns:
        Seznam pouze nových článků
    """
    processed_urls = get_processed_urls(history)

    new_articles = []
    skipped_count = 0

    for article in articles:
        url = article.get('link', '')
        if url and url not in processed_urls:
            new_articles.append(article)
        else:
            skipped_count += 1

    if skipped_count > 0:
        log.info("Přeskočeno %d již zpracovaných článků", skipped_count)

    return new_articles


def mark_as_processed(articles: List[Dict], history: Dict) -> Dict:
    """
    Označí články jako zpracované.

    Args:
        articles: Seznam zpracovaných článků
        history: Historie

    Returns:
        Aktualizovaná historie
    """
    today = datetime.now().strftime("%Y-%m-%d")

    for article in articles:
        url = article.get('link', '')
        if url:
            history["articles"][url] = today

    return history


def cleanup_old_entries(history: Dict, expiry_days: int = DEFAULT_EXPIRY_DAYS) -> Dict:
    """
    Odstraní záznamy starší než expiry_days.

    Args:
        history: Historie
        expiry_days: Po kolika dnech smazat

    Returns:
        Vyčištěná historie
    """
    if not history.get("articles"):
        return history

    cutoff_date = datetime.now() - timedelta(days=expiry_days)
    cutoff_str = cutoff_date.strftime("%Y-%m-%d")

    original_count = len(history["articles"])

    history["articles"] = {
        url: date for url, date in history["articles"].items()
        if date >= cutoff_str
    }

    removed_count = original_count - len(history["articles"])
    if removed_count > 0:
        log.info("Vyčištěno %d starých záznamů z historie", removed_count)

    return history


def get_stats(history: Dict = None) -> Dict:
    """
    Vrátí statistiky historie.

    Args:
        history: Volitelná historie (pokud None, načte z DB)

    Returns:
        Slovník se statistikami
    """
    if history is None:
        history = load_history()

    articles = history.get("articles", {})

    return {
        "total_processed": len(articles),
        "last_updated": history.get("last_updated"),
    }
