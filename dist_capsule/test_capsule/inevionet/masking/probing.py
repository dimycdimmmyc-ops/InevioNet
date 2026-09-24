"""InevioNet Prober."""
import time
import random
from enum import Enum
from typing import List, Dict, Optional
from dataclasses import dataclass


class ProbeType(str, Enum):
    HTTP_GET = "http_get"
    HTTPS_HELLO = "https_hello"
    DNS_QUERY = "dns_query"
    ICMP_ECHO = "icmp_echo"
    TLS_HANDSHAKE = "tls_handshake"
    WEBSOCKET = "websocket"


@dataclass
class ProbeResult:
    probe_type: str
    target: str
    success: bool
    action: str = "unknown"
    response_time_ms: float = 0.0
    timestamp: float = 0.0
    error: Optional[str] = None

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def __repr__(self):
        status = "OK" if self.success else "FAIL"
        return f"[{status}] Probe({self.probe_type} -> {self.target}, {self.response_time_ms:.1f}ms)"


class Prober:
    def __init__(self, timeout=5.0, max_retries=2, randomize_timing=True):
        self.timeout = timeout
        self.max_retries = max_retries
        self.randomize_timing = randomize_timing
        self.stats = {"total": 0, "successful": 0, "failed": 0, "blocked": 0}

    def _get_probe_features(self, probe_type, target):
        from .firewall_model import PacketFeatures
        features_map = {
            ProbeType.HTTP_GET.value: PacketFeatures(port=80, protocol="HTTP", size_bytes=350,
                                                    entropy=0.15, header_conformance=0.98),
            ProbeType.HTTPS_HELLO.value: PacketFeatures(port=443, protocol="HTTPS", size_bytes=517,
                                                       entropy=0.4, is_encrypted=True),
            ProbeType.DNS_QUERY.value: PacketFeatures(port=53, protocol="DNS", size_bytes=45,
                                                     entropy=0.2),
            ProbeType.ICMP_ECHO.value: PacketFeatures(port=0, protocol="ICMP", size_bytes=64,
                                                     entropy=0.3),
            ProbeType.TLS_HANDSHAKE.value: PacketFeatures(port=443, protocol="TLS", size_bytes=517,
                                                         entropy=0.35, is_encrypted=True),
            ProbeType.WEBSOCKET.value: PacketFeatures(port=80, protocol="WebSocket", size_bytes=400,
                                                     entropy=0.4),
        }
        return features_map.get(probe_type, PacketFeatures())

    def probe(self, probe_type, target, firewall_model=None):
        self.stats["total"] += 1
        start = time.time()
        if firewall_model is not None:
            features = self._get_probe_features(probe_type, target)
            from .firewall_model import FirewallAction
            action = firewall_model.check(features)
            success = action == FirewallAction.PASS
        else:
            rates = {
                "http_get": 0.95, "https_hello": 0.90, "dns_query": 0.98,
                "icmp_echo": 0.75, "tls_handshake": 0.92, "websocket": 0.88,
            }
            rate = rates.get(probe_type, 0.5)
            success = random.random() < rate
        elapsed = (time.time() - start) * 1000 + random.uniform(5, 50)
        if success:
            self.stats["successful"] += 1
        else:
            self.stats["failed"] += 1
        return ProbeResult(probe_type=probe_type, target=target,
                          success=success, response_time_ms=elapsed,
                          action="pass" if success else "block")

    def probe_all(self, target, probe_types=None, firewall_model=None, delay=0.01):
        probe_types = probe_types or [p.value for p in ProbeType]
        results = []
        for pt in probe_types:
            result = self.probe(pt, target, firewall_model)
            results.append(result)
            if delay > 0:
                time.sleep(delay)
        return results

    def analyze_results(self, results):
        if not results:
            return {"success_rate": 0.0}
        successful = [r for r in results if r.success]
        failed = [r for r in results if not r.success]
        return {
            "total": len(results),
            "successful": len(successful),
            "failed": len(failed),
            "success_rate": len(successful) / len(results),
            "avg_time_ms": sum(r.response_time_ms for r in results) / len(results),
            "best_protocols": [r.probe_type for r in successful],
            "blocked_protocols": [r.probe_type for r in failed],
        }

    def get_stats(self):
        return dict(self.stats)

    def __repr__(self):
        return f"Prober(timeout={self.timeout}, total={self.stats['total']})"


if __name__ == "__main__":
    print("Testing Prober...")
    prober = Prober()
    results = prober.probe_all("test.example.com", delay=0)
    analysis = prober.analyze_results(results)
    print(f"Success rate: {analysis['success_rate']:.2%}")
    print(f"Best protocols: {analysis['best_protocols']}")
    print("OK")
