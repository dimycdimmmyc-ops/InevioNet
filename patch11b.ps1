# Patch 11b: Bridge Broker
$ErrorActionPreference = "Stop"
$ProjectRoot = "E:\InevioNet"

$brokerPath = Join-Path $ProjectRoot "inevionet\network\bridge_broker.py"

if (Test-Path $brokerPath) {
    Write-Host "[--] bridge_broker.py already exists" -ForegroundColor Yellow
    return
}

$brokerCode = @'
"""P13: Bridge Broker - coordinates clients and relay nodes."""
import time
import random
import threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from ..core.logger import get_logger

logger = get_logger("inevionet.network.bridge_broker")


@dataclass
class RelayNode:
    """P13: Registered relay node."""
    node_id: str
    endpoint: str
    capacity: int = 10
    current_load: int = 0
    total_served: int = 0
    bytes_served: int = 0
    registered_at: float = 0.0
    last_heartbeat: float = 0.0
    region: str = "unknown"
    available: bool = True

    def __post_init__(self):
        if self.registered_at == 0.0:
            self.registered_at = time.time()
        if self.last_heartbeat == 0.0:
            self.last_heartbeat = time.time()

    @property
    def is_alive(self) -> bool:
        return (time.time() - self.last_heartbeat) < 300

    @property
    def is_available(self) -> bool:
        return self.available and self.is_alive and self.current_load < self.capacity

    @property
    def load_ratio(self) -> float:
        if self.capacity == 0:
            return 1.0
        return self.current_load / self.capacity

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "endpoint": self.endpoint,
            "capacity": self.capacity,
            "current_load": self.current_load,
            "total_served": self.total_served,
            "bytes_served": self.bytes_served,
            "region": self.region,
            "available": self.available,
            "load_ratio": round(self.load_ratio, 2),
            "age_sec": round(time.time() - self.registered_at, 1),
        }


class BridgeBroker:
    """P13: Coordinates clients and relay nodes."""

    def __init__(self, max_relays=1000):
        self.max_relays = max_relays
        self.relays: Dict[str, RelayNode] = {}
        self._lock = threading.Lock()
        self._stats = {
            "total_registrations": 0,
            "total_assignments": 0,
            "total_relay_removals": 0,
            "started_at": time.time(),
        }

    def register_relay(self, node_id: str, endpoint: str,
                       capacity: int = 10, region: str = "unknown") -> RelayNode:
        """P13: Register a new relay node."""
        with self._lock:
            if node_id in self.relays:
                node = self.relays[node_id]
                node.endpoint = endpoint
                node.capacity = capacity
                node.region = region
                node.last_heartbeat = time.time()
                node.available = True
                logger.info("[Broker] Relay updated: %s", node_id)
            else:
                if len(self.relays) >= self.max_relays:
                    self._cleanup_dead()
                node = RelayNode(
                    node_id=node_id, endpoint=endpoint,
                    capacity=capacity, region=region)
                self.relays[node_id] = node
                self._stats["total_registrations"] += 1
                logger.info("[Broker] Relay registered: %s @ %s", node_id, endpoint)
            return node

    def heartbeat(self, node_id: str, current_load: int = None) -> bool:
        """P13: Update relay heartbeat."""
        with self._lock:
            if node_id not in self.relays:
                return False
            node = self.relays[node_id]
            node.last_heartbeat = time.time()
            if current_load is not None:
                node.current_load = current_load
            node.available = True
            return True

    def unregister_relay(self, node_id: str) -> bool:
        """P13: Remove a relay node."""
        with self._lock:
            if node_id in self.relays:
                del self.relays[node_id]
                self._stats["total_relay_removals"] += 1
                logger.info("[Broker] Relay removed: %s", node_id)
                return True
            return False

    def pick_relay(self, region: str = None, exclude: List[str] = None) -> Optional[RelayNode]:
        """P13: Pick the best relay for a client."""
        exclude = exclude or []
        with self._lock:
            candidates = [r for r in self.relays.values()
                          if r.is_available and r.node_id not in exclude]

        if not candidates:
            logger.debug("[Broker] No available relays")
            return None

        if region:
            regional = [r for r in candidates if r.region == region]
            if regional:
                candidates = regional

        # Sort by load ratio (ascending)
        candidates.sort(key=lambda r: r.load_ratio)
        best = candidates[0]

        with self._lock:
            best.current_load += 1
            self._stats["total_assignments"] += 1

        logger.info("[Broker] Assigned relay: %s (load %d/%d)",
                    best.node_id, best.current_load, best.capacity)
        return best

    def release_relay(self, node_id: str, bytes_served: int = 0):
        """P13: Release relay after serving a client."""
        with self._lock:
            if node_id not in self.relays:
                return
            node = self.relays[node_id]
            node.current_load = max(0, node.current_load - 1)
            node.total_served += 1
            node.bytes_served += bytes_served

    def _cleanup_dead(self):
        """P13: Remove dead relays."""
        dead = [nid for nid, r in self.relays.items() if not r.is_alive]
        for nid in dead:
            del self.relays[nid]
            self._stats["total_relay_removals"] += 1
        if dead:
            logger.info("[Broker] Cleaned up %d dead relays", len(dead))

    def get_relays(self) -> List[Dict[str, Any]]:
        """P13: List all relays."""
        with self._lock:
            return [r.to_dict() for r in self.relays.values()]

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            available = sum(1 for r in self.relays.values() if r.is_available)
            total_load = sum(r.current_load for r in self.relays.values())
            total_capacity = sum(r.capacity for r in self.relays.values())
            return {
                **self._stats,
                "total_relays": len(self.relays),
                "available_relays": available,
                "total_load": total_load,
                "total_capacity": total_capacity,
                "uptime_sec": round(time.time() - self._stats["started_at"], 1),
            }

    def __repr__(self):
        return "BridgeBroker(relays=" + str(len(self.relays)) + ")"


if __name__ == "__main__":
    print("Testing BridgeBroker...")
    b = BridgeBroker()
    for i in range(5):
        b.register_relay("node_" + str(i), "192.168.1." + str(10 + i),
                        capacity=10, region="RU")
    print("Relays:", len(b.get_relays()))

    for _ in range(3):
        r = b.pick_relay(region="RU")
        if r:
            print("  Assigned:", r.node_id, "(load", r.current_load, "/", r.capacity, ")")

    print("Stats:", b.get_stats())
    print("BridgeBroker OK")
'@

$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($brokerPath, $brokerCode, $utf8)
Write-Host "[OK] Created: bridge_broker.py" -ForegroundColor Green

python -c "import ast; ast.parse(open(r'$brokerPath', encoding='utf-8').read()); print('OK')"

Write-Host ""
Write-Host "Testing BridgeBroker..." -ForegroundColor Cyan
python -c "
from inevionet.network.bridge_broker import BridgeBroker
b = BridgeBroker()
for i in range(5):
    b.register_relay('node_' + str(i), '192.168.1.' + str(10+i), capacity=10, region='RU')
print('Relays:', len(b.get_relays()))
for i in range(3):
    r = b.pick_relay(region='RU')
    if r:
        print('  Assigned:', r.node_id, '(load', r.current_load, '/', r.capacity, ')')
print('Stats:', b.get_stats())
"