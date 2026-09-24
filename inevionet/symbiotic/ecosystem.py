"""InevioNet Symbiotic Ecosystem - экосистема сетей."""
import time
import random
from typing import Dict, List, Any, Optional

from .network import SymbioticNetwork
from ..core.packet import GDPPacket
from ..core.logger import get_logger

logger = get_logger("inevionet.symbiotic.ecosystem")


class SymbioticEcosystem:
    """Симбиотическая экосистема - набор сетей."""

    def __init__(self, auto_heal=True, heal_interval=5.0):
        self.networks: Dict[str, SymbioticNetwork] = {}
        self.auto_heal = auto_heal
        self.heal_interval = heal_interval
        self._last_heal = time.time()
        self._total_processed = 0
        self._total_delivered = 0
        self._total_failed = 0
        self.inter_network_links: Dict[str, Dict[str, float]] = {}

    def add_network(self, name, network_type="generic", **kwargs):
        if name in self.networks:
            return self.networks[name]
        network = SymbioticNetwork(name, network_type, **kwargs)
        self.networks[name] = network
        for existing_name in self.networks:
            if existing_name == name:
                continue
            strength = random.uniform(0.3, 0.9)
            self.inter_network_links[f"{name}->{existing_name}"] = {
                "strength": strength, "created": time.time()}
            self.inter_network_links[f"{existing_name}->{name}"] = {
                "strength": strength, "created": time.time()}
        return network

    def remove_network(self, name):
        if name in self.networks:
            del self.networks[name]
            keys_to_remove = [k for k in self.inter_network_links
                              if k.startswith(f"{name}->") or k.endswith(f"->{name}")]
            for k in keys_to_remove:
                del self.inter_network_links[k]

    def create_standard_networks(self):
        standard = [
            ("5G", "cellular", {"initial_health": 0.9, "initial_trust": 0.6}),
            ("4G", "cellular", {"initial_health": 0.85, "initial_trust": 0.55}),
            ("WiFi", "wifi", {"initial_health": 0.8, "initial_trust": 0.7}),
            ("Satellite", "satellite", {"initial_health": 0.7, "initial_trust": 0.5}),
            ("Mesh", "mesh", {"initial_health": 0.75, "initial_trust": 0.8}),
            ("IoT", "iot", {"initial_health": 0.6, "initial_trust": 0.6}),
        ]
        for name, t, kwargs in standard:
            self.add_network(name, t, **kwargs)

    def select_best_network(self, packet: GDPPacket) -> Optional[str]:
        """Выбрать лучшую сеть для пакета."""
        if not self.networks:
            return None
        candidates = []
        for name, network in self.networks.items():
            if not network.should_process(packet):
                continue
            benefit = network.calculate_benefit(packet)
            score = (benefit * 0.5 + network.health * 0.25 +
                     network.trust * 0.15 + network.resource * 0.10)
            candidates.append((name, score))
        if not candidates:
            best = max(self.networks.values(), key=lambda n: n.health)
            return best.name
        candidates.sort(key=lambda x: x[1], reverse=True)
        top = candidates[:3]
        if len(top) == 1:
            return top[0][0]
        total = sum(s for _, s in top)
        if total == 0:
            return top[0][0]
        pick = random.uniform(0, total)
        current = 0
        for name, score in top:
            current += score
            if current >= pick:
                return name
        return top[-1][0]

    def process(self, packet: GDPPacket, network_name: Optional[str] = None) -> bool:
        if network_name is None:
            network_name = self.select_best_network(packet)
        if network_name not in self.networks:
            return False
        network = self.networks[network_name]
        if not network.should_process(packet):
            return False
        benefit = network.calculate_benefit(packet)
        network.record_symbiosis(packet, benefit)
        self._total_processed += 1
        return True

    def process_multiple(self, packet: GDPPacket, max_networks=3):
        processed_in = []
        sorted_networks = sorted(self.networks.values(),
                                 key=lambda n: n.health * n.trust, reverse=True)
        for network in sorted_networks[:max_networks]:
            if network.should_process(packet):
                benefit = network.calculate_benefit(packet)
                network.record_symbiosis(packet, benefit)
                processed_in.append(network.name)
                self._total_processed += 1
        return processed_in

    def record_delivery(self, network_name, success):
        if network_name in self.networks:
            network = self.networks[network_name]
            class FakePacket:
                packet_id = "fake"
                metadata = {}
                payload = b""
            network.record_delivery(FakePacket(), success)
        if success:
            self._total_delivered += 1
        else:
            self._total_failed += 1

    def auto_heal_networks(self):
        now = time.time()
        if now - self._last_heal < self.heal_interval:
            return
        self._last_heal = now
        for network in self.networks.values():
            network.heal()

    def get_ecosystem_health(self):
        if not self.networks:
            return 0.0
        return sum(n.health for n in self.networks.values()) / len(self.networks)

    def get_stats(self):
        network_stats = {name: network.get_stats()
                        for name, network in self.networks.items()}
        return {
            "networks_count": len(self.networks),
            "ecosystem_health": self.get_ecosystem_health(),
            "total_processed": self._total_processed,
            "total_delivered": self._total_delivered,
            "total_failed": self._total_failed,
            "success_rate": (self._total_delivered / self._total_processed
                             if self._total_processed > 0 else 0.0),
            "networks": network_stats,
            "inter_network_links": len(self.inter_network_links),
        }

    def __repr__(self):
        return (f"SymbioticEcosystem(networks={len(self.networks)}, "
                f"health={self.get_ecosystem_health():.2f})")


if __name__ == "__main__":
    print("Testing SymbioticEcosystem...")
    from ..core.packet import create_packet
    eco = SymbioticEcosystem()
    eco.create_standard_networks()
    print(f"Ecosystem: {eco}")
    print(f"Networks: {list(eco.networks.keys())}")
    print(f"Links: {len(eco.inter_network_links)}")

    network_usage = {}
    for i in range(50):
        p = create_packet(f"user_{i}", f"target_{i}",
                          b"data" * random.randint(5, 50),
                          metadata={"pheromones": random.random()})
        name = eco.select_best_network(p)
        if eco.process(p, name):
            network_usage[name] = network_usage.get(name, 0) + 1
            eco.record_delivery(name, success=random.random() > 0.1)

    print(f"Network usage: {network_usage}")
    stats = eco.get_stats()
    print(f"Ecosystem health: {stats['ecosystem_health']:.3f}")
    print(f"Success rate: {stats['success_rate']:.2%}")
    print("SymbioticEcosystem module OK")
