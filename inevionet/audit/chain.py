"""InevioNet Audit Chain - append-only журнал событий сети.

Каждое событие имеет hash = SHA256(prev_hash + event + ts + node_id).
Цепочка не блокчейн - нет блоков. Просто события с хэш-ссылками.
Любая подмена ломает цепочку. Verify пересчитывает все хэши.

События:
  - start    - узел стартовал
  - merge    - слита карта соседа
  - sprout   - проращён seed
  - relay    - переслан GDPPacket
  - deploy   - задеплоена капсула
  - punch    - hole punching
  - manual   - ручное событие (для теста)
"""
import os
import time
import json
import hashlib
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

from ..core.logger import get_logger

logger = get_logger("inevionet.audit.chain")


@dataclass
class AuditEvent:
    """Событие в audit-журнале."""
    event_type: str
    node_id: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0
    prev_hash: str = ""
    hash: str = ""

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def compute_hash(self) -> str:
        payload = (
            self.prev_hash +
            self.event_type +
            self.node_id +
            json.dumps(self.data, sort_keys=True) +
            str(self.timestamp)
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def seal(self):
        self.hash = self.compute_hash()

    def verify(self) -> bool:
        return self.hash == self.compute_hash()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**d)


class AuditChain:
    """Append-only hash-chain журнал событий сети."""

    def __init__(self, node_id: str, persist_path: Optional[str] = None,
                 max_events: int = 10000):
        self.node_id = node_id
        self.persist_path = persist_path
        self.max_events = max_events
        self.events: List[AuditEvent] = []
        self._stats = {
            "started_at": time.time(),
            "by_type": {},
        }
        self._load()
        if not self.events:
            self.add_event("start", {"mode": "init"}, initial=True)

    def add_event(self, event_type: str, data: Dict[str, Any],
                  initial: bool = False) -> AuditEvent:
        prev_hash = self.events[-1].hash if self.events else "0" * 64
        ev = AuditEvent(
            event_type=event_type,
            node_id=self.node_id,
            data=data or {},
            prev_hash=prev_hash,
        )
        ev.seal()
        self.events.append(ev)
        self._stats["by_type"][event_type] = self._stats["by_type"].get(event_type, 0) + 1
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events:]
        self._save()
        return ev

    def verify(self) -> Dict[str, Any]:
        errors = []
        prev = "0" * 64
        for i, ev in enumerate(self.events):
            if ev.prev_hash != prev:
                errors.append({"index": i, "error": "prev_hash_mismatch"})
            if not ev.verify():
                errors.append({"index": i, "error": "hash_mismatch"})
            prev = ev.hash
        return {
            "valid": len(errors) == 0,
            "events": len(self.events),
            "errors": errors[:10],
        }

    def get_recent(self, n: int = 20) -> List[Dict[str, Any]]:
        return [ev.to_dict() for ev in self.events[-n:]]

    def get_by_type(self, event_type: str, limit: int = 50) -> List[Dict[str, Any]]:
        result = []
        for ev in reversed(self.events):
            if ev.event_type == event_type:
                result.append(ev.to_dict())
                if len(result) >= limit:
                    break
        return result

    def get_stats(self) -> Dict[str, Any]:
        return {
            "events_total": len(self.events),
            "by_type": dict(self._stats["by_type"]),
            "latest_hash": self.events[-1].hash[:16] if self.events else "",
            "genesis_ts": self.events[0].timestamp if self.events else 0,
            "uptime_sec": round(time.time() - self._stats["started_at"], 1),
        }

    def _save(self):
        if not self.persist_path:
            return
        try:
            with open(self.persist_path, "w", encoding="utf-8") as f:
                json.dump({
                    "node_id": self.node_id,
                    "events": [ev.to_dict() for ev in self.events[-1000:]],
                }, f)
        except Exception as e:
            logger.debug("[Audit] save: %s", e)

    def _load(self):
        if not self.persist_path or not os.path.exists(self.persist_path):
            return
        try:
            with open(self.persist_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.events = [AuditEvent.from_dict(d) for d in data.get("events", [])]
            logger.info("[Audit] loaded %d events", len(self.events))
        except Exception as e:
            logger.debug("[Audit] load: %s", e)
