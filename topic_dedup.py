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
ENTITY_MATCH_DAYS = 3          # okno, ve kterém se shoda hry/entity bere přísně
ENTITY_MATCH_THRESHOLD = 0.18  # když game_name přesně sedí a téma je čerstvé, stačí malý překryv slov


def _age_days(timestamp: str) -> float:
    """Stáří záznamu ve dnech. Při chybě parsování vrací 0 (= ber jako čerstvé, raději blokuj)."""
    try:
        return (datetime.now() - datetime.fromisoformat(timestamp)).total_seconds() / 86400
    except Exception:
        return 0.0


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
            game = ''
            try:
                game = (json.loads(row['data_json']) or {}).get('game_name', '') or ''
            except (TypeError, ValueError):
                pass
            results.append({
                'topic': row['topic'] or '',
                'title': row['title'] or '',
                'game_name': game,
                'timestamp': row['timestamp'],
            })
        return results
    finally:
        conn.close()


def check_topic_duplicate(topic: Dict, recent_topics: List[Dict]) -> Tuple[bool, Optional[Dict]]:
    """
    Zkontroluje, jestli je téma duplicitní vůči nedávno publikovaným.
    Vrací (is_duplicate, match_info) kde match_info je dict s klíči
    `topic, title, timestamp, sim_score, match_type` ('game_name' nebo 'jaccard').
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

        # Přímá shoda game_name = silný signál → snížený práh. Pro čerstvá témata
        # (< ENTITY_MATCH_DAYS) ještě přísněji: Claude tutéž novinku rád přeformuluje
        # jinými slovy (sim spadne pod 0.3), takže stačí malý překryv. Po pár dnech
        # se práh vrátí na normál, ať se o populární hře zase může psát.
        if new_game and new_game != 'N/A':
            game_lower = new_game.lower()
            existing_game = (existing.get('game_name') or '').lower()
            if (game_lower in existing['topic'].lower()
                    or game_lower in existing['title'].lower()
                    or (existing_game and game_lower == existing_game)):
                fresh = _age_days(existing.get('timestamp', '')) < ENTITY_MATCH_DAYS
                game_threshold = ENTITY_MATCH_THRESHOLD if fresh else SIMILARITY_THRESHOLD * 0.7
                if similarity >= game_threshold:
                    log.info(
                        "DUPLICITA (game match%s): '%.60s' ~ '%.60s' (sim=%.2f, game='%s')",
                        ", čerstvé" if fresh else "", new_topic_text, existing['topic'], similarity, new_game,
                    )
                    return (True, {
                        'topic': existing['topic'],
                        'title': existing['title'],
                        'timestamp': existing['timestamp'],
                        'sim_score': round(similarity, 3),
                        'match_type': 'game_name',
                        'matched_game': new_game,
                    })

        if similarity >= SIMILARITY_THRESHOLD:
            log.info(
                "DUPLICITA: '%.60s' ~ '%.60s' (sim=%.2f)",
                new_topic_text, existing['topic'], similarity,
            )
            return (True, {
                'topic': existing['topic'],
                'title': existing['title'],
                'timestamp': existing['timestamp'],
                'sim_score': round(similarity, 3),
                'match_type': 'jaccard',
            })

    return (False, None)


def filter_duplicate_topics(topics: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """Odfiltruje duplicitní témata.

    Vrací (unique, duplicates). Každé téma v `duplicates` má pod klíčem
    `_dedup_match` detail shody (sim_score, matched_topic, timestamp,
    match_type) — slouží pro decision-transparency log.
    """
    recent = get_recent_published_topics()
    unique = []
    duplicates = []

    for topic in topics:
        is_dup, match = check_topic_duplicate(topic, recent)
        if is_dup:
            log.warning(
                "Přeskakuji duplicitní téma: '%s' (podobné: '%s' z %s, sim=%.2f)",
                topic.get('topic', '?'),
                match['topic'] if match else '?',
                match['timestamp'] if match else '?',
                match['sim_score'] if match else 0.0,
            )
            enriched = dict(topic)
            enriched['_dedup_match'] = match
            duplicates.append(enriched)
        else:
            unique.append(topic)

    return (unique, duplicates)


def _is_retryable(exc) -> bool:
    """Stejná retry politika jako claude_analyzer: overload/rate-limit/5xx/connection."""
    import anthropic
    if isinstance(exc, (anthropic.APIConnectionError, anthropic.APITimeoutError)):
        return True
    if isinstance(exc, anthropic.APIStatusError):
        return exc.status_code in (429, 500, 502, 503, 529)
    return False


def _llm_is_same_story(client, new_topic: Dict, recent: List[Dict]) -> Tuple[Optional[int], str]:
    """Zeptá se Haiku, jestli `new_topic` popisuje tutéž novinku jako některé z `recent`.

    Vrací (1-based index do `recent` při shodě jinak None, krátké zdůvodnění modelu).
    Při chybě API/parsování vrací (None, ...) — fail-open (lexikální filtr už proběhl,
    raději pustit než blokovat vše).

    Model nejdřív uvažuje a teprve pak hlásí VÝROK na posledním řádku — bare-verdict
    režim (max_tokens=20) svádí Haiku k mělkému „stejné jméno = duplicita" snapu a pak
    si halucinuje zdůvodnění; různé novinky o téže hře (rozpočet vs. změna vydavatele)
    se tím nesprávně slévaly do jedné. Proto: úvaha první, dost tokenů, parsuj poslední
    VÝROK (ne první výskyt slova „DUPLICITA" uvnitř úvahy).
    """
    import config

    listing = "\n".join(
        f"{i + 1}. {r['topic']} — {r['title']}"
        + (f" (hra: {r['game_name']})" if r.get('game_name') else "")
        for i, r in enumerate(recent)
    )
    new_line = (
        f"{new_topic.get('topic', '')} — {new_topic.get('title', '')}"
        + (f" (hra: {new_topic.get('game_name', '')})" if new_topic.get('game_name') else "")
    )

    prompt = (
        "Jsi přísný dedup filtr herního zpravodajského webu. Chytni JEN případy, kdy "
        "NOVÉ téma popisuje TUTÉŽ konkrétní novinku jako něco už publikovaného — typicky "
        "když se entita mezitím přejmenovala (dostala oficiální název) nebo se tatáž "
        "zpráva přeformulovala jinými slovy.\n\n"
        f"NOVÉ TÉMA:\n{new_line}\n\n"
        f"JIŽ PUBLIKOVANÁ TÉMATA:\n{listing}\n\n"
        "Pravidla:\n"
        "- Duplicita = stejná hra A tentýž konkrétní fakt/událost (totéž oznámení, "
        "tentýž odklad na totéž datum, tentýž leak/reveal).\n"
        "- RŮZNÉ novinky o stejné hře NEJSOU duplicita, i když jdou po sobě. "
        "Rozpočet × změna vydavatele × odklad × gameplay reveal × prodeje × recenze "
        "jsou samostatné články.\n"
        "- Pouhá zmínka hry ve velkém souhrnu (roundup, např. State of Play) NENÍ "
        "duplicita vůči dedikovanému článku o té hře, pokud nový článek nepřináší "
        "tentýž jediný fakt jako své jádro.\n"
        "- Když si nejsi jistý → OK (raději pusť než zablokuj).\n\n"
        "Nejdřív 1 větou zdůvodni. Pak na ÚPLNĚ POSLEDNÍM řádku napiš jen "
        "\"VÝROK: DUPLICITA: <číslo>\" nebo \"VÝROK: OK\"."
    )

    try:
        msg = client.messages.create(
            model=config.DEDUP_MODEL,
            max_tokens=250,
            temperature=0,
            messages=[{"role": "user", "content": prompt}],
        )
        text = "".join(b.text for b in msg.content if getattr(b, 'type', '') == 'text').strip()
    except Exception as exc:
        log.warning("LLM dedup pass selhal (%s) — propouštím téma bez sémantické kontroly", exc)
        return (None, "")

    # Poslední VÝROK je závazný; úvaha výše může slovo „DUPLICITA" obsahovat jen jako rozbor.
    matches = list(re.finditer(r'VÝROK:\s*(?:DUPLICITA:?\s*(\d+)|(OK))', text, re.IGNORECASE))
    # Zdůvodnění = poslední smysluplný řádek před VÝROK (přeskoč prázdné a markdown hlavičky).
    head = text[:matches[-1].start()] if matches else text
    meaningful = [
        ln.strip(" *#") for ln in head.splitlines()
        if ln.strip(" *#") and not ln.strip().lower().startswith(('analýza', '**analýza'))
    ]
    reason = meaningful[-1] if meaningful else ""
    if not matches:
        return (None, reason)  # truncated/nesrozumitelné → fail-open
    last = matches[-1]
    if not last.group(1):  # explicit OK
        return (None, reason)
    idx = int(last.group(1))
    if 1 <= idx <= len(recent):
        return (idx, reason)
    return (None, reason)


def llm_filter_duplicate_topics(topics: List[Dict]) -> Tuple[List[Dict], List[Dict]]:
    """Sémantická druhá vrstva dedupu (po lexikálním `filter_duplicate_topics`).

    Chytá případy, kdy se entita mezi běhy přejmenuje (ráno „bezejmenná závodní hra
    Maverick Games", odpoledne „Clutch") — na to lexikální shoda jména ani Jaccard
    nestačí. Vrací (unique, duplicates) se stejným `_dedup_match` formátem.
    """
    if not topics:
        return (topics, [])

    recent = get_recent_published_topics()
    if not recent:
        return (topics, [])

    import anthropic
    import config
    client = anthropic.Anthropic(api_key=config.CLAUDE_API_KEY, max_retries=2)

    unique, duplicates = [], []
    for topic in topics:
        idx, reason = _llm_is_same_story(client, topic, recent)
        if idx is None:
            unique.append(topic)
            continue
        match = recent[idx - 1]
        log.warning(
            "LLM DUPLICITA: '%s' ~ '%s' z %s | důvod: %s",
            topic.get('topic', '?'), match['topic'], match['timestamp'], reason or '(bez úvahy)',
        )
        enriched = dict(topic)
        enriched['_dedup_match'] = {
            'topic': match['topic'],
            'title': match['title'],
            'timestamp': match['timestamp'],
            'sim_score': None,
            'match_type': 'llm',
        }
        duplicates.append(enriched)

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
