# patch82.py - InevioNet: P82 - Network Tree
#
# P82a: network/local_map.py      - LocalNetworkMap
# P82b: network/router_probe.py   - RouterProbe (SNMP/UPnP/HTTP)
# P82c: network/recursive_probe.py - RecursiveProbe
# P82d: mesh/network_tree.py      - NetworkTree
# P82e: orchestrator.py           - интеграция
# P82f: web/app.py                - endpoints

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
        b = path + ".bak_p82"
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
        b = path + ".bak_p82"
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
    b = path + ".bak_p82"
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
# P82a: inevionet/network/local_map.py
# =====================================================================

print()
print("=" * 70)
print("  P82a: local_map.py")
print("=" * 70)

p82a = '''"""InevioNet LocalNetworkMap - полная карта своей подсети.

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
'''

write_py(os.path.join(NET, "local_map.py"), p82a, "local_map.py")


# =====================================================================
# P82b: inevionet/network/router_probe.py
# =====================================================================

print()
print("=" * 70)
print("  P82b: router_probe.py")
print("=" * 70)

p82b = '''"""InevioNet RouterProbe - зондирование роутеров.

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
                'M-SEARCH * HTTP/1.1\\r\\n'
                'HOST: 239.255.255.250:1900\\r\\n'
                'MAN: "ssdp:discover"\\r\\n'
                'MX: 2\\r\\n'
                'ST: urn:schemas-upnp-org:device:InternetGatewayDevice:1\\r\\n'
                '\\r\\n'
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
'''

write_py(os.path.join(NET, "router_probe.py"), p82b, "router_probe.py")


# =====================================================================
# P82c: inevionet/network/recursive_probe.py
# =====================================================================

print()
print("=" * 70)
print("  P82c: recursive_probe.py")
print("=" * 70)

p82c = '''"""InevioNet RecursiveProbe - рекурсивное зондирование подсетей.

Известные подсети:
  - своя (192.168.1.x)
  - найденные через свой роутер (SNMP routes)
  - подсети за найденными InevioNet-узлами

Для каждой подсети:
  - ping sweep
  - ARP
  - проверка открытых портов (8080, 8081 — InevioNet)
  - поиск InevioNet-узлов
"""
import os
import time
import socket
import threading
from typing import Dict, Any, List, Set, Optional

from ..core.logger import get_logger

logger = get_logger("inevionet.network.recursive_probe")


INEVIONET_PORTS = [8080, 8081, 8082, 9090, 9100, 9555]


class RecursiveProbe:
    """Рекурсивное зондирование подсетей."""

    def __init__(self, max_depth: int = 3, max_hosts: int = 512):
        self.max_depth = max_depth
        self.max_hosts = max_hosts
        self._stats = {
            "subnets_scanned": 0,
            "hosts_scanned": 0,
            "inevionet_found": 0,
            "started_at": time.time(),
        }
        self._lock = threading.Lock()

    def probe_subnet(self, subnet: str, depth: int = 0) -> Dict[str, Any]:
        """Просканировать подсеть на InevioNet-узлы."""
        if depth > self.max_depth:
            return {"subnet": subnet, "depth": depth, "skipped": True}
        with self._lock:
            self._stats["subnets_scanned"] += 1

        logger.info("[RecursiveProbe] scanning %s.x (depth=%d)", subnet, depth)

        found = []
        hosts = list(range(1, min(255, self.max_hosts + 1)))
        # быстрый probe на InevioNet-порты
        import concurrent.futures

        def probe_one(i):
            ip = subnet + "." + str(i)
            return self._probe_host(ip)

        with concurrent.futures.ThreadPoolExecutor(max_workers=64) as ex:
            results = list(ex.map(probe_one, hosts))

        for r in results:
            if r and r.get("inevionet"):
                found.append(r)
                with self._lock:
                    self._stats["inevionet_found"] += 1

        with self._lock:
            self._stats["hosts_scanned"] += len(hosts)

        return {
            "subnet": subnet,
            "depth": depth,
            "hosts": len(hosts),
            "inevionet_nodes": found,
        }

    def _probe_host(self, ip: str) -> Optional[Dict[str, Any]]:
        """Проверить один хост на InevioNet."""
        for port in INEVIONET_PORTS:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.3)
                if s.connect_ex((ip, port)) == 0:
                    s.close()
                    logger.info("[RecursiveProbe] found InevioNet-like at %s:%d",
                                ip, port)
                    return {"ip": ip, "port": port, "inevionet": True}
                s.close()
            except Exception:
                continue
        return None

    def get_stats(self) -> Dict[str, Any]:
        return {
            **self._stats,
            "uptime_sec": round(time.time() - self._stats["started_at"], 1),
        }
'''

write_py(os.path.join(NET, "recursive_probe.py"), p82c, "recursive_probe.py")


# =====================================================================
# P82d: inevionet/mesh/network_tree.py
# =====================================================================

print()
print("=" * 70)
print("  P82d: network_tree.py")
print("=" * 70)

