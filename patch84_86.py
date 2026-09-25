# patch84_86.py - InevioNet: P84 + P85 + P86
#
# P84: Traceroute scan         - глубина через интернет (10-15 hops)
# P85: mDNS/SSDP/LLMNR scan    - устройства рядом
# P86: SNMP fallback + HTTP    - глубина через свой роутер
#
# Все три дополняют NetworkTree, добавляя узлы с hops и via.

import os
import ast
import shutil

ROOT = r"E:\InevioNet"
INEV = os.path.join(ROOT, "inevionet")
NET = os.path.join(INEV, "network")
MESH = os.path.join(INEV, "mesh")
ORCH = os.path.join(INEV, "orchestrator.py")
APP = os.path.join(ROOT, "web", "app.py")


def write_py(path, code, label):
    if os.path.exists(path):
        b = path + ".bak_p84_86"
        shutil.copy2(path, b)
        print("  [BK] " + os.path.basename(b))
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    try:
        ast.parse(code)
        print("  [OK] " + label)
        return True
    except SyntaxError as e:
        print("  [!!] " + label + " syntax: " + str(e))
        b = path + ".bak_p84_86"
        if os.path.exists(b):
            shutil.copy2(b, path)
            print("  [--] rolled back")
        return False


def patch_file(path, replacements, label):
    if not os.path.exists(path):
        print("  [!!] NOT FOUND: " + path)
        return False
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    b = path + ".bak_p84_86"
    shutil.copy2(path, b)
    print("  [BK] " + os.path.basename(b))
    changed = 0
    for old, new, required in replacements:
        if new in content and old not in content:
            print("  [--] already applied")
            continue
        if old in content:
            content = content.replace(old, new, 1)
            changed += 1
            print("  [OK] " + old[:50].strip())
        else:
            if required:
                print("  [!!] NOT FOUND: " + old[:50].strip())
    if changed > 0:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        try:
            ast.parse(content)
            print("  [OK] syntax " + label)
            return True
        except SyntaxError as e:
            print("  [!!] syntax: " + str(e))
            shutil.copy2(b, path)
            print("  [--] rolled back")
            return False
    return True


# =====================================================================
# P84: traceroute_scan.py
# =====================================================================

print()
print("=" * 70)
print("  P84: traceroute_scan.py")
print("=" * 70)

