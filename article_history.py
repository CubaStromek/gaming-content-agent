"""
Správa historie zpracovaných článků
Zajišťuje, že se stejné články neanalyzují opakovaně
"""

import json
import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Set
from logger import setup_logger

log = setup_logger(__name__)

HISTORY_FILE = "processed_articles.json"
DEFAULT_EXPIRY_DAYS = 30

# File locking — fcntl na Linuxu, msvcrt na Windows
if sys.platform == 'win32':
    import msvcrt

    def _lock_file(f):
        msvcrt.locking(f.fileno(), msvcrt.LK_NBLCK, 1)

    def _unlock_file(f):
        try:
            f.seek(0)
            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
        except Exception:
            pass
else:
    import fcntl

    def _lock_file(f):
        fcntl.flock(f.fileno(), fcntl.LOCK_EX)

    def _unlock_file(f):
        fcntl.flock(f.fileno(), fcntl.LOCK_UN)


def load_history() -> Dict:
    """
    Načte historii zpracovaných článků

    Returns:
        Slovník s historií nebo prázdná struktura
    """
    if not os.path.exists(HISTORY_FILE):
        return {
            "last_updated": None,
            "articles": {}
        }

    try:
        with open(HISTORY_FILE, 'r', encoding='utf-8') as f:
            _lock_file(f)
            try:
                data = json.load(f)
            finally:
                _unlock_file(f)
            return data
    except (json.JSONDecodeError, Exception) as e:
        log.warning("⚠️  Chyba při načítání historie: %s", e)
        return {
            "last_updated": None,
            "articles": {}
        }


def save_history(history: Dict) -> bool:
    """
    Uloží historii zpracovaných článků

    Args:
        history: Slovník s historií

    Returns:
        True pokud úspěšně uloženo
    """
    try:
        history["last_updated"] = datetime.now().isoformat()

        with open(HISTORY_FILE, 'w', encoding='utf-8') as f:
            _lock_file(f)
            try:
                json.dump(history, f, ensure_ascii=False, indent=2)
            finally:
                _unlock_file(f)

        return True
    except Exception as e:
        log.error("❌ Chyba při ukládání historie: %s", e)
        return False


def get_processed_urls(history: Dict) -> Set[str]:
    """
    Vrátí množinu již zpracovaných URL

    Args:
        history: Slovník s historií

    Returns:
        Set URL adres
    """
    return set(history.get("articles", {}).keys())


def filter_new_articles(articles: List[Dict], history: Dict) -> List[Dict]:
    """
    Odfiltruje již zpracované články

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
        log.info("⏭️  Přeskočeno %d již zpracovaných článků", skipped_count)

    return new_articles


def mark_as_processed(articles: List[Dict], history: Dict) -> Dict:
    """
    Označí články jako zpracované

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
    Odstraní záznamy starší než expiry_days

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
        log.info("🧹 Vyčištěno %d starých záznamů z historie", removed_count)

    return history


def get_stats(history: Dict) -> Dict:
    """
    Vrátí statistiky historie

    Args:
        history: Historie

    Returns:
        Slovník se statistikami
    """
    articles = history.get("articles", {})

    return {
        "total_processed": len(articles),
        "last_updated": history.get("last_updated"),
    }


if __name__ == "__main__":
    # Test modulu
    log.info("🧪 Test article_history modulu")

    history = load_history()
    stats = get_stats(history)

    log.info("📊 Celkem zpracováno: %d článků", stats['total_processed'])
    log.info("🕐 Poslední aktualizace: %s", stats['last_updated'] or 'nikdy')
