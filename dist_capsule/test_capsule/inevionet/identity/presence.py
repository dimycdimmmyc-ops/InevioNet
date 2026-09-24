"""InevioNet Presence Manager."""
import time
import threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

from ..core.logger import get_logger

logger = get_logger("inevionet.identity.presence")


class PresenceStatus(str, Enum):
    ONLINE = "online"
    AWAY = "away"
    BUSY = "busy"
    OFFLINE = "offline"
    UNKNOWN = "unknown"


@dataclass
class PresenceRecord:
    device_id: str
    status: PresenceStatus = PresenceStatus.UNKNOWN
    last_seen: float = 0.0
    last_heartbeat: float = 0.0
    heartbeat_count: int = 0
    location: Optional[Dict[str, float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.last_seen == 0.0:
            self.last_seen = time.time()

    def update_heartbeat(self, status=PresenceStatus.ONLINE):
        self.last_heartbeat = time.time()
        self.last_seen = time.time()
        self.status = status
        self.heartbeat_count += 1

    @property
    def age_sec(self):
        return time.time() - self.last_seen

    @property
    def is_online(self):
        return self.age_sec < 60 and self.status == PresenceStatus.ONLINE

    @property
    def is_recent(self):
        return self.age_sec < 3600


class PresenceManager:
    def __init__(self, online_timeout_sec=60.0, recent_timeout_sec=3600.0):
        self.online_timeout_sec = online_timeout_sec
        self.recent_timeout_sec = recent_timeout_sec
        self.records: Dict[str, PresenceRecord] = {}
        self._lock = threading.Lock()

    def heartbeat(self, device_id, status=PresenceStatus.ONLINE,
                  location=None, metadata=None):
        with self._lock:
            if device_id not in self.records:
                self.records[device_id] = PresenceRecord(device_id=device_id)
            record = self.records[device_id]
            record.update_heartbeat(status)
            if location:
                record.location = location
            if metadata:
                record.metadata.update(metadata)

    def set_status(self, device_id, status):
        with self._lock:
            if device_id in self.records:
                self.records[device_id].status = status
                self.records[device_id].last_seen = time.time()

    def get(self, device_id):
        with self._lock:
            return self.records.get(device_id)

    def get_online(self):
        with self._lock:
            now = time.time()
            return [r for r in self.records.values()
                    if (now - r.last_seen) < self.online_timeout_sec
                    and r.status == PresenceStatus.ONLINE]

    def get_recent(self):
        with self._lock:
            now = time.time()
            return [r for r in self.records.values()
                    if (now - r.last_seen) < self.recent_timeout_sec]

    def is_online(self, device_id):
        record = self.get(device_id)
        if not record:
            return False
        return record.is_online

    def remove(self, device_id):
        with self._lock:
            if device_id in self.records:
                del self.records[device_id]
                return True
            return False

    def cleanup(self):
        with self._lock:
            now = time.time()
            to_remove = [did for did, r in self.records.items()
                         if (now - r.last_seen) > self.recent_timeout_sec * 2]
            for did in to_remove:
                del self.records[did]
            if to_remove:
                logger.info(f"Cleaned up {len(to_remove)} presence records")

    def get_stats(self):
        with self._lock:
            online = sum(1 for r in self.records.values() if r.is_online)
            recent = sum(1 for r in self.records.values() if r.is_recent)
            return {
                "total": len(self.records),
                "online": online,
                "recent": recent,
                "offline": len(self.records) - online,
            }

    def __repr__(self):
        return f"PresenceManager(records={len(self.records)})"


if __name__ == "__main__":
    print("Testing PresenceManager...")
    manager = PresenceManager()
    for i in range(5):
        manager.heartbeat(f"dev_{i}", PresenceStatus.ONLINE)
    manager.heartbeat("dev_5", PresenceStatus.AWAY)
    print(f"Records: {len(manager.records)}")
    online = manager.get_online()
    print(f"Online: {len(online)}")
    manager.set_status("dev_0", PresenceStatus.BUSY)
    record = manager.get("dev_0")
    print(f"dev_0 status: {record.status.value}")
    stats = manager.get_stats()
    print(f"Stats: {stats}")
    print("OK")
