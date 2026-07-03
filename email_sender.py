"""
Email sender
Posílá denní reporty emailem
"""

import html
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import config
from logger import setup_logger

log = setup_logger(__name__)

SMTP_TIMEOUT = 30  # sekundy


def _build_html_body(analysis: str, stats: dict) -> str:
    """Sestaví HTML tělo emailu s dark theme stylem."""
    sources = html.escape(', '.join(stats.get('sources', {}).keys()))
    total = stats.get('total_articles', 0)
    date_str = datetime.now().strftime('%d.%m.%Y v %H:%M')

    # Escapuj HTML (analýza může obsahovat <, >, & z titulků her) a až pak <br>
    analysis_html = html.escape(analysis).replace('\n', '<br>\n')

    return f"""<!DOCTYPE html>
<html>
<head><meta charset="UTF-8"></head>
<body style="margin:0;padding:0;background:#101c22;font-family:Arial,Helvetica,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#101c22;padding:20px 0;">
    <tr><td align="center">
      <table width="600" cellpadding="0" cellspacing="0" style="background:#1e1e1e;border-radius:8px;overflow:hidden;">
        <!-- Header -->
        <tr><td style="background:#181818;padding:20px 30px;border-bottom:1px solid rgba(255,255,255,0.1);">
          <h1 style="margin:0;color:#13a4ec;font-size:18px;">🎮 Gaming Content Agent</h1>
        </td></tr>
        <!-- Stats -->
        <tr><td style="padding:20px 30px;border-bottom:1px solid rgba(255,255,255,0.05);">
          <p style="color:#9ca3af;font-size:13px;margin:0 0 8px;">
            📊 Analyzováno článků: <strong style="color:#fff;">{total}</strong><br>
            🌐 Zdroje: <strong style="color:#fff;">{sources}</strong>
          </p>
        </td></tr>
        <!-- Analysis -->
        <tr><td style="padding:20px 30px;color:#d1d5db;font-size:14px;line-height:1.7;">
          {analysis_html}
        </td></tr>
        <!-- Footer -->
        <tr><td style="background:#181818;padding:15px 30px;border-top:1px solid rgba(255,255,255,0.05);">
          <p style="color:#6b7280;font-size:11px;margin:0;">
            🤖 Automaticky vygenerováno Gaming Content Agent · ⏰ {date_str}
          </p>
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def send_email_report(analysis: str, stats: dict) -> bool:
    """
    Pošle email report s analýzou článků

    Args:
        analysis: Analýza od Claude
        stats: Statistiky o stažených článcích

    Returns:
        True pokud email byl úspěšně odeslán
    """
    log.info("📧 Připravuji email report...")

    # Kontrola nastavení
    if not config.EMAIL_TO:
        log.warning("⚠️  EMAIL_TO není nastaven — email se neodešle, report bude jen v konzoli/souboru")
        return False

    # Vytvoření emailu
    subject = f"🎮 Gaming Content Ideas - {datetime.now().strftime('%d.%m.%Y')}"

    # Sestavení těla emailu (plain text fallback)
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
        log.info("ℹ️  SMTP není nakonfigurován - zobrazuji report v konzoli:")
        log.info("=" * 70)
        log.info(subject)
        log.info("=" * 70)
        log.info(body)
        log.info("=" * 70)
        return False

    try:
        # Vytvoření MIME zprávy (multipart/alternative: plain + HTML)
        msg = MIMEMultipart('alternative')
        msg['From'] = config.EMAIL_FROM
        msg['To'] = config.EMAIL_TO
        msg['Subject'] = subject

        # Plain text fallback
        msg.attach(MIMEText(body, 'plain', 'utf-8'))

        # HTML verze
        html_body = _build_html_body(analysis, stats)
        msg.attach(MIMEText(html_body, 'html', 'utf-8'))

        # Připojení k SMTP serveru — context manager zajistí quit() i při chybě
        log.info("   Připojuji se k %s:%d...", config.SMTP_HOST, config.SMTP_PORT)
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=SMTP_TIMEOUT) as server:
            server.starttls(context=ssl.create_default_context())

            # Přihlášení
            log.info("   Přihlašuji se jako %s...", config.SMTP_USER)
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)

            # Odeslání
            log.info("   Odesílám email na %s...", config.EMAIL_TO)
            server.send_message(msg)

        log.info("✅ Email úspěšně odeslán!")
        return True

    except Exception as e:
        log.error("❌ Chyba při odesílání emailu: %s", e)
        log.info("ℹ️  Report zobrazuji v konzoli místo toho:")
        log.info("=" * 70)
        log.info(subject)
        log.info("=" * 70)
        log.info(body)
        log.info("=" * 70)
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
        log.info("💾 Report uložen do: %s", filename)
        return filename
    except Exception as e:
        log.error("❌ Chyba při ukládání do souboru: %s", e)
        return None


if __name__ == "__main__":
    # Test email senderu
    log.info("🧪 Test Email Senderu")

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
