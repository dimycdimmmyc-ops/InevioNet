# Patch 7c: BLE scanner standalone
$ErrorActionPreference = "Stop"
$ProjectRoot = "E:\InevioNet"
$blePath = Join-Path $ProjectRoot "inevionet\network\ble_scanner.py"

if (Test-Path $blePath) {
    Write-Host "[!!] ble_scanner.py already exists" -ForegroundColor Yellow
    return
}

$bleCode = @'
"""P13: BLE scanner - separate module."""
import time
import sys
from typing import List, Dict, Any
from ..core.logger import get_logger

logger = get_logger("inevionet.network.ble_scanner")


def scan_ble(duration: float = 5.0, max_devices: int = 50) -> List[Dict[str, Any]]:
    """P13: Сканировать BLE-устройства.

    Returns: список {mac, name, rssi, address, type}
    """
    results = []

    if sys.platform != "win32":
        logger.debug("[BLE] non-Windows, skipping")
        return results

    # Пробуем bleson
    try:
        from bleson import get_provider, Observer
        provider = get_provider()
        observer = Observer(provider)
        collected = []

        def on_adv(adv):
            addr = getattr(adv, "address", None)
            name = getattr(adv, "name", None) or "(ble)"
            rssi = getattr(adv, "rssi", None)
            if addr:
                collected.append({
                    "mac": str(addr).replace(":", "").lower(),
                    "address": str(addr),
                    "name": name,
                    "rssi": rssi if rssi is not None else -70,
                    "type": "ble",
                })

        observer.on_advertisement = on_adv
        observer.start()
        deadline = time.time() + duration
        while time.time() < deadline and len(collected) < max_devices:
            time.sleep(0.2)
        try:
            observer.stop()
        except Exception:
            pass

        # Dedup by MAC
        seen = set()
        for d in collected:
            if d["mac"] and d["mac"] not in seen:
                seen.add(d["mac"])
                results.append(d)

        logger.info("[BLE] bleson: %d devices", len(results))
    except ImportError:
        logger.debug("[BLE] bleson not installed (pip install bleson)")
    except Exception as e:
        logger.debug("[BLE] error: %s", e)

    return results


if __name__ == "__main__":
    print("Testing BLE scanner...")
    devices = scan_ble(duration=5.0)
    print(f"Found: {len(devices)}")
    for d in devices[:10]:
        print(f"  {d['address']}  {d['name'][:30]}  RSSI={d['rssi']}")
    print("BLE scanner OK")
'@

$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($blePath, $bleCode, $utf8)
Write-Host "[OK] Created: $blePath" -ForegroundColor Green

python -c "import ast; ast.parse(open(r'$blePath', encoding='utf-8').read()); print('OK')"

# Тест
python -c "import sys; sys.path.insert(0, r'$ProjectRoot'); from inevionet.network.ble_scanner import scan_ble; d = scan_ble(duration=3.0); print('BLE devices:', len(d))"