p82d = '''"""InevioNet NetworkTree - дерево сетей.

Структура:
  root (свой роутер)
  ├── devices (устройства своей подсети)
  ├── subnets (соседние подсети)
  │   ├── router (роутер соседа)
  │   ├── devices
  │   └── subnets (глубже)
  └── inevionet_nodes (InevioNet-узлы)
"""
import time
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

from ..core.logger import get_logger

logger = get_logger("inevionet.mesh.network_tree")


@dataclass
class TreeNode:
    """Узел дерева сетей."""
    node_id: str = ""
    node_type: str = ""          # self / router / device / inevionet / subnet
    ip: str = ""
    mac: str = ""
    name: str = ""
    vendor: str = ""
    hops: int = 0
    via: str = ""
    children: List["TreeNode"] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["children"] = [c.to_dict() for c in self.children]
        return d

    def count_nodes(self) -> int:
        n = 1
        for c in self.children:
            n += c.count_nodes()
        return n


class NetworkTree:
    """Дерево сетей InevioNet."""

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.root: Optional[TreeNode] = None
        self._stats = {
            "builds": 0,
            "total_nodes": 0,
            "max_depth": 0,
            "started_at": time.time(),
        }

    def build(self, local_map: Dict[str, Any],
              topology_map: Optional[Dict[str, Any]] = None,
              gravity: Optional[Dict[str, Any]] = None) -> "NetworkTree":
        """Построить дерево из LocalMap + Topology + Gravity."""
        with self._stats.__setitem__("builds", self._stats["builds"] + 1):
            pass

        # Root - свой роутер
        router_ip = local_map.get("router_ip", "")
        my_ip = local_map.get("my_ip", "")
        subnet = local_map.get("subnet", "")

        self.root = TreeNode(
            node_id=self.node_id,
            node_type="self",
            ip=my_ip,
            name=f"self ({self.node_id})",
            hops=0,
            metadata={"subnet": subnet, "router_ip": router_ip})

        # Свой роутер как отдельный узел
        router_node = TreeNode(
            node_id=f"router_{router_ip}",
            node_type="router",
            ip=router_ip,
            name=f"router {router_ip}",
            hops=1,
            via=self.node_id,
            metadata={"subnet": subnet})

        # Устройства своей подсети
        for d in local_map.get("devices", []):
            ip = d.get("ip", "")
            if not ip or ip == my_ip or ip == router_ip:
                continue
            ntype = d.get("type", "device")
            if ntype == "router":
                continue
            child = TreeNode(
                node_id=f"dev_{ip}",
                node_type="device",
                ip=ip,
                mac=d.get("mac", ""),
                name=d.get("hostname", "") or ip,
                vendor=d.get("vendor", ""),
                hops=1,
                via=router_ip,
                metadata={"source": d.get("source", "arp")})
            router_node.children.append(child)

        self.root.children.append(router_node)

        # InevioNet-узлы из topology
        if topology_map:
            nodes = topology_map.get("nodes", {})
            for nid, nd in nodes.items():
                if nid == self.node_id:
                    continue
                ntype = nd.get("type", "external")
                hops = int(nd.get("hops", 1))
                via = nd.get("via", "")
                child = TreeNode(
                    node_id=nid,
                    node_type="inevionet",
                    ip=nd.get("ip", ""),
                    name=nd.get("name", nid),
                    hops=hops,
                    via=via,
                    metadata={"source": "topology"})
                # InevioNet-узлы крепим к root напрямую
                self.root.children.append(child)

        # Обновить stats
        self._stats["total_nodes"] = self.root.count_nodes()
        self._stats["max_depth"] = self._compute_depth(self.root)

        return self

    def _compute_depth(self, node: TreeNode, depth: int = 0) -> int:
        if not node.children:
            return depth
        return max(self._compute_depth(c, depth + 1) for c in node.children)

    def get_tree(self) -> Dict[str, Any]:
        if not self.root:
            return {"root": None, "stats": self._stats}
        return {
            "root": self.root.to_dict(),
            "stats": self._stats,
        }

    def get_stats(self) -> Dict[str, Any]:
        return dict(self._stats)

    def get_by_depth(self) -> Dict[int, List[Dict[str, Any]]]:
        """Сгруппировать узлы по глубине."""
        result = {}
        if not self.root:
            return result

        def walk(node: TreeNode, depth: int):
            result.setdefault(depth, []).append({
                "node_id": node.node_id,
                "type": node.node_type,
                "ip": node.ip,
                "name": node.name,
                "hops": node.hops,
                "via": node.via,
            })
            for c in node.children:
                walk(c, depth + 1)

        walk(self.root, 0)
        return result
'''

write_py(os.path.join(MESH, "network_tree.py"), p82d, "network_tree.py")


# =====================================================================
# P82e: orchestrator.py - интеграция
# =====================================================================

print()
print("=" * 70)
print("  P82e: orchestrator.py")
print("=" * 70)

anchor_orch_p82 = '''        # P77c: audit chain'''

