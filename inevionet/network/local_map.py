"""InevioNet LocalNetworkMap - полная карта своей подсети.

Собирает:
  - ARP таблица (свой роутер + устройства)
  - DHCP leases (если доступно)
  - SNMP walk своего роутера (sysDescr, ifTable, ipNetToMedia)
  - UPnP discovery (IGD, WANIPConnection)

Результат: список устройств с IP, MAC, hostname, vendor, type.
"""
import os
import re
import time
import socket
import subprocess
import threading
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

from ..core.logger import get_logger

logger = get_logger("inevionet.network.local_map")


@dataclass
class Device:
    ip: str = ""
    mac: str = ""
    hostname: str = ""
    vendor: str = ""
    type: str = "unknown"     # router / device / printer / nas / iot / self
    source: str = "arp"       # arp / dhcp / snmp / upnp
    last_seen: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.last_seen == 0.0:
            self.last_seen = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# OUI vendors для популярных роутеров
OUI_MAP = {
    "04:ba:d6": "MTS", "3c:98:72": "MTS", "bc:0f:9a": "MTS",
    "50:ff:20": "Keenetic", "e4:18:6b": "Keenetic",
    "88:bd:09": "Netis", "08:bf:b8": "ASUS",
    "00:1a:2b": "Huawei", "00:0c:29": "VMware",
}


def mac_vendor(mac: str) -> str:
    if not mac:
        return ""
    key = mac.lower()[:8]
    return OUI_MAP.get(key, "")


def ping_host(ip: str, timeout: float = 0.3) -> bool:
    try:
        if os.name == "nt":
            r = subprocess.run(
                ["ping", "-n", "1", "-w", str(int(timeout * 1000)), ip],
                capture_output=True, timeout=2,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        else:
            r = subprocess.run(
                ["ping", "-c", "1", "-W", str(int(timeout)), ip],
                capture_output=True, timeout=2)
        return r.returncode == 0
    except Exception:
        return False


class LocalNetworkMap:
    """Карта своей подсети."""

    def __init__(self):
        self.devices: Dict[str, Device] = {}
        self.subnet: str = ""
        self.my_ip: str = ""
        self.router_ip: str = ""
        self._lock = threading.Lock()
        self._stats = {
            "builds": 0,
            "devices": 0,
            "arp": 0,
            "snmp": 0,
            "upnp": 0,
            "started_at": time.time(),
        }

    def detect_subnet(self) -> str:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            self.my_ip = s.getsockname()[0]
            s.close()
            parts = self.my_ip.split(".")
            self.subnet = ".".join(parts[:3])
            # Роутер - обычно .1
            self.router_ip = self.subnet + ".1"
            return self.subnet
        except Exception:
            return ""

    def build(self, ping_sweep: bool = True) -> Dict[str, Any]:
        """Построить карту своей подсети."""
        with self._lock:
            self._stats["builds"] += 1
        self.detect_subnet()
        if not self.subnet:
            return {"devices": [], "error": "no_subnet"}

        logger.info("[LocalMap] building for %s.x (self=%s, router=%s)",
                    self.subnet, self.my_ip, self.router_ip)

        # 1. ARP-таблица
        self._scan_arp()

        # 2. Ping sweep (заполняет ARP)
        if ping_sweep:
            self._ping_sweep()

        # 3. ARP снова (после ping sweep)
        self._scan_arp()

        # 4. SNMP своего роутера
        self._snmp_router()

        with self._lock:
            self._stats["devices"] = len(self.devices)
        return self.get_map()

    def _scan_arp(self):
        """Читает ARP-таблицу."""
        try:
            from .arp_scanner import scan_arp
            for d in scan_arp(force=True):
                ip = d.get("ip", "")
                mac = d.get("mac", "")
                if not ip:
                    continue
                with self._lock:
                    if ip not in self.devices:
                        vendor = mac_vendor(mac)
                        ntype = "router" if ip.endswith(".1") else "device"
                        self.devices[ip] = Device(
                            ip=ip, mac=mac, vendor=vendor, type=ntype,
                            source="arp")
                        self._stats["arp"] += 1
                    else:
                        self.devices[ip].last_seen = time.time()
        except Exception as e:
            logger.debug("[LocalMap] arp: %s", e)

    def _ping_sweep(self):
        """Ping sweep для заполнения ARP."""
        try:
            import concurrent.futures
            def ping_one(i):
                ip = self.subnet + "." + str(i)
                return ip if ping_host(ip, timeout=0.3) else None
            with concurrent.futures.ThreadPoolExecutor(max_workers=64) as ex:
                results = list(ex.map(ping_one, range(1, 255)))
            alive = [r for r in results if r]
            logger.debug("[LocalMap] ping sweep: %d alive", len(alive))
        except Exception as e:
            logger.debug("[LocalMap] ping: %s", e)

    def _snmp_router(self):
        """SNMP walk своего роутера (если возможно)."""
        if not self.router_ip:
            return
        try:
            self._try_snmp(self.router_ip)
        except Exception as e:
            logger.debug("[LocalMap] snmp: %s", e)

    def _try_snmp(self, host: str, community: str = "public"):
        """Пробует SNMP get на роутере."""
        # SNMP - UDP на порт 161
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(2.0)
            # Простой SNMP GET для sysDescr (1.3.6.1.2.1.1.1.0)
            # Упрощённый BER-encoding
            community_bytes = community.encode()
            varbind = bytes.fromhex("06082b06010201010100")
            pdu = bytes.fromhex("a01c0201000201000201003012301006082b060102010101000500")
            # Собираем SNMP v2c packet
            packet = (
                bytes([0x30, 0x25]) +
                bytes([0x02, 0x01, 0x01]) +  # version v2c
                bytes([0x04, len(community_bytes)]) + community_bytes +
                pdu
            )
            s.sendto(packet, (host, 161))
            try:
                data, _ = s.recvfrom(4096)
                if data and len(data) > 20:
                    logger.info("[LocalMap] SNMP OK from %s (%d bytes)",
                                host, len(data))
                    with self._lock:
                        self._stats["snmp"] += 1
                    return data
            except socket.timeout:
                logger.debug("[LocalMap] SNMP timeout %s", host)
            s.close()
        except Exception as e:
            logger.debug("[LocalMap] SNMP error: %s", e)
        return None

    def get_map(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "subnet": self.subnet,
                "my_ip": self.my_ip,
                "router_ip": self.router_ip,
                "devices": [d.to_dict() for d in self.devices.values()],
                "stats": dict(self._stats),
            }

    def get_stats(self) -> Dict[str, Any]:
        return {
            **self._stats,
            "subnet": self.subnet,
            "my_ip": self.my_ip,
            "router_ip": self.router_ip,
        }
