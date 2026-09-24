"""InevioNet Gravity - маршрутизация через поле притяжения."""
import time
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Any

from ..core.logger import get_logger

logger = get_logger("inevionet.mesh.gravity")


@dataclass
class NodeMass:
    node_id: str
    mass: float = 1.0
    last_update: float = 0.0
    successes: int = 0
    failures: int = 0

    def __post_init__(self):
        if self.last_update == 0.0:
            self.last_update = time.time()


class GravityField:
    def __init__(self, decay=0.01, min_mass=0.1):
        self.decay = decay
        self.min_mass = min_mass
        self.nodes: Dict[str, NodeMass] = {}
        self.edges: Dict[tuple, float] = {}
        self._last_decay = time.time()

    def add_mass(self, node_id: str, delta: float = 1.0):
        if node_id not in self.nodes:
            self.nodes[node_id] = NodeMass(node_id=node_id)
        self.nodes[node_id].mass += delta
        self.nodes[node_id].successes += 1
        self.nodes[node_id].last_update = time.time()

    def remove_mass(self, node_id: str, delta: float = 0.5):
        if node_id in self.nodes:
            self.nodes[node_id].mass = max(self.min_mass,
                self.nodes[node_id].mass - delta)
            self.nodes[node_id].failures += 1

    def set_edge(self, a: str, b: str, strength: float):
        key = (a, b) if a < b else (b, a)
        self.edges[key] = max(0.0, min(1.0, strength))

    def get_edge(self, a: str, b: str) -> float:
        key = (a, b) if a < b else (b, a)
        return self.edges.get(key, 0.0)

    def decay_all(self):
        now = time.time()
        if now - self._last_decay < 60.0:
            return
        dt = now - self._last_decay
        factor = math.exp(-self.decay * dt / 60.0)
        for nm in self.nodes.values():
            nm.mass = max(self.min_mass, nm.mass * factor)
        self._last_decay = now

    def attract(self, from_node: str, to_node: str) -> float:
        if to_node not in self.nodes:
            return 0.0
        target_mass = self.nodes[to_node].mass
        edge = self.get_edge(from_node, to_node)
        if edge > 0:
            return edge * (0.5 + 0.5 * min(1.0, target_mass / 10.0))
        return 0.1 * min(1.0, target_mass / 10.0)

    def next_hop(self, from_node: str, target: str, candidates: List[str]) -> Optional[str]:
        if not candidates:
            return None
        best = None
        best_score = -1.0
        for c in candidates:
            if c == from_node:
                continue
            score = self.attract(from_node, c)
            if c == target:
                score += 10.0
            if score > best_score:
                best_score = score
                best = c
        return best

    def get_stats(self) -> Dict[str, Any]:
        self.decay_all()
        if not self.nodes:
            return {"nodes": 0, "edges": 0}
        masses = [nm.mass for nm in self.nodes.values()]
        return {
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            "total_mass": round(sum(masses), 2),
            "max_mass": round(max(masses), 2),
            "min_mass": round(min(masses), 2),
            "avg_mass": round(sum(masses) / len(masses), 2),
            "top_nodes": sorted(
                [(nid, round(nm.mass, 2)) for nid, nm in self.nodes.items()],
                key=lambda x: -x[1])[:5],
        }


class GravityRouter:
    def __init__(self, field: GravityField, topology=None):
        self.field = field
        self.topology = topology

    def route(self, from_node: str, target: str) -> List[str]:
        if from_node == target:
            return [from_node]
        candidates = []
        if self.topology and hasattr(self.topology, "nodes"):
            candidates = list(self.topology.nodes.keys())
        path = [from_node]
        current = from_node
        visited = {from_node}
        for _ in range(10):
            next_hop = self.field.next_hop(current, target, candidates)
            if not next_hop or next_hop in visited:
                break
            path.append(next_hop)
            visited.add(next_hop)
            if next_hop == target:
                return path
            current = next_hop
        if target not in path:
            path.append(target)
        return path