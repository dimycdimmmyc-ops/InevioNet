"""InevioNet Device ID - unique device identifier."""
import hashlib
import base64
import time
import platform
import uuid
import json
import socket
from typing import Optional, Dict, Any
from dataclasses import dataclass, field
from enum import Enum

from ..core.logger import get_logger
from ..core.crypto import random_id, generate_signing_keypair, KeyPair

logger = get_logger("inevionet.identity.device_id")


class DeviceType(str, Enum):
    UNKNOWN = "unknown"
    ENDPOINT = "endpoint"
    ROUTER = "router"
    GATEWAY = "gateway"
    DRONE = "drone"
    SENSOR = "sensor"
    SERVER = "server"
    MOBILE = "mobile"
    RELAY = "relay"
    BRIDGE = "bridge"


class DeviceRole(str, Enum):
    CLIENT = "client"
    SERVER = "server"
    PEER = "peer"
    SUPER_NODE = "super_node"


@dataclass
class DeviceID:
    """
    Unique device identifier.
    Format: {type_prefix}_{hash}[_{short_name}]
    Example: dev_a1b2c3d4e5f6
    DeviceID = SHA-256(public_key)[:16]
    """
    device_id: str = ""
    device_type: DeviceType = DeviceType.UNKNOWN
    role: DeviceRole = DeviceRole.PEER
    created_at: float = 0.0
    public_key: Optional[bytes] = None
    nickname: Optional[str] = None

    def __post_init__(self):
        if not self.device_id:
            self.device_id = self._generate_id()
        if self.created_at == 0.0:
            self.created_at = time.time()

    def _generate_id(self):
        prefix = self.device_type.value[:4]
        unique_part = random_id("", 8)
        return f"{prefix}_{unique_part}"

    @classmethod
    def from_public_key(cls, public_key, device_type=DeviceType.UNKNOWN, nickname=None):
        hash_bytes = hashlib.sha256(public_key).digest()
        hash_hex = hash_bytes.hex()[:16]
        prefix = device_type.value[:4]
        device_id = f"{prefix}_{hash_hex}"
        return cls(device_id=device_id, device_type=device_type,
                   public_key=public_key, nickname=nickname)

    @classmethod
    def generate_new(cls, device_type=DeviceType.UNKNOWN, nickname=None):
        keypair = generate_signing_keypair()
        return cls.from_public_key(keypair.public_key, device_type, nickname)

    @property
    def short_id(self):
        return self.device_id[:8]

    @property
    def is_valid(self):
        return len(self.device_id) >= 8 and "_" in self.device_id

    def to_dict(self):
        return {
            "device_id": self.device_id,
            "device_type": self.device_type.value,
            "role": self.role.value,
            "created_at": self.created_at,
            "public_key": base64.b64encode(self.public_key).decode() if self.public_key else None,
            "nickname": self.nickname,
        }

    @classmethod
    def from_dict(cls, data):
        public_key = None
        if data.get("public_key"):
            public_key = base64.b64decode(data["public_key"].encode())
        return cls(
            device_id=data["device_id"],
            device_type=DeviceType(data.get("device_type", "unknown")),
            role=DeviceRole(data.get("role", "peer")),
            created_at=data.get("created_at", 0.0),
            public_key=public_key,
            nickname=data.get("nickname"))

    def __repr__(self):
        nick = f" ({self.nickname})" if self.nickname else ""
        return f"DeviceID({self.device_id}{nick}, type={self.device_type.value})"

    def __hash__(self):
        return hash(self.device_id)

    def __eq__(self, other):
        if isinstance(other, DeviceID):
            return self.device_id == other.device_id
        return False


class DeviceIDGenerator:
    @staticmethod
    def generate_crypto(device_type=DeviceType.UNKNOWN, nickname=None):
        return DeviceID.generate_new(device_type, nickname)

    @staticmethod
    def generate_hardware(device_type=DeviceType.UNKNOWN, nickname=None):
        hw_info = {
            "platform": platform.system(),
            "processor": platform.processor(),
            "machine": platform.machine(),
            "node": platform.node(),
            "python_version": platform.python_version(),
            "uuid": str(uuid.getnode()),
        }
        hw_string = json.dumps(hw_info, sort_keys=True)
        hash_bytes = hashlib.sha256(hw_string.encode()).digest()
        hash_hex = hash_bytes.hex()[:16]
        prefix = device_type.value[:4]
        device_id = f"{prefix}_{hash_hex}"
        return DeviceID(device_id=device_id, device_type=device_type, nickname=nickname)

    @staticmethod
    def generate_network(device_type=DeviceType.UNKNOWN, nickname=None):
        try:
            hostname = socket.gethostname()
            ip = socket.gethostbyname(hostname)
        except Exception:
            hostname = "unknown"
            ip = "0.0.0.0"
        net_info = {"hostname": hostname, "ip": ip, "mac": str(uuid.getnode())}
        net_string = json.dumps(net_info, sort_keys=True)
        hash_bytes = hashlib.sha256(net_string.encode()).digest()
        hash_hex = hash_bytes.hex()[:16]
        prefix = device_type.value[:4]
        device_id = f"{prefix}_{hash_hex}"
        return DeviceID(device_id=device_id, device_type=device_type, nickname=nickname)

    @staticmethod
    def generate_random(device_type=DeviceType.UNKNOWN, nickname=None):
        return DeviceID(device_type=device_type, nickname=nickname)


if __name__ == "__main__":
    print("Testing DeviceID...")
    dev1 = DeviceIDGenerator.generate_crypto(DeviceType.DRONE, "Alpha")
    print(f"Crypto ID: {dev1}")
    dev2 = DeviceIDGenerator.generate_hardware(DeviceType.SERVER, "MainServer")
    print(f"Hardware ID: {dev2}")
    dev3 = DeviceIDGenerator.generate_random(DeviceType.SENSOR, "sensor_1")
    print(f"Random ID: {dev3}")
    data = dev1.to_dict()
    restored = DeviceID.from_dict(data)
    assert restored.device_id == dev1.device_id
    print("Serialization OK")
    print("OK")
