"""Telegram alerty pro autopublish pipeline.

Znovupoužívá bota @Cubajs_bot (TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID v .env).
Účel: upozornit na telefon, když se běh zastaví dřív, než cokoliv vygeneruje
(typicky nedostupný WP = spadlá VPN / Webglobe blacklist). Tím se neplatí za
nepublikovatelné články a uživatel ví, že má zapnout VPN.

Best-effort: alert nikdy nesmí shodit pipeline — všechny chyby se jen zalogují.
"""
import logging

import requests

import config

log = logging.getLogger("gaming-agent")


def send_alert(text: str) -> bool:
    """Pošle Telegram zprávu. Vrací True při úspěchu, jinak False (a zaloguje).

    Nikdy nevyhazuje výjimku — alert je doplňková funkce, ne kritická cesta.
    """
    if not config.TELEGRAM_BOT_TOKEN or not config.TELEGRAM_CHAT_ID:
        log.warning("Telegram alert přeskočen — chybí TELEGRAM_BOT_TOKEN/CHAT_ID v .env")
        return False
    try:
        resp = requests.post(
            f"https://api.telegram.org/bot{config.TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": config.TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": True,
            },
            timeout=10,
        )
        if resp.status_code == 200:
            log.info("📲 Telegram alert odeslán")
            return True
        log.warning("Telegram alert selhal: HTTP %s %s", resp.status_code, resp.text[:200])
        return False
    except Exception:
        log.exception("Telegram alert selhal (síťová chyba)")
        return False
