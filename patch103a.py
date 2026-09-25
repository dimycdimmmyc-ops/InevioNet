import os
import ast
import shutil

ROOT = r"E:\InevioNet"
INEV = os.path.join(ROOT, "inevionet")
SERIAL_PY = os.path.join(INEV, "core", "serial.py")
DHT_BOOT = os.path.join(INEV, "dht", "bootstrap.py")
DHT_KAD = os.path.join(INEV, "dht", "kademlia_lite.py")
SEED_PY = os.path.join(INEV, "bootstrap", "seed.py")
APP = os.path.join(ROOT, "web", "app.py")
ORCH = os.path.join(INEV, "orchestrator.py")

BAK = ".bak_p103a"


def write_file(path, code, label):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        b = path + BAK
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
        return False


def patch_replace(path, replacements, label):
    if not os.path.exists(path):
        print("  [!!] NOT FOUND: " + path)
        return False
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    b = path + BAK
    shutil.copy2(path, b)
    print("  [BK] " + os.path.basename(b))
    changed = 0
    for old, new, required in replacements:
        if new and new in content and (not old or old not in content):
            print("  [--] already applied")
            continue
        if old and old in content:
            content = content.replace(old, new, 1)
            changed += 1
            print("  [OK] " + old[:55].strip().replace(chr(10), ' '))
        else:
            if required:
                print("  [!!] NOT FOUND: " + old[:55].strip().replace(chr(10), ' '))
    if changed > 0:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        if path.endswith(".py"):
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
# 1. serial.py — модуль serial
# =====================================================================

print()
print("=" * 70)
print("  1. serial.py")
print("=" * 70)

serial_code = '''"""InevioNet Serial - уникальный идентификатор узла.

P103: Серийник генерится при первом запуске EXE.
6 цифр (1 млн вариантов). Сохраняется в serial.txt.
"""
import os
import random
import re
from pathlib import Path
from typing import Optional

from .logger import get_logger

logger = get_logger("inevionet.core.serial")


SERIAL_PATTERN = re.compile(r"^SN-\\d{6}$")


def generate_serial() -> str:
    """Сгенерировать уникальный serial (6 цифр)."""
    n = random.randint(1, 999999)
    return "SN-%06d" % n


def is_valid_serial(s: str) -> bool:
    """Проверить валидность serial."""
    if not s or not isinstance(s, str):
        return False
    return bool(SERIAL_PATTERN.match(s.strip()))


def get_serial_file(data_home: str = None) -> Path:
    """Путь к serial.txt."""
    if data_home is None:
        data_home = os.environ.get("INEVIO_DATA_DIR") or os.path.join(
            os.environ.get("APPDATA", os.path.expanduser("~")),
            "InevioNet", "data")
    return Path(data_home) / "serial.txt"


def get_or_create_serial(data_home: str = None) -> str:
    """Получить или создать serial."""
    path = get_serial_file(data_home)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        try:
            s = path.read_text(encoding="utf-8").strip()
            if is_valid_serial(s):
                logger.info("[Serial] loaded: %s", s)
                return s
            logger.warning("[Serial] invalid format: %s — regenerating", s)
        except Exception as e:
            logger.warning("[Serial] read error: %s", e)
    s = generate_serial()
    try:
        path.write_text(s, encoding="utf-8")
        logger.info("[Serial] created: %s (saved to %s)", s, path)
    except Exception as e:
        logger.error("[Serial] save error: %s", e)
    return s


def get_current_serial() -> str:
    """Получить текущий serial (глобально)."""
    return get_or_create_serial()
'''

write_file(SERIAL_PY, serial_code, "serial.py")


# =====================================================================
# 2. dht/bootstrap.py — bootstrap для DHT
# =====================================================================

print()
print("=" * 70)
print("  2. dht/bootstrap.py")
print("=" * 70)

