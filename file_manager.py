"""
File Manager pro Gaming Content Agent
Spravuje ukládání souborů do strukturovaných složek
"""

import os
from datetime import datetime
from pathlib import Path


def create_run_directory() -> str:
    """
    Vytvoří složku pro aktuální běh agenta

    Returns:
        Cesta ke složce pro tento běh
    """
    # Hlavní výstupní složka
    output_dir = Path("output")
    output_dir.mkdir(exist_ok=True)

    # Složka pro tento běh (timestamp)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    run_dir = output_dir / timestamp
    run_dir.mkdir(exist_ok=True)

    return str(run_dir)


def get_filepath(run_dir: str, filename: str) -> str:
    """
    Vytvoří cestu k souboru v run directory

    Args:
        run_dir: Cesta ke složce běhu
        filename: Název souboru

    Returns:
        Úplná cesta k souboru
    """
    return os.path.join(run_dir, filename)
