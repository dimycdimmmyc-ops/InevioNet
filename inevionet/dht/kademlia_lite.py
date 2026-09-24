"""InevioNet DHT - Kademlia-lite implementation for mini-server nodes."""
import hashlib
import json
import os
import random
import threading
import time
from collections import OrderedDict

class KademliaNode:
    """Lightweight DHT node for mini-servers."""
    
    def __init__(self, node_id, port=8801):
        self.node_id = node_id
        self.port = port
        self.routing_table = OrderedDict()  # node_id -> {ip, port, last_seen, fitness}
        self.storage = {}  # key -> {value, timestamp, ttl}
        self.lock = threading.Lock()
        self.k = 20  # k-bucket size
        self.alpha = 3  # parallel lookups
        
    def distance(self, node_id1, node_id2=None):
        """XOR distance between two node IDs."""
        id2 = node_id2 or self.node_id
        id1_bytes = bytes.fromhex(node_id1) if isinstance(node_id1, str) else node_id1
        id2_bytes = bytes.fromhex(id2) if isinstance(id2, str) else id2
        return sum(a ^ b for a, b in zip(id1_bytes, id2_bytes))
    
    def ping(self, node_id, ip, port):
        """Add/update node in routing table."""
        with self.lock:
            self.routing_table[node_id] = {
                'ip': ip, 'port': port, 
                'last_seen': time.time(),
                'fitness': 0.0
            }
            # Keep only k closest nodes
            if len(self.routing_table) > self.k:
                # Remove farthest node
                farthest = max(self.routing_table.keys(), 
                              key=lambda x: self.distance(x))
                del self.routing_table[farthest]
    
    def store(self, key, value, ttl=3600):
        """Store key-value pair with TTL."""
        with self.lock:
            self.storage[key] = {
                'value': value,
                'timestamp': time.time(),
                'ttl': ttl
            }
            # Cleanup old entries
            now = time.time()
            self.storage = {
                k: v for k, v in self.storage.items()
                if now - v['timestamp'] < v['ttl']
            }
    
    def get(self, key):
        """Retrieve value by key."""
        with self.lock:
            entry = self.storage.get(key)
            if entry and time.time() - entry['timestamp'] < entry['ttl']:
                return entry['value']
            return None
    
    def find_closest_nodes(self, target_id, k=None):
        """Find k closest nodes to target."""
        k = k or self.k
        with self.lock:
            sorted_nodes = sorted(
                self.routing_table.keys(),
                key=lambda x: self.distance(x, target_id)
            )
            return sorted_nodes[:k]
    
    def to_dict(self):
        return {
            'node_id': self.node_id,
            'port': self.port,
            'peers': len(self.routing_table),
            'storage_keys': len(self.storage)
        }
