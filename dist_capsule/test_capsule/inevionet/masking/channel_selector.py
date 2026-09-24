"""InevioNet Channel Selector."""
import random
import math
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from .vulnerability_map import VulnerabilityMap
from .bayesian import BayesianUpdater


@dataclass
class ChannelScore:
    channel: str
    probability: float
    capacity: float
    cost: float
    latency_ms: float
    stealth: float

    @property
    def score(self):
        numerator = self.probability * math.log(1 + self.capacity) * self.stealth
        denominator = (0.1 + self.cost) * (1.0 + self.latency_ms / 1000.0)
        return numerator / denominator if denominator > 0 else 0.0

    def __repr__(self):
        return f"ChannelScore({self.channel}, P={self.probability:.3f}, score={self.score:.4f})"


class ChannelSelector:
    PROFILES = {
        "HTTP": {"capacity": 4096, "cost": 0.2, "latency_ms": 50, "stealth": 0.85},
        "HTTPS": {"capacity": 4096, "cost": 0.2, "latency_ms": 50, "stealth": 0.9},
        "DNS": {"capacity": 253, "cost": 0.1, "latency_ms": 30, "stealth": 0.95},
        "ICMP": {"capacity": 1472, "cost": 0.3, "latency_ms": 20, "stealth": 0.8},
        "WebSocket": {"capacity": 65536, "cost": 0.15, "latency_ms": 25, "stealth": 0.75},
        "TLS": {"capacity": 512, "cost": 0.2, "latency_ms": 60, "stealth": 0.9},
        "QUIC": {"capacity": 1400, "cost": 0.2, "latency_ms": 30, "stealth": 0.85},
        "NTP": {"capacity": 48, "cost": 0.05, "latency_ms": 40, "stealth": 0.95},
        "SMTP": {"capacity": 1024, "cost": 0.3, "latency_ms": 100, "stealth": 0.6},
        "MQTT": {"capacity": 256, "cost": 0.1, "latency_ms": 40, "stealth": 0.7},
        # === P11.2a: новые каналы ===
        "LTE":         {"capacity": 1400, "cost": 0.4,  "latency_ms": 60,  "stealth": 0.90},
        "BLE":         {"capacity": 512,  "cost": 0.2,  "latency_ms": 20,  "stealth": 0.95},
        "Timing":      {"capacity": 32,   "cost": 0.05, "latency_ms": 200, "stealth": 0.99},
        "Polymorphic": {"capacity": 8192, "cost": 0.3,  "latency_ms": 80,  "stealth": 0.95},
    }

    def __init__(self, vmap=None, bayesian=None, exploration_rate=0.1):
        self.vmap = vmap or VulnerabilityMap()
        self.bayesian = bayesian or BayesianUpdater()
        self.exploration_rate = exploration_rate

    def update(self, node, channel, success, time_ms=0.0):
        self.vmap.record(node, channel, success, time_ms)
        self.bayesian.update(f"{node}:{channel}", success)

    def score_channel(self, node, channel):
        profile = self.PROFILES.get(channel, {"capacity": 512, "cost": 0.3,
                                              "latency_ms": 50, "stealth": 0.5})
        record = self.vmap.get_channel_record(node, channel)
        if record and record.attempts > 0:
            p_local = record.reliability
        else:
            p_local = 0.5
        p_bayes = self.bayesian.get_probability(f"{node}:{channel}")
        probability = 0.4 * p_local + 0.6 * p_bayes
        if record:
            if record.state.value == "blocked":
                probability *= 0.1
            elif record.state.value == "working":
                probability = min(1.0, probability * 1.2)
        return ChannelScore(
            channel=channel, probability=probability,
            capacity=profile["capacity"], cost=profile["cost"],
            latency_ms=profile["latency_ms"], stealth=profile["stealth"])

    def score_all_channels(self, node, channels=None):
        channels = channels or list(self.PROFILES.keys())
        scores = [self.score_channel(node, c) for c in channels]
        scores.sort(key=lambda s: s.score, reverse=True)
        return scores

    def select(self, node, channels=None, randomize=True):
        scores = self.score_all_channels(node, channels)
        if not scores:
            return None
        if not randomize:
            return scores[0]
        top = scores[:3]
        total = sum(s.score for s in top)
        if total <= 0:
            return top[0]
        pick = random.uniform(0, total)
        current = 0
        for score in top:
            current += score.score
            if current >= pick:
                return score
        return top[-1]

    def select_with_ucb(self, node, channels):
        for channel in channels:
            record = self.vmap.get_channel_record(node, channel)
            if record is None or record.attempts < 2:
                return channel
        bayesian_channels = [f"{node}:{c}" for c in channels]
        best_key = self.bayesian.select_best_channel(
            bayesian_channels, exploration_rate=self.exploration_rate)
        if best_key.startswith(f"{node}:"):
            return best_key[len(node) + 1:]
        return channels[0]

    def get_recommendations(self, node):
        scores = self.score_all_channels(node)
        return {
            "node": node,
            "best_channel": scores[0].channel if scores else None,
            "best_score": scores[0].score if scores else 0.0,
            "top_3": [{"channel": s.channel, "score": s.score} for s in scores[:3]],
            "working": self.vmap.get_working_channels(node),
            "blocked": self.vmap.get_blocked_channels(node),
        }

    def get_stats(self):
        return {
            "vmap": self.vmap.get_stats(),
            "bayesian": self.bayesian.get_stats(),
            "channels_known": len(self.PROFILES),
        }

    def __repr__(self):
        return f"ChannelSelector(channels={len(self.PROFILES)})"


if __name__ == "__main__":
    print("Testing ChannelSelector...")
    vmap = VulnerabilityMap()
    for _ in range(5):
        vmap.record("node1", "HTTP", True, 25)
    for _ in range(5):
        vmap.record("node1", "SMTP", False)
    sel = ChannelSelector(vmap)
    best = sel.select("node1")
    print(f"Best: {best.channel} (score={best.score:.4f})")
    scores = sel.score_all_channels("node1")
    for s in scores[:3]:
        print(f"  {s.channel}: {s.score:.4f}")
    print("OK")

