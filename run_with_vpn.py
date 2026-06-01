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
CONNECT_TIMEOUT = 300       # s — z launchd je studený start výrazně pomalejší než z terminálu
CONNECT_RETRY_INTERVAL = 75 # s — connect deep link NEspamovat: opakovat až po pauze, jinak appku resetuje
DISCONNECT_TIMEOUT = 90     # s — deep-link disconnect z launchd taky potřebuje rezervu


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
    """Spustí NordVPN a připojí. Vrací True když je tunel nahoře do CONNECT_TIMEOUT.

    POZOR na zaseklou appku: když NordVPN běží dlouho (např. přes noc po ručním
    connectu) a je odpojená, `open -a NordVPN` ji jen aktivuje a `nordvpn://connect`
    na takovou instanci nezabere — tunel nikdy nenaskočí (přesně tak selhal běh 8:00).
    Ověřeno reprodukcí: čerstvě spuštěná appka deep link přijme do ~15 s, zaseklá ne.
    Proto appku nejdřív tvrdě restartujeme (kill → relaunch), ať je vždy v čistém stavu.

    Restart NESMÍ jít přes `osascript … quit`: Apple Events z launchd narážejí na
    TCC/Automation oprávnění a tiše selžou → appka se neukončí (tak selhal běh 11:00).
    Proto `pkill`, který TCC nepotřebuje. Killujeme JEN GUI proces (cesta MacOS/NordVPN),
    NE network extension ani helper. Při connectu je tunel vždy dole (volá se jen když
    was_up == False), takže kill GUI nenechá osiřelý tunel.

    Connect deep link posíláme JEDNOU a pak trpělivě čekáme. Spamovat ho NESMÍME:
    další `nordvpn://connect` během probíhajícího connectu appku restartuje v půlce
    → zacyklí se v "connecting", default route se nikdy nepřepne na utun → vpn_up()
    pořád False → další spam (tak selhal běh 8:00 s 9s opakováním). Ověřeno: jediný
    connect na čerstvou appku přepne route na utun do ~5 s. Opakujeme až po
    CONNECT_RETRY_INTERVAL, jen kdyby první deep link při studeném startu spadl pod stůl.
    """
    # Restart appky — zaseklou běžící instanci jen aktivovat nestačí (viz docstring).
    subprocess.run(["pkill", "-f", "NordVPN.app/Contents/MacOS/NordVPN"])
    time.sleep(4)  # nech proces doběhnout
    subprocess.run(["open", "-a", "NordVPN"])
    time.sleep(10)  # inicializace čerstvě spuštěné appky
    deadline = time.time() + CONNECT_TIMEOUT
    last_connect = 0.0
    while time.time() < deadline:
        if vpn_up():
            return True
        now = time.time()
        # 1. connect hned (last_connect=0), pak opakovat až po dlouhé pauze — NE spamovat.
        if now - last_connect >= CONNECT_RETRY_INTERVAL:
            subprocess.run(["open", "nordvpn://connect"])
            last_connect = now
        time.sleep(3)
    return vpn_up()


def disconnect_vpn() -> bool:
    """Odpojí tunel přes `nordvpn://disconnect` deep link. Vrací True když je tunel dole.

    NE přes `osascript … quit`: Apple Events z launchd blokuje TCC (tichý no-op) — tak
    VPN zůstávala viset i po úspěšném běhu. Deep link TCC nepotřebuje. Tunel necháváme
    shodit network extension (graceful), proto appku NEpkillujeme — kill GUI při tunelu
    nahoře by nechal osiřelý tunel, který už nelze ovládat.
    """
    deadline = time.time() + DISCONNECT_TIMEOUT
    last_cmd = 0.0
    while time.time() < deadline:
        if not vpn_up():
            return True
        now = time.time()
        # Stejně jako u connectu: poslat jednou, neopakovat dřív než po pauze.
        if now - last_cmd >= CONNECT_RETRY_INTERVAL:
            subprocess.run(["open", "nordvpn://disconnect"])
            last_cmd = now
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
            # Appka se může připojit POZDĚ (po timeoutu) → VPN by pak visela nahoře a nikdo
            # ji nevypne (skončili jsme returnem 1). Zabijeme GUI proces; tunel je teď dole
            # (connect neuspěl), takže žádný osiřelý tunel nehrozí.
            subprocess.run(["pkill", "-f", "NordVPN.app/Contents/MacOS/NordVPN"])
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
