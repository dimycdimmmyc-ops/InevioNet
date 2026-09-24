"""InevioNet Penetration - методы проникновения."""
import time
import random
import threading
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

from ..core.logger import get_logger
from ..core.constants import is_root

logger = get_logger("inevionet.mycelium.penetration")


@dataclass
class PenetrationMethod:
    """Метод проникновения с адаптацией."""
    name: str
    protocol: str
    description: str = ""
    initial_success_rate: float = 0.5
    requires_root: bool = False
    active: bool = True
    uses: int = 0
    successes: int = 0
    failures: int = 0
    last_used: float = 0.0
    last_success: float = 0.0
    current_rate: float = 0.0

    def __post_init__(self):
        if self.current_rate == 0.0:
            self.current_rate = self.initial_success_rate

    @property
    def success_rate(self):
        if self.uses < 5:
            return self.initial_success_rate * 0.7 + self.current_rate * 0.3
        return self.successes / self.uses

    @property
    def reliability(self):
        confidence = min(1.0, self.uses / 20)
        return self.success_rate * confidence + 0.5 * (1 - confidence)

    def record_attempt(self, success):
        self.uses += 1
        self.last_used = time.time()
        if success:
            self.successes += 1
            self.last_success = time.time()
            self.current_rate = min(1.0, self.current_rate * 0.9 + 0.1)
        else:
            self.failures += 1
            self.current_rate = max(0.1, self.current_rate * 0.95)

    def to_dict(self):
        return {
            "name": self.name, "protocol": self.protocol,
            "uses": self.uses, "successes": self.successes,
            "failures": self.failures, "current_rate": self.current_rate,
            "active": self.active,
        }

    def __repr__(self):
        status = "OK" if self.active else "OFF"
        return f"[{status}] {self.name} ({self.protocol}, rate={self.success_rate:.2f})"


class PenetrationEngine:
    """Движок проникновения с адаптацией."""

    def __init__(self, timeout=10.0):
        self.timeout = timeout
        self.methods: Dict[str, PenetrationMethod] = {}
        self._lock = threading.Lock()
        self.blocked: Dict[str, float] = {}
        self._init_methods()
        self.is_root = is_root()
        self._update_active_by_permissions()

    def _init_methods(self):
        methods_data = [
            ("DNS_Tunneling", "DNS", "DNS queries for data", 0.85, False),
            ("HTTP_Tunneling", "HTTPS", "HTTP/HTTPS disguise", 0.90, False),
            ("ICMP_Tunneling", "ICMP", "ICMP payload", 0.75, True),
            ("TCP_Tunneling", "TCP", "TCP tunneling", 0.92, False),
            ("UDP_Tunneling", "UDP", "UDP tunneling", 0.80, False),
            ("WebSocket_Tunneling", "WEBSOCKET", "WebSocket frames", 0.88, False),
        ]
        for name, proto, desc, rate, root in methods_data:
            self.methods[name] = PenetrationMethod(
                name=name, protocol=proto, description=desc,
                initial_success_rate=rate, requires_root=root)

    def _update_active_by_permissions(self):
        for m in self.methods.values():
            if m.requires_root and not self.is_root:
                m.active = False

    def penetrate(self, target_network, test_data=b"INEVIONET_PROBE",
                  max_attempts=5):
        """Попытаться проникнуть в сеть."""
        with self._lock:
            methods = sorted([m for m in self.methods.values() if m.active],
                             key=lambda m: m.reliability, reverse=True)
        if not methods:
            return False, None
        attempts = 0
        for method in methods:
            if attempts >= max_attempts:
                break
            key = f"{target_network}:{method.name}"
            if key in self.blocked:
                if time.time() - self.blocked[key] > 300:
                    del self.blocked[key]
                else:
                    continue
            attempts += 1
            success = self._try_method(method, target_network, test_data)
            method.record_attempt(success)
            if success:
                return True, method.name
            if method.uses >= 5 and method.success_rate < 0.2:
                self.blocked[key] = time.time()
        return False, None

    def _try_method(self, method, target_network, test_data):
        try:
            from ..network.transport import UniversalTransport
            transport = UniversalTransport(timeout=self.timeout)
            protocol_map = {
                "HTTPS": ("HTTP", "http://httpbin.org/get"),
                "HTTP": ("HTTP", "http://httpbin.org/get"),
                "DNS": ("DNS", "test.example.com"),
                "ICMP": ("ICMP", "8.8.8.8"),
                "TCP": ("TCP", "example.com:80"),
                "UDP": ("UDP", "8.8.8.8:53"),
                "WEBSOCKET": ("WebSocket", "wss://echo.websocket.org"),
            }
            if method.protocol not in protocol_map:
                return False
            proto, target = protocol_map[method.protocol]
            result = transport.send(test_data, proto, target)
            transport.close()
            return result.success
        except Exception as e:
            logger.debug(f"Method {method.name} error: {e}")
            return False

    def get_best_method(self):
        with self._lock:
            active = [m for m in self.methods.values() if m.active]
        if not active:
            return None
        return max(active, key=lambda m: m.reliability)

    def get_working_methods(self):
        with self._lock:
            return [m for m in self.methods.values()
                    if m.active and m.success_rate > 0.5]

    def enable_method(self, name):
        if name in self.methods:
            self.methods[name].active = True

    def disable_method(self, name):
        if name in self.methods:
            self.methods[name].active = False

    def unblock_network(self, network):
        keys_to_remove = [k for k in self.blocked if k.startswith(f"{network}:")]
        for k in keys_to_remove:
            del self.blocked[k]

    def get_stats(self):
        with self._lock:
            methods_stats = {name: m.to_dict() for name, m in self.methods.items()}
        return {
            "methods_count": len(self.methods),
            "active_methods": sum(1 for m in self.methods.values() if m.active),
            "is_root": self.is_root,
            "blocked_count": len(self.blocked),
            "methods": methods_stats,
        }

    def __repr__(self):
        active = sum(1 for m in self.methods.values() if m.active)
        return f"PenetrationEngine(methods={len(self.methods)}, active={active})"


if __name__ == "__main__":
    print("Testing PenetrationEngine...")
    engine = PenetrationEngine()
    print(f"Engine: {engine}")
    print(f"Root: {engine.is_root}")
    print(f"Active methods: {sum(1 for m in engine.methods.values() if m.active)}")
    for network in ["5G_Network", "WiFi_Network", "Satellite_Network"]:
        success, method = engine.penetrate(network, max_attempts=2)
        status = "OK" if success else "FAIL"
        print(f"  [{status}] {network}: {method if method else 'no method'}")
    best = engine.get_best_method()
    if best:
        print(f"Best: {best.name} (rate={best.success_rate:.2f})")
    print("PenetrationEngine module OK")
