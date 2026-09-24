"""InevioNet Firewall/DPI Model."""
import math
from enum import Enum
from typing import Dict, List, Optional
from dataclasses import dataclass


class FirewallAction(str, Enum):
    PASS = "pass"
    BLOCK = "block"
    INSPECT = "inspect"


@dataclass
class PacketFeatures:
    port: int = 80
    protocol: str = "TCP"
    size_bytes: int = 1400
    entropy: float = 0.5
    header_conformance: float = 1.0
    timing_regularity: float = 0.5
    payload_entropy: float = 0.5
    is_encrypted: bool = False
    has_known_signature: bool = False


class DPIModel:
    def __init__(self, threshold=0.7, profile="medium"):
        self.threshold = threshold
        self.profile = profile
        profiles = {
            "low": {"size": 0.10, "entropy": 0.15, "header": 0.30, "timing": 0.10,
                    "payload": 0.15, "encryption": 0.10, "signature": 0.10},
            "medium": {"size": 0.10, "entropy": 0.20, "header": 0.25, "timing": 0.10,
                       "payload": 0.20, "encryption": 0.05, "signature": 0.10},
            "high": {"size": 0.10, "entropy": 0.25, "header": 0.20, "timing": 0.15,
                     "payload": 0.20, "encryption": 0.05, "signature": 0.05},
            "military": {"size": 0.15, "entropy": 0.25, "header": 0.15, "timing": 0.20,
                         "payload": 0.15, "encryption": 0.05, "signature": 0.05},
        }
        self.weights = profiles.get(profile, profiles["medium"])

    def _f_entropy(self, entropy):
        if entropy < 0.3:
            return 0.0
        elif entropy < 0.7:
            return (entropy - 0.3) / 0.4 * 0.5
        return 0.5 + (entropy - 0.7) / 0.3 * 0.5

    def _f_size(self, size):
        if 64 <= size <= 1500:
            return 0.0
        elif size < 64:
            return 0.3
        return min(1.0, (size - 1500) / 5000)

    def _f_header(self, conformance):
        return 1.0 - conformance

    def _f_timing(self, regularity):
        return 1.0 - abs(regularity - 0.5) * 2

    def _f_payload_entropy(self, entropy):
        return entropy

    def _f_encryption(self, is_encrypted):
        return 0.1 if is_encrypted else 0.0

    def _f_signature(self, has_signature):
        return 0.9 if has_signature else 0.0

    def _sigmoid(self, x):
        try:
            return 1.0 / (1.0 + math.exp(-x))
        except OverflowError:
            return 0.0 if x < 0 else 1.0

    def detection_probability(self, features):
        score = (
            self.weights["size"] * self._f_size(features.size_bytes) +
            self.weights["entropy"] * self._f_entropy(features.entropy) +
            self.weights["header"] * self._f_header(features.header_conformance) +
            self.weights["timing"] * self._f_timing(features.timing_regularity) +
            self.weights["payload"] * self._f_payload_entropy(features.payload_entropy) +
            self.weights["encryption"] * self._f_encryption(features.is_encrypted) +
            self.weights["signature"] * self._f_signature(features.has_known_signature))
        return self._sigmoid((score - self.threshold) * 10)

    def decide(self, features):
        p = self.detection_probability(features)
        if p < 0.5:
            return FirewallAction.PASS
        elif p < 0.8:
            return FirewallAction.INSPECT
        return FirewallAction.BLOCK

    def get_score_breakdown(self, features):
        return {
            "size": self.weights["size"] * self._f_size(features.size_bytes),
            "entropy": self.weights["entropy"] * self._f_entropy(features.entropy),
            "header": self.weights["header"] * self._f_header(features.header_conformance),
            "timing": self.weights["timing"] * self._f_timing(features.timing_regularity),
            "payload": self.weights["payload"] * self._f_payload_entropy(features.payload_entropy),
            "encryption": self.weights["encryption"] * self._f_encryption(features.is_encrypted),
            "signature": self.weights["signature"] * self._f_signature(features.has_known_signature),
            "threshold": self.threshold,
        }

    def update_threshold(self, new_threshold):
        self.threshold = max(0.0, min(1.0, new_threshold))

    def __repr__(self):
        return f"DPIModel(profile={self.profile}, threshold={self.threshold})"


class FirewallModel:
    def __init__(self, name="firewall", dpi_profile="medium", threshold=0.7,
                 default_action=FirewallAction.PASS):
        self.name = name
        self.dpi = DPIModel(threshold=threshold, profile=dpi_profile)
        self.default_action = default_action
        self.blocked_ports = set()
        self.allowed_ports = set()
        self.stats = {"checked": 0, "passed": 0, "blocked": 0, "inspected": 0}

    def block_port(self, port):
        self.blocked_ports.add(port)

    def allow_port(self, port):
        self.allowed_ports.add(port)
        if port in self.blocked_ports:
            self.blocked_ports.remove(port)

    def check(self, features):
        self.stats["checked"] += 1
        if features.port in self.blocked_ports:
            self.stats["blocked"] += 1
            return FirewallAction.BLOCK
        action = self.dpi.decide(features)
        if features.port in self.allowed_ports and action == FirewallAction.PASS:
            self.stats["passed"] += 1
            return FirewallAction.PASS
        if action == FirewallAction.BLOCK:
            self.stats["blocked"] += 1
        elif action == FirewallAction.INSPECT:
            self.stats["inspected"] += 1
        else:
            self.stats["passed"] += 1
        return action

    def get_stats(self):
        return {
            "name": self.name,
            "dpi_profile": self.dpi.profile,
            "threshold": self.dpi.threshold,
            "blocked_ports": list(self.blocked_ports),
            "allowed_ports": list(self.allowed_ports),
            **self.stats,
            "pass_rate": self.stats["passed"] / self.stats["checked"] if self.stats["checked"] > 0 else 0.0,
        }

    def __repr__(self):
        return f"FirewallModel({self.name}, dpi={self.dpi.profile})"


if __name__ == "__main__":
    print("Testing FirewallModel...")
    fw = FirewallModel("test_fw", dpi_profile="high")
    fw.block_port(25)
    features = PacketFeatures(port=80, protocol="HTTP", size_bytes=350, entropy=0.15)
    p = fw.dpi.detection_probability(features)
    action = fw.check(features)
    print(f"P_detect: {p:.4f}")
    print(f"Action: {action.value}")
    print("OK")
