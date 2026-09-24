"""Tests for steganography modules."""
import pytest
from inevionet.steganography import (
    DNSTunnel, HTTPHeadersTunnel, ICMPPayloadTunnel,
    TimingChannel, SteganographyEngine)


class TestDNSTunnel:
    def test_encode_decode_qname(self):
        tunnel = DNSTunnel()
        data = b"Test data"
        chunks = tunnel.encode_qname(data)
        assert len(chunks) > 0
        decoded = tunnel.decode_qname(chunks)
        assert decoded == data

    def test_large_data(self):
        tunnel = DNSTunnel()
        data = b"x" * 1000
        chunks = tunnel.encode_qname(data)
        decoded = tunnel.decode_qname(chunks)
        assert decoded == data


class TestHTTPHeadersTunnel:
    def test_encode_decode(self):
        tunnel = HTTPHeadersTunnel()
        data = b"Secret message"
        headers, chunks = tunnel.encode(data)
        assert chunks > 0
        decoded = tunnel.decode(headers)
        assert decoded == data


class TestTimingChannel:
    def test_encode_intervals(self):
        ch = TimingChannel(bit_delay=0.05, tolerance=0.02)
        data = b"Hi"
        intervals = ch.encode_bytes_to_intervals(data)
        # 2 bytes = 16 bits = 16 intervals
        assert len(intervals) == 16
        # Each interval should be either bit_delay or 2*bit_delay
        for interval in intervals:
            assert interval in [ch.bit_delay, ch.bit_delay * 2]

    def test_decode_intervals_clean(self):
        ch = TimingChannel(bit_delay=0.05, tolerance=0.02)
        data = b"Hi"
        intervals = ch.encode_bytes_to_intervals(data)
        # Feed exact intervals back (no noise)
        decoded = ch.decode_intervals_to_bytes(intervals)
        assert decoded == data


class TestSteganographyEngine:
    def test_create(self):
        engine = SteganographyEngine()
        assert engine is not None
        engine.close()

    def test_encode_decode_roundtrip(self):
        engine = SteganographyEngine()
        data = b"Test message"
        # DNS QNAME roundtrip
        dns = engine._get_dns()
        chunks = dns.encode_qname(data)
        decoded = dns.decode_qname(chunks)
        assert decoded == data
        engine.close()
