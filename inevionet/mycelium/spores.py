"""InevioNet Spores - автономные агенты распространения."""
import time
import json
import threading
import random
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from ..core.logger import get_logger
from ..core.crypto import random_id
from ..core.constants import DataPaths

logger = get_logger("inevionet.mycelium.spores")


@dataclass
class Spore:
    """Спора - ретрансляционный агент."""
    spore_id: str = ""
    node_id: str = ""
    target_network: str = ""
    method: str = ""
    viability: float = 0.5
    timestamp: float = 0.0
    last_used: float = 0.0
    ttl: float = 3600.0
    cache: List[bytes] = field(default_factory=list)
    max_cache_size: int = 10
    retransmissions: int = 0
    bytes_cached: int = 0
    bytes_retransmitted: int = 0

    # P16: capsule payload
    capsule_code: bytes = b""
    capsule_target: str = ""
    capsule_method: str = "auto"
    capsule_version: str = "1.0.0"
    parent_capsule_id: str = ""
    generation: int = 0

    # P38: map data (щупальце)
    map_data: Dict[str, Any] = field(default_factory=dict)
    probe_ttl: int = 5
    probe_time: float = 0.0
    is_probe: bool = False

    # P92b: профиль сети (от разведчиков)
    network_profile: Dict[str, Any] = field(default_factory=dict)
    profile_updated: float = 0.0

    def __post_init__(self):
        if not self.spore_id:
            self.spore_id = random_id("spore", 8)
        if self.timestamp == 0.0:
            self.timestamp = time.time()
        if self.last_used == 0.0:
            self.last_used = time.time()

    @property
    def age(self):
        return time.time() - self.timestamp

    @property
    def remaining_life(self):
        return max(0.0, self.ttl - self.age)

    def is_alive(self):
        if self.remaining_life <= 0:
            return False
        if self.viability < 0.1:
            return False
        return True

    def can_retransmit(self):
        return self.is_alive() and len(self.cache) > 0

    def add_to_cache(self, data):
        if not self.is_alive():
            return False
        if len(self.cache) >= self.max_cache_size:
            removed = self.cache.pop(0)
            self.bytes_cached -= len(removed)
        self.cache.append(data)
        self.bytes_cached += len(data)
        self.last_used = time.time()
        return True

    def pop_from_cache(self):
        if not self.cache:
            return None
        data = self.cache.pop(0)
        self.bytes_cached -= len(data)
        self.bytes_retransmitted += len(data)
        self.retransmissions += 1
        self.last_used = time.time()
        self.viability -= 0.01
        return data

    def tick(self, hours=1.0):
        decay = 0.05 * hours
        self.viability = max(0.0, self.viability - decay)

    def mark_success(self):
        """P12-Fix-3a: retransmit успешен — восстанавливаем viability."""
        self.viability = min(1.0, self.viability + 0.05)
        self.last_used = time.time()

    def mark_failure(self):
        """P12-Fix-3a: retransmit неуспешен — снижаем viability."""
        self.viability = max(0.0, self.viability - 0.05)
        self.last_used = time.time()

    def to_dict(self):
        return {
            "spore_id": self.spore_id, "node_id": self.node_id,
            "target_network": self.target_network, "method": self.method,
            "viability": self.viability, "timestamp": self.timestamp,
            "last_used": self.last_used, "ttl": self.ttl,
            "cache_size": len(self.cache),
            "retransmissions": self.retransmissions,
            "network_profile": self.network_profile,
            "profile_updated": self.profile_updated,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            spore_id=data.get("spore_id", ""),
            node_id=data.get("node_id", ""),
            target_network=data.get("target_network", ""),
            method=data.get("method", ""),
            viability=data.get("viability", 0.5),
            timestamp=data.get("timestamp", time.time()),
            last_used=data.get("last_used", time.time()),
            ttl=data.get("ttl", 3600.0),
            network_profile=data.get("network_profile", {}),
            profile_updated=data.get("profile_updated", 0.0))

    def __repr__(self):
        return (f"Spore({self.spore_id[:8]}, network={self.target_network}, "
                f"viability={self.viability:.2f}, cache={len(self.cache)})")


