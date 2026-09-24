"""Integration tests - end-to-end scenarios."""
import pytest
import time
from inevionet import InevioNet


class TestEndToEnd:
    def test_full_send_receive(self, running_net):
        packet = running_net.send("test_receiver", "Hello, world!")
        assert packet is not None
        success, data = running_net.receive(packet)
        assert success
        assert "Hello, world!" in str(data)

    def test_multiple_messages(self, running_net):
        for i in range(5):
            packet = running_net.send("target", f"Message {i}")
            assert packet is not None
        stats = running_net.get_stats()
        assert stats["packets_sent"] >= 5

    def test_guaranteed_delivery(self, running_net):
        success, packet = running_net.send_with_guarantee("critical", "Critical!")
        assert success
        assert packet is not None


class TestDataTypes:
    def test_text(self, running_net):
        packet = running_net.send("a", "Test text")
        success, data = running_net.receive(packet)
        assert success
        assert "Test text" in str(data)

    def test_json(self, running_net):
        data = {"key": "value", "num": 42}
        packet = running_net.send("b", data)
        success, received = running_net.receive(packet)
        assert success

    def test_bytes(self, running_net):
        packet = running_net.send("c", b"\x00\x01\x02")
        success, _ = running_net.receive(packet)
        assert success


class TestComponents:
    def test_masking_enabled(self, running_net):
        engine = running_net.enable_masking(dpi_profile="medium")
        assert engine is not None
        assert running_net.masking_enabled

    def test_mycelium_spread(self, running_net):
        results = running_net.spread_mycelium(["TestNet1", "TestNet2"])
        assert len(results) == 2

    def test_evolution(self, running_net):
        best = running_net.evolve(5)
        assert best is not None
        assert 0 <= best.fitness <= 1

    def test_identity(self, running_net):
        identity = running_net.enable_identity("drone", "TestDrone")
        assert identity is not None
        info = running_net.get_identity_info()
        assert "device_id" in info

    def test_trust(self, running_net):
        running_net.enable_identity()
        for _ in range(5):
            running_net.record_interaction("peer1", True)
        trust = running_net.get_trust("peer1")
        assert trust > 0.5

    def test_stats(self, running_net):
        stats = running_net.get_stats()
        assert "node_id" in stats
        assert "packets_sent" in stats
        assert "uptime" in stats


class TestFullWorkflow:
    def test_complete_scenario(self, running_net):
        # 1. Enable identity
        running_net.enable_identity("drone", "WorkflowDrone")

        # 2. Enable masking
        running_net.enable_masking()

        # 3. Send with guarantee
        success, packet = running_net.send_with_guarantee(
            "receiver", "Critical workflow message")
        assert success

        # 4. Spread mycelium
        results = running_net.spread_mycelium(["5G", "WiFi"])
        assert len(results) == 2

        # 5. Check stats
        stats = running_net.get_stats()
        assert stats["packets_sent"] >= 1

        # 6. Check identity
        info = running_net.get_identity_info()
        assert info["device_type"] == "drone"
