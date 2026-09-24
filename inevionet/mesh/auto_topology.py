"""InevioNet Auto Topology - mesh network topology builder."""
import time
import math
import json
import heapq
from collections import defaultdict
from typing import Dict, List, Any, Optional, Tuple, Set
from dataclasses import dataclass, field

from ..core.logger import get_logger
from ..network.rf_scanner import RFScanner, RFSignal, RFSignalType

logger = get_logger("inevionet.mesh.auto_topology")


@dataclass
class TopologyNode:
    node_id: str
    name: str = ""
    node_type: str = "generic"
    position: Optional[Tuple[float, float]] = None
    rssi_dbm: float = -100.0
    quality: float = 0.0
    is_active: bool = True
    timestamp: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def to_dict(self):
        return {
            "node_id": self.node_id, "name": self.name,
            "type": self.node_type, "position": self.position,
            "rssi_dbm": self.rssi_dbm, "quality": self.quality,
            "is_active": self.is_active,
        }

    def __repr__(self):
        return f"TopologyNode({self.node_id}, RSSI={self.rssi_dbm:.1f}dBm)"


@dataclass
class TopologyEdge:
    source_id: str
    target_id: str
    weight: float = 1.0
    rssi_dbm: float = -100.0
    capacity_mbps: float = 10.0
    latency_ms: float = 10.0
    is_active: bool = True
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def __lt__(self, other):
        return self.weight < other.weight

    def __repr__(self):
        return f"TopologyEdge({self.source_id}->{self.target_id}, w={self.weight:.3f})"


