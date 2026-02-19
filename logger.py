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
    # Obecné API klíče / tokeny v key=value formátu
    (re.compile(r'(?i)(api[_-]?key|password|token|secret|app[_-]?password)\s*[=:]\s*\S+'),
     lambda m: f'{m.group(1)}=***'),
    # Basic Auth header hodnoty
    (re.compile(r'Basic\s+[A-Za-z0-9+/=]{10,}'), 'Basic ***'),
    # Bearer token hodnoty
    (re.compile(r'Bearer\s+[A-Za-z0-9\-_.]{10,}'), 'Bearer ***'),
]


class SanitizingFilter(logging.Filter):
    """Filtr, který maskuje citlivé údaje v log zprávách."""

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
        for pattern, replacement in _SENSITIVE_PATTERNS:
            if callable(replacement):
                text = pattern.sub(replacement, text)
            else:
                text = pattern.sub(replacement, text)
        return text


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

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    handler.setFormatter(formatter)

    # Přidat sanitizační filtr
    handler.addFilter(SanitizingFilter())

    logger.addHandler(handler)
    logger.propagate = False

    return logger
