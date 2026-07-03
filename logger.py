"""
Centrální logger setup pro Gaming Content Agent.
Obsahuje sanitizaci citlivých údajů v logových zprávách (Fáze 1).
"""

import os
import re
import sys
import logging
from dotenv import load_dotenv

load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# Vzory citlivých údajů k maskování
_SENSITIVE_PATTERNS = [
    # Anthropic API klíče
    (re.compile(r'sk-ant-[a-zA-Z0-9\-_]{10,}'), 'sk-ant-***'),
    # Telegram bot tokeny (např. v URL api.telegram.org/bot<token>/...)
    (re.compile(r'bot\d+:[A-Za-z0-9_-]{20,}'), 'bot***'),
    # Obecné API klíče / tokeny v key=value formátu
    (re.compile(r'(?i)(api[_-]?key|password|token|secret|app[_-]?password)\s*[=:]\s*\S+'),
     lambda m: f'{m.group(1)}=***'),
    # Basic Auth header hodnoty
    (re.compile(r'Basic\s+[A-Za-z0-9+/=]{10,}'), 'Basic ***'),
    # Bearer token hodnoty
    (re.compile(r'Bearer\s+[A-Za-z0-9\-_.]{10,}'), 'Bearer ***'),
]


def _sanitize(text):
    """Zamaskuje citlivé údaje v textu podle _SENSITIVE_PATTERNS."""
    for pattern, replacement in _SENSITIVE_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


class SanitizingFormatter(logging.Formatter):
    """Formatter, který maskuje citlivé údaje ve VÝSLEDNÉM formátovaném stringu.

    Na rozdíl od filtru na record.msg/args tak pokryje i tracebacky
    z exc_info (URL s tokeny ve stack trace apod.).
    """

    def format(self, record):
        return _sanitize(super().format(record))


class SanitizingFilter(logging.Filter):
    """Filtr maskující msg/args (ponecháno pro zpětnou kompatibilitu).

    Nepokrývá text výjimek z exc_info — hlavní sanitizaci dělá
    SanitizingFormatter nad výsledným stringem.
    """

    def filter(self, record):
        if isinstance(record.msg, str):
            record.msg = self._sanitize(record.msg)
        if record.args:
            if isinstance(record.args, dict):
                record.args = {
                    k: self._sanitize(v) if isinstance(v, str) else v
                    for k, v in record.args.items()
                }
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    self._sanitize(a) if isinstance(a, str) else a
                    for a in record.args
                )
        return True

    @staticmethod
    def _sanitize(text):
        return _sanitize(text)


def setup_logger(name: str) -> logging.Logger:
    """
    Vrátí konfigurovaný logger s daným názvem.

    Formát: %(asctime)s [%(levelname)s] %(message)s
    Handler: StreamHandler (stdout) — zachovává kompatibilitu se subprocess čtením.
    Sanitizace: Automatické maskování API klíčů, hesel a tokenů.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    # Sanitizace přes Formatter — pokrývá i tracebacky z exc_info,
    # které by filtr na msg/args minul.
    formatter = SanitizingFormatter("%(asctime)s [%(levelname)s] %(message)s")
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    logger.propagate = False

    return logger
