"""InevioNet Ambient Masking - traffic-adaptive stealth."""
import time
import math
import statistics
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, field
from collections import Counter, deque

from ..core.logger import get_logger
from .detection import KLDivergence
from .firewall_model import PacketFeatures

logger = get_logger("inevionet.masking.ambient")


@dataclass
class AmbientProfile:
    timestamp: float = 0.0
    sample_duration_ms: float = 0.0
    size_distribution: Dict[int, int] = field(default_factory=dict)
    protocol_distribution: Dict[str, int] = field(default_factory=dict)
    entropy_distribution: Dict[float, int] = field(default_factory=dict)
    total_packets: int = 0
    avg_size: float = 0.0
    avg_entropy: float = 0.0
    avg_interval_ms: float = 0.0
    dominant_protocol: str = "unknown"
    typical_size: int = 1400
    typical_entropy: float = 0.5

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def to_dict(self):
        return {
            "timestamp": self.timestamp,
            "total_packets": self.total_packets,
            "avg_size": self.avg_size,
            "avg_entropy": self.avg_entropy,
            "dominant_protocol": self.dominant_protocol,
            "typical_size": self.typical_size,
            "typical_entropy": self.typical_entropy,
        }


class AmbientAnalyzer:
    def __init__(self, max_samples=10000, window_size=1000):
        self.max_samples = max_samples
        self.window_size = window_size
        self._samples = deque(maxlen=max_samples)
        self._timestamps = deque(maxlen=max_samples)
        self._size_counter = Counter()
        self._protocol_counter = Counter()
        self._entropy_bins = Counter()
        self.stats = {"observations": 0, "last_update": 0.0}
        # P92c: данные от разведчиков
        self._recon_profile = None
        self._recon_ts = 0.0
        self._recon_raw = {}

    def observe(self, size, protocol, entropy, interval_ms=0.0):
        sample = {"size": size, "protocol": protocol,
                  "entropy": entropy, "interval_ms": interval_ms,
                  "timestamp": time.time()}
        self._samples.append(sample)
        self._timestamps.append(sample["timestamp"])
        self._size_counter[size] += 1
        self._protocol_counter[protocol] += 1
        self._entropy_bins[round(entropy, 1)] += 1
        self.stats["observations"] += 1
        self.stats["last_update"] = time.time()

    def observe_features(self, features):
        self.observe(features.size_bytes, features.protocol, features.entropy)

    def feed_from_recon(self, recon_data):
        """P92c: заполнить профиль из данных разведки.

        recon_data = {
          network_type, protocols, avg_packet_size, avg_entropy,
          ttl_typical, os_hints, services, device_types, total_devices,
          unique_routers, ...
        }
        """
        if not recon_data or not isinstance(recon_data, dict):
            return False
        self._recon_raw = dict(recon_data)
        self._recon_ts = time.time()
        # Синтезируем "наблюдения" из recon-профиля:
        # 1 наблюдение за протокол с весом = вероятность
        protocols = recon_data.get("protocols") or {}
        avg_size = int(recon_data.get("avg_packet_size", 800))
        avg_entropy = float(recon_data.get("avg_entropy", 0.7))
        # 5 семплов на каждый протокол — чтобы профиль ожил
        for proto, prob in protocols.items():
            try:
                weight = max(1, int(round(float(prob) * 10)))
            except Exception:
                weight = 1
            for _ in range(weight):
                self.observe(avg_size, proto, avg_entropy, interval_ms=100.0)
        self.stats["recon_feeds"] = self.stats.get("recon_feeds", 0) + 1
        return True

    def get_recon_profile(self):
        """P92c: последний recon-профиль."""
        return dict(self._recon_raw) if self._recon_raw else {}

    def get_network_type(self):
        """P92c: тип сети из recon."""
        return self._recon_raw.get("network_type", "unknown") if self._recon_raw else "unknown"

    def get_merged_profile(self):
        """P92c: профиль с учётом recon (если свой пуст — recon)."""
        p = self.get_profile()
        if p.total_packets == 0 and self._recon_raw:
            # Синтезировать профиль из recon
            proto = self._recon_raw.get("protocols") or {}
            dominant = max(proto, key=proto.get) if proto else "unknown"
            return AmbientProfile(
                timestamp=time.time(),
                total_packets=1,
                avg_size=float(self._recon_raw.get("avg_packet_size", 800)),
                avg_entropy=float(self._recon_raw.get("avg_entropy", 0.7)),
                dominant_protocol=dominant,
                typical_size=int(self._recon_raw.get("avg_packet_size", 800)),
                typical_entropy=float(self._recon_raw.get("avg_entropy", 0.7)),
                protocol_distribution=dict(proto),
            )
        return p

    def get_profile(self):
        if not self._samples:
            return AmbientProfile()
        sizes = [s["size"] for s in self._samples]
        entropies = [s["entropy"] for s in self._samples]
        intervals = [s["interval_ms"] for s in self._samples if s["interval_ms"] > 0]
        avg_size = sum(sizes) / len(sizes)
        avg_entropy = sum(entropies) / len(entropies)
        avg_interval = sum(intervals) / len(intervals) if intervals else 0.0
        dominant = self._protocol_counter.most_common(1)
        dominant_protocol = dominant[0][0] if dominant else "unknown"
        typical_size = int(statistics.median(sizes))
        typical_entropy = statistics.median(entropies)
        return AmbientProfile(
            timestamp=time.time(),
            sample_duration_ms=((self._timestamps[-1] - self._timestamps[0]) * 1000
                                if len(self._timestamps) > 1 else 0.0),
            size_distribution=dict(self._size_counter.most_common(10)),
            protocol_distribution=dict(self._protocol_counter),
            entropy_distribution={float(k): v for k, v in self._entropy_bins.items()},
            total_packets=len(self._samples),
            avg_size=avg_size, avg_entropy=avg_entropy,
            avg_interval_ms=avg_interval,
            dominant_protocol=dominant_protocol,
            typical_size=typical_size, typical_entropy=typical_entropy)

    def estimate_ambient_entropy(self):
        if not self._samples:
            return 0.5
        return sum(s["entropy"] for s in self._samples) / len(self._samples)

    def get_protocol_distribution(self):
        if not self._protocol_counter:
            return {}
        total = sum(self._protocol_counter.values())
        return {p: c / total for p, c in self._protocol_counter.items()}

    def get_size_distribution(self):
        if not self._size_counter:
            return {}
        total = sum(self._size_counter.values())
        return {s: c / total for s, c in self._size_counter.items()}

    def similarity_to_ambient(self, observed_protocol, observed_size, observed_entropy):
        if not self._samples:
            return 0.5
        proto_dist = self.get_protocol_distribution()
        p_proto = proto_dist.get(observed_protocol, 0.0)
        size_dist = self.get_size_distribution()
        closest_size = min(size_dist.keys(), key=lambda s: abs(s - observed_size),
                          default=observed_size)
        p_size = size_dist.get(closest_size, 0.0)
        avg_entropy = self.estimate_ambient_entropy()
        entropy_diff = abs(observed_entropy - avg_entropy)
        p_entropy = max(0.0, 1.0 - entropy_diff)
        return min(1.0, max(0.0, 0.4 * p_proto + 0.3 * p_size + 0.3 * p_entropy))

    def get_stats(self):
        return {
            **self.stats,
            "samples_in_buffer": len(self._samples),
            "unique_protocols": len(self._protocol_counter),
            "unique_sizes": len(self._size_counter),
        }

    def clear(self):
        self._samples.clear()
        self._timestamps.clear()
        self._size_counter.clear()
        self._protocol_counter.clear()
        self._entropy_bins.clear()

    def __repr__(self):
        return f"AmbientAnalyzer(samples={len(self._samples)})"