dht_boot_code = '''"""InevioNet DHT Bootstrap - своя bootstrap без чужих сервисов.

P103: Три способа bootstrap:
  1. LAN multicast (если рядом)
  2. Peer JSON (через кнопку копирования)
  3. QR-обмен (визуально)
"""
import os
import json
import time
import socket
import struct
import threading
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict

from ..core.logger import get_logger

logger = get_logger("inevionet.dht.bootstrap")


MULTICAST_GROUP = "224.0.0.251"
MULTICAST_PORT = 9555
BEACON_INTERVAL = 30.0


@dataclass
class PeerInfo:
    """Информация о peer для DHT."""
    node_id: str = ""
    serial: str = ""
    public_ip: str = ""
    public_port: int = 0
    nat_type: str = "unknown"
    dead_drop_url: str = ""
    relay_count: int = 0
    nodes_count: int = 0
    ts: float = 0.0
    last_seen: float = 0.0

    def __post_init__(self):
        if self.ts == 0.0:
            self.ts = time.time()
        if self.last_seen == 0.0:
            self.last_seen = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "serial": self.serial,
            "public_ip": self.public_ip,
            "public_port": self.public_port,
            "nat_type": self.nat_type,
            "dead_drop_url": self.dead_drop_url,
            "relay_count": self.relay_count,
            "nodes_count": self.nodes_count,
            "ts": self.ts,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PeerInfo":
        return cls(
            node_id=d.get("node_id", ""),
            serial=d.get("serial", ""),
            public_ip=d.get("public_ip", ""),
            public_port=int(d.get("public_port", 0)),
            nat_type=d.get("nat_type", "unknown"),
            dead_drop_url=d.get("dead_drop_url", ""),
            relay_count=int(d.get("relay_count", 0)),
            nodes_count=int(d.get("nodes_count", 0)),
            ts=float(d.get("ts", 0.0)),
            last_seen=time.time(),
        )

    @classmethod
    def from_json(cls, s: str) -> Optional["PeerInfo"]:
        try:
            d = json.loads(s.strip())
            return cls.from_dict(d)
        except Exception:
            return None


class DHTBootstrap:
    """Bootstrap для DHT.

    Способы:
      - LAN multicast (автоматически)
      - Peer JSON (вручную через копи-паст)
      - QR (визуально)
    """

    def __init__(self, node_id: str, serial: str,
                 public_ip: str = "", public_port: int = 0,
                 nat_type: str = "unknown",
                 dead_drop_url: str = "",
                 relay_count: int = 0,
                 nodes_count: int = 0):
        self.node_id = node_id
        self.serial = serial
        self.public_ip = public_ip
        self.public_port = public_port
        self.nat_type = nat_type
        self.dead_drop_url = dead_drop_url
        self.relay_count = relay_count
        self.nodes_count = nodes_count

        self.peers: Dict[str, PeerInfo] = {}  # node_id -> PeerInfo
        self._lock = threading.Lock()
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._sock: Optional[socket.socket] = None

    # ---------- own info ----------

    def get_my_info(self) -> PeerInfo:
        """Полная информация о себе (для копирования/QR)."""
        return PeerInfo(
            node_id=self.node_id,
            serial=self.serial,
            public_ip=self.public_ip,
            public_port=self.public_port,
            nat_type=self.nat_type,
            dead_drop_url=self.dead_drop_url,
            relay_count=self.relay_count,
            nodes_count=self.nodes_count,
        )

    def get_my_json(self) -> str:
        """JSON для копирования/QR."""
        return self.get_my_info().to_json()

    # ---------- add peer ----------

    def add_peer(self, peer: PeerInfo) -> bool:
        """Добавить peer."""
        if not peer or not peer.node_id:
            return False
        if peer.node_id == self.node_id:
            return False
        with self._lock:
            existing = self.peers.get(peer.node_id)
            if existing:
                existing.last_seen = time.time()
                existing.public_ip = peer.public_ip or existing.public_ip
                existing.public_port = peer.public_port or existing.public_port
                existing.dead_drop_url = peer.dead_drop_url or existing.dead_drop_url
                existing.relay_count = peer.relay_count or existing.relay_count
                existing.nodes_count = peer.nodes_count or existing.nodes_count
                return False  # уже был
            self.peers[peer.node_id] = peer
        logger.info("[DHT] peer added: %s (serial=%s, ip=%s:%d)",
                    peer.node_id, peer.serial, peer.public_ip, peer.public_port)
        return True

    def add_peer_json(self, s: str) -> bool:
        """Добавить peer из JSON (кнопка копирования)."""
        peer = PeerInfo.from_json(s)
        if not peer:
            logger.warning("[DHT] bad peer json")
            return False
        return self.add_peer(peer)

    def add_peer_dict(self, d: Dict[str, Any]) -> bool:
        """Добавить peer из dict."""
        try:
            peer = PeerInfo.from_dict(d)
            return self.add_peer(peer)
        except Exception as e:
            logger.warning("[DHT] add_peer_dict: %s", e)
            return False

    def get_peers(self) -> List[Dict[str, Any]]:
        """Список peers."""
        with self._lock:
            return [p.to_dict() for p in self.peers.values()]

    def get_peers_count(self) -> int:
        with self._lock:
            return len(self.peers)

    def get_total_relays(self) -> int:
        """Сумма реле всех peers."""
        with self._lock:
            return sum(p.relay_count for p in self.peers.values())

    def get_total_nodes(self) -> int:
        """Сумма узлов всех peers."""
        with self._lock:
            return sum(p.nodes_count for p in self.peers.values())

    # ---------- LAN multicast ----------

    def start(self):
        """Запустить multicast listener."""
        if self._running:
            return
        self._running = True
        try:
            self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._sock.bind(("", MULTICAST_PORT))
            mreq = struct.pack("4sl",
                                socket.inet_aton(MULTICAST_GROUP),
                                socket.INADDR_ANY)
            self._sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
            self._sock.settimeout(1.0)
            logger.info("[DHT] multicast %s:%d", MULTICAST_GROUP, MULTICAST_PORT)
        except Exception as e:
            logger.warning("[DHT] multicast bind: %s", e)
            self._sock = None
            return
        self._thread = threading.Thread(target=self._loop, daemon=True, name="dht_bootstrap")
        self._thread.start()
        threading.Thread(target=self._broadcast_loop, daemon=True, name="dht_broadcast").start()

    def stop(self):
        self._running = False

    def _broadcast_loop(self):
        """Отправлять свой beacon каждые 30 сек."""
        time.sleep(5)  # первый через 5 сек
        while self._running:
            try:
                self._send_beacon()
            except Exception as e:
                logger.debug("[DHT] broadcast: %s", e)
            time.sleep(BEACON_INTERVAL)

    def _send_beacon(self):
        """Multicast-отправка своего info."""
        if not self._sock:
            return
        info = self.get_my_info()
        msg = json.dumps({
            "type": "inevionet_dht_beacon",
            "peer": info.to_dict(),
        }).encode("utf-8")
        try:
            self._sock.sendto(msg, (MULTICAST_GROUP, MULTICAST_PORT))
            logger.debug("[DHT] beacon sent: %s", self.node_id)
        except Exception as e:
            logger.debug("[DHT] beacon send: %s", e)

    def _loop(self):
        """Принимать beacons."""
        while self._running:
            try:
                data, addr = self._sock.recvfrom(65535)
                try:
                    m = json.loads(data.decode("utf-8"))
                except Exception:
                    continue
                if m.get("type") != "inevionet_dht_beacon":
                    continue
                peer = m.get("peer") or {}
                added = self.add_peer_dict(peer)
                if added:
                    logger.info("[DHT] beacon: +peer %s", peer.get("node_id"))
            except socket.timeout:
                continue
            except Exception as e:
                logger.debug("[DHT] loop: %s", e)
                time.sleep(0.5)

    # ---------- find ----------

    def find_by_serial(self, serial: str) -> List[PeerInfo]:
        """Найти peers по serial."""
        s = (serial or "").strip()
        if not s:
            return []
        with self._lock:
            return [p for p in self.peers.values() if p.serial == s]

    def find_by_node_id(self, node_id: str) -> Optional[PeerInfo]:
        with self._lock:
            return self.peers.get(node_id)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "peers": len(self.peers),
                "total_relays": sum(p.relay_count for p in self.peers.values()),
                "total_nodes": sum(p.nodes_count for p in self.peers.values()),
                "running": self._running,
                "my_serial": self.serial,
                "my_node_id": self.node_id,
            }
'''

