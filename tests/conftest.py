"""InevioNet pytest configuration and fixtures."""
import os
import sys
import time
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from inevionet import InevioNet
from inevionet.core.crypto import InevioCrypto
from inevionet.core.packet import GDPPacket, create_packet
from inevionet.identity import DeviceIdentity, DeviceType, DeviceRole


@pytest.fixture
def crypto():
    """Crypto engine fixture."""
    return InevioCrypto("test_password_123")


@pytest.fixture
def packet():
    """Test packet fixture."""
    return create_packet(
        sender="alice", receiver="bob",
        payload=b"Hello, World!",
        protocol="HTTPS")


@pytest.fixture
def net():
    """InevioNet instance (not started)."""
    net = InevioNet(
        password="test_password",
        node_id="test_node",
        auto_start=False)
    yield net
    net.stop()


@pytest.fixture
def running_net():
    """Started InevioNet."""
    net = InevioNet(
        password="test_password",
        node_id="running_test_node",
        auto_start=True)
    yield net
    net.stop()


@pytest.fixture
def identity():
    """Device identity fixture."""
    return DeviceIdentity.create(
        device_type=DeviceType.DRONE,
        role=DeviceRole.PEER,
        nickname="Test-Drone")


@pytest.fixture
def sample_data():
    """Sample data for tests."""
    return {
        "small": b"Hi",
        "medium": b"Hello, InevioNet! " * 100,
        "large": os.urandom(10000),
        "text": "Test text message",
        "json": {"key": "value", "number": 42},
    }


def pytest_configure(config):
    """Register markers."""
    config.addinivalue_line("markers", "slow: slow tests")
    config.addinivalue_line("markers", "network: network tests (require internet)")
    config.addinivalue_line("markers", "integration: integration tests")
