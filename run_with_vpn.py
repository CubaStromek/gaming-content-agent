#!/usr/bin/env python3
"""Wrapper: zapne NordVPN jen na dobu běhu autopublishe, pak ji zase vypne.

Řeší konflikt dvou potřeb na jednom stroji:
  - gamefo.cz (Webglobe) blokuje sdílenou Starlink CGNAT IP → publish potřebuje VPN,
  - VPN ale zpomaluje net pro běžný provoz.
Proto: VPN je OFF napořád (rychlý net) a tento wrapper ji zapne jen na ~5–13 min
běhu a po doběhnutí vypne. Spolehlivost requestů přes VPN řeší streaming ve writeru.

Ovládání NordVPN na macOS (nemá CLI):
  - connect:   `open -a NordVPN` + `open nordvpn://connect` (URL scheme), poll na utun
  - disconnect: graceful quit přes Apple Event (`osascript … quit`). POZOR: z launchd
    může narazit na Automation/TCC oprávnění — proto fail-safe Telegram alert.
  - killall NEPOUŽÍVAT: zabije GUI, ale network extension nechá tunel osiřelý nahoře.

Respektuje ruční session: pokud VPN běžela už PŘED námi, po běhu ji nevypínáme.

Použití:
  python run_with_vpn.py            # ostrý běh (connect → agent → disconnect)
  python run_with_vpn.py --dry-run  # jen otestuje connect → disconnect (bez agenta)
"""
import subprocess
import sys
import time

import config  # noqa: F401  (načte .env mj. pro telegram_alert)
import telegram_alert
from logger import setup_logger

log = setup_logger("gaming-agent")

BASE = "/Users/openclaw/AI-Projects/gaming-content-agent"
PYTHON = f"{BASE}/venv/bin/python"
AGENT = f"{BASE}/auto_publish.py"
CONNECT_TIMEOUT = 60   # s — jak dlouho čekat na tunel
DISCONNECT_TIMEOUT = 25


def _default_iface() -> str:
    """Vrátí název výchozího network interface (en1 = napřímo, utunX = VPN tunel)."""
    try:
        out = subprocess.run(
            ["route", "-n", "get", "default"], capture_output=True, text=True, timeout=10
        ).stdout
    except Exception:
        return ""
    for line in out.splitlines():
        if "interface:" in line:
            return line.split(":", 1)[1].strip()
    return ""


def vpn_up() -> bool:
    return _default_iface().startswith("utun")


def connect_vpn() -> bool:
    """Spustí NordVPN a připojí. Vrací True když je tunel nahoře do CONNECT_TIMEOUT."""
    subprocess.run(["open", "-a", "NordVPN"])
    time.sleep(10)  # inicializace appky
    subprocess.run(["open", "nordvpn://connect"])
    deadline = time.time() + CONNECT_TIMEOUT
    while time.time() < deadline:
        if vpn_up():
            return True
        time.sleep(3)
    return vpn_up()


def disconnect_vpn() -> bool:
    """Graceful quit NordVPN (tím network extension shodí tunel). Vrací True když je tunel dole."""
    subprocess.run(["osascript", "-e", 'tell application "NordVPN" to quit'])
    deadline = time.time() + DISCONNECT_TIMEOUT
    while time.time() < deadline:
        if not vpn_up():
            return True
        time.sleep(3)
    return not vpn_up()


def main() -> int:
    dry = "--dry-run" in sys.argv
    was_up = vpn_up()

    if was_up:
        log.info("🔌 VPN už běží (ruční session) — nechávám zapnutou, jen spustím běh")
    else:
        log.info("🔌 Zapínám NordVPN na dobu běhu...")
        if not connect_vpn():
            log.error("VPN se nepodařilo zapnout do %ds — přeskakuji běh (žádná útrata)", CONNECT_TIMEOUT)
            telegram_alert.send_alert(
                "⚠️ <b>GAMEfo autopublish: VPN se nezapnula</b>\n\n"
                "Nepodařilo se připojit NordVPN → běh přeskočen (nic se neutratilo).\n"
                "➡️ Zkontroluj NordVPN appku na Mac Mini."
            )
            return 1
        log.info("✅ VPN nahoře (%s)", _default_iface())

    try:
        if dry:
            log.info("🧪 --dry-run: agenta nespouštím, jen test VPN cyklu")
            rc = 0
        else:
            rc = subprocess.run([PYTHON, AGENT]).returncode
            log.info("Agent skončil s kódem %d", rc)
        return rc
    finally:
        if was_up:
            log.info("🔌 VPN byla zapnutá už před během — nechávám ji zapnutou")
        else:
            log.info("🔌 Vypínám NordVPN...")
            if disconnect_vpn():
                log.info("✅ VPN odpojena (%s) — net zase napřímo", _default_iface())
            else:
                log.warning("VPN se nepodařilo odpojit (Automation/TCC?) — zůstává nahoře")
                telegram_alert.send_alert(
                    "⚠️ <b>GAMEfo: VPN se po běhu nevypnula</b>\n\n"
                    "Běh proběhl, ale NordVPN zůstala zapnutá (net bude pomalejší).\n"
                    "➡️ Odpoj ji ručně. Možná chybí Automation oprávnění pro odpojení skriptem."
                )


if __name__ == "__main__":
    sys.exit(main())
