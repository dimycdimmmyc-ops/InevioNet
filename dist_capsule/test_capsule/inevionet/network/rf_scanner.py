"""InevioNet RF Scanner — расширенный скан эфира.

Сканирует:
  1. WiFi       — через netsh wlan (Windows) / iwlist (Linux)
  2. Bluetooth  — bleson/pybluez2 (Windows) / bluetoothctl (Linux)
  3. BLE        — через pywinrt / hcitool lescan
  4. LTE/5G     — через netsh mbn / mmcli (соты, Cell ID, RSSI)
  5. GPS        — через gpsd или COM-порт
  6. WiFi probes — через scapy (если есть права + monitor mode)

Каждый сигнал → RFSignal (единый формат) → потенциальный узел InevioNet.

Философия: узел САМ сканирует эфир, находит сети, закрепляется в них.
Никаких ручных проверок.
"""
import os
import re
import sys
import time
import json
import socket
import logging
import subprocess
import threading
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field
from enum import Enum

try:
    from ..core.logger import get_logger
    log = get_logger("inevionet.network.rf_scanner")
except ImportError:
    log = logging.getLogger("inevionet.network.rf_scanner")


# ==============================================================
# ENUMS + DATA
# ==============================================================
class RFSignalType(str, Enum):
    WIFI = "wifi"
    BLUETOOTH = "bluetooth"
    BLE = "ble"
    LTE = "lte"
    NR_5G = "5g"
    GPS = "gps"
    WIFI_PROBE = "wifi_probe"
    UNKNOWN = "unknown"


@dataclass
class RFSignal:
    """Единый формат сигнала из любого диапазона."""
    signal_type: RFSignalType
    identifier: str          # BSSID / MAC / Cell ID / имя
    name: str = ""
    rssi_dbm: float = -100.0
    quality: float = 0.0
    frequency_mhz: float = 0.0
    channel: int = 0
    encryption: str = ""
    operator: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()
        if self.quality == 0.0 and self.rssi_dbm != -100.0:
            # RSSI -100..-30 → 0..1
            self.quality = max(0.0, min(1.0, (self.rssi_dbm + 100) / 70.0))


@dataclass
class RFScanResult:
    success: bool
    signals: List[RFSignal] = field(default_factory=list)
    by_type: Dict[str, int] = field(default_factory=dict)
    duration_ms: float = 0.0
    method: str = "auto"
    error: Optional[str] = None
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    @property
    def total_count(self):
        return len(self.signals)

    def by_signal_type(self):
        result: Dict[str, List[RFSignal]] = {}
        for s in self.signals:
            result.setdefault(s.signal_type.value, []).append(s)
        return result


