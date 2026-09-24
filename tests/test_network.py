"""Tests for network modules."""
import pytest
from inevionet.network import (
    TCPClient, UDPClient, DNSClient, HTTPClient,
    ICMPClient, UniversalTransport)


class TestTCPClient:
    def test_create(self):
        c = TCPClient("example.com", 80, timeout=5)
        assert c.host == "example.com"
        assert c.port == 80
        assert not c.is_connected

    def test_connection_error(self):
        c = TCPClient("invalid.host.example", 80, timeout=1)
        assert not c.connect()


class TestUDPClient:
    def test_create(self):
        c = UDPClient(timeout=5)
        assert c.local_port > 0
        c.close()


class TestDNSClient:
    def test_create(self):
        c = DNSClient("8.8.8.8")
        assert c.server == "8.8.8.8"

    def test_encode_domain(self):
        encoded = DNSClient._encode_domain("example.com")
        assert encoded[-1] == 0
        assert len(encoded) > 10


class TestHTTPClient:
    def test_create(self):
        c = HTTPClient(timeout=10)
        assert c.timeout == 10


class TestICMPClient:
    def test_create(self):
        c = ICMPClient()
        assert c.identifier > 0
        c.close()


class TestUniversalTransport:
    def test_create(self):
        t = UniversalTransport(timeout=5)
        assert t.timeout == 5
        t.close()

    def test_parse_hostport(self):
        host, port = UniversalTransport._parse_hostport("example.com:8080", 80)
        assert host == "example.com"
        assert port == 8080

    def test_unknown_protocol(self):
        t = UniversalTransport(timeout=2)
        result = t.send(b"data", protocol="UNKNOWN")
        assert not result.success
        t.close()