class AmbientMasker:
    def __init__(self, analyzer=None, adaptation_strength=0.7):
        self.analyzer = analyzer or AmbientAnalyzer()
        self.adaptation_strength = adaptation_strength
        self.adaptation_history = []
        # P92d: профиль сети (от разведчиков)
        self._network_profile = {}
        self._network_type = "unknown"

    def observe(self, size, protocol, entropy, interval_ms=0.0):
        self.analyzer.observe(size, protocol, entropy, interval_ms)

    def adapt_to_network(self, network_profile):
        """P92d: подстроить маскировку под профиль сети.

        network_profile = {network_type, protocols, avg_packet_size,
                           avg_entropy, ttl_typical, ...}
        """
        if not network_profile or not isinstance(network_profile, dict):
            return False
        self._network_profile = dict(network_profile)
        self._network_type = network_profile.get("network_type", "unknown")
        # Скорректировать силу адаптации:
        # corporate -> слабее (не выделяться), home -> среднее, public -> сильнее
        strength_map = {
            "corporate": 0.5,
            "home": 0.7,
            "public": 0.85,
            "unknown": 0.7,
        }
        self.adaptation_strength = strength_map.get(self._network_type, 0.7)
        # Передать recon в analyzer
        try:
            self.analyzer.feed_from_recon(network_profile)
        except Exception:
            pass
        self.adaptation_history.append({
            "event": "adapt_to_network",
            "network_type": self._network_type,
            "strength": self.adaptation_strength,
            "ts": time.time(),
        })
        logger.info("[P92d] adapted: type=%s strength=%.2f",
                    self._network_type, self.adaptation_strength)
        return True

    def get_network_profile(self):
        """P92d: текущий профиль сети."""
        return dict(self._network_profile) if self._network_profile else {}

    def get_network_type(self):
        """P92d: текущий тип сети."""
        return self._network_type

    def adapt_packet(self, size, protocol, entropy):
        profile = self.analyzer.get_profile()
        if profile.total_packets == 0:
            return {"size": size, "protocol": protocol,
                    "entropy": entropy, "adapted": False}
        adapted_size = int(size * (1 - self.adaptation_strength) +
                          profile.typical_size * self.adaptation_strength)
        if self.adaptation_strength > 0.5:
            adapted_protocol = profile.dominant_protocol
        else:
            adapted_protocol = protocol
        adapted_entropy = (entropy * (1 - self.adaptation_strength) +
                          profile.typical_entropy * self.adaptation_strength)
        result = {
            "size": adapted_size, "protocol": adapted_protocol,
            "entropy": adapted_entropy, "adapted": True,
            "similarity": self.analyzer.similarity_to_ambient(
                adapted_protocol, adapted_size, adapted_entropy),
        }
        self.adaptation_history.append({
            "original": {"size": size, "protocol": protocol, "entropy": entropy},
            "adapted": result, "timestamp": time.time(),
        })
        return result

    def adapt_to_features(self, features):
        adapted = self.adapt_packet(features.size_bytes, features.protocol,
                                    features.entropy)
        return PacketFeatures(
            port=features.port, protocol=adapted["protocol"],
            size_bytes=adapted["size"], entropy=adapted["entropy"],
            header_conformance=features.header_conformance,
            timing_regularity=features.timing_regularity,
            payload_entropy=adapted["entropy"],
            is_encrypted=features.is_encrypted)

    def evaluate_stealth(self, size, protocol, entropy):
        profile = self.analyzer.get_profile()
        if profile.total_packets == 0:
            return {"size_match": 0.5, "protocol_match": 0.5,
                    "entropy_match": 0.5, "overall": 0.5}
        size_diff = abs(size - profile.typical_size) / max(profile.typical_size, 1)
        size_match = max(0.0, 1.0 - size_diff)
        proto_dist = self.analyzer.get_protocol_distribution()
        protocol_match = proto_dist.get(protocol, 0.0)
        entropy_diff = abs(entropy - profile.typical_entropy)
        entropy_match = max(0.0, 1.0 - entropy_diff)
        overall = 0.4 * size_match + 0.3 * protocol_match + 0.3 * entropy_match
        return {"size_match": size_match, "protocol_match": protocol_match,
                "entropy_match": entropy_match, "overall": overall}

    def get_stats(self):
        return {
            "analyzer": self.analyzer.get_stats(),
            "adaptations": len(self.adaptation_history),
            "adaptation_strength": self.adaptation_strength,
        }

    def __repr__(self):
        return (f"AmbientMasker(strength={self.adaptation_strength}, "
                f"adaptations={len(self.adaptation_history)})")


