"""InevioNet RouterProbe - зондирование роутеров.

Для каждого найденного роутера:
  - определить IP
  - SNMP walk (ARP, маршруты, DHCP)
  - UPnP (WANIPConnection)
  - HTTP админка (если без пароля)
"""
import os
import re
import time
import socket
import subprocess
import threading
from typing import Dict, Any, List, Optional
import urllib.request

from ..core.logger import get_logger

logger = get_logger("inevionet.network.router_probe")


# Регулярки для HTTP админок
ROUTER_SIGNATURES = {
    "mts": ["mts", "мтс", "mtc"],
    "keenetic": ["keenetic", "кинетик"],
    "asus": ["asus", "rt-", "zenwifi"],
    "tp-link": ["tp-link", "tplink", "archer"],
    "netis": ["netis", "netis-"],
    "xiaomi": ["xiaomi", "mi router", "miwifi"],
    "huawei": ["huawei", "honor"],
    "tenda": ["tenda"],
    "zyxel": ["zyxel"],
    "mikrotik": ["mikrotik", "routeros"],
}


def detect_vendor_from_html(html: str) -> str:
    if not html:
        return ""
    low = html.lower()
    for vendor, patterns in ROUTER_SIGNATURES.items():
        for p in patterns:
            if p in low:
                return vendor
    return ""


class RouterProbe:
    """Зондирование роутера."""

    def __init__(self, timeout: float = 3.0):
        self.timeout = timeout
        self._stats = {
            "probes": 0,
            "http_ok": 0,
            "snmp_ok": 0,
            "upnp_ok": 0,
            "vendors": {},
        }

    def probe(self, ip: str) -> Dict[str, Any]:
        """Полное зондирование роутера."""
        self._stats["probes"] += 1
        result = {
            "ip": ip,
            "vendor": "",
            "model": "",
            "firmware": "",
            "open_ports": [],
            "http_title": "",
            "snmp": False,
            "upnp": False,
            "arp_count": 0,
            "reachable": False,
        }

        # 1. Проверка reachable
        result["reachable"] = self._ping(ip)
        if not result["reachable"]:
            return result

        # 2. HTTP probe
        http_info = self._probe_http(ip)
        result.update(http_info)

        # 3. SNMP probe
        snmp_info = self._probe_snmp(ip)
        result.update(snmp_info)

        # 4. UPnP probe
        upnp_info = self._probe_upnp(ip)
        result.update(upnp_info)

        # 5. Vendor из HTML
        if result.get("http_html"):
            v = detect_vendor_from_html(result["http_html"])
            if v:
                result["vendor"] = v
                self._stats["vendors"][v] = self._stats["vendors"].get(v, 0) + 1
        # убрать html из ответа (большой)
        result.pop("http_html", None)

        return result

    def _ping(self, ip: str) -> bool:
        try:
            if os.name == "nt":
                r = subprocess.run(
                    ["ping", "-n", "1", "-w", "1000", ip],
                    capture_output=True, timeout=3,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            else:
                r = subprocess.run(["ping", "-c", "1", "-W", "1", ip],
                    capture_output=True, timeout=3)
            return r.returncode == 0
        except Exception:
            return False

    def _probe_http(self, ip: str) -> Dict[str, Any]:
        """HTTP-зонд: 80/443/8080/8443."""
        info = {"http_title": "", "http_html": "", "open_ports": []}
        ctx = None
        try:
            import ssl as _ssl
            ctx = _ssl._create_unverified_context()
        except Exception:
            pass

        for port, scheme in [(80, "http"), (443, "https"),
                             (8080, "http"), (8443, "https")]:
            url = f"{scheme}://{ip}:{port}/"
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=self.timeout, context=ctx) as r:
                    if r.status == 200:
                        html = r.read(4096).decode("utf-8", errors="replace")
                        info["open_ports"].append(port)
                        self._stats["http_ok"] += 1
                        # Title
                        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
                        if m:
                            info["http_title"] = m.group(1).strip()[:200]
                        info["http_html"] = html[:2000]
                        break
            except Exception:
                continue
        return info

    def _probe_snmp(self, ip: str) -> Dict[str, Any]:
        """SNMP-зонд (public/private/cisco)."""
        for community in ("public", "private", "cisco"):
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                s.settimeout(2.0)
                community_bytes = community.encode()
                varbind = bytes.fromhex("06082b06010201010100")
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
                        self._stats["snmp_ok"] += 1
                        return {"snmp": True, "snmp_community": community}
                except socket.timeout:
                    pass
                s.close()
            except Exception:
                pass
        return {"snmp": False}

    def _probe_upnp(self, ip: str) -> Dict[str, Any]:
        """UPnP SSDP discovery."""
        try:
            msg = (
                'M-SEARCH * HTTP/1.1\r\n'
                'HOST: 239.255.255.250:1900\r\n'
                'MAN: "ssdp:discover"\r\n'
                'MX: 2\r\n'
                'ST: urn:schemas-upnp-org:device:InternetGatewayDevice:1\r\n'
                '\r\n'
            ).encode()
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(3.0)
            s.sendto(msg, ("239.255.255.250", 1900))
            try:
                while True:
                    data, addr = s.recvfrom(4096)
                    if addr[0] == ip:
                        s.close()
                        self._stats["upnp_ok"] += 1
                        return {"upnp": True}
            except socket.timeout:
                s.close()
        except Exception as e:
            logger.debug("[RouterProbe] upnp: %s", e)
        return {"upnp": False}

    def get_stats(self) -> Dict[str, Any]:
        return dict(self._stats)
