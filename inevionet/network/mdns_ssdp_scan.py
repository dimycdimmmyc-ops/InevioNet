"""InevioNet mDNS/SSDP/LLMNR scan - устройства рядом.

  - mDNS: _services._dns-sd._udp.local (принтеры, ТВ, Apple)
  - SSDP: M-SEARCH (UPnP-устройства)
  - LLMNR: multicast name query (Windows)

Возвращает список устройств с IP, hostname, type.
"""
import os
import re
import time
import socket
import struct
import threading
from typing import List, Dict, Any, Optional

from ..core.logger import get_logger

logger = get_logger("inevionet.network.mdns_ssdp_scan")


class MDNSScan:
    """mDNS discovery."""

    MDNS_ADDR = "224.0.0.251"
    MDNS_PORT = 5353

    def scan(self, timeout: float = 3.0) -> List[Dict[str, Any]]:
        results = []
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.settimeout(timeout)

            # mDNS query для _services._dns-sd._udp.local
            # Упрощённый DNS-запрос
            query = self._build_mdns_query("_services._dns-sd._udp.local")
            s.sendto(query, (self.MDNS_ADDR, self.MDNS_PORT))

            deadline = time.time() + timeout
            seen = set()
            while time.time() < deadline:
                try:
                    data, addr = s.recvfrom(4096)
                    if addr[0] in seen:
                        continue
                    seen.add(addr[0])
                    results.append({
                        "ip": addr[0],
                        "source": "mdns",
                        "raw_len": len(data),
                    })
                except socket.timeout:
                    break
            s.close()
        except Exception as e:
            logger.debug("[mDNS] error: %s", e)
        return results

    def _build_mdns_query(self, name: str) -> bytes:
        """Простой mDNS query."""
        # Header
        txid = 0
        flags = 0
        qdcount = 1
        header = struct.pack("!HHHHHH", txid, flags, qdcount, 0, 0, 0)
        # Question
        q = b""
        for part in name.split("."):
            q += bytes([len(part)]) + part.encode()
        q += b"\x00"
        q += struct.pack("!HH", 12, 1)  # PTR, IN
        return header + q


class SSDPScan:
    """SSDP (UPnP) discovery."""

    SSDP_ADDR = "239.255.255.250"
    SSDP_PORT = 1900

    def scan(self, timeout: float = 3.0) -> List[Dict[str, Any]]:
        results = []
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.settimeout(timeout)

            msg = (
                'M-SEARCH * HTTP/1.1\r\n'
                'HOST: 239.255.255.250:1900\r\n'
                'MAN: "ssdp:discover"\r\n'
                'MX: 2\r\n'
                'ST: ssdp:all\r\n'
                '\r\n'
            ).encode()
            s.sendto(msg, (self.SSDP_ADDR, self.SSDP_PORT))

            deadline = time.time() + timeout
            seen = set()
            while time.time() < deadline:
                try:
                    data, addr = s.recvfrom(4096)
                    ip = addr[0]
                    if ip in seen:
                        continue
                    seen.add(ip)
                    text = data.decode("utf-8", errors="replace")
                    server = ""
                    location = ""
                    for line in text.splitlines():
                        if line.lower().startswith("server:"):
                            server = line.split(":", 1)[1].strip()[:100]
                        elif line.lower().startswith("location:"):
                            location = line.split(":", 1)[1].strip()[:200]
                    results.append({
                        "ip": ip,
                        "source": "ssdp",
                        "server": server,
                        "location": location,
                    })
                except socket.timeout:
                    break
            s.close()
        except Exception as e:
            logger.debug("[SSDP] error: %s", e)
        return results


class LLMNRScan:
    """LLMNR (Windows name resolution)."""

    LLMNR_ADDR = "224.0.0.252"
    LLMNR_PORT = 5355

    def scan(self, timeout: float = 2.0) -> List[Dict[str, Any]]:
        results = []
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            s.settimeout(timeout)
            s.sendto(b"\x00\x00", (self.LLMNR_ADDR, self.LLMNR_PORT))
            deadline = time.time() + timeout
            while time.time() < deadline:
                try:
                    data, addr = s.recvfrom(1024)
                    results.append({"ip": addr[0], "source": "llmnr"})
                except socket.timeout:
                    break
            s.close()
        except Exception as e:
            logger.debug("[LLMNR] error: %s", e)
        return results


class LocalDiscovery:
    """Объединяет mDNS + SSDP + LLMNR."""

    def __init__(self):
        self.mdns = MDNSScan()
        self.ssdp = SSDPScan()
        self.llmnr = LLMNRScan()
        self._stats = {
            "scans": 0,
            "mdns": 0,
            "ssdp": 0,
            "llmnr": 0,
            "started_at": time.time(),
        }

    def scan_all(self, timeout: float = 3.0) -> Dict[str, Any]:
        """Полный скан всеми методами."""
        self._stats["scans"] += 1

        devices = {}

        # mDNS
        try:
            for d in self.mdns.scan(timeout):
                ip = d["ip"]
                if ip not in devices:
                    devices[ip] = d
                    self._stats["mdns"] += 1
        except Exception as e:
            logger.debug("[mDNS] %s", e)

        # SSDP
        try:
            for d in self.ssdp.scan(timeout):
                ip = d["ip"]
                if ip not in devices:
                    devices[ip] = d
                    self._stats["ssdp"] += 1
                else:
                    devices[ip].update(d)
        except Exception as e:
            logger.debug("[SSDP] %s", e)

        # LLMNR
        try:
            for d in self.llmnr.scan(timeout):
                ip = d["ip"]
                if ip not in devices:
                    devices[ip] = d
                    self._stats["llmnr"] += 1
        except Exception as e:
            logger.debug("[LLMNR] %s", e)

        return {
            "devices": list(devices.values()),
            "total": len(devices),
        }

    def get_stats(self) -> Dict[str, Any]:
        return dict(self._stats)
