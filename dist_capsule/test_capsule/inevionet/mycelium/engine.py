"""InevioNet Mycelium Engine - главный движок мицелия."""
import time
import random
import threading
from typing import Dict, List, Optional, Any, Tuple

from .penetration import PenetrationEngine
from .spores import SporeManager
from .pheromones import PheromoneEngine
from ..core.packet import GDPPacket
from ..core.logger import get_logger

logger = get_logger("inevionet.mycelium.engine")


class MyceliumEngine:
    """Главный движок мицелия."""

    def __init__(self, node_id="local_node", auto_spread=True, auto_heal=True,
                 tick_interval=60.0):
        self.node_id = node_id
        self.auto_spread = auto_spread
        self.auto_heal = auto_heal
        self.tick_interval = tick_interval
        self.penetration = PenetrationEngine()
        self.spores = SporeManager()
        self.pheromones = PheromoneEngine()
        self._running = False
        self._tick_thread = None
        self._lock = threading.Lock()
        self.known_networks: Dict[str, Dict[str, Any]] = {}
        self.stats = {
            "penetrations": 0, "successful_penetrations": 0,
            "packets_spread": 0, "packets_retransmitted": 0,
            "spores_created": 0, "spores_used": 0,
        }
        logger.info(f"MyceliumEngine created: node_id={node_id}")

    def start(self):
        if self._running:
            return
        self._running = True
        if self.auto_heal:
            self._tick_thread = threading.Thread(target=self._tick_loop, daemon=True)
            self._tick_thread.start()
        logger.info("MyceliumEngine started")

    def stop(self):
        self._running = False
        if self._tick_thread:
            self._tick_thread.join(timeout=2)
        logger.info("MyceliumEngine stopped")

    def _tick_loop(self):
        while self._running:
            time.sleep(self.tick_interval)
            try:
                self.tick()
            except Exception as e:
                logger.error(f"tick error: {e}")

    def tick(self):
        self.spores.tick_all(hours=0.5)
        self.spores.cleanup()
        self.pheromones.evaporate()

    def infiltrate(self, network, max_attempts=3):
        with self._lock:
            self.stats["penetrations"] += 1
        success, method = self.penetration.penetrate(network, max_attempts=max_attempts)
        if success:
            with self._lock:
                self.stats["successful_penetrations"] += 1
                self.known_networks[network] = {
                    "first_seen": time.time(),
                    "method": method,
                    "spores_created": 0,
                }
            spores_count = 3 + random.randint(0, 3)
            for _ in range(spores_count):
                self.spores.create(
                    node_id=self.node_id, target_network=network,
                    method=method or "generic",
                    viability=random.uniform(0.4, 0.9))
                with self._lock:
                    self.stats["spores_created"] += 1
                    self.known_networks[network]["spores_created"] += 1
        return success, method

    def spread(self, data):
        if not self.spores.get_alive():
            return 0
        count = self.spores.spread(data, source_node=self.node_id)
        with self._lock:
            self.stats["packets_spread"] += 1
        return count

    def spread_packet(self, packet: GDPPacket):
        packet_data = packet.to_bytes()
        count = self.spread(packet_data)
        if count > 0:
            self.pheromones.add(
                source=packet.sender, destination=packet.receiver,
                protocol=packet.protocol)
        return count

    def harvest(self):
        data_list = self.spores.retransmit(exclude_node=self.node_id)
        if data_list:
            with self._lock:
                self.stats["packets_retransmitted"] += len(data_list)
                self.stats["spores_used"] += 1
        return data_list

    def harvest_packets(self):
        data_list = self.harvest()
        packets = []
        for data in data_list:
            try:
                packet = GDPPacket.from_bytes(data)
                packets.append(packet)
            except Exception:
                continue
        return packets

    def record_success(self, source, destination, protocol):
        self.pheromones.mark_result(source, destination, protocol, True)

    def record_failure(self, source, destination, protocol):
        self.pheromones.mark_result(source, destination, protocol, False)

    def get_best_protocol(self, source, destination):
        return self.pheromones.get_best_protocol(source, destination)

    def auto_infiltrate(self, networks=None):
        networks = networks or ["5G", "4G", "WiFi", "Satellite", "Mesh", "IoT", "Corporate"]
        results = {}
        for network in networks:
            if network in self.known_networks:
                continue
            success, method = self.infiltrate(network, max_attempts=2)
            results[network] = success
            time.sleep(0.2)
        return results

    def get_spores(self):
        """P13: РЎРѓР С—Р С‘РЎРѓР С•Р С” Р В¶Р С‘Р Р†РЎвЂ№РЎвЂ¦ РЎРѓР С—Р С•РЎР‚ Р Т‘Р В»РЎРЏ UI/discovery."""
        try:
            alive = self.spores.get_alive()
            return [s.to_dict() for s in alive]
        except Exception:
            return []

    def get_stats(self):
        with self._lock:
            base = dict(self.stats)
        return {
            **base,
            "running": self._running,
            "known_networks": list(self.known_networks.keys()),
            "networks_count": len(self.known_networks),
            "spores": self.spores.get_stats(),
            "pheromones": self.pheromones.get_stats(),
            "penetration": self.penetration.get_stats(),
        }

    def get_network_info(self, network):
        return self.known_networks.get(network)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()

    def __repr__(self):
        return (f"MyceliumEngine(node={self.node_id}, "
                f"networks={len(self.known_networks)}, running={self._running})")


if __name__ == "__main__":
    print("Testing MyceliumEngine...")
    engine = MyceliumEngine(node_id="test_node", auto_heal=False)
    print(f"Engine: {engine}")
    results = engine.auto_infiltrate(["5G", "WiFi"])
    for net, ok in results.items():
        print(f"  {'OK' if ok else 'FAIL'}: {net}")
    stats = engine.get_stats()
    print(f"Penetrations: {stats['penetrations']}")
    print(f"Successful: {stats['successful_penetrations']}")
    print(f"Spores created: {stats['spores_created']}")
    from ..core.packet import create_packet
    packet = create_packet("alice", "bob", b"Critical data" * 20)
    count = engine.spread_packet(packet)
    print(f"Spread to {count} spores")
    harvested = engine.harvest_packets()
    print(f"Harvested: {len(harvested)} packets")
    engine.record_success("alice", "bob", "HTTPS")
    engine.record_success("alice", "bob", "HTTPS")
    best = engine.get_best_protocol("alice", "bob")
    print(f"Best protocol: {best}")
    print("MyceliumEngine module OK")
