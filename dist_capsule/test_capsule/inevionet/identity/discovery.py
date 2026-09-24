"""InevioNet Discovery - broadcast/multicast device discovery."""
import time
import threading
import socket
import json
from typing import Dict, List, Optional, Any, Callable, Set
from dataclasses import dataclass, field
from enum import Enum

from .device_id import DeviceID, DeviceType
from .identity import DeviceIdentity
from .registry import DeviceRegistry
from ..core.logger import get_logger
from ..core.crypto import random_id, verify_signature

logger = get_logger("inevionet.identity.discovery")


class DiscoveryMethod(str, Enum):
    BROADCAST = "broadcast"
    MULTICAST = "multicast"
    BEACON = "beacon"
    DHT = "dht"
    MANUAL = "manual"


@dataclass
class DeviceAnnouncement:
    device_id: str
    device_type: str
    nickname: Optional[str]
    signing_public_key: str
    exchange_public_key: str
    endpoint: Optional[str] = None
    timestamp: float = 0.0
    signature: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def to_bytes(self):
        data = {
            "device_id": self.device_id, "device_type": self.device_type,
            "nickname": self.nickname,
            "signing_public_key": self.signing_public_key,
            "exchange_public_key": self.exchange_public_key,
            "endpoint": self.endpoint, "timestamp": self.timestamp,
            "metadata": self.metadata,
        }
        return json.dumps(data, sort_keys=True).encode()

    @classmethod
    def from_bytes(cls, data):
        try:
            obj = json.loads(data.decode())
            return cls(**obj)
        except Exception as e:
            raise ValueError(f"Invalid announcement: {e}")

    def sign(self, identity):
        data = self.to_bytes()
        signature = identity.sign(data)
        self.signature = signature.hex()

    def verify(self):
        try:
            signing_pub = bytes.fromhex(self.signing_public_key)
            signature = bytes.fromhex(self.signature)
            data = self.to_bytes()
            return verify_signature(signing_pub, signature, data)
        except Exception:
            return False