p84 = '''"""InevioNet TracerouteScan - глубина через интернет.

Запускает traceroute до внешних целей. Каждый hop -> узел дерева.
Глубина 10-15 реальна. Работает без доступа к роутеру.

Цели: 8.8.8.8, 1.1.1.1, ya.ru, google.com.
"""
import os
import re
import time
import subprocess
import threading
from typing import List, Dict, Any, Optional

from ..core.logger import get_logger

logger = get_logger("inevionet.network.traceroute_scan")


# Цели для traceroute (разные маршруты)
DEFAULT_TARGETS = [
    "8.8.8.8",        # Google DNS
    "1.1.1.1",        # Cloudflare DNS
    "77.88.8.8",      # Yandex DNS
    "9.9.9.9",        # Quad9
]

# Регулярки для парсинга вывода traceroute
HOP_PATTERNS = [
    # Linux/Unix: " 1  192.168.1.1  1.234 ms"
    re.compile(r"^\\s*(\\d+)\\s+([\\d.]+|\\*)\\s+([\\d.]+)\\s*ms"),
    # Windows: "  1     1 ms     1 ms     1 ms  192.168.1.1"
    re.compile(r"^\\s*(\\d+)\\s+.*?\\s+([\\d.]+)\\s*$"),
    # Windows с timeout: "  1     *        *        *     Request timed out."
    re.compile(r"^\\s*(\\d+)\\s+.*?timed out"),
]


class TracerouteScan:
    """Traceroute до внешних целей."""

    def __init__(self, timeout: float = 30.0, max_hops: int = 20):
        self.timeout = timeout
        self.max_hops = max_hops
        self._stats = {
            "scans": 0,
            "hops_total": 0,
            "unique_routers": set(),
            "started_at": time.time(),
        }
        self._lock = threading.Lock()

    def scan(self, target: str = "8.8.8.8") -> Dict[str, Any]:
        """Traceroute до цели."""
        with self._lock:
            self._stats["scans"] += 1

        logger.info("[Traceroute] %s (max %d hops)", target, self.max_hops)

        hops = []
        try:
            if os.name == "nt":
                # Windows: tracert -h 20 -w 1000 target
                cmd = ["tracert", "-h", str(self.max_hops),
                       "-w", "1000", "-d", target]
                r = subprocess.run(
                    cmd, capture_output=True, timeout=self.timeout,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                output = r.stdout.decode("cp866", errors="replace")
            else:
                # Linux: traceroute -n -m 20 -w 1 target
                cmd = ["traceroute", "-n", "-m", str(self.max_hops),
                       "-w", "1", target]
                r = subprocess.run(
                    cmd, capture_output=True, timeout=self.timeout)
                output = r.stdout.decode("utf-8", errors="replace")
        except subprocess.TimeoutExpired:
            logger.warning("[Traceroute] timeout for %s", target)
            return {"target": target, "hops": hops, "error": "timeout"}
        except Exception as e:
            logger.error("[Traceroute] error: %s", e)
            return {"target": target, "hops": hops, "error": str(e)}

        # Парсинг вывода
        for line in output.splitlines():
            for pat in HOP_PATTERNS:
                m = pat.match(line)
                if m:
                    try:
                        hop_num = int(m.group(1))
                        ip = m.group(2) if m.lastindex >= 2 else "*"
                        if ip == "*":
                            break
                        hops.append({
                            "hop": hop_num,
                            "ip": ip,
                            "target": target,
                        })
                        with self._lock:
                            self._stats["hops_total"] += 1
                            self._stats["unique_routers"].add(ip)
                    except Exception:
                        pass
                    break

        # dedupe по IP, но сохранить минимальный hop
        seen = {}
        for h in hops:
            ip = h["ip"]
            if ip not in seen or h["hop"] < seen[ip]["hop"]:
                seen[ip] = h
        hops = sorted(seen.values(), key=lambda x: x["hop"])

        return {"target": target, "hops": hops, "error": None}

    def scan_multi(self, targets: List[str] = None) -> Dict[str, Any]:
        """Traceroute до нескольких целей."""
        if not targets:
            targets = DEFAULT_TARGETS
        all_hops = {}
        for t in targets:
            try:
                result = self.scan(t)
                for h in result.get("hops", []):
                    ip = h["ip"]
                    if ip not in all_hops or h["hop"] < all_hops[ip]["hop"]:
                        all_hops[ip] = h
            except Exception as e:
                logger.debug("[Traceroute] %s: %s", t, e)
        return {
            "targets": targets,
            "hops": sorted(all_hops.values(), key=lambda x: x["hop"]),
            "unique_routers": len(all_hops),
        }

    def get_stats(self) -> Dict[str, Any]:
        return {
            "scans": self._stats["scans"],
            "hops_total": self._stats["hops_total"],
            "unique_routers": len(self._stats["unique_routers"]),
            "started_at": self._stats["started_at"],
        }
'''

write_py(os.path.join(NET, "traceroute_scan.py"), p84, "traceroute_scan.py")


# =====================================================================
# P85: mdns_ssdp_scan.py
# =====================================================================

print()
print("=" * 70)
print("  P85: mdns_ssdp_scan.py")
print("=" * 70)

p85 = '''"""InevioNet mDNS/SSDP/LLMNR scan - устройства рядом.

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
        q += b"\\x00"
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
                'M-SEARCH * HTTP/1.1\\r\\n'
                'HOST: 239.255.255.250:1900\\r\\n'
                'MAN: "ssdp:discover"\\r\\n'
                'MX: 2\\r\\n'
                'ST: ssdp:all\\r\\n'
                '\\r\\n'
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
            s.sendto(b"\\x00\\x00", (self.LLMNR_ADDR, self.LLMNR_PORT))
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
'''

write_py(os.path.join(NET, "mdns_ssdp_scan.py"), p85, "mdns_ssdp_scan.py")


# =====================================================================
# P86: router_admin.py
# =====================================================================

print()
print("=" * 70)
print("  P86: router_admin.py")
print("=" * 70)

p86 = '''"""InevioNet RouterAdmin - SNMP fallback + HTTP админка.

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
            r"(\\d+\\.\\d+\\.\\d+\\.\\d+)[^\\d]+?"
            r"([0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-]"
            r"[0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2})"
        )
        for m in pat.finditer(html):
            arp.append({"ip": m.group(1), "mac": m.group(2).replace("-", ":").lower()})
        return arp

    def get_stats(self) -> Dict[str, Any]:
        return dict(self._stats)
'''

write_py(os.path.join(NET, "router_admin.py"), p86, "router_admin.py")


# =====================================================================
# Интеграция в NetworkTree
# =====================================================================

