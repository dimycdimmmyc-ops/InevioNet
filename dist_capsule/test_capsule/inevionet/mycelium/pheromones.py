"""InevioNet Pheromones - феромонная маршрутизация."""
import time
import math
import json
import threading
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field

from ..core.logger import get_logger
from ..core.constants import DataPaths

logger = get_logger("inevionet.mycelium.pheromones")


@dataclass
class Pheromone:
    """Феромонная метка на маршруте."""
    source: str
    destination: str
    protocol: str
    strength: float = 1.0
    timestamp: float = 0.0
    hops: int = 0
    success_count: int = 1
    total_attempts: int = 1

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    @property
    def success_rate(self) -> float:
        if self.total_attempts == 0:
            return 0.0
        return self.success_count / self.total_attempts

    @property
    def age(self) -> float:
        return time.time() - self.timestamp

    @property
    def score(self) -> float:
        return self.strength * self.success_rate

    def reinforce(self, factor: float = 0.1):
        self.strength = min(1.0, self.strength + factor)
        self.success_count += 1
        self.total_attempts += 1
        self.timestamp = time.time()

    def mark_failure(self):
        self.total_attempts += 1
        self.strength *= 0.9
        self.strength = max(0.01, self.strength)

    def decay(self, evaporation_rate: float = 0.01):
        age = self.age
        decay_factor = math.exp(-evaporation_rate * age / 60)
        self.strength *= decay_factor
        self.strength = max(0.01, self.strength)

    def is_alive(self, max_age: float = 3600) -> bool:
        return self.strength > 0.01 and self.age < max_age

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source, "destination": self.destination,
            "protocol": self.protocol, "strength": self.strength,
            "timestamp": self.timestamp, "hops": self.hops,
            "success_count": self.success_count,
            "total_attempts": self.total_attempts,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Pheromone":
        return cls(
            source=data["source"], destination=data["destination"],
            protocol=data["protocol"], strength=data.get("strength", 1.0),
            timestamp=data.get("timestamp", time.time()),
            hops=data.get("hops", 0),
            success_count=data.get("success_count", 1),
            total_attempts=data.get("total_attempts", 1))

    def __repr__(self):
        return (f"Pheromone({self.source}->{self.destination}, "
                f"protocol={self.protocol}, strength={self.strength:.2f}, "
                f"rate={self.success_rate:.2f})")


class PheromoneEngine:
    """Движок феромонной маршрутизации."""

    def __init__(self, evaporation_rate=0.01, max_age=3600,
                 auto_evaporate=True, persist=True):
        self.evaporation_rate = evaporation_rate
        self.max_age = max_age
        self.persist = persist
        self.pheromones: Dict[str, Pheromone] = {}
        self._lock = threading.Lock()
        if persist:
            self._load()
        if auto_evaporate:
            self._start_evaporation()

    def _make_key(self, source, destination, protocol):
        return f"{source}:{destination}:{protocol}"

    def add(self, source, destination, protocol, hops=0):
        key = self._make_key(source, destination, protocol)
        with self._lock:
            if key in self.pheromones:
                self.pheromones[key].reinforce()
                self.pheromones[key].hops = min(self.pheromones[key].hops, hops)
            else:
                self.pheromones[key] = Pheromone(
                    source=source, destination=destination,
                    protocol=protocol, hops=hops)
        if self.persist:
            self._save()

    def mark_result(self, source, destination, protocol, success):
        key = self._make_key(source, destination, protocol)
        with self._lock:
            if key in self.pheromones:
                if success:
                    self.pheromones[key].reinforce()
                else:
                    self.pheromones[key].mark_failure()
            elif not success:
                p = Pheromone(source=source, destination=destination,
                              protocol=protocol, strength=0.1)
                p.total_attempts = 1
                p.success_count = 0
                self.pheromones[key] = p
        if self.persist:
            self._save()

    def get_best_protocol(self, source, destination):
        alternatives = self.get_alternatives(source, destination, limit=1)
        return alternatives[0][0] if alternatives else None

    def get_alternatives(self, source, destination, limit=5):
        candidates = []
        with self._lock:
            for phero in self.pheromones.values():
                if phero.source == source and phero.destination == destination:
                    if phero.is_alive(self.max_age):
                        candidates.append((phero.protocol, phero.score))
        candidates.sort(key=lambda x: x[1], reverse=True)
        return candidates[:limit]

    def get_all_for_destination(self, destination):
        with self._lock:
            return [p for p in self.pheromones.values()
                    if p.destination == destination and p.is_alive(self.max_age)]

    def evaporate(self):
        keys_to_remove = []
        with self._lock:
            for key, phero in self.pheromones.items():
                phero.decay(self.evaporation_rate)
                if not phero.is_alive(self.max_age):
                    keys_to_remove.append(key)
            for key in keys_to_remove:
                del self.pheromones[key]
        if self.persist and keys_to_remove:
            self._save()

    def _start_evaporation(self):
        def loop():
            while True:
                time.sleep(60)
                self.evaporate()
        thread = threading.Thread(target=loop, daemon=True)
        thread.start()

    def _get_state_file(self):
        path = DataPaths.get_state_dir()
        path.mkdir(parents=True, exist_ok=True)
        return path / "pheromones.json"

    def _save(self):
        try:
            with self._lock:
                data = {k: p.to_dict() for k, p in self.pheromones.items()}
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
                for k, v in data.items():
                    p = Pheromone.from_dict(v)
                    if p.is_alive(self.max_age):
                        self.pheromones[k] = p
        except Exception as e:
            logger.error(f"Load error: {e}")

    def get_stats(self):
        with self._lock:
            if not self.pheromones:
                return {"total": 0, "avg_strength": 0.0, "by_protocol": {}}
            by_protocol = {}
            total_strength = 0.0
            for p in self.pheromones.values():
                by_protocol[p.protocol] = by_protocol.get(p.protocol, 0) + 1
                total_strength += p.strength
            return {
                "total": len(self.pheromones),
                "avg_strength": total_strength / len(self.pheromones),
                "by_protocol": by_protocol,
            }

    def clear(self):
        with self._lock:
            self.pheromones.clear()
        if self.persist:
            self._save()

    def __repr__(self):
        return f"PheromoneEngine(pheromones={len(self.pheromones)})"


if __name__ == "__main__":
    print("Testing PheromoneEngine...")
    engine = PheromoneEngine(persist=False, auto_evaporate=False)
    engine.add("alice", "bob", "HTTPS")
    engine.add("alice", "bob", "DNS")
    engine.add("alice", "bob", "ICMP")
    print(f"Total: {engine.get_stats()['total']}")
    for _ in range(5):
        engine.mark_result("alice", "bob", "HTTPS", True)
    best = engine.get_best_protocol("alice", "bob")
    print(f"Best protocol: {best}")
    alts = engine.get_alternatives("alice", "bob")
    for proto, score in alts:
        print(f"  {proto}: {score:.3f}")
    print("PheromoneEngine module OK")
