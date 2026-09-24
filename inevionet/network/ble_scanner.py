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
            # РћР±РЅРѕРІР»СЏРµРј RSSI
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