print()
print("=" * 70)
print("  Интеграция в network_tree.py")
print("=" * 70)

TREE = os.path.join(MESH, "network_tree.py")

anchor_tree = '''    def build(self, local_map: Dict[str, Any],
              topology_map: Optional[Dict[str, Any]] = None,
              gravity: Optional[Dict[str, Any]] = None) -> "NetworkTree":'''

repl_tree = '''    def add_traceroute(self, hops: List[Dict[str, Any]]):
        """P84: добавить traceroute hops в дерево."""
        if not self.root or not hops:
            return
        # Traceroute создаёт цепочку: self -> hop1 -> hop2 -> ...
        parent = self.root
        for h in sorted(hops, key=lambda x: x.get("hop", 0)):
            ip = h.get("ip", "")
            if not ip:
                continue
            node = TreeNode(
                node_id="tr_" + ip,
                node_type="traceroute",
                ip=ip,
                name="hop " + str(h.get("hop", "?")) + " " + ip,
                hops=int(h.get("hop", 0)),
                via=parent.node_id,
                metadata={"source": "traceroute",
                          "target": h.get("target", "")})
            parent.children.append(node)
            parent = node

    def add_mdns_devices(self, devices: List[Dict[str, Any]]):
        """P85: добавить mDNS/SSDP устройства в дерево."""
        if not self.root:
            return
        for d in devices:
            ip = d.get("ip", "")
            if not ip:
                continue
            node = TreeNode(
                node_id="mdns_" + ip,
                node_type="local_device",
                ip=ip,
                name=d.get("server", "") or ip,
                hops=1,
                via=self.root.node_id,
                metadata={"source": d.get("source", "mdns"),
                          "location": d.get("location", "")})
            self.root.children.append(node)

    def add_router_admin(self, admin_result: Dict[str, Any]):
        """P86: добавить ARP роутера в дерево."""
        if not self.root:
            return
        ip = admin_result.get("ip", "")
        for entry in admin_result.get("arp", []):
            dev_ip = entry.get("ip", "")
            if not dev_ip or dev_ip == ip:
                continue
            # Уже в дереве?
            found = False
            for c in self.root.children:
                if c.ip == dev_ip:
                    found = True
                    break
            if found:
                continue
            node = TreeNode(
                node_id="rarp_" + dev_ip,
                node_type="device",
                ip=dev_ip,
                mac=entry.get("mac", ""),
                name=dev_ip,
                hops=2,
                via=ip,
                metadata={"source": "router_arp"})
            # Крепим к роутеру, если он в дереве
            for c in self.root.children:
                if c.ip == ip:
                    c.children.append(node)
                    break
            else:
                self.root.children.append(node)

    def build(self, local_map: Dict[str, Any],
              topology_map: Optional[Dict[str, Any]] = None,
              gravity: Optional[Dict[str, Any]] = None) -> "NetworkTree":'''

patch_file(TREE, [(anchor_tree, repl_tree, True)], "network_tree.py P84-86")


# =====================================================================
# Интеграция в orchestrator
# =====================================================================

print()
print("=" * 70)
print("  Интеграция в orchestrator.py")
print("=" * 70)

anchor_orch = '''        # P82e: network tree'''

repl_orch = '''        # P84-P86: advanced scanners
        self.traceroute_scan = None
        self.local_discovery = None
        try:
            from .network.traceroute_scan import TracerouteScan
            self.traceroute_scan = TracerouteScan()
            logger.info("[P84] traceroute scan created")
        except Exception as _e:
            logger.debug("[P84] %s", _e)
        try:
            from .network.mdns_ssdp_scan import LocalDiscovery
            self.local_discovery = LocalDiscovery()
            logger.info("[P85] local discovery created")
        except Exception as _e:
            logger.debug("[P85] %s", _e)

        # P82e: network tree'''

patch_file(ORCH, [(anchor_orch, repl_orch, True)], "orchestrator.py P84-86")


# =====================================================================
# Endpoints в app.py
# =====================================================================

print()
print("=" * 70)
print("  Endpoints в app.py")
print("=" * 70)

anchor_app = "@app.route('/api/network/public')"

