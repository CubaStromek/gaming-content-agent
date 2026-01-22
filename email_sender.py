"""
Email sender
Posílá denní reporty emailem
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import config

def send_email_report(analysis: str, stats: dict) -> bool:
    """
    Pošle email report s analýzou článků

    Args:
        analysis: Analýza od Claude
        stats: Statistiky o stažených článcích

    Returns:
        True pokud email byl úspěšně odeslán
    """
    print("\n📧 Připravuji email report...")

    # Kontrola nastavení
    if not config.EMAIL_TO:
        print("⚠️  EMAIL_TO není nastaven - report se neuloží jen do konzole")
        return False

    # Vytvoření emailu
    subject = f"🎮 Gaming Content Ideas - {datetime.now().strftime('%d.%m.%Y')}"

    # Sestavení těla emailu
    body = f"""Ahoj!

Tvůj Gaming Content Agent našel dnes zajímavá témata pro článek.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 STATISTIKY:
• Analyzováno článků: {stats.get('total_articles', 0)}
• Zdroje: {', '.join(stats.get('sources', {}).keys())}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{analysis}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🤖 Automaticky vygenerováno Gaming Content Agent
⏰ {datetime.now().strftime('%d.%m.%Y v %H:%M')}

---
Tento email byl odeslán z tvého Content Discovery Agenta.
Pro změnu nastavení uprav soubor .env
"""

    # Pokud není SMTP nakonfigurován, jen vypiš do konzole
    if not config.SMTP_USER or not config.SMTP_PASSWORD:
        print("ℹ️  SMTP není nakonfigurován - zobrazuji report v konzoli:\n")
        print("="*70)
        print(subject)
        print("="*70)
        print(body)
        print("="*70)
        return False

    try:
        # Vytvoření MIME zprávy
        msg = MIMEMultipart()
        msg['From'] = config.EMAIL_FROM
        msg['To'] = config.EMAIL_TO
        msg['Subject'] = subject

        # Přidání těla emailu
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        # Připojení k SMTP serveru
        print(f"   Připojuji se k {config.SMTP_HOST}:{config.SMTP_PORT}...")
        server = smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT)
        server.starttls()

        # Přihlášení
        print(f"   Přihlašuji se jako {config.SMTP_USER}...")
        server.login(config.SMTP_USER, config.SMTP_PASSWORD)

        # Odeslání
        print(f"   Odesílám email na {config.EMAIL_TO}...")
        server.send_message(msg)
        server.quit()

        print("✅ Email úspěšně odeslán!")
        return True

    except Exception as e:
        print(f"❌ Chyba při odesílání emailu: {e}")
        print("\nℹ️  Report zobrazuji v konzoli místo toho:\n")
        print("="*70)
        print(subject)
        print("="*70)
        print(body)
        print("="*70)
        return False


def save_report_to_file(analysis: str, stats: dict, run_dir: str = ".") -> str:
    """
    Uloží report do souboru (záložní varianta)

    Args:
        analysis: Analýza od Claude
        stats: Statistiky
        run_dir: Složka, kam uložit (výchozí aktuální složka)

    Returns:
        Cesta k souboru
    """
    import os
    filename = os.path.join(run_dir, "report.txt")

    content = f"""Gaming Content Agent - Report
Datum: {datetime.now().strftime('%d.%m.%Y %H:%M')}

STATISTIKY:
Analyzováno článků: {stats.get('total_articles', 0)}
Zdroje: {', '.join(stats.get('sources', {}).keys())}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

{analysis}
"""

    try:
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"💾 Report uložen do: {filename}")
        return filename
    except Exception as e:
        print(f"❌ Chyba při ukládání do souboru: {e}")
        return None


if __name__ == "__main__":
    # Test email senderu
    print("🧪 Test Email Senderu\n")

    test_analysis = """🎮 TÉMA 1: GTA 6 Nový Trailer
📰 NAVRŽENÝ TITULEK: GTA 6: Rozbor druhého traileru - co nás čeká?
🎯 ÚHEL POHLEDU: Detailní analýza traileru
🔥 VIRALITA: 95/100
💡 PROČ TEĎKA: Trailer právě vyšel, obrovský zájem
🔗 ZDROJE: IGN, GameSpot
🏷️ SEO: GTA 6, trailer, analýza, Rockstar
"""

    test_stats = {
        'total_articles': 50,
        'sources': {'IGN': 10, 'GameSpot': 10, 'PC Gamer': 10}
    }

    send_email_report(test_analysis, test_stats)
