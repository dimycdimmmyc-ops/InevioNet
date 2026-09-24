"""InevioNet Industrial Base - base classes for industrial protocols."""
import struct
import time
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, field

from ..core.logger import get_logger
from ..core.exceptions import IndustrialProtocolError

logger = get_logger("inevionet.industrial")


@dataclass
class IndustrialPacket:
    protocol: str
    data: bytes
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def to_bytes(self):
        import json
        header = json.dumps({
            "protocol": self.protocol,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "data_length": len(self.data),
        }).encode("utf-8")
        header_length = struct.pack("!I", len(header))
        return header_length + header + self.data

    @classmethod
    def from_bytes(cls, raw):
        import json
        if len(raw) < 4:
            raise IndustrialProtocolError("unknown", "Packet too short")
        header_length = struct.unpack("!I", raw[:4])[0]
        header = json.loads(raw[4:4+header_length].decode("utf-8"))
        data = raw[4+header_length:]
        return cls(
            protocol=header["protocol"],
            data=data,
            metadata=header.get("metadata", {}),
            timestamp=header.get("timestamp", time.time()))

    def __repr__(self):
        return f"IndustrialPacket({self.protocol}, {len(self.data)}B)"


class IndustrialProtocol:
    def __init__(self, target_host="", target_port=0, timeout=10.0):
        self.target_host = target_host
        self.target_port = target_port
        self.timeout = timeout
        self.stats = {
            "packets_sent": 0,
            "packets_received": 0,
            "bytes_sent": 0,
            "bytes_received": 0,
            "errors": 0,
        }

    def encode(self, *args, **kwargs):
        raise NotImplementedError

    def decode(self, data):
        raise NotImplementedError

    def wrap(self, data, metadata=None):
        return IndustrialPacket(
            protocol=self.__class__.__name__,
            data=data,
            metadata=metadata or {})

    def get_stats(self):
        return dict(self.stats)

    def reset_stats(self):
        for k in self.stats:
            self.stats[k] = 0

    def __repr__(self):
        return f"{self.__class__.__name__}(target={self.target_host}:{self.target_port})"


if __name__ == "__main__":
    print("Testing IndustrialPacket...")
    packet = IndustrialPacket(
        protocol="TestProtocol",
        data=b"test data",
        metadata={"command": "test"})
    print(f"Packet: {packet}")
    raw = packet.to_bytes()
    print(f"Size: {len(raw)} bytes")
    restored = IndustrialPacket.from_bytes(raw)
    assert restored.protocol == packet.protocol
    assert restored.data == packet.data
    print("Serialization OK")
    print("OK")