class SporeManager:
    """Управление спорами."""

    def __init__(self, max_spores=10000, persist=True):
        self.max_spores = max_spores
        self.persist = persist
        self.spores: Dict[str, Spore] = {}
        self._lock = threading.Lock()
        if persist:
            self._load()

    def create(self, node_id, target_network, method="generic",
               viability=None, ttl=3600.0):
        if viability is None:
            viability = random.uniform(0.3, 0.9)
        spore = Spore(node_id=node_id, target_network=target_network,
                      method=method, viability=viability, ttl=ttl)
        with self._lock:
            if len(self.spores) >= self.max_spores:
                self._cleanup_oldest(100)
            self.spores[spore.spore_id] = spore
        if self.persist:
            self._save()
        return spore

    def get(self, spore_id):
        with self._lock:
            return self.spores.get(spore_id)

    def get_by_network(self, network):
        with self._lock:
            return [s for s in self.spores.values()
                    if s.target_network == network and s.is_alive()]

    def get_alive(self):
        with self._lock:
            return [s for s in self.spores.values() if s.is_alive()]

    def spread(self, data, source_node=""):
        count = 0
        with self._lock:
            spores = list(self.spores.values())
        for spore in spores:
            if spore.is_alive() and spore.node_id != source_node:
                if spore.add_to_cache(data):
                    count += 1
        if self.persist and count > 0:
            self._save()
        return count

    def retransmit(self, exclude_node=""):
        data_list = []
        with self._lock:
            spores = list(self.spores.values())
        for spore in spores:
            if spore.can_retransmit() and spore.node_id != exclude_node:
                data = spore.pop_from_cache()
                if data:
                    data_list.append(data)
        if self.persist and data_list:
            self._save()
        return data_list

    def create_probe(self, node_id, target_network, ttl=5):
        """P38: create probe-spore with map."""
        spore = Spore(
            node_id=node_id, target_network=target_network,
            method="probe", ttl=600.0, viability=1.0,
        )
        spore.probe_ttl = ttl
        spore.is_probe = True
        spore.probe_time = time.time()
        with self._lock:
            if len(self.spores) >= self.max_spores:
                self._cleanup_oldest(100)
            self.spores[spore.spore_id] = spore
        if self.persist:
            self._save()
        return spore

    def merge_map(self, spore_id, map_data):
        """P38: merge map from spore."""
        spore = self.get(spore_id)
        if not spore:
            return False
        spore.map_data = map_data or {}
        spore.probe_time = time.time()
        if self.persist:
            self._save()
        return True

    def set_profile(self, spore_id, profile):
        """P92b: сохранить профиль сети в споре."""
        spore = self.get(spore_id)
        if not spore:
            return False
        spore.network_profile = dict(profile or {})
        spore.profile_updated = time.time()
        if self.persist:
            self._save()
        return True

    def get_profile(self, spore_id):
        """P92b: профиль сети из споры."""
        spore = self.get(spore_id)
        return dict(spore.network_profile) if spore else {}

    def set_profile_all(self, profile):
        """P92b: обновить профиль всем живым спорам."""
        n = 0
        with self._lock:
            for s in self.spores.values():
                if s.is_alive():
                    s.network_profile = dict(profile or {})
                    s.profile_updated = time.time()
                    n += 1
        if self.persist and n:
            self._save()
        return n

    def get_any_profile(self):
        """P92b: последний непустой профиль от спор."""
        best = None
        best_ts = 0.0
        with self._lock:
            for s in self.spores.values():
                if s.network_profile and s.profile_updated > best_ts:
                    best = dict(s.network_profile)
                    best_ts = s.profile_updated
        return best or {}

    def get_maps(self):
        """P38: all maps from spores."""
        with self._lock:
            return {
                sid: s.map_data for sid, s in self.spores.items()
                if s.map_data
            }

    def get_probes(self):
        """P38: all probe-spores."""
        with self._lock:
            return [s for s in self.spores.values() if s.is_probe and s.is_alive()]

    def tick_all(self, hours=1.0):
        with self._lock:
            for spore in self.spores.values():
                spore.tick(hours)

    def cleanup(self):
        with self._lock:
            dead = [sid for sid, s in self.spores.items() if not s.is_alive()]
            for sid in dead:
                del self.spores[sid]
        if self.persist and dead:
            self._save()
        return len(dead)

    def _cleanup_oldest(self, count):
        sorted_spores = sorted(self.spores.items(), key=lambda x: x[1].timestamp)
        for sid, _ in sorted_spores[:count]:
            del self.spores[sid]

    def get_stats(self):
        with self._lock:
            alive = [s for s in self.spores.values() if s.is_alive()]
            by_network = {}
            by_method = {}
            total_cache = 0
            for s in alive:
                by_network[s.target_network] = by_network.get(s.target_network, 0) + 1
                by_method[s.method] = by_method.get(s.method, 0) + 1
                total_cache += len(s.cache)
            return {
                "total": len(self.spores), "alive": len(alive),
                "dead": len(self.spores) - len(alive),
                "by_network": by_network, "by_method": by_method,
                "total_cached_packets": total_cache,
                "total_retransmissions": sum(s.retransmissions for s in alive),
            }

    def _get_state_file(self):
        path = DataPaths.get_state_dir()
        path.mkdir(parents=True, exist_ok=True)
        return path / "spores.json"

    def _save(self):
        try:
            with self._lock:
                data = {sid: s.to_dict() for sid, s in self.spores.items()}
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
                for sid, sdata in data.items():
                    spore = Spore.from_dict(sdata)
                    if spore.is_alive():
                        self.spores[sid] = spore
        except Exception as e:
            logger.error(f"Load error: {e}")

    def __repr__(self):
        return f"SporeManager(total={len(self.spores)})"


if __name__ == "__main__":
    print("Testing SporeManager...")
    mgr = SporeManager(persist=False)
    for i in range(5):
        mgr.create(node_id=f"node_{i}",
                   target_network=random.choice(["5G", "WiFi", "Satellite"]),
                   method="HTTP")
    stats = mgr.get_stats()
    print(f"Created: {stats['total']} spores, alive: {stats['alive']}")
    count = mgr.spread(b"Test data 1", source_node="external")
    count += mgr.spread(b"Test data 2", source_node="external")
    print(f"Spread to {count} spores")
    data = mgr.retransmit(exclude_node="external")
    print(f"Retransmitted: {len(data)} packets")
    for _ in range(20):
        mgr.tick_all(hours=1.0)
    stats = mgr.get_stats()
    print(f"After tick: alive={stats['alive']}, dead={stats['dead']}")
    removed = mgr.cleanup()
    print(f"Cleaned up: {removed}")
    print("SporeManager module OK")
