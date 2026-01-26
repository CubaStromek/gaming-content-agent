"""
Správa historie zpracovaných článků
Zajišťuje, že se stejné články neanalyzují opakovaně
"""

import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Set

HISTORY_FILE = "processed_articles.json"
DEFAULT_EXPIRY_DAYS = 30


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
            return json.load(f)
    except (json.JSONDecodeError, Exception) as e:
        print(f"⚠️  Chyba při načítání historie: {e}")
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
            json.dump(history, f, ensure_ascii=False, indent=2)

        return True
    except Exception as e:
        print(f"❌ Chyba při ukládání historie: {e}")
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
        print(f"⏭️  Přeskočeno {skipped_count} již zpracovaných článků")

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
        print(f"🧹 Vyčištěno {removed_count} starých záznamů z historie")

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
    print("🧪 Test article_history modulu\n")

    history = load_history()
    stats = get_stats(history)

    print(f"📊 Celkem zpracováno: {stats['total_processed']} článků")
    print(f"🕐 Poslední aktualizace: {stats['last_updated'] or 'nikdy'}")
