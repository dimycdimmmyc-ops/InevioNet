"""P13: Cellular scanner - LTE/5G/GSM detection + operator lookup."""
import re
import sys
import json
import socket
import subprocess
import urllib.request
from typing import List, Dict, Any, Optional
from ..core.logger import get_logger

logger = get_logger("inevionet.network.cellular_scanner")


# MCC/MNC -> operator name (RU + CIS)
OPERATORS = {
    "25001": "MTS", "25002": "MegaFon", "25020": "Tele2",
    "25099": "Beeline", "25011": "Yota", "25016": "MTS",
    "25017": "MTS", "25035": "MOTIV", "25039": "Rostelecom",
    "25050": "MTS", "25092": "MegaFon",
    "25501": "Vodafone UA", "25502": "Kyivstar", "25503": "lifecell",
    "25701": "A1 BY", "25702": "MTS BY", "25704": "life:)",
    "40101": "Beeline KZ", "40102": "Kcell", "40177": "Tele2 KZ",
}


def scan_cellular() -> List[Dict[str, Any]]:
    """Scan for cellular networks.

    Uses netsh mbn (Windows) or mmcli (Linux). If no modem,
    returns empty list.
    """
    if sys.platform == "win32":
        return _scan_cellular_windows()
    return _scan_cellular_linux()


def _scan_cellular_windows() -> List[Dict[str, Any]]:
    """Windows: netsh mbn show interfaces."""
    results = []
    try:
        r = subprocess.run(
            ["netsh", "mbn", "show", "interfaces"],
            capture_output=True, timeout=8,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            raw = r.stdout.decode("cp866", errors="replace")
        except Exception:
            raw = r.stdout.decode("utf-8", errors="replace")

        current = {}
        for line in raw.splitlines():
            if ":" not in line:
                continue
            key, _, val = line.partition(":")
            key_l = key.strip().lower()
            val = val.strip()

            if "РёРјСЏ РѕРїРµСЂР°С‚РѕСЂР°" in key_l or "operator" in key_l:
                current["operator"] = val
            elif "С‚РµС…РЅРѕР»РѕРіРёСЏ" in key_l or "technology" in key_l:
                current["tech"] = val
            elif "СѓСЂРѕРІРµРЅСЊ СЃРёРіРЅР°Р»Р°" in key_l or "signal" in key_l:
                current["signal"] = val
            elif "РёРґРµРЅС‚РёС„РёРєР°С‚РѕСЂ" in key_l or "id" in key_l:
                current["cell_id"] = val
            elif not line.startswith(" ") and current:
                results.append(current)
                current = {}

        if current:
            results.append(current)

        for c in results:
            c["type"] = "5g" if "5g" in c.get("tech", "").lower() else "lte"
            c["operator"] = c.get("operator", "unknown")

    except Exception as e:
        logger.debug("[Cellular] netsh mbn error: %s", e)
    return results


def _scan_cellular_linux() -> List[Dict[str, Any]]:
    """Linux: mmcli -L."""
    results = []
    try:
        r = subprocess.run(["mmcli", "-L"], capture_output=True, timeout=5)
        raw = r.stdout.decode("utf-8", errors="replace")
        for line in raw.splitlines():
            m = re.match(r"\s*/Modem/(\d+)", line)
            if m:
                results.append({
                    "modem_id": m.group(1),
                    "operator": "unknown",
                    "tech": "unknown",
                    "type": "lte",
                })
    except Exception as e:
        logger.debug("[Cellular] mmcli error: %s", e)
    return results


def guess_operator_from_ssid(ssid: str) -> Optional[str]:
    """P13: Guess operator from WiFi SSID."""
    ssid_upper = (ssid or "").upper()
    if "MTS" in ssid_upper or "РњРўРЎ" in ssid_upper:
        return "MTS"
    if "MEGAFON" in ssid_upper or "РњР•Р“РђР¤РћРќ" in ssid_upper or "MEGA" in ssid_upper:
        return "MegaFon"
    if "BEELINE" in ssid_upper or "Р‘РР›РђР™Рќ" in ssid_upper or "BEEL" in ssid_upper:
        return "Beeline"
    if "TELE2" in ssid_upper or "РўР•Р›Р•2" in ssid_upper:
        return "Tele2"
    if "YOTA" in ssid_upper or "Р™РћРўРђ" in ssid_upper:
        return "Yota"
    if "ROSTELECOM" in ssid_upper or "Р РћРЎРўР•Р›Р•РљРћРњ" in ssid_upper:
        return "Rostelecom"
    return None


def lookup_operator(mcc: str, mnc: str) -> Optional[str]:
    """Lookup operator by MCC/MNC."""
    key = str(mcc).zfill(3) + str(mnc).zfill(2)
    return OPERATORS.get(key)


def scan_cellular_via_wifi() -> List[Dict[str, Any]]:
    """P13: Guess cellular operator via WiFi SSIDs.

    Many mobile operators have branded WiFi routers.
    """
    results = []
    try:
        r = subprocess.run(
            ["netsh", "wlan", "show", "networks"],
            capture_output=True, timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            raw = r.stdout.decode("cp866", errors="replace")
        except Exception:
            raw = r.stdout.decode("utf-8", errors="replace")

        seen_ops = set()
        for line in raw.splitlines():
            if "SSID" in line and ":" in line:
                ssid = line.split(":", 1)[1].strip()
                op = guess_operator_from_ssid(ssid)
                if op and op not in seen_ops:
                    seen_ops.add(op)
                    results.append({
                        "operator": op,
                        "tech": "via_wifi",
                        "type": "cellular",
                        "source": "wifi_ssid:" + ssid,
                    })
    except Exception as e:
        logger.debug("[Cellular] wifi guess error: %s", e)
    return results


def geolocate_via_wifi() -> Optional[Dict[str, float]]:
    """P13: Geolocate by WiFi BSSIDs (Mozilla Location Service).

    Returns {lat, lon, accuracy_m} or None.
    """
    try:
        # Get WiFi BSSIDs
        r = subprocess.run(
            ["netsh", "wlan", "show", "networks", "mode=bssid"],
            capture_output=True, timeout=5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            raw = r.stdout.decode("cp866", errors="replace")
        except Exception:
            raw = r.stdout.decode("utf-8", errors="replace")

        bssids = re.findall(r"([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}", raw)
        if not bssids:
            return None

        # Mozilla Location Service API
        payload = json.dumps({
            "wifiAccessPoints": [
                {"macAddress": b.upper().replace("-", ":")} for b in bssids[:10]
            ]
        }).encode("utf-8")

        req = urllib.request.Request(
            "https://location.services.mozilla.com/v1/geolocate?key=test",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            loc = data.get("location", {})
            if "lat" in loc and "lng" in loc:
                return {
                    "lat": loc["lat"],
                    "lon": loc["lng"],
                    "accuracy_m": loc.get("accuracy", 1000),
                }
    except Exception as e:
        logger.debug("[Cellular] geolocate error: %s", e)
    return None


def full_cellular_scan() -> Dict[str, Any]:
    """P13: Full cellular scan - modem + WiFi guess + geolocation."""
    return {
        "modem": scan_cellular(),
        "via_wifi": scan_cellular_via_wifi(),
        "location": geolocate_via_wifi(),
    }


if __name__ == "__main__":
    print("Testing cellular_scanner...")
    print("Modem scan:", scan_cellular())
    print("WiFi guess:", scan_cellular_via_wifi())
    loc = geolocate_via_wifi()
    print("Location:", loc)
    print("Full:", full_cellular_scan())
    print("cellular_scanner OK")