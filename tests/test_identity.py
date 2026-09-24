"""Tests for identity module."""
import pytest
from inevionet.identity import (
    DeviceID, DeviceType, DeviceRole,
    DeviceIdentity, DeviceRegistry, DeviceRecord,
    TrustEngine, TrustRecord, TrustLevel,
    DeviceFingerprint, PresenceManager, PresenceRecord, PresenceStatus)


class TestDeviceID:
    def test_generate(self):
        did = DeviceID.generate_new(DeviceType.DRONE, "TestDrone")
        assert did.is_valid
        assert did.device_type == DeviceType.DRONE

    def test_from_public_key(self):
        from inevionet.core.crypto import generate_signing_keypair
        kp = generate_signing_keypair()
        did = DeviceID.from_public_key(kp.public_key, DeviceType.SERVER)
        assert len(did.device_id) >= 16

    def test_serialization(self):
        did = DeviceID.generate_new()
        data = did.to_dict()
        restored = DeviceID.from_dict(data)
        assert restored.device_id == did.device_id


class TestDeviceIdentity:
    def test_create(self, identity):
        assert identity.device_id.device_type == DeviceType.DRONE
        assert identity.device_id.nickname == "Test-Drone"

    def test_sign_verify(self, identity):
        data = b"Sign me"
        sig = identity.sign(data)
        assert identity.verify(data, sig)

    def test_certificate(self, identity):
        cert = identity.create_certificate()
        assert "certificate" in cert
        assert "signature" in cert
        valid, dev_id = DeviceIdentity.verify_certificate(
            cert["certificate"], cert["signature"])
        assert valid

    def test_ecdh(self):
        id1 = DeviceIdentity.create(DeviceType.SERVER)
        id2 = DeviceIdentity.create(DeviceType.SERVER)
        shared1 = id1.derive_shared_secret(id2.exchange_keypair.public_key)
        shared2 = id2.derive_shared_secret(id1.exchange_keypair.public_key)
        assert shared1 == shared2


class TestDeviceRegistry:
    def test_register_local(self, identity):
        reg = DeviceRegistry(persist=False)
        local_id = reg.register_local(identity)
        assert reg.local_device_id == local_id

    def test_register_peer(self, identity):
        reg = DeviceRegistry(persist=False)
        reg.register_local(identity)
        peer = DeviceIdentity.create(DeviceType.SENSOR, nickname="Sensor-1")
        peer_id = reg.register_peer(peer, trust_score=0.7)
        assert reg.get(peer_id) is not None

    def test_get_by_nickname(self, identity):
        reg = DeviceRegistry(persist=False)
        reg.register_local(identity)
        peer = DeviceIdentity.create(DeviceType.DRONE, nickname="Alpha")
        reg.register_peer(peer)
        found = reg.get_by_nickname("Alpha")
        assert found is not None


class TestTrustEngine:
    def test_create(self):
        t = TrustEngine(local_id="node1", persist=False)
        assert t.local_id == "node1"

    def test_record_success(self):
        t = TrustEngine(local_id="node1", persist=False)
        for _ in range(10):
            t.record_success("node1", "node2")
        score = t.get_trust("node1", "node2")
        assert score > 0.5

    def test_record_failure(self):
        t = TrustEngine(local_id="node1", persist=False)
        for _ in range(10):
            t.record_failure("node1", "node2")
        score = t.get_trust("node1", "node2")
        assert score < 0.5

    def test_trust_level(self):
        t = TrustEngine(local_id="node1", persist=False)
        for _ in range(20):
            t.record_success("node1", "node2")
        level = t.get_trust_level("node1", "node2")
        assert level in [TrustLevel.HIGH, TrustLevel.VERIFIED]


class TestDeviceFingerprint:
    def test_collect(self):
        fp = DeviceFingerprint.collect()
        assert len(fp.fingerprint) == 64
        assert "platform" in fp.hw_info

    def test_stability(self):
        fp1 = DeviceFingerprint.collect()
        fp2 = DeviceFingerprint.collect()
        assert fp1.fingerprint == fp2.fingerprint


class TestPresenceManager:
    def test_heartbeat(self):
        pm = PresenceManager()
        pm.heartbeat("node1")
        assert pm.is_online("node1")

    def test_offline(self):
        pm = PresenceManager()
        assert not pm.is_online("unknown_node")

    def test_stats(self):
        pm = PresenceManager()
        for i in range(5):
            pm.heartbeat(f"node_{i}")
        stats = pm.get_stats()
        assert stats["total"] == 5
        assert stats["online"] == 5
