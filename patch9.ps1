# Patch 9: BLE via bleak + RFScanner wifi_provider fix
$ErrorActionPreference = "Stop"
$ProjectRoot = "E:\InevioNet"

# === 9.1. Переписать ble_scanner.py через bleak ===
$blePath = Join-Path $ProjectRoot "inevionet\network\ble_scanner.py"
$backupDir = Join-Path $ProjectRoot "_backup_ble"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
if (Test-Path $blePath) {
    Copy-Item $blePath (Join-Path $backupDir "ble_scanner.py") -Force
}

$bleCode = @'
"""P13: BLE scanner via bleak (no C++ needed)."""
import asyncio
import time
from typing import List, Dict, Any
from ..core.logger import get_logger

logger = get_logger("inevionet.network.ble_scanner")


def scan_ble(duration: float = 5.0, max_devices: int = 50) -> List[Dict[str, Any]]:
    """P13: Scan BLE devices via bleak (WinRT backend on Windows).

    Returns: [{mac, address, name, rssi, type}]
    """
    try:
        from bleak import BleakScanner
    except ImportError:
        logger.debug("[BLE] bleak not installed (pip install bleak)")
        return []

    devices_seen = {}

    def detection_callback(device, advertisement_data):
        mac = (device.address or "").replace(":", "").lower()
        if not mac:
            return
        if mac not in devices_seen:
            devices_seen[mac] = {
                "mac": mac,
                "address": device.address,
                "name": advertisement_data.local_name or device.name or "(ble)",
                "rssi": advertisement_data.rssi if advertisement_data.rssi is not None else -70,
                "type": "ble",
                "manufacturer_data": bool(advertisement_data.manufacturer_data),
                "service_uuids": list(advertisement_data.service_uuids or [])[:3],
            }
        else:
            # Обновляем RSSI
            devices_seen[mac]["rssi"] = advertisement_data.rssi

    async def _scan():
        scanner = BleakScanner(detection_callback=detection_callback)
        await scanner.start()
        try:
            deadline = time.time() + duration
            while time.time() < deadline and len(devices_seen) < max_devices:
                await asyncio.sleep(0.3)
        finally:
            await scanner.stop()

    try:
        asyncio.run(_scan())
    except Exception as e:
        logger.debug("[BLE] scan error: %s", e)

    results = list(devices_seen.values())
    logger.info("[BLE] bleak: %d devices", len(results))
    return results


if __name__ == "__main__":
    print("Testing BLE scanner (bleak)...")
    devices = scan_ble(duration=5.0)
    print(f"Found: {len(devices)}")
    for d in devices[:10]:
        print(f"  {d['address']}  {d['name'][:30]}  RSSI={d['rssi']}")
    print("BLE scanner OK")
'@

$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($blePath, $bleCode, $utf8)
Write-Host "[OK] ble_scanner.py rewritten (bleak)" -ForegroundColor Green

python -c "import ast; ast.parse(open(r'$blePath', encoding='utf-8').read()); print('OK')"

# === 9.2. Fix RFScanner wifi_provider в orchestrator ===
$orchPath = Join-Path $ProjectRoot "inevionet\orchestrator.py"
$orch = [System.IO.File]::ReadAllText($orchPath, [System.Text.Encoding]::UTF8)
$orch = $orch -replace "`r`n", "`n"

if ($orch.Contains("P13: wifi_provider fix")) {
    Write-Host "[--] orchestrator already patched" -ForegroundColor Yellow
} else {
    $oldRF = @'
def _enable_rf_scanning_impl(self, interface=None):
    from .network.rf_scanner import RFScanner
    if not hasattr(self, '_rf_scanner') or self._rf_scanner is None:
        self._rf_scanner = RFScanner(interface=interface)
        logger.info(f"RF scanning enabled: {self._rf_scanner}")
    return self._rf_scanner
'@

    $newRF = @'
def _enable_rf_scanning_impl(self, interface=None, wifi_provider=None):
    # P13: wifi_provider fix
    from .network.rf_scanner import RFScanner
    if not hasattr(self, '_rf_scanner') or self._rf_scanner is None:
        self._rf_scanner = RFScanner(
            interface=interface,
            wifi_provider=wifi_provider,
        )
        logger.info(f"RF scanning enabled: {self._rf_scanner}")
    return self._rf_scanner
'@

    if ($orch.Contains($oldRF)) {
        $orch = $orch.Replace($oldRF, $newRF)
        $utf8 = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($orchPath, $orch, $utf8)
        Write-Host "[OK] orchestrator: wifi_provider added" -ForegroundColor Green
        python -c "import ast; ast.parse(open(r'$orchPath', encoding='utf-8').read()); print('OK')"
    } else {
        Write-Host "[!!] RF impl not found" -ForegroundColor Red
    }
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  Testing BLE via bleak..." -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
python -c "from inevionet.network.ble_scanner import scan_ble; d = scan_ble(duration=5.0); print('BLE devices:', len(d))"

Write-Host ""
Write-Host "Done!" -ForegroundColor Green