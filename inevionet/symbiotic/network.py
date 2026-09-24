"""InevioNet Symbiotic Network - симбиотическая сеть."""
import time
import random
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

from ..core.logger import get_logger
from ..core.packet import GDPPacket

logger = get_logger("inevionet.symbiotic.network")


class SymbioticNetwork:
    """
    Симбиотическая сеть - сеть, вступающая в симбиоз с пакетами.
    Сеть получает: феромоны, данные, обучение.
    Пакет получает: приоритет, восстановление TTL, резервные маршруты.
    """

    def __init__(self, name, network_type="generic", initial_health=0.8,
                 initial_resource=0.7, initial_trust=0.5):
        self.name = name
        self.network_type = network_type
        self.health = initial_health
        self.resource = initial_resource
        self.trust = initial_trust
        self.rewards = {
            "pheromones": 0.3,
            "data": 0.2,
            "intelligence": 0.4,
            "energy": 0.1,
        }
        self.symbionts: Dict[str, Dict[str, Any]] = {}
        self.packets_processed = 0
        self.packets_delivered = 0
        self.packets_failed = 0
        self.symbiotic_events = 0
        self.history: List[Dict[str, Any]] = []
        logger.debug(f"SymbioticNetwork created: {name} ({network_type})")

    def calculate_benefit(self, packet: GDPPacket) -> float:
        """Вычислить выгоду от обработки пакета."""
        benefit = 0.0
        if "pheromones" in packet.metadata:
            benefit += self.rewards["pheromones"] * float(packet.metadata.get("pheromones", 0))
        else:
            benefit += self.rewards["pheromones"] * 0.3
        if packet.payload:
            data_factor = min(1.0, len(packet.payload) / 4096)
            benefit += self.rewards["data"] * data_factor
        if "new_route" in packet.metadata or "optimized" in packet.metadata:
            benefit += self.rewards["intelligence"] * 0.5
        else:
            benefit += self.rewards["intelligence"] * 0.2
        if "optimized" in packet.metadata:
            benefit += self.rewards["energy"] * 0.5
        else:
            benefit += self.rewards["energy"] * 0.2
        benefit *= (0.5 + self.health * 0.5)
        benefit *= (0.3 + self.resource * 0.7)
        if self.trust > 0.7:
            benefit *= 1.2
        return min(1.0, benefit)

    def should_process(self, packet: GDPPacket) -> bool:
        """Решить, вступать ли в симбиоз с пакетом."""
        benefit = self.calculate_benefit(packet)
        threshold = 0.25 + (1.0 - self.resource) * 0.3
        if self.trust > 0.7:
            threshold *= 0.7
        return benefit > threshold

    def record_symbiosis(self, packet: GDPPacket, benefit: float = None):
        """Записать факт симбиоза."""
        if benefit is None:
            benefit = self.calculate_benefit(packet)
        pid = packet.packet_id
        self.symbionts[pid] = {
            "benefit": benefit,
            "timestamp": time.time(),
            "generation": packet.metadata.get("generation", 0),
        }
        self.packets_processed += 1
        self.symbiotic_events += 1
        self.resource = max(0.1, self.resource - benefit * 0.01)
        self.health = min(1.0, self.health + benefit * 0.005)
        self.trust = min(1.0, self.trust + benefit * 0.01)
        if len(self.symbionts) > 1000:
            sorted_items = sorted(self.symbionts.items(), key=lambda x: x[1]["timestamp"])
            for k, _ in sorted_items[:500]:
                del self.symbionts[k]

    def record_delivery(self, packet: GDPPacket, success: bool):
        if success:
            self.packets_delivered += 1
            self.trust = min(1.0, self.trust + 0.02)
        else:
            self.packets_failed += 1
            self.trust = max(0.1, self.trust - 0.01)

    def heal(self) -> float:
        """Самовосстановление сети."""
        if self.health >= 0.9:
            self.resource = min(1.0, self.resource + 0.01)
            return 0.0
        healing = 0.02 * (1.0 - self.health)
        self.health = min(1.0, self.health + healing)
        self.resource = min(1.0, self.resource + 0.005)
        return healing

    def get_capabilities(self):
        return {
            "name": self.name,
            "type": self.network_type,
            "health": self.health,
            "resource": self.resource,
            "trust": self.trust,
            "success_rate": (self.packets_delivered / self.packets_processed
                             if self.packets_processed > 0 else 0.0),
        }

    def get_stats(self):
        return {
            **self.get_capabilities(),
            "symbionts": len(self.symbionts),
            "symbiotic_events": self.symbiotic_events,
            "packets_processed": self.packets_processed,
            "packets_delivered": self.packets_delivered,
            "packets_failed": self.packets_failed,
        }

    def __repr__(self):
        return (f"SymbioticNetwork({self.name}, "
                f"health={self.health:.2f}, trust={self.trust:.2f})")


if __name__ == "__main__":
    print("Testing SymbioticNetwork...")
    from ..core.packet import create_packet
    network = SymbioticNetwork("5G-Moscow", "cellular")
    print(f"Network: {network}")
    packet = create_packet("alice", "bob", b"Test data")
    benefit = network.calculate_benefit(packet)
    print(f"Benefit: {benefit:.3f}")
    if network.should_process(packet):
        network.record_symbiosis(packet, benefit)
        network.record_delivery(packet, True)
        print(f"Symbiosis recorded")
    for i in range(100):
        p = create_packet("x", "y", b"data" * 10)
        b = network.calculate_benefit(p)
        if network.should_process(p):
            network.record_symbiosis(p, b)
            network.record_delivery(p, True)
    stats = network.get_stats()
    print(f"Stats: processed={stats['packets_processed']}, "
          f"success_rate={stats['success_rate']:.2%}")
    print("SymbioticNetwork module OK")
