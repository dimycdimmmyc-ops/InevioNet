"""Tests for GDPPacket."""
import os
import json
import time
import pytest
from inevionet.core.packet import GDPPacket, create_packet, create_text_packet


class TestPacketCreation:
    def test_create_packet(self):
        p = create_packet("alice", "bob", b"Hello")
        assert p.sender == "alice"
        assert p.receiver == "bob"
        assert p.payload == b"Hello"

    def test_attractor_range(self):
        p = create_packet("a", "b", b"data")
        assert 0 <= p.attractor < 100

    def test_unique_ids(self):
        p1 = create_packet("a", "b", b"data")
        p2 = create_packet("a", "b", b"data")
        assert p1.packet_id != p2.packet_id

    def test_text_packet(self):
        p = create_text_packet("alice", "bob", "Hello")
        assert p.payload == b"Hello"


class TestPacketCloning:
    def test_clone(self, packet):
        clone = packet.clone("test")
        assert clone.packet_id != packet.packet_id
        assert clone.parent_id == packet.packet_id
        assert clone.is_clone
        assert clone.payload == packet.payload

    def test_original_id(self, packet):
        clone = packet.clone()
        assert clone.get_original_id() == packet.packet_id

    def test_clone_full_ttl(self, packet):
        packet.ttl = 5
        clone = packet.clone()
        assert clone.ttl == packet.max_ttl


class TestPacketTTL:
    def test_ttl_tick(self, packet):
        initial = packet.ttl
        packet.tick()
        assert packet.ttl == initial - 1

    def test_ttl_heal(self, packet):
        packet.ttl = 5
        packet.heal(3)
        assert packet.ttl == 8

    def test_expired(self):
        p = create_packet("a", "b", b"data", ttl=0)
        assert p.is_expired

    def test_not_expired(self):
        p = create_packet("a", "b", b"data", ttl=10)
        assert not p.is_expired


class TestPacketSerialization:
    def test_json_roundtrip(self, packet):
        json_str = packet.to_json()
        restored = GDPPacket.from_json(json_str)
        assert restored.packet_id == packet.packet_id
        assert restored.payload == packet.payload
        assert restored.sender == packet.sender
        assert restored.receiver == packet.receiver

    def test_binary_roundtrip(self, packet):
        binary = packet.to_bytes()
        restored = GDPPacket.from_bytes(binary)
        assert restored.packet_id == packet.packet_id
        assert restored.payload == packet.payload
        assert restored.sender == packet.sender
        assert restored.receiver == packet.receiver

    def test_large_payload(self):
        data = os.urandom(10000)
        p = create_packet("a", "b", data)
        binary = p.to_bytes()
        restored = GDPPacket.from_bytes(binary)
        assert restored.payload == data


class TestPacketSignature:
    def test_sign_verify(self, packet):
        from inevionet.core.crypto import generate_signing_keypair
        kp = generate_signing_keypair()
        packet.sign(kp.private_key)
        assert packet.verify(kp.public_key)

    def test_tampered_signature_fails(self, packet):
        from inevionet.core.crypto import generate_signing_keypair
        kp = generate_signing_keypair()
        packet.sign(kp.private_key)
        packet.payload = b"tampered"
        assert not packet.verify(kp.public_key)


class TestPacketState:
    def test_set_delivered(self, packet):
        packet.set_delivered()
        assert packet.state == "delivered"

    def test_set_failed(self, packet):
        packet.set_failed("test reason")
        assert packet.state == "failed"
        assert packet.metadata["fail_reason"] == "test reason"
