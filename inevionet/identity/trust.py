"""InevioNet Trust Engine - Bayesian trust model."""
import time
import math
import threading
import json
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from ..core.logger import get_logger
from ..core.constants import DataPaths

logger = get_logger("inevionet.identity.trust")


class TrustLevel(str, Enum):
    UNKNOWN = "unknown"
    SUSPICIOUS = "suspicious"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERIFIED = "verified"


@dataclass
class TrustRecord:
    source_id: str
    target_id: str
    alpha: float = 1.0
    beta: float = 1.0
    direct_observations: int = 0
    recommendations: int = 0
    last_interaction: float = 0.0
    created_at: float = 0.0

    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()

    @property
    def trust_score(self):
        total = self.alpha + self.beta
        if total == 0:
            return 0.5
        return self.alpha / total

    @property
    def confidence(self):
        total = self.alpha + self.beta
        return min(1.0, total / 20.0)

    @property
    def uncertainty(self):
        return 1.0 - self.confidence

    @property
    def level(self):
        score = self.trust_score
        conf = self.confidence
        if conf < 0.2:
            return TrustLevel.UNKNOWN
        if score < 0.2:
            return TrustLevel.SUSPICIOUS
        if score < 0.4:
            return TrustLevel.LOW
        if score < 0.7:
            return TrustLevel.MEDIUM
        if score < 0.9:
            return TrustLevel.HIGH
        return TrustLevel.VERIFIED

    def record_success(self, weight=1.0):
        self.alpha += weight
        self.direct_observations += 1
        self.last_interaction = time.time()

    def record_failure(self, weight=1.0):
        self.beta += weight
        self.direct_observations += 1
        self.last_interaction = time.time()

    def apply_recommendation(self, recommender_trust, recommendation, weight=0.5):
        effective_weight = weight * recommender_trust
        if recommendation > 0.5:
            self.alpha += effective_weight * (recommendation - 0.5) * 2
        else:
            self.beta += effective_weight * (0.5 - recommendation) * 2
        self.recommendations += 1

    def decay(self, decay_rate=0.01):
        if self.last_interaction == 0:
            return
        age_hours = (time.time() - self.last_interaction) / 3600
        decay_factor = math.exp(-decay_rate * age_hours)
        self.alpha = 1.0 + (self.alpha - 1.0) * decay_factor
        self.beta = 1.0 + (self.beta - 1.0) * decay_factor

    def to_dict(self):
        return {
            "source_id": self.source_id, "target_id": self.target_id,
            "alpha": self.alpha, "beta": self.beta,
            "direct_observations": self.direct_observations,
            "recommendations": self.recommendations,
            "last_interaction": self.last_interaction,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(**data)


class TrustEngine:
    def __init__(self, local_id, decay_rate=0.01, recommendation_weight=0.5, persist=True):
        self.local_id = local_id
        self.decay_rate = decay_rate
        self.recommendation_weight = recommendation_weight
        self.persist = persist
        self.records: Dict[Tuple[str, str], TrustRecord] = {}
        self._lock = threading.RLock()
        if persist:
            self._load()

    @staticmethod
    def _make_key(source, target):
        return (source, target)

    def record_success(self, source, target, weight=1.0):
        key = self._make_key(source, target)
        with self._lock:
            if key not in self.records:
                self.records[key] = TrustRecord(source_id=source, target_id=target)
            self.records[key].record_success(weight)
            if self.persist:
                self._save()

    def record_failure(self, source, target, weight=1.0):
        key = self._make_key(source, target)
        with self._lock:
            if key not in self.records:
                self.records[key] = TrustRecord(source_id=source, target_id=target)
            self.records[key].record_failure(weight)
            if self.persist:
                self._save()

    def record_interaction(self, source, target, success):
        if success:
            self.record_success(source, target)
        else:
            self.record_failure(source, target)

    def record_recommendation(self, source, target, recommender, recommendation):
        key = self._make_key(source, target)
        with self._lock:
            if key not in self.records:
                self.records[key] = TrustRecord(source_id=source, target_id=target)
            recommender_trust = self._get_trust_internal(source, recommender)
            self.records[key].apply_recommendation(
                recommender_trust=recommender_trust,
                recommendation=recommendation,
                weight=self.recommendation_weight)
            if self.persist:
                self._save()

    def get_trust(self, source, target):
        with self._lock:
            return self._get_trust_internal(source, target)

    def _get_trust_internal(self, source, target):
        key = self._make_key(source, target)
        if key in self.records:
            return self.records[key].trust_score
        return 0.5

    def get_trust_record(self, source, target):
        with self._lock:
            key = self._make_key(source, target)
            return self.records.get(key)

    def get_trust_level(self, source, target):
        record = self.get_trust_record(source, target)
        if record:
            return record.level
        return TrustLevel.UNKNOWN

    def get_global_reputation(self, target):
        with self._lock:
            total_weight = 0.0
            total_score = 0.0
            for (source, t), record in self.records.items():
                if t == target:
                    source_trust = self._get_trust_internal(self.local_id, source)
                    weight = source_trust * record.confidence
                    total_weight += weight
                    total_score += record.trust_score * weight
            if total_weight > 0:
                return total_score / total_weight
            return 0.5

    def should_trust(self, source, target, min_trust=0.5):
        return self.get_trust(source, target) >= min_trust

    def should_accept_data(self, source, target, min_trust=0.6):
        trust = self.get_trust(source, target)
        record = self.get_trust_record(source, target)
        if trust < min_trust:
            return False
        if record and record.direct_observations < 3:
            return False
        return True

    def decay_all(self):
        with self._lock:
            for record in self.records.values():
                record.decay(self.decay_rate)
            if self.persist:
                self._save()

    def remove_records_for(self, device_id):
        with self._lock:
            keys = [k for k in self.records if device_id in k]
            for key in keys:
                del self.records[key]
            if self.persist and keys:
                self._save()

    def get_stats(self):
        with self._lock:
            levels = {level.value: 0 for level in TrustLevel}
            for record in self.records.values():
                levels[record.level.value] += 1
            return {
                "total_records": len(self.records),
                "local_id": self.local_id,
                "by_level": levels,
                "avg_trust": (sum(r.trust_score for r in self.records.values()) / len(self.records)
                              if self.records else 0.5),
            }

    def _get_state_file(self):
        path = DataPaths.get_state_dir()
        path.mkdir(parents=True, exist_ok=True)
        return path / "trust_engine.json"

    def _save(self):
        try:
            with self._lock:
                data = {
                    "local_id": self.local_id,
                    "records": {f"{s}:{t}": r.to_dict() for (s, t), r in self.records.items()},
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
                for key, rec_data in data.get("records", {}).items():
                    src, tgt = key.split(":", 1)
                    self.records[(src, tgt)] = TrustRecord.from_dict(rec_data)
                logger.info(f"Loaded {len(self.records)} trust records")
        except Exception as e:
            logger.error(f"Load error: {e}")

    def __repr__(self):
        return f"TrustEngine(local={self.local_id}, records={len(self.records)})"


if __name__ == "__main__":
    print("Testing TrustEngine...")
    engine = TrustEngine(local_id="dev_local", persist=False)
    for _ in range(10):
        engine.record_success("dev_local", "dev_peer1")
    for _ in range(3):
        engine.record_failure("dev_local", "dev_peer1")
    trust = engine.get_trust("dev_local", "dev_peer1")
    level = engine.get_trust_level("dev_local", "dev_peer1")
    print(f"Trust: {trust:.4f}")
    print(f"Level: {level.value}")
    engine.record_recommendation("dev_local", "dev_peer2",
                                 recommender="dev_peer1", recommendation=0.9)
    print(f"Peer2 trust: {engine.get_trust('dev_local', 'dev_peer2'):.4f}")
    should = engine.should_trust("dev_local", "dev_peer1")
    print(f"Should trust peer1: {should}")
    stats = engine.get_stats()
    print(f"Stats: {stats}")
    print("OK")