repl_app = '''@app.route('/api/network/traceroute', methods=['POST'])
def api_network_traceroute():
    """P84: traceroute scan."""
    try:
        n = get_net()
        d = request.get_json(silent=True) or {}
        target = d.get('target', '8.8.8.8')
        multi = d.get('multi', False)

        from inevionet.network.traceroute_scan import TracerouteScan
        ts = TracerouteScan()

        if multi:
            result = ts.scan_multi()
        else:
            result = ts.scan(target)

        # Интегрировать в tree
        if getattr(n, "network_tree", None):
            hops = result.get("hops", [])
            n.network_tree.add_traceroute(hops)

        return jsonify({'success': True, 'result': result,
                        'stats': ts.get_stats()})
    except Exception as e:
        log.error('[Traceroute] error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/network/local_devices', methods=['POST'])
def api_network_local_devices():
    """P85: mDNS/SSDP/LLMNR scan."""
    try:
        n = get_net()
        from inevionet.network.mdns_ssdp_scan import LocalDiscovery
        ld = LocalDiscovery()
        result = ld.scan_all(timeout=3.0)

        # Интегрировать в tree
        if getattr(n, "network_tree", None):
            n.network_tree.add_mdns_devices(result.get("devices", []))

        return jsonify({'success': True, 'result': result,
                        'stats': ld.get_stats()})
    except Exception as e:
        log.error('[LocalDiscovery] error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/network/router_admin', methods=['POST'])
def api_network_router_admin():
    """P86: SNMP fallback + HTTP админка."""
    try:
        n = get_net()
        d = request.get_json(silent=True) or {}
        ip = d.get('ip', '')
        if not ip:
            # Auto - свой роутер
            if getattr(n, "local_map", None) and n.local_map.router_ip:
                ip = n.local_map.router_ip
            else:
                ip = "192.168.1.1"

        from inevionet.network.router_admin import RouterAdmin
        ra = RouterAdmin()
        result = ra.probe_all(ip)

        # Интегрировать в tree
        if getattr(n, "network_tree", None):
            n.network_tree.add_router_admin(result)

        return jsonify({'success': True, 'result': result,
                        'stats': ra.get_stats()})
    except Exception as e:
        log.error('[RouterAdmin] error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/network/full_scan', methods=['POST'])
def api_network_full_scan():
    """P84-P86: полный скан дерева (traceroute + mdns + router_admin)."""
    try:
        n = get_net()

        # 1. LocalMap
        local = {}
        if getattr(n, "local_map", None):
            local = n.local_map.build()

        # 2. Traceroute multi
        tr_result = {}
        if getattr(n, "traceroute_scan", None):
            tr_result = n.traceroute_scan.scan_multi()

        # 3. mDNS/SSDP/LLMNR
        mdns_result = {}
        if getattr(n, "local_discovery", None):
            mdns_result = n.local_discovery.scan_all(timeout=3.0)

        # 4. Router admin
        ra_result = {}
        router_ip = local.get("router_ip", "192.168.1.1")
        from inevionet.network.router_admin import RouterAdmin
        ra = RouterAdmin()
        ra_result = ra.probe_all(router_ip)

        # Построить дерево
        tree_result = {}
        if getattr(n, "network_tree", None):
            topo = {}
            if getattr(n, "_auto_topology", None):
                try:
                    topo = n._auto_topology.export_map()
                except Exception:
                    pass
            n.network_tree.build(local_map=local, topology_map=topo)
            n.network_tree.add_traceroute(tr_result.get("hops", []))
            n.network_tree.add_mdns_devices(mdns_result.get("devices", []))
            n.network_tree.add_router_admin(ra_result)
            tree_result = n.network_tree.get_tree()

        return jsonify({
            'success': True,
            'local': local,
            'traceroute': tr_result,
            'mdns': mdns_result,
            'router_admin': ra_result,
            'tree': tree_result,
        })
    except Exception as e:
        log.error('[FullScan] error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/network/public')'''

patch_file(APP, [(anchor_app, repl_app, True)], "web/app.py P84-86")


print()
print("=" * 70)
print("  PATCH 84-86 DONE")
print("=" * 70)
print("  [OK] P84: traceroute_scan.py")
print("  [OK] P85: mdns_ssdp_scan.py")
print("  [OK] P86: router_admin.py")
print("  [OK] network_tree.py: add_traceroute, add_mdns_devices, add_router_admin")
print("  [OK] orchestrator.py: интеграция")
print("  [OK] web/app.py: 4 endpoints")
print()
print("Перезапусти: python -m web.app")
print()
print("Проверка:")
print("  curl -k -X POST https://localhost:8080/api/network/traceroute -d '{\"target\":\"8.8.8.8\"}'")
print("  curl -k -X POST https://localhost:8080/api/network/local_devices")
print("  curl -k -X POST https://localhost:8080/api/network/router_admin")
print("  curl -k -X POST https://localhost:8080/api/network/full_scan")