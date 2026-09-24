"""Tests for mycelium module."""
import pytest
from inevionet.mycelium import (
    MyceliumEngine, PheromoneEngine, Pheromone,
    SporeManager, Spore, PenetrationEngine)


class TestPheromone:
    def test_create(self):
        p = Pheromone(source="alice", destination="bob", protocol="HTTPS")
        assert p.strength == 1.0
        assert p.success_rate == 1.0

    def test_reinforce(self):
        p = Pheromone(source="a", destination="b", protocol="HTTPS", strength=0.5)
        p.reinforce(0.2)
        assert p.strength == 0.7

    def test_decay(self):
        p = Pheromone(source="a", destination="b", protocol="HTTPS", strength=1.0)
        p.timestamp = 0
        p.decay(0.5)
        assert p.strength < 1.0


class TestPheromoneEngine:
    def test_add(self):
        engine = PheromoneEngine(persist=False, auto_evaporate=False)
        engine.add("alice", "bob", "HTTPS")
        best = engine.get_best_protocol("alice", "bob")
        assert best == "HTTPS"

    def test_multiple_protocols(self):
        engine = PheromoneEngine(persist=False, auto_evaporate=False)
        engine.add("alice", "bob", "HTTPS")
        engine.add("alice", "bob", "DNS")
        for _ in range(5):
            engine.mark_result("alice", "bob", "HTTPS", True)
        best = engine.get_best_protocol("alice", "bob")
        assert best == "HTTPS"


class TestSpore:
    def test_create(self):
        s = Spore(node_id="node1", target_network="5G")
        assert s.viability > 0
        assert s.is_alive()

    def test_cache(self):
        s = Spore(node_id="node1", target_network="5G")
        s.add_to_cache(b"test data")
        assert len(s.cache) == 1
        data = s.pop_from_cache()
        assert data == b"test data"

    def test_tick(self):
        s = Spore(node_id="node1", target_network="5G", viability=1.0)
        s.tick(hours=10)
        assert s.viability < 1.0


class TestSporeManager:
    def test_create(self):
        mgr = SporeManager(persist=False)
        spore = mgr.create("node1", "5G", "HTTP")
        assert spore.spore_id in mgr.spores

    def test_spread(self):
        mgr = SporeManager(persist=False)
        for i in range(5):
            mgr.create(f"node_{i}", "5G", "HTTP")
        count = mgr.spread(b"test data", source_node="external")
        assert count > 0

    def test_retransmit(self):
        mgr = SporeManager(persist=False)
        for i in range(5):
            mgr.create(f"node_{i}", "5G", "HTTP")
        mgr.spread(b"test data", source_node="external")
        data = mgr.retransmit(exclude_node="external")
        assert len(data) > 0


class TestMyceliumEngine:
    def test_create(self):
        engine = MyceliumEngine(node_id="test", auto_heal=False)
        assert engine.node_id == "test"

    def test_infiltrate(self):
        engine = MyceliumEngine(node_id="test", auto_heal=False)
        success, method = engine.infiltrate("test_network", max_attempts=1)
        assert isinstance(success, bool)

    def test_spread_packet(self):
        engine = MyceliumEngine(node_id="test", auto_heal=False)
        engine.infiltrate("test_network", max_attempts=2)
        from inevionet.core.packet import create_packet
        packet = create_packet("alice", "bob", b"test data")
        count = engine.spread_packet(packet)
        assert count >= 0