class DiscoveryEngine:
    MULTICAST_GROUP = "239.1.2.3"
    DISCOVERY_PORT = 9555
    BEACON_INTERVAL = 5.0

    def __init__(self, identity, registry, broadcast_port=9555,
                 enable_multicast=True, enable_beacon=True):
        self.identity = identity
        self.registry = registry
        self.broadcast_port = broadcast_port
        self.enable_multicast = enable_multicast
        self.enable_beacon = enable_beacon
        self._running = False
        self._listen_thread: Optional[threading.Thread] = None
        self._beacon_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self.discovered: Dict[str, DeviceAnnouncement] = {}
        self._on_discovered: List[Callable] = []
        logger.info(f"DiscoveryEngine created: port={broadcast_port}")

    def start(self):
        if self._running:
            return
        self._running = True
        self._listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self._listen_thread.start()
        if self.enable_beacon:
            self._beacon_thread = threading.Thread(target=self._beacon_loop, daemon=True)
            self._beacon_thread.start()
        logger.info("DiscoveryEngine started")

    def stop(self):
        self._running = False
        if self._listen_thread:
            self._listen_thread.join(timeout=2)
        if self._beacon_thread:
            self._beacon_thread.join(timeout=2)
        logger.info("DiscoveryEngine stopped")

    def announce(self, endpoint=None):
        announcement = DeviceAnnouncement(
            device_id=self.identity.device_id.device_id,
            device_type=self.identity.device_id.device_type.value,
            nickname=self.identity.device_id.nickname,
            signing_public_key=self.identity.signing_keypair.public_key.hex(),
            exchange_public_key=self.identity.exchange_keypair.public_key.hex(),
            endpoint=endpoint,
            metadata={"role": self.identity.device_id.role.value})
        announcement.sign(self.identity)
        self._send_broadcast(announcement.to_bytes())
        if self.enable_multicast:
            self._send_multicast(announcement.to_bytes())

    def _listen_loop(self):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            sock.settimeout(1.0)
            try:
                sock.bind(("", self.broadcast_port))
            except OSError as e:
                logger.error(f"Bind error on {self.broadcast_port}: {e}")
                return
            if self.enable_multicast:
                try:
                    mreq = socket.inet_aton(self.MULTICAST_GROUP) + socket.inet_aton("0.0.0.0")
                    sock.setsockopt(socket.IPPROTO_IP, socket.IP_ADD_MEMBERSHIP, mreq)
                except Exception as e:
                    logger.warning(f"Multicast join error: {e}")
            logger.info(f"Discovery listening on port {self.broadcast_port}")
            while self._running:
                try:
                    data, addr = sock.recvfrom(65536)
                    self._handle_announcement(data, addr)
                except socket.timeout:
                    continue
                except Exception as e:
                    if self._running:
                        logger.debug(f"Recv error: {e}")
            sock.close()
        except Exception as e:
            logger.error(f"Listen loop error: {e}")

    def _handle_announcement(self, data, addr):
        try:
            announcement = DeviceAnnouncement.from_bytes(data)
            if announcement.device_id == self.identity.device_id.device_id:
                return
            if not announcement.verify():
                logger.warning(f"Invalid signature from {announcement.device_id}")
                return
            announcement.endpoint = f"{addr[0]}:{addr[1]}"
            with self._lock:
                is_new = announcement.device_id not in self.discovered
                self.discovered[announcement.device_id] = announcement
            self.registry.register_peer({
                "device_id": announcement.device_id,
                "device_type": announcement.device_type,
                "nickname": announcement.nickname,
                "signing_public_key": announcement.signing_public_key,
                "exchange_public_key": announcement.exchange_public_key,
                "endpoint": announcement.endpoint,
                "metadata": announcement.metadata,
            })
            if is_new:
                logger.info(f"Discovered device: {announcement.device_id} at {addr}")
                for cb in self._on_discovered:
                    try:
                        cb(announcement)
                    except Exception as e:
                        logger.error(f"Callback error: {e}")
        except Exception as e:
            logger.debug(f"Announcement handling error: {e}")

    def _beacon_loop(self):
        while self._running:
            try:
                self.announce()
                time.sleep(self.BEACON_INTERVAL)
            except Exception as e:
                logger.debug(f"Beacon error: {e}")
                time.sleep(1.0)

    def _send_broadcast(self, data):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(data, ("<broadcast>", self.broadcast_port))
            sock.close()
        except Exception as e:
            logger.debug(f"Broadcast error: {e}")

    def _send_multicast(self, data):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
            sock.sendto(data, (self.MULTICAST_GROUP, self.broadcast_port))
            sock.close()
        except Exception as e:
            logger.debug(f"Multicast error: {e}")

    def get_discovered(self):
        with self._lock:
            return list(self.discovered.values())

    def get_discovered_ids(self):
        with self._lock:
            return set(self.discovered.keys())

    def is_discovered(self, device_id):
        with self._lock:
            return device_id in self.discovered

    def on_discovered(self, callback):
        self._on_discovered.append(callback)

    def get_stats(self):
        with self._lock:
            return {
                "discovered_count": len(self.discovered),
                "broadcast_port": self.broadcast_port,
                "multicast_enabled": self.enable_multicast,
                "beacon_enabled": self.enable_beacon,
                "running": self._running,
            }

    def __repr__(self):
        return f"DiscoveryEngine(port={self.broadcast_port}, discovered={len(self.discovered)})"


if __name__ == "__main__":
    print("Testing DiscoveryEngine...")
    identity = DeviceIdentity.create(DeviceType.SERVER, nickname="TestServer")
    registry = DeviceRegistry(persist=False)
    registry.register_local(identity)
    announcement = DeviceAnnouncement(
        device_id=identity.device_id.device_id,
        device_type=identity.device_id.device_type.value,
        nickname=identity.device_id.nickname,
        signing_public_key=identity.signing_keypair.public_key.hex(),
        exchange_public_key=identity.exchange_keypair.public_key.hex(),
        endpoint="192.168.1.100:9555")
    announcement.sign(identity)
    data = announcement.to_bytes()
    print(f"Announcement size: {len(data)} bytes")
    restored = DeviceAnnouncement.from_bytes(data)
    valid = restored.verify()
    print(f"Signature valid: {valid}")
    engine = DiscoveryEngine(identity, registry, broadcast_port=9556)
    print(f"Engine: {engine}")
    stats = engine.get_stats()
    print(f"Stats: {stats}")
    print("OK")