class SpatialDensityModel:
    def __init__(self, density_per_km2=100.0, detection_range_km=0.1):
        self.density = density_per_km2
        self.detection_range = detection_range_km

    def poisson_probability(self, k, area_km2=1.0):
        lambda_a = self.density * area_km2
        try:
            return (lambda_a ** k) * math.exp(-lambda_a) / math.factorial(k)
        except (OverflowError, ValueError):
            return 0.0

    def expected_signals(self, area_km2=1.0):
        return self.density * area_km2

    def detection_probability(self, range_km=None):
        R = range_km or self.detection_range
        area = math.pi * (R ** 2)
        lambda_a = self.density * area
        return 1.0 - math.exp(-lambda_a)

    def non_detection_probability(self, range_km=None):
        return 1.0 - self.detection_probability(range_km)

    def mean_nearest_neighbor_distance(self):
        if self.density <= 0:
            return float("inf")
        return 1.0 / (2.0 * math.sqrt(self.density))

    def median_nearest_neighbor_distance(self):
        if self.density <= 0:
            return float("inf")
        return math.sqrt(math.log(2) / (math.pi * self.density))

    def distance_distribution(self, r):
        area = math.pi * (r ** 2)
        lambda_a = self.density * area
        return 1.0 - math.exp(-lambda_a)

    def distance_density(self, r):
        area = math.pi * (r ** 2)
        lambda_a = self.density * area
        return 2 * math.pi * self.density * r * math.exp(-lambda_a)

    def coverage_probability(self, n_nodes, area_km2=1.0):
        expected = self.density * area_km2
        if expected <= 0:
            return 0.0
        return self.poisson_probability(n_nodes, area_km2)

    def required_density_for_coverage(self, coverage_probability=0.95, area_km2=1.0):
        if coverage_probability <= 0 or coverage_probability >= 1:
            return float("inf")
        return -math.log(1 - coverage_probability) / area_km2

    def analyze(self, area_km2=1.0):
        return {
            "density": self.density,
            "area_km2": area_km2,
            "expected_signals": self.expected_signals(area_km2),
            "detection_probability": self.detection_probability(),
            "mean_nearest_distance": self.mean_nearest_neighbor_distance(),
            "median_nearest_distance": self.median_nearest_neighbor_distance(),
            "required_density_95": self.required_density_for_coverage(0.95, area_km2),
        }

    def __repr__(self):
        return f"SpatialDensityModel(λ={self.density}, R={self.detection_range})"


if __name__ == "__main__":
    print("Testing Ambient modules...")
    import random
    analyzer = AmbientAnalyzer()
    masker = AmbientMasker(analyzer, adaptation_strength=0.7)
    for _ in range(100):
        size = random.choice([512, 1024, 1400, 1500])
        protocol = random.choice(["HTTP", "HTTPS", "DNS", "ICMP"])
        entropy = random.uniform(0.2, 0.8)
        masker.observe(size, protocol, entropy)
    profile = analyzer.get_profile()
    print(f"Dominant protocol: {profile.dominant_protocol}")
    print(f"Typical size: {profile.typical_size}")
    adapted = masker.adapt_packet(2000, "CUSTOM", 0.95)
    print(f"Adapted: {adapted}")
    model = SpatialDensityModel(density_per_km2=1000.0, detection_range_km=0.1)
    analysis = model.analyze(1.0)
    print(f"Detection prob: {analysis['detection_probability']:.4f}")
    print(f"Mean distance: {analysis['mean_nearest_distance']:.4f} km")
    print("OK")
