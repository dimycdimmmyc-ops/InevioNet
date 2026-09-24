"""InevioNet Cache - LRU + TTL caching."""
import time
import hashlib
import threading
from typing import Optional, Dict, Any, Callable, TypeVar, Generic
from collections import OrderedDict

from .logger import get_logger

logger = get_logger("inevionet.core.cache")

T = TypeVar("T")


class LRUCache(Generic[T]):
    """LRU cache with TTL."""

    def __init__(self, max_size=1000, default_ttl=300.0):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache = OrderedDict()
        self._lock = threading.RLock()
        self.hits = 0
        self.misses = 0
        self.evictions = 0
        self.expirations = 0

    def get(self, key):
        with self._lock:
            if key not in self._cache:
                self.misses += 1
                return None
            value, created_at, ttl, hits = self._cache[key]
            if time.time() - created_at > ttl:
                del self._cache[key]
                self.expirations += 1
                self.misses += 1
                return None
            self._cache.move_to_end(key)
            self._cache[key] = (value, created_at, ttl, hits + 1)
            self.hits += 1
            return value

    def set(self, key, value, ttl=None):
        ttl = ttl or self.default_ttl
        with self._lock:
            if key in self._cache:
                del self._cache[key]
            while len(self._cache) >= self.max_size:
                self._cache.popitem(last=False)
                self.evictions += 1
            self._cache[key] = (value, time.time(), ttl, 0)

    def delete(self, key):
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self):
        with self._lock:
            self._cache.clear()

    def cleanup(self):
        with self._lock:
            now = time.time()
            expired = [k for k, v in self._cache.items()
                       if now - v[1] > v[2]]
            for k in expired:
                del self._cache[k]
                self.expirations += 1

    @property
    def size(self):
        return len(self._cache)

    @property
    def hit_rate(self):
        total = self.hits + self.misses
        return self.hits / total if total > 0 else 0.0

    def get_stats(self):
        return {
            "size": self.size,
            "max_size": self.max_size,
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
            "expirations": self.expirations,
            "hit_rate": self.hit_rate,
        }

    def __repr__(self):
        return f"LRUCache(size={self.size}/{self.max_size}, hit_rate={self.hit_rate:.2%})"


class KLDivergenceCache:
    """Кэш для KL-дивергенции."""

    def __init__(self, max_size=10000, ttl=3600.0):
        self._cache = LRUCache(max_size=max_size, default_ttl=ttl)

    def _make_key(self, p, q):
        p_items = sorted(p.items())
        q_items = sorted(q.items())
        data = f"{p_items}|{q_items}".encode("utf-8")
        return hashlib.sha256(data).hexdigest()[:32]

    def compute(self, p, q, smoothing=1e-10):
        key = self._make_key(p, q)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        import math
        all_keys = set(p.keys()) | set(q.keys())
        p_sum = sum(p.values()) + smoothing * len(all_keys)
        q_sum = sum(q.values()) + smoothing * len(all_keys)
        kl = 0.0
        for k in all_keys:
            p_i = (p.get(k, 0.0) + smoothing) / p_sum
            q_i = (q.get(k, 0.0) + smoothing) / q_sum
            if p_i > 0:
                kl += p_i * math.log(p_i / q_i)
        kl = max(0.0, kl)
        self._cache.set(key, kl)
        return kl

    def clear(self):
        self._cache.clear()

    def get_stats(self):
        return self._cache.get_stats()


class FirewallCache:
    """Кэш решений файрвола."""

    def __init__(self, max_size=10000, ttl=300.0):
        self._cache = LRUCache(max_size=max_size, default_ttl=ttl)

    def _make_key(self, features):
        items = sorted((k, str(v)) for k, v in features.items())
        data = "|".join(f"{k}={v}" for k, v in items).encode("utf-8")
        return hashlib.md5(data).hexdigest()

    def get_decision(self, features, compute_func):
        key = self._make_key(features)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        decision = compute_func()
        self._cache.set(key, decision)
        return decision

    def clear(self):
        self._cache.clear()

    def get_stats(self):
        return self._cache.get_stats()


_kl_cache = KLDivergenceCache()
_fw_cache = FirewallCache()
_dns_cache = LRUCache(max_size=1000, default_ttl=300)


def get_kl_cache():
    return _kl_cache


def get_firewall_cache():
    return _fw_cache


def get_dns_cache():
    return _dns_cache


def get_all_cache_stats():
    return {
        "kl_cache": _kl_cache.get_stats(),
        "firewall_cache": _fw_cache.get_stats(),
        "dns_cache": _dns_cache.get_stats(),
    }


def clear_all_caches():
    _kl_cache.clear()
    _fw_cache.clear()
    _dns_cache.clear()


if __name__ == "__main__":
    print("Testing cache...")
    cache = LRUCache(max_size=3, default_ttl=10)
    cache.set("a", "value_a")
    cache.set("b", "value_b")
    cache.set("c", "value_c")
    print(f"get('a'): {cache.get('a')}")
    cache.set("d", "value_d")
    print(f"After set('d'): get('c') = {cache.get('c')}")
    print(f"Stats: {cache.get_stats()}")

    kl_cache = KLDivergenceCache()
    p = {"A": 0.7, "B": 0.2, "C": 0.1}
    q = {"A": 0.6, "B": 0.3, "C": 0.1}
    kl1 = kl_cache.compute(p, q)
    kl2 = kl_cache.compute(p, q)
    assert kl1 == kl2
    print(f"KL: {kl1:.6f}")
    print("Cache module OK")
