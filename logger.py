"""
Centrální logger setup pro Gaming Content Agent
"""

import os
import sys
import logging
from dotenv import load_dotenv

load_dotenv()

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()


def setup_logger(name: str) -> logging.Logger:
    """
    Vrátí konfigurovaný logger s daným názvem.

    Formát: %(asctime)s [%(levelname)s] %(message)s
    Handler: StreamHandler (stdout) — zachovává kompatibilitu se subprocess čtením.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    handler.setFormatter(formatter)

    logger.addHandler(handler)
    logger.propagate = False

    return logger