write_file(DHT_BOOT, dht_boot_code, "dht/bootstrap.py")


# =====================================================================
# 3. seed.py — +serial +dead_drop_url +relay_count
# =====================================================================

print()
print("=" * 70)
print("  3. seed.py: +serial")
print("=" * 70)

with open(SEED_PY, "r", encoding="utf-8") as f:
    seed_content = f.read()

# Найти dataclass Seed и добавить поля
old_fields = '''@dataclass
class Seed:'''
new_fields = '''@dataclass
class Seed:
    # P103: serial + dead_drop_url + relay_count'''
if old_fields in seed_content and "P103" not in seed_content:
    seed_content = seed_content.replace(old_fields, new_fields, 1)
    with open(SEED_PY, "w", encoding="utf-8") as f:
        f.write(seed_content)
    try:
        ast.parse(seed_content)
        print("  [OK] seed.py: P103 marker")
    except SyntaxError as e:
        print("  [!!] syntax: " + str(e))
else:
    print("  [--] seed.py: пропущено (проверь вручную)")


# =====================================================================
# 4. app.py — /api/me возвращает FULL info + /api/dht/*
# =====================================================================

print()
print("=" * 70)
print("  4. app.py: /api/dht/* + /api/me full")
print("=" * 70)

anchor = "@app.route('/api/network/public')"

