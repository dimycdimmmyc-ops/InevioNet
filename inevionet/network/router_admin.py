"""InevioNet RouterAdmin - SNMP fallback + HTTP админка.

Пробует:
  - SNMP с расширенными community (public, private, cisco, mts, mtc, admin, ...)
  - HTTP админка с default credentials (admin/admin, admin/1234, ...)
  - Если получилось - парсит ARP + routes + DHCP

Этично: только на своём роутере. Для чужих - только probe.
"""
import os
import re
import time
import socket
import base64
import subprocess
import threading
from typing import Dict, Any, List, Optional
import urllib.request

from ..core.logger import get_logger

logger = get_logger("inevionet.network.router_admin")


# SNMP community для перебора
SNMP_COMMUNITIES = [
    "public", "private", "cisco", "admin", "password",
    "mts", "mtc", "beeline", "mgts", "1234",
]

# Default credentials для MTS/Keenetic/ASUS
DEFAULT_CREDS = [
    ("admin", "admin"),
    ("admin", "1234"),
    ("admin", "password"),
    ("admin", ""),
    ("root", "admin"),
    ("admin", "admin123"),
]


# Пути к ARP в HTTP админках разных прошивок
ROUTER_ARP_PATHS = [
    "/cgi-bin/luci/admin/status/routes",
    "/cgi-bin/webproc",
    "/cgi-bin/status.cgi",
    "/status.cgi",
    "/cgi-bin/luci/admin/network/dhcp",
    "/api/v1/route",
    "/api/v1/dhcp",
]


class RouterAdmin:
    """SNMP fallback + HTTP админка."""

    def __init__(self, timeout: float = 3.0):
        self.timeout = timeout
        self._stats = {
            "snmp_attempts": 0,
            "snmp_ok": 0,
            "http_attempts": 0,
            "http_ok": 0,
            "arp_entries": 0,
        }

    def probe_all(self, ip: str) -> Dict[str, Any]:
        """SNMP + HTTP probe."""
        result = {
            "ip": ip,
            "snmp_community": None,
            "http_creds": None,
            "arp": [],
            "routes": [],
            "dhcp": [],
        }

        # SNMP
        snmp = self._snmp_probe(ip)
        if snmp.get("community"):
            result["snmp_community"] = snmp["community"]
            self._stats["snmp_ok"] += 1

        # HTTP админка
        http = self._http_probe(ip)
        if http.get("creds"):
            result["http_creds"] = http["creds"]
            self._stats["http_ok"] += 1
            result["arp"] = http.get("arp", [])
            result["routes"] = http.get("routes", [])
            result["dhcp"] = http.get("dhcp", [])

        return result

    def _snmp_probe(self, ip: str) -> Dict[str, Any]:
        """Перебор SNMP community."""
        for community in SNMP_COMMUNITIES:
            self._stats["snmp_attempts"] += 1
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.settimeout(self.timeout)
                community_bytes = community.encode()
                # SNMP GET для sysDescr.0
                pdu = bytes.fromhex("a01c0201000201000201003012301006082b060102010101000500")
                packet = (
                    bytes([0x30, 0x25]) +
                    bytes([0x02, 0x01, 0x01]) +
                    bytes([0x04, len(community_bytes)]) + community_bytes +
                    pdu
                )
                s.sendto(packet, (ip, 161))
                try:
                    data, _ = s.recvfrom(4096)
                    if data and len(data) > 20:
                        s.close()
                        logger.info("[RouterAdmin] SNMP OK %s community=%s",
                                    ip, community)
                        return {"community": community, "data": data}
                except socket.timeout:
                    pass
                s.close()
            except Exception:
                pass
        return {}

    def _http_probe(self, ip: str) -> Dict[str, Any]:
        """HTTP админка - перебор credentials."""
        for user, password in DEFAULT_CREDS:
            self._stats["http_attempts"] += 1
            try:
                auth = base64.b64encode(f"{user}:{password}".encode()).decode()
                for path in ROUTER_ARP_PATHS:
                    url = f"http://{ip}{path}"
                    req = urllib.request.Request(
                        url, headers={
                            "Authorization": f"Basic {auth}",
                            "User-Agent": "Mozilla/5.0",
                        })
                    try:
                        with urllib.request.urlopen(req, timeout=self.timeout) as r:
                            if r.status == 200:
                                html = r.read(16384).decode("utf-8", errors="replace")
                                arp = self._parse_arp(html)
                                if arp:
                                    logger.info("[RouterAdmin] HTTP OK %s %s:%s (%d arp)",
                                                ip, user, password, len(arp))
                                    return {
                                        "creds": f"{user}:{password}",
                                        "arp": arp,
                                        "path": path,
                                    }
                    except Exception:
                        continue
            except Exception:
                pass
        return {}

    def _parse_arp(self, html: str) -> List[Dict[str, str]]:
        """Парсит ARP из HTML."""
        arp = []
        # IP + MAC в HTML
        pat = re.compile(
            r"(\d+\.\d+\.\d+\.\d+)[^\d]+?"
            r"([0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-]"
            r"[0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2})"
        )
        for m in pat.finditer(html):
            arp.append({"ip": m.group(1), "mac": m.group(2).replace("-", ":").lower()})
        return arp

    def get_stats(self) -> Dict[str, Any]:
        return dict(self._stats)
