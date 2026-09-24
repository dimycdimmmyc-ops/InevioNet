"""Tests for masking modules."""
import pytest
from inevionet.masking import (
    FirewallModel, DPIModel, FirewallAction, PacketFeatures,
    DetectionProbability, KLDivergence,
    PolymorphicEncoder, Fragment,
    Prober, VulnerabilityMap, BayesianUpdater,
    ChannelSelector, MaskingEngine,
    AmbientAnalyzer, AmbientMasker, SpatialDensityModel)


class TestDPIModel:
    def test_create(self):
        dpi = DPIModel(threshold=0.7, profile="medium")
        assert dpi.threshold == 0.7

    def test_detection_probability(self):
        dpi = DPIModel()
        features = PacketFeatures(port=80, protocol="HTTP",
                                  size_bytes=350, entropy=0.15)
        p = dpi.detection_probability(features)
        assert 0 <= p <= 1

    def test_decide_pass(self):
        dpi = DPIModel(threshold=0.9)
        features = PacketFeatures(port=80, protocol="HTTP",
                                  size_bytes=350, entropy=0.1)
        action = dpi.decide(features)
        assert action in [FirewallAction.PASS, FirewallAction.INSPECT,
                          FirewallAction.BLOCK]


class TestFirewallModel:
    def test_create(self):
        fw = FirewallModel("test", dpi_profile="high")
        assert fw.name == "test"

    def test_block_port(self):
        fw = FirewallModel()
        fw.block_port(25)
        features = PacketFeatures(port=25)
        action = fw.check(features)
        assert action == FirewallAction.BLOCK


class TestKLDivergence:
    def test_compute(self):
        p = {"A": 0.7, "B": 0.3}
        q = {"A": 0.6, "B": 0.4}
        kl = KLDivergence.compute(p, q)
        assert kl >= 0

    def test_similar(self):
        p = {"A": 0.7, "B": 0.3}
        q = {"A": 0.7, "B": 0.3}
        assert KLDivergence.compute(p, q) < 0.001


class TestPolymorphicEncoder:
    def test_encode_decode(self):
        enc = PolymorphicEncoder()
        data = b"Test data " * 50
        fragments = enc.encode(data)
        assert len(fragments) > 1
        restored = enc.decode(fragments)
        assert restored == data

    def test_fragment_checksum(self):
        f = Fragment(sequence=0, total_fragments=1, data=b"test")
        assert f.verify_checksum()


class TestVulnerabilityMap:
    def test_record(self):
        vmap = VulnerabilityMap()
        vmap.record("node1", "HTTP", True, 25)
        vmap.record("node1", "HTTP", True, 30)
        best = vmap.get_best_channel("node1")
        assert best == "HTTP"

    def test_blocked_channels(self):
        vmap = VulnerabilityMap()
        for _ in range(5):
            vmap.record("node1", "SMTP", False)
        assert "SMTP" in vmap.get_blocked_channels("node1")


class TestBayesianUpdater:
    def test_update(self):
        b = BayesianUpdater()
        for _ in range(10):
            b.update("HTTP", True)
        p = b.get_probability("HTTP")
        assert p > 0.5

    def test_select_best(self):
        b = BayesianUpdater()
        for _ in range(10):
            b.update("HTTP", True)
        for _ in range(3):
            b.update("DNS", False)
        best = b.select_best_channel(["HTTP", "DNS"])
        assert best == "HTTP"


class TestAmbientMasker:
    def test_adapt(self):
        masker = AmbientMasker(adaptation_strength=0.7)
        for _ in range(50):
            masker.observe(size=1400, protocol="HTTP", entropy=0.3)
        adapted = masker.adapt_packet(2000, "CUSTOM", 0.9)
        assert adapted["adapted"] is True


class TestSpatialDensityModel:
    def test_poisson(self):
        model = SpatialDensityModel(density_per_km2=100)
        p = model.poisson_probability(0, 1.0)
        assert 0 <= p <= 1

    def test_detection_probability(self):
        model = SpatialDensityModel(density_per_km2=1000, detection_range_km=0.1)
        p = model.detection_probability()
        assert p > 0.9


class TestMaskingEngine:
    def test_create(self):
        engine = MaskingEngine(dpi_profile="medium")
        assert engine.dpi.profile == "medium"

    def test_probe(self):
        engine = MaskingEngine()
        analysis = engine.probe_node("test.example.com")
        assert "success_rate" in analysis