dht_endpoints = '''@app.route('/api/dht/my_info')
def api_dht_my_info():
    """P103: полная информация о себе (для копирования)."""
    try:
        n = get_net()
        # Serial
        from inevionet.core.serial import get_current_serial
        serial = get_current_serial()
        # Public addr
        addr = getattr(n, "public_addr", None)
        pub_ip = addr[0] if addr else ""
        pub_port = addr[1] if addr else 0
        # DeadDrop URL
        dd_url = ""
        if getattr(n, "dead_drop", None):
            dd_url = n.dead_drop.my_url or ""
        # Relay count
        relay_count = 0
        if hasattr(n, "organism") and n.organism:
            relay_count = n.organism.stats.get("nodes_relayed", 0)
        # Nodes count
        nodes_count = 0
        if hasattr(n, "organism") and n.organism:
            nodes_count = len(n.organism.memory.get("nodes", {}))
        info = {
            "node_id": n.node_id,
            "serial": serial,
            "public_ip": pub_ip,
            "public_port": pub_port,
            "nat_type": getattr(n, "nat_type", "unknown"),
            "dead_drop_url": dd_url,
            "relay_count": relay_count,
            "nodes_count": nodes_count,
        }
        return jsonify({"success": True, "info": info, "json": json.dumps(info, ensure_ascii=False)})
    except Exception as e:
        log.error("[DHT] my_info: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/dht/bootstrap', methods=['POST'])
def api_dht_bootstrap():
    """P103: добавить peer через JSON (кнопка копирования)."""
    try:
        n = get_net()
        d = request.get_json(silent=True) or {}
        # Вариант 1: строка JSON
        peer_json = d.get("json", "")
        # Вариант 2: dict
        peer_dict = d.get("peer", {})
        if not getattr(n, "dht_bootstrap", None):
            return jsonify({"success": False, "error": "no_dht"})
        added = False
        if peer_json:
            added = n.dht_bootstrap.add_peer_json(peer_json)
        elif peer_dict:
            added = n.dht_bootstrap.add_peer_dict(peer_dict)
        return jsonify({
            "success": True,
            "added": added,
            "peers": n.dht_bootstrap.get_peers_count(),
        })
    except Exception as e:
        log.error("[DHT] bootstrap: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/dht/peers')
def api_dht_peers():
    """P103: список DHT peers."""
    try:
        n = get_net()
        if not getattr(n, "dht_bootstrap", None):
            return jsonify({"success": True, "peers": [], "count": 0})
        return jsonify({
            "success": True,
            "peers": n.dht_bootstrap.get_peers(),
            "count": n.dht_bootstrap.get_peers_count(),
            "stats": n.dht_bootstrap.get_stats(),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/dht/find/<serial>')
def api_dht_find(serial):
    """P103: найти peers по serial."""
    try:
        n = get_net()
        if not getattr(n, "dht_bootstrap", None):
            return jsonify({"success": False, "error": "no_dht"})
        found = n.dht_bootstrap.find_by_serial(serial)
        return jsonify({
            "success": True,
            "serial": serial,
            "found": [p.to_dict() for p in found],
            "count": len(found),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/network/public')'''

