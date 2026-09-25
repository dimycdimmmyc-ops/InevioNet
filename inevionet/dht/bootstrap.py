"""InevioNet DHT Bootstrap - своя bootstrap без чужих сервисов.

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
