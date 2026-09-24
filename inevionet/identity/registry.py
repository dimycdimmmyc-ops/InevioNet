"""InevioNet Device Registry."""
import time
import json
import threading
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field

from .device_id import DeviceID, DeviceType, DeviceRole
from .identity import DeviceIdentity
from ..core.logger import get_logger
from ..core.constants import DataPaths

logger = get_logger("inevionet.identity.registry")


@dataclass
class DeviceRecord:
    device_id: str
    identity: Optional[DeviceIdentity] = None
    public_info: Dict[str, Any] = field(default_factory=dict)
    first_seen: float = 0.0
    last_seen: float = 0.0
    seen_count: int = 0
    trust_score: float = 0.5
    is_local: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.first_seen == 0.0:
            self.first_seen = time.time()
        self.last_seen = self.first_seen

    def touch(self):
        self.last_seen = time.time()
        self.seen_count += 1

    @property
    def age_hours(self):
        return (time.time() - self.first_seen) / 3600

    @property
    def is_active(self):
        return (time.time() - self.last_seen) < 3600

    def to_dict(self):
        return {
            "device_id": self.device_id,
            "public_info": self.public_info,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "seen_count": self.seen_count,
            "trust_score": self.trust_score,
            "is_local": self.is_local,
            "metadata": self.metadata,
        }