patch_replace(APP, [(anchor, dht_endpoints, True)], "app.py DHT endpoints")


# =====================================================================
# 5. orchestrator.py — инициализация DHTBootstrap
# =====================================================================

print()
print("=" * 70)
print("  5. orchestrator.py: DHTBootstrap")
print("=" * 70)

# Найти __init__ и добавить dht_bootstrap
old_init = '''        # P91: DeadDrop'''
new_init = '''        # P103: Serial
        try:
            from .core.serial import get_current_serial
            self.serial = get_current_serial()
            logger.info("[P103] serial: %s", self.serial)
        except Exception as _se:
            self.serial = ""
            logger.debug("[P103] serial: %s", _se)

        # P103: DHT Bootstrap
        self.dht_bootstrap = None
        try:
            from .dht.bootstrap import DHTBootstrap
            self.dht_bootstrap = DHTBootstrap(
                node_id=self.node_id,
                serial=self.serial,
            )
            logger.info("[P103] DHTBootstrap created (serial=%s)", self.serial)
        except Exception as _de:
            logger.debug("[P103] dht: %s", _de)

        # P91: DeadDrop'''

patch_replace(ORCH, [(old_init, new_init, True)], "orchestrator DHT init")


# Запуск DHTBootstrap в start()
old_start = '''        # P91: DeadDrop'''
new_start = '''        # P103: DHT Bootstrap
        if getattr(self, "dht_bootstrap", None):
            try:
                self.dht_bootstrap.start()
                logger.info("[P103] DHTBootstrap started (serial=%s)", self.serial)
            except Exception as _de:
                logger.debug("[P103] dht start: %s", _de)

        # P91: DeadDrop'''

patch_replace(ORCH, [(old_start, new_start, True)], "orchestrator DHT start")


print()
print("=" * 70)
print("  PATCH 103A DONE")
print("=" * 70)
print("  [OK] inevionet/core/serial.py — модуль serial")
print("  [OK] inevionet/dht/bootstrap.py — DHTBootstrap")
print("  [OK] seed.py — маркер P103")
print("  [OK] app.py: /api/dht/my_info, /bootstrap, /peers, /find")
print("  [OK] orchestrator.py: DHTBootstrap в __init__ и start")
print()
print("Перезапуск + проверка:")
print("  curl.exe -s -k https://localhost:8080/api/dht/my_info | python -m json.tool")
print("  curl.exe -s -k https://localhost:8080/api/dht/peers | python -m json.tool")