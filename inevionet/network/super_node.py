"""InevioNet Super-Node - trained node that broadcasts experience."""
import time, threading
from typing import Dict, Any, Optional
from ..core.logger import get_logger
log = get_logger("inevionet.network.super_node")

class SuperNodeManager:
    def __init__(self, fitness_threshold=0.9, delivery_rate_threshold=0.9,
                 delivery_attempts_threshold=5, seen_count_threshold=10,
                 recon_required=False, broadcast_interval=60.0):
        self.fitness_threshold = fitness_threshold
        self.delivery_rate_threshold = delivery_rate_threshold
        self.delivery_attempts_threshold = delivery_attempts_threshold
        self.seen_count_threshold = seen_count_threshold
        self.recon_required = recon_required
        self.broadcast_interval = broadcast_interval
        self.super_nodes: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()
        self._last_broadcast = {}

    def meets_criteria(self, node, evolution_stats, delivery_stats, spore_findings) -> Optional[str]:
        best_fitness = evolution_stats.get('best_fitness', 0.0)
        if best_fitness < self.fitness_threshold: return None
        ssid = node.get('name', '')
        ds = delivery_stats.get(ssid, {})
        tried = ds.get('tried', []); succeeded = ds.get('succeeded', [])
        if len(tried) < self.delivery_attempts_threshold: return None
        rate = (len(succeeded) / len(tried)) if tried else 0.0
        if rate < self.delivery_rate_threshold: return None
        if node.get('seen_count', 0) < self.seen_count_threshold: return None
        if self.recon_required and node.get('type') == 'wifi':
            bssid = node.get('node_id', '').replace('wifi_', '')
            if bssid not in spore_findings: return None
        return ("fitness=%.3f, delivery=%.2f%% (%d/%d), seen=%d"
                % (best_fitness, rate*100, len(succeeded), len(tried), node.get('seen_count', 0)))

    def try_promote(self, node, evolution_stats, delivery_stats, spore_findings) -> bool:
        nid = node.get('node_id')
        if not nid: return False
        with self._lock:
            if nid in self.super_nodes: return True
            reason = self.meets_criteria(node, evolution_stats, delivery_stats, spore_findings)
            if reason is None: return False
            self.super_nodes[nid] = {'node_id': nid, 'name': node.get('name'),
                'type': node.get('type'), 'promoted_at': time.time(), 'reason': reason,
                'experience': {'best_fitness': evolution_stats.get('best_fitness'),
                               'best_protocol': delivery_stats.get(node.get('name'), {}).get('last_method'),
                               'node_type': node.get('type'), 'extracted_at': time.time()}}
            log.info('[SuperNode] promoted to SUPER: "%s": %s', node.get('name') or nid, reason)
            return True

    def get_broadcast_payload(self, node_id):
        with self._lock:
            if node_id not in self.super_nodes: return None
            now = time.time()
            if now - self._last_broadcast.get(node_id, 0) < self.broadcast_interval: return None
            self._last_broadcast[node_id] = now
            sn = self.super_nodes[node_id]
            return {'type': 'super_experience', 'from': node_id,
                    'from_name': sn.get('name'), 'experience': sn.get('experience'), 'ts': now}

    def is_super(self, node_id):
        with self._lock: return node_id in self.super_nodes

    def get_all(self):
        with self._lock: return dict(self.super_nodes)

    def get_stats(self):
        with self._lock:
            return {'count': len(self.super_nodes),
                    'nodes': [{'node_id': k, 'name': v['name'], 'type': v['type'],
                               'reason': v['reason'], 'promoted_at': v['promoted_at']}
                              for k, v in self.super_nodes.items()]}