class DeviceRegistry:
    def __init__(self, max_devices=10000, persist=True):
        self.max_devices = max_devices
        self.persist = persist
        self._lock = threading.RLock()
        self.devices: Dict[str, DeviceRecord] = {}
        self._by_nickname: Dict[str, str] = {}
        self._by_type: Dict[DeviceType, List[str]] = {}
        self.local_device_id: Optional[str] = None
        self.local_identity: Optional[DeviceIdentity] = None
        self._on_device_added: List[Callable] = []
        self._on_device_removed: List[Callable] = []
        self._on_device_updated: List[Callable] = []
        if persist:
            self._load()

    def register_local(self, identity):
        with self._lock:
            device_id = identity.device_id.device_id
            record = DeviceRecord(
                device_id=device_id, identity=identity,
                public_info=identity.export_public(),
                is_local=True, trust_score=1.0)
            self.devices[device_id] = record
            self.local_device_id = device_id
            self.local_identity = identity
            if identity.device_id.nickname:
                self._by_nickname[identity.device_id.nickname] = device_id
            dt = identity.device_id.device_type
            if dt not in self._by_type:
                self._by_type[dt] = []
            self._by_type[dt].append(device_id)
            if self.persist:
                self._save()
            logger.info(f"Local device registered: {device_id}")
            return device_id

    def register_peer(self, identity_or_info, trust_score=0.5):
        with self._lock:
            if isinstance(identity_or_info, DeviceIdentity):
                device_id = identity_or_info.device_id.device_id
                public_info = identity_or_info.export_public()
            elif isinstance(identity_or_info, dict):
                device_id = identity_or_info.get("device_id", "")
                public_info = identity_or_info
            else:
                raise ValueError(f"Unknown type: {type(identity_or_info)}")
            if not device_id:
                raise ValueError("device_id cannot be empty")
            if device_id in self.devices:
                record = self.devices[device_id]
                record.touch()
                record.trust_score = (record.trust_score + trust_score) / 2
                for cb in self._on_device_updated:
                    try:
                        cb(record)
                    except Exception as e:
                        logger.error(f"Callback error: {e}")
                return device_id
            record = DeviceRecord(
                device_id=device_id, public_info=public_info,
                trust_score=trust_score, is_local=False)
            self.devices[device_id] = record
            nickname = public_info.get("nickname")
            if nickname:
                self._by_nickname[nickname] = device_id
            dt_str = public_info.get("device_type", "unknown")
            try:
                dt = DeviceType(dt_str)
            except ValueError:
                dt = DeviceType.UNKNOWN
            if dt not in self._by_type:
                self._by_type[dt] = []
            self._by_type[dt].append(device_id)
            if len(self.devices) > self.max_devices:
                self._prune()
            for cb in self._on_device_added:
                try:
                    cb(record)
                except Exception as e:
                    logger.error(f"Callback error: {e}")
            if self.persist:
                self._save()
            logger.info(f"Peer registered: {device_id}")
            return device_id

    def get(self, device_id):
        with self._lock:
            return self.devices.get(device_id)

    def get_by_nickname(self, nickname):
        with self._lock:
            did = self._by_nickname.get(nickname)
            if did:
                return self.devices.get(did)
            return None

    def get_by_type(self, device_type):
        with self._lock:
            dids = self._by_type.get(device_type, [])
            return [self.devices[d] for d in dids if d in self.devices]

    def get_active(self, max_age_sec=3600):
        with self._lock:
            now = time.time()
            return [r for r in self.devices.values()
                    if (now - r.last_seen) < max_age_sec]

    def get_all(self):
        with self._lock:
            return list(self.devices.values())

    def get_local(self):
        if self.local_device_id:
            return self.devices.get(self.local_device_id)
        return None

    def update_trust(self, device_id, new_trust):
        with self._lock:
            if device_id in self.devices:
                self.devices[device_id].trust_score = max(0.0, min(1.0, new_trust))
                if self.persist:
                    self._save()

    def touch(self, device_id):
        with self._lock:
            if device_id in self.devices:
                self.devices[device_id].touch()

    def remove(self, device_id):
        with self._lock:
            if device_id not in self.devices:
                return False
            record = self.devices[device_id]
            nickname = record.public_info.get("nickname")
            if nickname and nickname in self._by_nickname:
                del self._by_nickname[nickname]
            dt_str = record.public_info.get("device_type", "unknown")
            try:
                dt = DeviceType(dt_str)
                if dt in self._by_type and device_id in self._by_type[dt]:
                    self._by_type[dt].remove(device_id)
            except ValueError:
                pass
            del self.devices[device_id]
            for cb in self._on_device_removed:
                try:
                    cb(record)
                except Exception as e:
                    logger.error(f"Callback error: {e}")
            if self.persist:
                self._save()
            return True

    def _prune(self):
        sorted_devices = sorted(self.devices.items(),
                                key=lambda x: x[1].last_seen, reverse=True)
        target = int(self.max_devices * 0.8)
        to_keep = dict(sorted_devices[:target])
        removed = [d for d in self.devices if d not in to_keep]
        for device_id in removed:
            if device_id == self.local_device_id:
                continue
            del self.devices[device_id]
        if removed:
            logger.info(f"Pruned {len(removed)} old devices")
            self._rebuild_indexes()

    def _rebuild_indexes(self):
        self._by_nickname.clear()
        self._by_type.clear()
        for device_id, record in self.devices.items():
            nickname = record.public_info.get("nickname")
            if nickname:
                self._by_nickname[nickname] = device_id
            dt_str = record.public_info.get("device_type", "unknown")
            try:
                dt = DeviceType(dt_str)
            except ValueError:
                dt = DeviceType.UNKNOWN
            if dt not in self._by_type:
                self._by_type[dt] = []
            self._by_type[dt].append(device_id)

    def on_device_added(self, callback):
        self._on_device_added.append(callback)

    def on_device_removed(self, callback):
        self._on_device_removed.append(callback)

    def on_device_updated(self, callback):
        self._on_device_updated.append(callback)

    def get_stats(self):
        with self._lock:
            by_type = {}
            for dt, dids in self._by_type.items():
                by_type[dt.value] = len(dids)
            active = sum(1 for r in self.devices.values() if r.is_active)
            return {
                "total_devices": len(self.devices),
                "active_devices": active,
                "local_device": self.local_device_id,
                "by_type": by_type,
                "max_devices": self.max_devices,
            }

    def _get_state_file(self):
        path = DataPaths.get_state_dir()
        path.mkdir(parents=True, exist_ok=True)
        return path / "device_registry.json"

    def _save(self):
        try:
            with self._lock:
                data = {
                    "local_device_id": self.local_device_id,
                    "devices": {did: r.to_dict() for did, r in self.devices.items()
                                if not r.is_local},
                    "saved_at": time.time(),
                }
            with open(self._get_state_file(), "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Save error: {e}")

    def _load(self):
        try:
            path = self._get_state_file()
            if not path.exists():
                return
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            with self._lock:
                for device_id, record_data in data.get("devices", {}).items():
                    record = DeviceRecord(
                        device_id=device_id,
                        public_info=record_data.get("public_info", {}),
                        first_seen=record_data.get("first_seen", 0),
                        last_seen=record_data.get("last_seen", 0),
                        seen_count=record_data.get("seen_count", 0),
                        trust_score=record_data.get("trust_score", 0.5),
                        is_local=False)
                    self.devices[device_id] = record
                self._rebuild_indexes()
                logger.info(f"Loaded {len(self.devices)} devices")
        except Exception as e:
            logger.error(f"Load error: {e}")

    def __repr__(self):
        return f"DeviceRegistry(devices={len(self.devices)}, local={self.local_device_id})"


if __name__ == "__main__":
    print("Testing DeviceRegistry...")
    registry = DeviceRegistry(persist=False)
    identity = DeviceIdentity.create(DeviceType.SERVER, nickname="MyServer")
    local_id = registry.register_local(identity)
    print(f"Local ID: {local_id}")
    for i in range(5):
        peer = DeviceIdentity.create(
            DeviceType.DRONE if i % 2 == 0 else DeviceType.SENSOR,
            nickname=f"Peer-{i}")
        peer_id = registry.register_peer(peer, trust_score=0.7)
    stats = registry.get_stats()
    print(f"Total devices: {stats['total_devices']}")
    print(f"By type: {stats['by_type']}")
    by_nick = registry.get_by_nickname("Peer-2")
    print(f"By nickname 'Peer-2': {by_nick.device_id if by_nick else 'None'}")
    print("OK")