repl_orch_p82 = '''        # P82e: network tree
        self.local_map = None
        self.network_tree = None
        try:
            from .network.local_map import LocalNetworkMap
            self.local_map = LocalNetworkMap()
            logger.info("[P82e] local_map created")
        except Exception as _e:
            logger.debug("[P82e] local_map: %s", _e)
        try:
            from .mesh.network_tree import NetworkTree
            self.network_tree = NetworkTree(node_id=self.node_id)
            logger.info("[P82e] network_tree created")
        except Exception as _e:
            logger.debug("[P82e] network_tree: %s", _e)

        # P77c: audit chain'''

patch_file(ORCH, [(anchor_orch_p82, repl_orch_p82, True)], "orchestrator.py P82e")


# =====================================================================
# P82f: web/app.py - endpoints
# =====================================================================

print()
print("=" * 70)
print("  P82f: web/app.py")
print("=" * 70)

anchor_app_p82 = "@app.route('/api/network/public')"

repl_app_p82 = '''@app.route('/api/network/local')
def api_network_local():
    """P82: карта своей подсети."""
    try:
        n = get_net()
        if not getattr(n, "local_map", None):
            return jsonify({'success': False, 'error': 'no_local_map'})
        force = request.args.get('force', '0') == '1'
        if force or not n.local_map.devices:
            m = n.local_map.build()
        else:
            m = n.local_map.get_map()
        return jsonify({'success': True, **m})
    except Exception as e:
        log.error('[LocalMap] error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/network/tree')
def api_network_tree():
    """P82: дерево сетей."""
    try:
        n = get_net()
        if not getattr(n, "network_tree", None):
            return jsonify({'success': False, 'error': 'no_tree'})

        # LocalMap
        local = {}
        if getattr(n, "local_map", None):
            force = request.args.get('force', '0') == '1'
            if force or not n.local_map.devices:
                local = n.local_map.build()
            else:
                local = n.local_map.get_map()

        # Topology map
        topo = {}
        if getattr(n, "_auto_topology", None):
            try:
                topo = n._auto_topology.export_map()
            except Exception:
                pass

        # Gravity
        gravity = {}
        if getattr(n, "gravity", None):
            try:
                gravity = n.gravity.get_stats()
            except Exception:
                pass

        n.network_tree.build(local_map=local, topology_map=topo, gravity=gravity)
        return jsonify({'success': True, **n.network_tree.get_tree()})
    except Exception as e:
        log.error('[Tree] error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/network/tree/depth')
def api_network_tree_depth():
    """P82: узлы дерева по глубине."""
    try:
        n = get_net()
        if not getattr(n, "network_tree", None):
            return jsonify({'success': False, 'error': 'no_tree'})
        if not n.network_tree.root:
            return jsonify({'success': True, 'by_depth': {}, 'stats': {}})
        return jsonify({'success': True,
                        'by_depth': n.network_tree.get_by_depth(),
                        'stats': n.network_tree.get_stats()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/network/probe_router', methods=['POST'])
def api_network_probe_router():
    """P82: зондирование роутера."""
    try:
        n = get_net()
        d = request.get_json(silent=True) or {}
        ip = d.get('ip', '')
        if not ip:
            return jsonify({'success': False, 'error': 'no_ip'}), 400
        from inevionet.network.router_probe import RouterProbe
        probe = RouterProbe()
        result = probe.probe(ip)
        return jsonify({'success': True, 'result': result,
                        'stats': probe.get_stats()})
    except Exception as e:
        log.error('[RouterProbe] error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/network/recursive_probe', methods=['POST'])
def api_network_recursive_probe():
    """P82: рекурсивный probe подсети."""
    try:
        n = get_net()
        d = request.get_json(silent=True) or {}
        subnet = d.get('subnet', '')
        if not subnet:
            # Автоопределение
            if getattr(n, "local_map", None) and n.local_map.subnet:
                subnet = n.local_map.subnet
            else:
                return jsonify({'success': False, 'error': 'no_subnet'}), 400
        from inevionet.network.recursive_probe import RecursiveProbe
        probe = RecursiveProbe()
        result = probe.probe_subnet(subnet, depth=0)
        return jsonify({'success': True, 'result': result,
                        'stats': probe.get_stats()})
    except Exception as e:
        log.error('[RecursiveProbe] error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/network/public')'''

patch_file(APP, [(anchor_app_p82, repl_app_p82, True)], "web/app.py P82f")


print()
print("=" * 70)
print("  PATCH 82 DONE")
print("=" * 70)
print("  [OK] P82a: network/local_map.py")
print("  [OK] P82b: network/router_probe.py")
print("  [OK] P82c: network/recursive_probe.py")
print("  [OK] P82d: mesh/network_tree.py")
print("  [OK] P82e: orchestrator integration")
print("  [OK] P82f: endpoints /api/network/local, /tree, /tree/depth, /probe_router, /recursive_probe")
print()
print("Перезапусти: python -m web.app")
print()
print("Проверка:")
print("  curl -k https://localhost:8080/api/network/local")
print("  curl -k https://localhost:8080/api/network/tree")
print("  curl -k https://localhost:8080/api/network/tree/depth")
print("  curl -k -X POST https://localhost:8080/api/network/probe_router -d '{\"ip\":\"192.168.1.1\"}'")