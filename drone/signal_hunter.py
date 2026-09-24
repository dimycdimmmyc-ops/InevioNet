"""🍄 InevioNet Signal Hunter (P8).

Каждый сигнал в эфире = потенциальный узел.

Сканирует:
  - WiFi (pywifi / iw / netsh)
  - Bluetooth classic
  - BLE (beacon'ы, IoT)
  - LTE/5G соты
  - GPS координаты

Философия:
  - Телефон в эфире = ретранслятор.
  - Сотовая вышка = транспорт между сетями.
  - IoT-устройство = узел мицелия.
"""
import os
import sys
import time
import json
import socket
import subprocess
import platform
from pathlib import Path
from typing import Dict, Any, List, Optional

import logging
log = logging.getLogger("inevionet.drone.signal_hunter")

IS_WINDOWS = platform.system() == "Windows"
IS_LINUX = platform.system() == "Linux"


class SignalHunter:
    """Единый сканер эфира для дрона."""

    def __init__(self):
        self.scan_count = 0
        self.last_scan = 0.0
        self._wifi_iface = None

    def scan_all(self) -> Dict[str, Any]:
        t0 = time.time()
        signals = []
        by_type = {}

        # P8: порядок важен!
        # BLE — первым, пока WiFi-радио не занято pywifi.
        # pywifi блокирует combo-чип (Intel AX201) на несколько секунд,
        # и bleak не может получить доступ к BLE-радио.
        for name, fn in (
            ("ble", self._scan_ble),
            ("wifi", self._scan_wifi),
            ("bluetooth", self._scan_bt),
            ("lte", self._scan_lte),
            ("gps", self._scan_gps),
        ):
            try:
                items = fn()
                signals.extend(items)
                by_type[name] = len(items)
            except Exception as e:
                log.debug("[Hunter] %s: %s", name, e)
                by_type[name] = 0

        self.scan_count += 1
        self.last_scan = time.time()

        return {
            "signals": signals,
            "by_type": by_type,
            "total": len(signals),
            "duration_ms": (time.time() - t0) * 1000,
            "ts": self.last_scan,
        }

    # ==============================================================
    def _scan_wifi(self) -> List[Dict[str, Any]]:
        if IS_WINDOWS:
            try:
                import pywifi
                if self._wifi_iface is None:
                    w = pywifi.PyWiFi()
                    ifaces = w.interfaces()
                    if not ifaces:
                        return []
                    self._wifi_iface = ifaces[0]
                self._wifi_iface.scan()
                time.sleep(3)
                results = self._wifi_iface.scan_results()
                out = []
                seen = set()
                for r in results:
                    ssid = (r.ssid or "").strip()
                    bssid = (r.bssid or "").strip().rstrip(":").lower()
                    if not bssid or bssid in seen:
                        continue
                    seen.add(bssid)
                    out.append({
                        "node_id": "wifi_" + bssid.replace(":", ""),
                        "type": "wifi",
                        "name": ssid or "(hidden)",
                        "bssid": bssid,
                        "rssi_dbm": float(r.signal) if r.signal else -100.0,
                    })
                return out
            except Exception:
                return []

        if IS_LINUX:
            try:
                r = subprocess.run(
                    ["iw", "dev", "wlan0", "scan"],
                    capture_output=True, timeout=10, text=True,
                )
                out = []
                current = {}
                for line in r.stdout.splitlines():
                    line = line.strip()
                    if line.startswith("BSS "):
                        if current:
                            out.append(current)
                        bssid = line.split()[1].rstrip(":")
                        current = {
                            "node_id": "wifi_" + bssid.replace(":", ""),
                            "type": "wifi",
                            "name": "(hidden)",
                            "bssid": bssid,
                            "rssi_dbm": -100.0,
                        }
                    elif line.startswith("SSID:") and current:
                        current["name"] = line.split(":", 1)[1].strip()
                    elif line.startswith("signal:") and current:
                        try:
                            current["rssi_dbm"] = float(
                                line.split(":", 1)[1].strip().split()[0])
                        except Exception:
                            pass
                if current:
                    out.append(current)
                return out
            except Exception:
                return []

        return []

    # ==============================================================
    def _scan_bt(self) -> List[Dict[str, Any]]:
        """BT classic — только Linux.

        На Windows Get-PnpDevice -Class Bluetooth возвращает
        BLE-устройства + сервисы + адаптеры — НЕ BT classic.
        Не используем, чтобы не засорять вывод.
        """
        if not IS_LINUX:
            return []
        try:
            r = subprocess.run(
                ["bluetoothctl", "devices"],
                capture_output=True, timeout=10, text=True,
            )
            out = []
            for line in r.stdout.splitlines():
                parts = line.split(" ", 2)
                if len(parts) >= 3 and parts[0] == "Device":
                    mac = parts[1]
                    name = parts[2]
                    out.append({
                        "node_id": "bt_" + mac.replace(":", ""),
                        "type": "bluetooth",
                        "name": name,
                        "mac": mac,
                        "rssi_dbm": -70.0,
                    })
            return out
        except Exception:
            return []

    # ==============================================================
    def _scan_ble(self) -> List[Dict[str, Any]]:
        try:
            from inevionet.network.ble_scanner import scan_ble
            return scan_ble(timeout=5.0)
        except Exception as e:
            log.debug("[Hunter] ble (модуль): %s", e)
        return []

    # ==============================================================
    def _scan_lte(self) -> List[Dict[str, Any]]:
        try:
            from inevionet.network.lte_scanner import scan_lte
            return scan_lte()
        except Exception as e:
            log.debug("[Hunter] lte (модуль): %s", e)
        return []

    # ==============================================================
    def _scan_gps(self) -> List[Dict[str, Any]]:
        try:
            from inevionet.network.gps_scanner import scan_gps
            return scan_gps()
        except Exception as e:
            log.debug("[Hunter] gps (модуль): %s", e)
        return []


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO,
                        format="[%(asctime)s] [%(levelname)s] %(message)s")
    h = SignalHunter()
    result = h.scan_all()
    print(json.dumps(result, ensure_ascii=False, indent=2))