class AutoTopology:
    def __init__(self, rf_scanner=None, rssi_to_weight=True):
        self.scanner = rf_scanner or RFScanner()
        self.rssi_to_weight = rssi_to_weight
        self.nodes: Dict[str, TopologyNode] = {}
        self.edges: Dict[Tuple[str, str], TopologyEdge] = {}
        self.adjacency: Dict[str, List[Tuple[str, float]]] = defaultdict(list)
        self.build_history: List[Dict[str, Any]] = []
        self.stats = {
            "builds": 0, "nodes_discovered": 0,
            "edges_created": 0, "last_build_time": 0.0,
        }
        logger.info("AutoTopology created")

    def build_from_scanner(self, signal_types=None, min_quality=0.3):
        start = time.time()
        scan = self.scanner.scan_all()
        if not scan.success:
            return {"success": False, "error": scan.error}
        signals = scan.signals
        if signal_types:
            signals = [s for s in signals if s.signal_type.value in signal_types]
        signals = [s for s in signals if s.quality >= min_quality]
        for sig in signals:
            node_id = sig.identifier
            if node_id not in self.nodes:
                self.nodes[node_id] = TopologyNode(
                    node_id=node_id, name=sig.name,
                    node_type=sig.signal_type.value,
                    rssi_dbm=sig.rssi_dbm, quality=sig.quality,
                    metadata={
                        "frequency_mhz": sig.frequency_mhz,
                        "channel": sig.channel,
                        "encryption": sig.encryption,
                    })
        node_ids = list(self.nodes.keys())
        for i, id1 in enumerate(node_ids):
            for id2 in node_ids[i+1:]:
                edge = self._create_edge(id1, id2)
                if edge:
                    key = (id1, id2) if id1 < id2 else (id2, id1)
                    self.edges[key] = edge
                    self.adjacency[id1].append((id2, edge.weight))
                    self.adjacency[id2].append((id1, edge.weight))
        elapsed = (time.time() - start) * 1000
        build_info = {
            "success": True, "duration_ms": elapsed,
            "nodes": len(self.nodes), "edges": len(self.edges),
            "signals_processed": len(signals),
        }
        self.build_history.append(build_info)
        self.stats["builds"] += 1
        self.stats["nodes_discovered"] = len(self.nodes)
        self.stats["edges_created"] = len(self.edges)
        self.stats["last_build_time"] = elapsed
        logger.info(f"Topology built: {len(self.nodes)} nodes, {len(self.edges)} edges")
        return build_info

    def _create_edge(self, node_id1, node_id2):
        node1 = self.nodes.get(node_id1)
        node2 = self.nodes.get(node_id2)
        if not node1 or not node2:
            return None
        avg_rssi = (node1.rssi_dbm + node2.rssi_dbm) / 2
        if self.rssi_to_weight:
            weight = 10 ** ((-avg_rssi - 30) / 70)
            weight = max(0.1, min(10.0, weight))
        else:
            weight = 1.0
        capacity = max(1.0, 100 * (1 - weight / 10))
        latency = 10 * weight
        return TopologyEdge(
            source_id=node_id1, target_id=node_id2,
            weight=weight, rssi_dbm=avg_rssi,
            capacity_mbps=capacity, latency_ms=latency)

    def shortest_path(self, source, target):
        if source not in self.nodes or target not in self.nodes:
            return None
        queue = [(0.0, source, [source])]
        visited = set()
        while queue:
            cost, node, path = heapq.heappop(queue)
            if node == target:
                return path
            if node in visited:
                continue
            visited.add(node)
            for neighbor, weight in self.adjacency.get(node, []):
                if neighbor not in visited:
                    heapq.heappush(queue, (cost + weight, neighbor, path + [neighbor]))
        return None

    def shortest_path_cost(self, source, target):
        path = self.shortest_path(source, target)
        if not path:
            return float("inf")
        total = 0.0
        for i in range(len(path) - 1):
            key = (path[i], path[i+1]) if path[i] < path[i+1] else (path[i+1], path[i])
            edge = self.edges.get(key)
            if edge:
                total += edge.weight
        return total

    def minimum_spanning_tree(self):
        sorted_edges = sorted(self.edges.values(), key=lambda e: e.weight)
        parent = {node: node for node in self.nodes}
        rank = {node: 0 for node in self.nodes}

        def find(x):
            if parent[x] != x:
                parent[x] = find(parent[x])
            return parent[x]

        def union(x, y):
            rx, ry = find(x), find(y)
            if rx == ry:
                return False
            if rank[rx] < rank[ry]:
                parent[rx] = ry
            elif rank[rx] > rank[ry]:
                parent[ry] = rx
            else:
                parent[ry] = rx
                rank[rx] += 1
            return True

        mst = []
        for edge in sorted_edges:
            if union(edge.source_id, edge.target_id):
                mst.append(edge)
                if len(mst) == len(self.nodes) - 1:
                    break
        return mst

    def mst_cost(self):
        return sum(e.weight for e in self.minimum_spanning_tree())

    def is_connected(self):
        if not self.nodes:
            return True
        start = next(iter(self.nodes))
        visited = set()
        queue = [start]
        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            for neighbor, _ in self.adjacency.get(node, []):
                if neighbor not in visited:
                    queue.append(neighbor)
        return len(visited) == len(self.nodes)

    def connected_components(self):
        visited = set()
        components = []
        for node in self.nodes:
            if node not in visited:
                component = set()
                queue = [node]
                while queue:
                    current = queue.pop(0)
                    if current in visited:
                        continue
                    visited.add(current)
                    component.add(current)
                    for neighbor, _ in self.adjacency.get(current, []):
                        if neighbor not in visited:
                            queue.append(neighbor)
                components.append(component)
        return components

    def clustering_coefficient(self):
        if not self.nodes:
            return 0.0
        total = 0.0
        count = 0
        for node in self.nodes:
            neighbors = [n for n, _ in self.adjacency.get(node, [])]
            k = len(neighbors)
            if k < 2:
                continue
            triangles = 0
            for i, n1 in enumerate(neighbors):
                for n2 in neighbors[i+1:]:
                    key = (n1, n2) if n1 < n2 else (n2, n1)
                    if key in self.edges:
                        triangles += 1
            c = 2 * triangles / (k * (k - 1))
            total += c
            count += 1
        return total / count if count > 0 else 0.0

    def average_path_length(self):
        if len(self.nodes) < 2:
            return 0.0
        total = 0.0
        count = 0
        node_ids = list(self.nodes.keys())
        for i, src in enumerate(node_ids):
            for tgt in node_ids[i+1:]:
                path = self.shortest_path(src, tgt)
                if path:
                    total += len(path) - 1
                    count += 1
        return total / count if count > 0 else float("inf")

    def diameter(self):
        if len(self.nodes) < 2:
            return 0
        max_len = 0
        node_ids = list(self.nodes.keys())
        for i, src in enumerate(node_ids):
            for tgt in node_ids[i+1:]:
                path = self.shortest_path(src, tgt)
                if path:
                    max_len = max(max_len, len(path) - 1)
        return max_len

    def get_stats(self):
        return {
            "nodes": len(self.nodes), "edges": len(self.edges),
            "is_connected": self.is_connected(),
            "components": len(self.connected_components()),
            "clustering": self.clustering_coefficient(),
            "avg_path_length": self.average_path_length(),
            "diameter": self.diameter(),
            "mst_cost": self.mst_cost(),
            "builds": self.stats["builds"],
        }

    def analyze(self):
        stats = self.get_stats()
        mst = self.minimum_spanning_tree()
        return {
            "stats": stats, "mst_edges": len(mst),
            "mst_total_weight": sum(e.weight for e in mst),
            "node_types": self._count_by_type(),
            "edge_weights": self._edge_weight_stats(),
        }

    def _count_by_type(self):
        counts = defaultdict(int)
        for node in self.nodes.values():
            counts[node.node_type] += 1
        return dict(counts)

    def _edge_weight_stats(self):
        if not self.edges:
            return {"min": 0, "max": 0, "avg": 0}
        weights = [e.weight for e in self.edges.values()]
        return {"min": min(weights), "max": max(weights),
                "avg": sum(weights) / len(weights)}

    def export_json(self):
        data = {
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [{"source": e.source_id, "target": e.target_id,
                       "weight": e.weight, "rssi_dbm": e.rssi_dbm,
                       "capacity_mbps": e.capacity_mbps,
                       "latency_ms": e.latency_ms} for e in self.edges.values()],
            "stats": self.get_stats(),
        }
        return json.dumps(data, ensure_ascii=False, indent=2)

    def export_map(self) -> dict:
        """P38: export map for sharing (nodes + edges)."""
        return {
            "nodes": {
                nid: {
                    "name": n.name,
                    "type": n.node_type,
                    "rssi": n.rssi_dbm,
                    "quality": n.quality,
                }
                for nid, n in self.nodes.items()
            },
            "edges": [
                {
                    "source": e.source_id,
                    "target": e.target_id,
                    "weight": e.weight,
                }
                for e in self.edges.values()
            ],
            "stats": {
                "nodes": len(self.nodes),
                "edges": len(self.edges),
            },
        }

    def merge(self, other_map: dict, via_node_id: str = "") -> dict:
        """P38: merge external map (nodes + edges) into self.

        P60: via_node_id — node_id того, от кого получена карта.
        Записывается в metadata['via'] и добавляет ребро via -> node,
        чтобы Dijkstra нашёл путь для relay.
        """
        added_nodes = 0
        added_edges = 0
        if not other_map:
            return {"added_nodes": 0, "added_edges": 0}
        for node_id, node_data in other_map.get("nodes", {}).items():
            if node_id in self.nodes:
                continue
            try:
                self.nodes[node_id] = TopologyNode(
                    node_id=node_id,
                    name=node_data.get("name", node_id),
                    node_type=node_data.get("type", "external"),
                    rssi_dbm=float(node_data.get("rssi", -80)),
                    quality=float(node_data.get("quality", 0.5)),
                    metadata={"source": "merged", "via": via_node_id},
                )
                added_nodes += 1
                # P60: add edge via -> node (so relay path exists)
                if (via_node_id
                        and via_node_id != node_id
                        and via_node_id in self.nodes):
                    _k = (via_node_id, node_id) if via_node_id < node_id else (node_id, via_node_id)
                    if _k not in self.edges:
                        self.edges[_k] = TopologyEdge(
                            source_id=via_node_id, target_id=node_id,
                            weight=0.5)
                        self.adjacency.setdefault(via_node_id, []).append((node_id, 0.5))
                        self.adjacency.setdefault(node_id, []).append((via_node_id, 0.5))
                        added_edges += 1
            except Exception:
                pass
        for edge in other_map.get("edges", []):
            try:
                src = edge["source"]
                dst = edge["target"]
                w = float(edge.get("weight", 1.0))
                if src not in self.nodes or dst not in self.nodes:
                    continue
                key = (src, dst) if src < dst else (dst, src)
                if key in self.edges:
                    continue
                self.edges[key] = TopologyEdge(
                    source_id=src, target_id=dst, weight=w)
                self.adjacency[src].append((dst, w))
                self.adjacency[dst].append((src, w))
                added_edges += 1
            except Exception:
                pass
        if added_nodes or added_edges:
            logger.info("[Topology] MERGED: +%d nodes, +%d edges",
                        added_nodes, added_edges)
        return {"added_nodes": added_nodes, "added_edges": added_edges}

    def clear(self):
        self.nodes.clear()
        self.edges.clear()
        self.adjacency.clear()

    def __repr__(self):
        return f"AutoTopology(nodes={len(self.nodes)}, edges={len(self.edges)})"


if __name__ == "__main__":
    print("Testing AutoTopology...")
    topology = AutoTopology()
    print(f"Topology: {topology}")
    build_info = topology.build_from_scanner()
    print(f"Build: {build_info}")
    stats = topology.get_stats()
    print(f"Nodes: {stats['nodes']}, Edges: {stats['edges']}")
    print(f"Connected: {stats['is_connected']}, Diameter: {stats['diameter']}")
    print("OK")
