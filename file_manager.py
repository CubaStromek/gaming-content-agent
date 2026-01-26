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


def save_report(analysis: str, stats: dict, run_dir: str, articles: list = None) -> str:
    """
    Uloží report do souboru

    Args:
        analysis: Analýza od Claude
        stats: Statistiky
        run_dir: Složka, kam uložit
        articles: Seznam všech článků (pro sekci "ostatní články")

    Returns:
        Cesta k souboru nebo None při chybě
    """
    import re

    filename = os.path.join(run_dir, "report.txt")

    # Extrahuj URL použité v analýze
    url_pattern = r'https?://[^\s<>"\')\]]+[^\s<>"\')\].,]'
    used_urls = set(re.findall(url_pattern, analysis))

    # Získej všechny články a najdi ty, které nebyly použity
    all_articles = articles or []
    remaining_articles = [
        article for article in all_articles
        if article.get('link', '') not in used_urls
    ]

    # Seřaď zbylé články podle zdroje
    remaining_articles.sort(key=lambda x: (x.get('source', ''), x.get('title', '')))

    # Formátování zbylých článků
    remaining_section = ""
    if remaining_articles:
        remaining_section = f"""

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📋 OSTATNÍ ČLÁNKY ({len(remaining_articles)} článků nebylo vybráno do TOP témat)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

"""
        current_source = None
        for article in remaining_articles:
            source = article.get('source', 'Neznámý')
            if source != current_source:
                if current_source is not None:
                    remaining_section += "\n"
                remaining_section += f"▸ {source}\n"
                remaining_section += "─" * 40 + "\n"
                current_source = source

            title = article.get('title', 'Bez názvu')
            link = article.get('link', '')
            remaining_section += f"  • {title}\n"
            remaining_section += f"    {link}\n"

    content = f"""Gaming Content Agent - Report
Datum: {datetime.now().strftime('%d.%m.%Y %H:%M')}

STATISTIKY:
Analyzováno článků: {stats.get('total_articles', 0)}
Zdroje: {', '.join(stats.get('sources', {}).keys())}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🏆 TOP TÉMATA
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{analysis}
{remaining_section}"""

    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"💾 Report uložen do: {filename}")
        return filename
    except Exception as e:
        print(f"❌ Chyba při ukládání reportu: {e}")
        return None