# ==============================================================
# RF SCANNER
# ==============================================================
class RFScanner:
    def __init__(self, interface: str = None, enable_all: bool = True,
                 wifi_provider=None):
        """wifi_provider — callable() -> list[dict] с ключами ssid, bssid, signal, rssi_dbm.

        Если задан, RFScanner не вызывает netsh сам для WiFi — берёт готовые
        данные из web.app. Это решает проблему одновременного доступа
        к WiFi-адаптеру Windows.
        """
        self.interface = interface
        self.enable_all = enable_all
        self.wifi_provider = wifi_provider
        self.stats = {"scans": 0, "total_signals": 0}
        self._lock = threading.RLock()
        log.info("RFScanner created: interface=%s, enable_all=%s, wifi_provider=%s",
                 interface, enable_all, "yes" if wifi_provider else "no")

    # ----------------------------------------------------------
    # MAIN SCAN
    # ----------------------------------------------------------
    def scan_all(self) -> RFScanResult:
        """Сканировать все диапазоны."""
        t0 = time.time()
        all_signals: List[RFSignal] = []

        # 1. WiFi
        try:
            all_signals.extend(self._scan_wifi())
        except Exception as e:
            log.debug("[rf] wifi: %s", e)

        # 2. Bluetooth classic
        try:
            all_signals.extend(self._scan_bluetooth())
        except Exception as e:
            log.debug("[rf] bt: %s", e)

        # 3. BLE
        try:
            all_signals.extend(self._scan_ble())
        except Exception as e:
            log.debug("[rf] ble: %s", e)

        # 4. LTE/5G соты
        try:
            all_signals.extend(self._scan_cellular())
        except Exception as e:
            log.debug("[rf] lte: %s", e)

        # 5. GPS
        try:
            all_signals.extend(self._scan_gps())
        except Exception as e:
            log.debug("[rf] gps: %s", e)

        duration_ms = (time.time() - t0) * 1000

        by_type: Dict[str, int] = {}
        for s in all_signals:
            by_type[s.signal_type.value] = by_type.get(s.signal_type.value, 0) + 1

        with self._lock:
            self.stats["scans"] += 1
            self.stats["total_signals"] += len(all_signals)

        log.info("[rf] скан завершён: %d сигналов за %.0fms (%s)",
                 len(all_signals), duration_ms,
                 ", ".join(f"{k}={v}" for k, v in by_type.items()) or "пусто")

        return RFScanResult(
            success=True,
            signals=all_signals,
            by_type=by_type,
            duration_ms=duration_ms,
            method="multi_band",
        )

    # ----------------------------------------------------------
    # WIFI
    # ----------------------------------------------------------
    def _scan_wifi(self) -> List[RFSignal]:
        """Скан WiFi.

        Если задан wifi_provider — берём данные из web.app (избегаем гонки
        за WiFi-адаптер). Иначе — сканируем сами через netsh.
        """
        # 1. Если есть provider — берём оттуда
        if self.wifi_provider is not None:
            try:
                raw_signals = self.wifi_provider()
                if raw_signals:
                    signals = []
                    for sig in raw_signals:
                        ssid = sig.get("ssid", "")
                        bssid = sig.get("bssid", "")
                        pct = int(sig.get("signal", 0))
                        rssi = sig.get("rssi_dbm", -100 + (pct / 100.0) * 50)
                        if not bssid:
                            bssid = "ssid_" + re.sub(r"[^a-zA-Z0-9]", "_", ssid)[:32]
                        signals.append(RFSignal(
                            signal_type=RFSignalType.WIFI,
                            identifier=bssid,
                            name=ssid,
                            rssi_dbm=round(rssi, 1),
                            quality=pct / 100.0 if pct > 0 else 0.5,
                            extra={"signal_percent": pct},
                        ))
                    if signals:
                        return signals
            except Exception as e:
                log.debug("[rf] wifi_provider: %s", e)

        # 2. Fallback — сами через netsh
        if sys.platform == "win32":
            return self._scan_wifi_windows()
        return self._scan_wifi_linux()

    def _scan_wifi_windows(self) -> List[RFSignal]:
        """Сканирование WiFi на Windows через netsh.

        Использует ту же логику фильтрации, что и web/app.py::scan_wifi:
          - отсеивает битые SSID (кракозябры)
          - отсеивает "тип сети:" / "type:"
          - отсеивает длинные мусорные строки
        """
        signals = []
        try:
            r = subprocess.run(
                ["netsh", "wlan", "show", "networks"],
                capture_output=True, timeout=10,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
        except Exception as e:
            log.debug("[rf] netsh: %s", e)
            return signals

        try:
            raw = r.stdout.decode("cp866", errors="replace")
        except Exception:
            try:
                raw = r.stdout.decode("utf-8", errors="replace")
            except Exception:
                raw = ""

        # Проверка "слеп" ли адаптер
        low = raw.lower()
        blind_markers = ("беспроводная сеть отключена", "wireless is off")
        if any(m in low for m in blind_markers):
            log.debug("[rf] wifi adapter blind")
            return signals

        # Разделяем по "SSID N :"
        parts = re.split(r"(?im)^\s*SSID\s+\d+\s*:\s*", "\n" + raw)

        def is_broken_ssid(s: str) -> bool:
            """Та же логика, что в web/app.py."""
            if not s:
                return True
            if len(s) > 32:
                return True
            broken = ("вХ", "вФ", "вЦ", "вЬ", "в§", "в®", "вЂ",
                      "–њ", "–≤", "–љ", "—В", "—Б", "—П",
                      "—Г", "—Д", "—З", "—И", "—Л", "—К")
            for m in broken:
                if m in s:
                    return True
            non_ascii = sum(1 for c in s if ord(c) > 127)
            if non_ascii > len(s) * 0.4:
                cyr = sum(1 for c in s if "а" <= c.lower() <= "я" or c.lower() == "ё")
                if cyr < non_ascii * 0.7:
                    return True
            return False

        for block in parts[1:]:
            lines = block.split("\n")
            ssid = lines[0].strip() if lines else ""
            if not ssid or len(ssid) < 2:
                continue
            if is_broken_ssid(ssid):
                log.debug("[rf] skip broken SSID: %r", ssid[:40])
                continue
            ssid_lower = ssid.lower().strip()
            if ssid_lower in ("тип сети:", "type:", "инфраструктура", "infrastructure"):
                continue
            if ssid_lower.startswith("тип сети") or ssid_lower.startswith("type:"):
                continue
            if ": " in ssid and len(ssid) > 20:
                continue

            bssid, pct = None, 0
            for line in lines[1:20]:
                if not bssid:
                    m = re.search(r"([0-9a-fA-F]{2}[:-]){5}([0-9a-fA-F]{2})", line)
                    if m:
                        bssid = m.group(0)
                if "%" in line and not pct:
                    m = re.search(r":\s*(\d+)\s*%", line)
                    if m:
                        pct = int(m.group(1))

            if not bssid:
                bssid = "ssid_" + re.sub(r"[^a-zA-Z0-9]", "_", ssid)[:32]

            rssi = -100 + (pct / 100.0) * 50 if pct > 0 else -75.0
            signals.append(RFSignal(
                signal_type=RFSignalType.WIFI,
                identifier=bssid,
                name=ssid,
                rssi_dbm=round(rssi, 1),
                quality=pct / 100.0 if pct > 0 else 0.5,
                extra={"signal_percent": pct},
            ))

        return signals

    def _scan_wifi_linux(self) -> List[RFSignal]:
        signals = []
        try:
            r = subprocess.run(
                ["iwlist", self.interface or "wlan0", "scan"],
                capture_output=True, timeout=15,
            )
            raw = r.stdout.decode("utf-8", errors="replace")
            current = {}
            for line in raw.splitlines():
                line = line.strip()
                if "Cell " in line and "Address:" in line:
                    if current:
                        signals.append(self._make_wifi_signal(current))
                    m = re.search(r"Address:\s*([0-9A-Fa-f:]{17})", line)
                    current = {"bssid": m.group(1) if m else "unknown"}
                elif "ESSID:" in line:
                    current["ssid"] = line.split("ESSID:")[1].strip().strip('"')
                elif "Signal level=" in line:
                    m = re.search(r"Signal level=(-?\d+)", line)
                    if m:
                        current["rssi"] = int(m.group(1))
                elif "Frequency:" in line:
                    m = re.search(r"Frequency:([\d.]+)", line)
                    if m:
                        current["freq"] = float(m.group(1))
            if current:
                signals.append(self._make_wifi_signal(current))
        except Exception as e:
            log.debug("[rf] iwlist: %s", e)
        return signals

    def _make_wifi_signal(self, data: Dict) -> RFSignal:
        return RFSignal(
            signal_type=RFSignalType.WIFI,
            identifier=data.get("bssid", "unknown"),
            name=data.get("ssid", ""),
            rssi_dbm=float(data.get("rssi", -100)),
            frequency_mhz=float(data.get("freq", 0)) * 1000,
        )

    # ----------------------------------------------------------
    # BLUETOOTH CLASSIC
    # ----------------------------------------------------------
    def _scan_bluetooth(self) -> List[RFSignal]:
        """BT classic — платформо-зависимо.

        Linux:   bluetoothctl devices (надёжнее deprecated hcitool)
        Windows: blesonar → pybluez (BT classic)
                 НЕ Get-PnpDevice — он возвращает BLE + сервисы + адаптеры,
                 а не BT classic.
        """
        signals: List[RFSignal] = []

        if sys.platform == "win32":
            signals = self._scan_bluetooth_windows()
        else:
            signals = self._scan_bluetooth_linux()

        return signals

    def _scan_bluetooth_windows(self) -> List[RFSignal]:
        """Windows BT classic.

        Пробуем по очереди:
          1. bleson    — кроссплатформенный BT/BLE (PyPI: bleson)
          2. pybluez2  — классический BT (import bluetooth, PyPI: pybluez2)
        Если ни один не установлен — возвращаем [] (без мусора).

        ВАЖНО: на Windows для сборки этих пакетов нужен
        Microsoft Visual C++ 14.0+ Build Tools. Без него —
        они не установятся, и функция вернёт [].
        """
        signals: List[RFSignal] = []

        # --- 1. bleson ---
        try:
            from bleson import get_provider, Observer

            provider = get_provider()
            observer = Observer(provider)
            collected: List[Dict[str, Any]] = []

            def _on_advertisement(advertisement):
                addr = getattr(advertisement, "address", None)
                name = getattr(advertisement, "name", None) or "(bt)"
                rssi = getattr(advertisement, "rssi", None)
                if addr:
                    collected.append({
                        "address": str(addr),
                        "name": name,
                        "rssi": rssi,
                    })

            observer.on_advertisement = _on_advertisement
            observer.start()

            import time as _t
            deadline = _t.time() + 5.0
            while _t.time() < deadline and len(collected) < 50:
                _t.sleep(0.2)

            try:
                observer.stop()
            except Exception:
                pass

            seen = set()
            for d in collected:
                mac = d["address"].replace(":", "").lower()
                if not mac or mac in seen:
                    continue
                seen.add(mac)
                rssi_val = d.get("rssi")
                signals.append(RFSignal(
                    signal_type=RFSignalType.BLUETOOTH,
                    identifier="bt_" + mac,
                    name=d["name"],
                    rssi_dbm=float(rssi_val) if rssi_val is not None else -70.0,
                    quality=0.5,
                    frequency_mhz=2402.0,
                ))
            if signals:
                log.info("[rf] BT (bleson): %d устройств", len(signals))
                return signals
        except ImportError:
            pass
        except Exception as e:
            log.debug("[rf] bleson: %s", e)

        # --- 2. pybluez2 ---
        try:
            import bluetooth as _bt
            try:
                devices = _bt.discover_devices(
                    duration=5, flush_cache=True, lookup_names=True)
                for addr, name in devices:
                    signals.append(RFSignal(
                        signal_type=RFSignalType.BLUETOOTH,
                        identifier="bt_" + addr.replace(":", "").lower(),
                        name=name or "(bt)",
                        rssi_dbm=-70.0,
                        quality=0.5,
                        frequency_mhz=2402.0,
                    ))
                if signals:
                    log.info("[rf] BT classic (pybluez2): %d устройств",
                             len(signals))
                    return signals
            except Exception as e:
                log.debug("[rf] pybluez2 discover: %s", e)
        except ImportError:
            pass
        except Exception as e:
            log.debug("[rf] pybluez2: %s", e)

        # Ничего не установлено — пусто (не мусор)
        log.debug("[rf] BT classic: нет bleson/pybluez2 — пропускаем")
        return []

    def _scan_bluetooth_linux(self) -> List[RFSignal]:
        """Linux BT classic через bluetoothctl devices."""
        signals: List[RFSignal] = []
        try:
            r = subprocess.run(
                ["bluetoothctl", "devices"],
                capture_output=True, timeout=10, text=True,
            )
            for line in r.stdout.splitlines():
                parts = line.split(" ", 2)
                if len(parts) >= 3 and parts[0] == "Device":
                    mac = parts[1]
                    name = parts[2] or "(bt)"
                    signals.append(RFSignal(
                        signal_type=RFSignalType.BLUETOOTH,
                        identifier="bt_" + mac.replace(":", "").lower(),
                        name=name,
                        rssi_dbm=-70.0,
                        quality=0.5,
                        frequency_mhz=2402.0,
                    ))
        except FileNotFoundError:
            # bluetoothctl нет — пробуем hcitool scan
            try:
                r = subprocess.run(
                    ["hcitool", "scan"],
                    capture_output=True, timeout=10,
                )
                raw = r.stdout.decode("utf-8", errors="replace")
                for line in raw.splitlines():
                    m = re.match(r"\s*([0-9A-Fa-f:]{17})\s+(.+)", line)
                    if m:
                        signals.append(RFSignal(
                            signal_type=RFSignalType.BLUETOOTH,
                            identifier="bt_" + m.group(1).replace(":", "").lower(),
                            name=m.group(2).strip(),
                            rssi_dbm=-70.0,
                            quality=0.5,
                            frequency_mhz=2402.0,
                        ))
            except Exception as e:
                log.debug("[rf] hcitool: %s", e)
        except Exception as e:
            log.debug("[rf] bluetoothctl: %s", e)
        return signals

    # ----------------------------------------------------------
    # BLE
    # ----------------------------------------------------------
    def _scan_ble(self) -> List[RFSignal]:
        """BLE-скан. На Windows — через PowerShell WMI. На Linux — hcitool lescan."""
        signals = []
        if sys.platform == "win32":
            # Windows не даёт прямого BLE-скана без WinRT / BLE-API.
            # Пропускаем (или пишем debug).
            log.debug("[rf] BLE-скан на Windows не реализован (нужен WinRT)")
            return signals
        try:
            # hcitool lescan --duplicates (5 сек)
            proc = subprocess.Popen(
                ["hcitool", "lescan", "--duplicates"],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            time.sleep(5)
            proc.terminate()
            out, _ = proc.communicate(timeout=2)
            raw = out.decode("utf-8", errors="replace")
            seen = set()
            for line in raw.splitlines():
                m = re.match(r"([0-9A-Fa-f:]{17})\s+(.+)", line)
                if m:
                    mac = m.group(1)
                    if mac in seen:
                        continue
                    seen.add(mac)
                    signals.append(RFSignal(
                        signal_type=RFSignalType.BLE,
                        identifier="ble_" + mac.replace(":", ""),
                        name=m.group(2).strip(),
                        rssi_dbm=-70.0,
                    ))
        except Exception as e:
            log.debug("[rf] lescan: %s", e)
        return signals

    # ----------------------------------------------------------
    # LTE / 5G СОТЫ
    # ----------------------------------------------------------
    def _scan_cellular(self) -> List[RFSignal]:
        signals = []
        if sys.platform == "win32":
            # netsh mbn show interfaces — мобильные интерфейсы
            try:
                r = subprocess.run(
                    ["netsh", "mbn", "show", "interfaces"],
                    capture_output=True, timeout=8,
                    creationflags=subprocess.CREATE_NO_WINDOW,
                )
                raw = r.stdout.decode("cp866", errors="replace")
                # Парсим: "Название интерфейса : ...", "Состояние : ...",
                # "Имя оператора : MTS", "Технология : LTE"
                cells = []
                current = {}
                for line in raw.splitlines():
                    if ":" not in line:
                        continue
                    key, _, val = line.partition(":")
                    key = key.strip().lower()
                    val = val.strip()
                    if "имя оператора" in key or "operator" in key:
                        current["operator"] = val
                    elif "технология" in key or "technology" in key:
                        current["tech"] = val
                    elif "уровень сигнала" in key or "signal" in key:
                        current["signal"] = val
                    elif not line.startswith(" ") and current:
                        if current:
                            cells.append(current)
                        current = {}
                if current:
                    cells.append(current)

                for cell in cells:
                    op = cell.get("operator", "unknown")
                    tech = cell.get("tech", "unknown")
                    stype = RFSignalType.NR_5G if "5g" in tech.lower() else RFSignalType.LTE
                    signals.append(RFSignal(
                        signal_type=stype,
                        identifier="cell_" + op.lower()[:16],
                        name=f"{op} ({tech})",
                        rssi_dbm=-85.0,
                        operator=op,
                        extra={"tech": tech},
                    ))
            except Exception as e:
                log.debug("[rf] netsh mbn: %s", e)
        else:
            # Linux: mmcli
            try:
                r = subprocess.run(["mmcli", "-L"], capture_output=True, timeout=5)
                raw = r.stdout.decode("utf-8", errors="replace")
                for line in raw.splitlines():
                    m = re.match(r"\s*/Modem/(\d+)", line)
                    if m:
                        signals.append(RFSignal(
                            signal_type=RFSignalType.LTE,
                            identifier=f"cell_{m.group(1)}",
                            name=f"Modem {m.group(1)}",
                            rssi_dbm=-85.0,
                        ))
            except Exception as e:
                log.debug("[rf] mmcli: %s", e)
        return signals

    # ----------------------------------------------------------
    # GPS
    # ----------------------------------------------------------
    def _scan_gps(self) -> List[RFSignal]:
        """GPS — попытка подключиться к gpsd (localhost:2947)."""
        signals = []
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2.0)
            s.connect(("127.0.0.1", 2947))
            s.sendall(b'?WATCH={"enable":true,"json":true}\n')
            time.sleep(0.5)
            data = s.recv(4096).decode("utf-8", errors="replace")
            s.close()
            for line in data.splitlines():
                try:
                    obj = json.loads(line)
                    if obj.get("class") == "TPV" and "lat" in obj and "lon" in obj:
                        signals.append(RFSignal(
                            signal_type=RFSignalType.GPS,
                            identifier="gps_self",
                            name=f"{obj.get('lat'):.5f},{obj.get('lon'):.5f}",
                            extra={"lat": obj["lat"], "lon": obj["lon"]},
                        ))
                        break
                except Exception:
                    pass
        except Exception:
            pass
        return signals

    # ----------------------------------------------------------
    # STATS
    # ----------------------------------------------------------
    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self.stats)

    def estimate_rf_density(self) -> Dict[str, Any]:
        """Оценка плотности эфира по последнему скану."""
        result = self.scan_all()
        by_type = result.by_type
        return {
            "total_signals": result.total_count,
            "by_type": by_type,
            "wifi_count": by_type.get("wifi", 0),
            "bt_count": by_type.get("bluetooth", 0) + by_type.get("ble", 0),
            "cell_count": by_type.get("lte", 0) + by_type.get("5g", 0),
            "has_gps": by_type.get("gps", 0) > 0,
            "total_density": result.total_count / 1.0,
        }

    def __repr__(self):
        return f"RFScanner(interface={self.interface}, scans={self.stats['scans']})"




# ==============================================================
# BACKWARD COMPATIBILITY (старое имя ScanResult)
# ==============================================================
# В inevionet/network/__init__.py ожидается ScanResult.
# В новом коде — RFScanResult. Делаем алиас.
ScanResult = RFScanResult

# Alias для Signal (если используется в других модулях)
Signal = RFSignal

if __name__ == "__main__":
    print("Testing RFScanner (extended)...")
    scanner = RFScanner()
    result = scanner.scan_all()
    print(f"Success: {result.success}")
    print(f"Total signals: {result.total_count}")
    print(f"Duration: {result.duration_ms:.0f}ms")
    print(f"By type: {result.by_type}")
    print()
    for sig in result.signals[:20]:
        print(f"  [{sig.signal_type.value:10s}] {sig.identifier[:30]:30s} "
              f"{sig.name[:30]:30s} RSSI={sig.rssi_dbm:.0f}")
    print()
    print(f"Density: {scanner.estimate_rf_density()}")
    print("OK")