"""P13: LTE/5G scanner - cellular detection."""
import re
import sys
import subprocess
from typing import List, Dict, Any
from ..core.logger import get_logger

logger = get_logger("inevionet.network.lte_scanner")


def scan_lte() -> List[Dict[str, Any]]:
    """P13: РћРїСЂРµРґРµР»РёС‚СЊ LTE/5G СЃРѕС‚С‹.

    Returns: [{operator, tech, signal, type}]
    """
    results = []

    if sys.platform == "win32":
        results = _scan_lte_windows()
    else:
        results = _scan_lte_linux()

    logger.info("[LTE] %d cells found", len(results))
    return results


def _scan_lte_windows() -> List[Dict[str, Any]]:
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
            elif not line.startswith(" ") and current:
                results.append(current)
                current = {}

        if current:
            results.append(current)

        # РќРѕСЂРјР°Р»РёР·СѓРµРј
        for c in results:
            c["type"] = "5g" if "5g" in c.get("tech", "").lower() else "lte"
            c["operator"] = c.get("operator", "unknown")

    except Exception as e:
        logger.debug("[LTE] netsh mbn error: %s", e)
    return results


def _scan_lte_linux() -> List[Dict[str, Any]]:
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
        logger.debug("[LTE] mmcli error: %s", e)
    return results


if __name__ == "__main__":
    print("Testing LTE scanner...")
    cells = scan_lte()
    print(f"Found: {len(cells)}")
    for c in cells:
        print(f"  [{c.get('type')}] {c.get('operator')} ({c.get('tech')})")
    print("LTE scanner OK")