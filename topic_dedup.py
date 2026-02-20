"""
Deduplikace témat — zabraňuje publikování stejného tématu vícekrát.
Porovnává nová témata s historií v publish_log (posledních 7 dní).
"""

import json
import re
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from database import get_db
from logger import setup_logger

log = setup_logger(__name__)

DEDUP_WINDOW_DAYS = 7
SIMILARITY_THRESHOLD = 0.45


def _normalize(text: str) -> set:
    """Normalizuje text na množinu slov pro porovnání."""
    text = text.lower()
    text = re.sub(r'[^\w\s]', ' ', text)
    words = {w for w in text.split() if len(w) > 2}
    return words


def _jaccard_similarity(set_a: set, set_b: set) -> float:
    """Jaccard similarity dvou množin slov."""
    if not set_a or not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


def get_recent_published_topics(days: int = DEDUP_WINDOW_DAYS) -> List[Dict]:
    """Načte témata publikovaná za posledních N dní z publish_log."""
    cutoff = (datetime.now() - timedelta(days=days)).strftime('%Y-%m-%dT%H:%M:%S')

    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT topic, title, data_json, timestamp FROM publish_log "
            "WHERE action = 'published' AND timestamp >= ? "
            "ORDER BY timestamp DESC",
            (cutoff,),
        ).fetchall()

        results = []
        for row in rows:
            results.append({
                'topic': row['topic'] or '',
                'title': row['title'] or '',
                'timestamp': row['timestamp'],
            })
        return results
    finally:
        conn.close()


def check_topic_duplicate(topic: Dict, recent_topics: List[Dict]) -> Tuple[bool, Optional[Dict]]:
    """
    Zkontroluje, jestli je téma duplicitní vůči nedávno publikovaným.
    Vrací (is_duplicate, matching_entry).
    """
    if not recent_topics:
        return (False, None)

    new_topic_text = topic.get('topic', '')
    new_title = topic.get('title', '')
    new_game = topic.get('game_name', '')

    new_words = _normalize(f"{new_topic_text} {new_title}")

    for existing in recent_topics:
        existing_words = _normalize(f"{existing['topic']} {existing['title']}")
        similarity = _jaccard_similarity(new_words, existing_words)

        # Přímá shoda game_name = silný signál → snížený práh
        if new_game and new_game != 'N/A':
            game_lower = new_game.lower()
            if game_lower in existing['topic'].lower() or game_lower in existing['title'].lower():
                if similarity >= SIMILARITY_THRESHOLD * 0.7:
                    log.info(
                        "DUPLICITA (game match): '%.60s' ~ '%.60s' (sim=%.2f, game='%s')",
                        new_topic_text, existing['topic'], similarity, new_game,
                    )
                    return (True, existing)

        if similarity >= SIMILARITY_THRESHOLD:
            log.info(
                "DUPLICITA: '%.60s' ~ '%.60s' (sim=%.2f)",
                new_topic_text, existing['topic'], similarity,
            )
            return (True, existing)

    return (False, None)


def filter_duplicate_topics(topics: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """Odfiltruje duplicitní témata. Vrací (unique, duplicates)."""
    recent = get_recent_published_topics()
    unique = []
    duplicates = []

    for topic in topics:
        is_dup, match = check_topic_duplicate(topic, recent)
        if is_dup:
            log.warning(
                "Přeskakuji duplicitní téma: '%s' (podobné: '%s' z %s)",
                topic.get('topic', '?'),
                match['topic'] if match else '?',
                match['timestamp'] if match else '?',
            )
            duplicates.append(topic)
        else:
            unique.append(topic)

    return (unique, duplicates)


def format_recent_topics_for_prompt(days: int = 3) -> str:
    """Formátuje seznam nedávných témat pro vložení do Claude promptu."""
    recent = get_recent_published_topics(days=days)
    if not recent:
        return ""

    lines = [f"- {entry['topic']} ({entry['timestamp'][:10]})" for entry in recent]

    return (
        "\n\nNEDÁVNO PUBLIKOVANÁ TÉMATA (neopakuj je!):\n"
        + "\n".join(lines)
        + "\n\nVýše uvedená témata už byla publikována. NESMÍŠ je vybrat znovu, "
        "i kdyby se ve zdrojových článcích objevovaly. Vyber JINÉ téma.\n"
    )
