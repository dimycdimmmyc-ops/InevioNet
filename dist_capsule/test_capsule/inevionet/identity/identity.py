"""InevioNet Device Identity - cryptographic identity."""
import time
import json
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass, field

from .device_id import DeviceID, DeviceType, DeviceRole
from ..core.crypto import (
    KeyPair, generate_signing_keypair, generate_exchange_keypair,
    sign_data, verify_signature, derive_shared_secret)
from ..core.logger import get_logger

logger = get_logger("inevionet.identity.identity")


@dataclass
class DeviceIdentity:
    device_id: DeviceID
    signing_keypair: KeyPair
    exchange_keypair: KeyPair
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    last_seen: float = 0.0

    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()
        self.last_seen = self.created_at

    @classmethod
    def create(cls, device_type=DeviceType.UNKNOWN, role=DeviceRole.PEER,
               nickname=None, metadata=None):
        signing_kp = generate_signing_keypair()
        exchange_kp = generate_exchange_keypair()
        device_id = DeviceID.from_public_key(signing_kp.public_key, device_type, nickname)
        device_id.role = role
        return cls(device_id=device_id, signing_keypair=signing_kp,
                   exchange_keypair=exchange_kp, metadata=metadata or {})

    def sign(self, data):
        return sign_data(self.signing_keypair.private_key, data)

    def verify(self, data, signature):
        return verify_signature(self.signing_keypair.public_key, signature, data)

    def sign_message(self, message):
        return self.sign(message.encode("utf-8"))

    def derive_shared_secret(self, peer_public_key):
        return derive_shared_secret(self.exchange_keypair.private_key, peer_public_key)

    def create_certificate(self):
        cert_data = {
            "device_id": self.device_id.device_id,
            "device_type": self.device_id.device_type.value,
            "role": self.device_id.role.value,
            "nickname": self.device_id.nickname,
            "signing_public_key": self.signing_keypair.public_key.hex(),
            "exchange_public_key": self.exchange_keypair.public_key.hex(),
            "created_at": self.created_at,
            "metadata": self.metadata,
        }
        cert_json = json.dumps(cert_data, sort_keys=True).encode()
        signature = self.sign(cert_json)
        return {"certificate": cert_data, "signature": signature.hex()}

    @staticmethod
    def verify_certificate(certificate, signature_hex):
        try:
            # Support both full cert dict and inner cert_data
            if "certificate" in certificate:
                cert_data = certificate["certificate"]
            else:
                cert_data = certificate
            signing_pub_hex = cert_data["signing_public_key"]
            signing_pub = bytes.fromhex(signing_pub_hex)
            device_id = DeviceID.from_public_key(
                public_key=signing_pub,
                device_type=DeviceType(cert_data.get("device_type", "unknown")),
                nickname=cert_data.get("nickname"))
            cert_json = json.dumps(cert_data, sort_keys=True).encode()
            signature = bytes.fromhex(signature_hex)
            valid = verify_signature(signing_pub, signature, cert_json)
            return valid, device_id if valid else None
        except Exception as e:
            logger.error(f"Certificate verify error: {e}")
            return False, None

    def to_dict(self, include_private=False):
        data = {
            "device_id": self.device_id.to_dict(),
            "signing_public_key": self.signing_keypair.public_key.hex(),
            "exchange_public_key": self.exchange_keypair.public_key.hex(),
            "metadata": self.metadata,
            "created_at": self.created_at,
            "last_seen": self.last_seen,
        }
        if include_private:
            data["signing_private_key"] = self.signing_keypair.private_key.hex()
            data["exchange_private_key"] = self.exchange_keypair.private_key.hex()
        return data

    def export_public(self):
        return {
            "device_id": self.device_id.device_id,
            "device_type": self.device_id.device_type.value,
            "role": self.device_id.role.value,
            "nickname": self.device_id.nickname,
            "signing_public_key": self.signing_keypair.public_key.hex(),
            "exchange_public_key": self.exchange_keypair.public_key.hex(),
        }

    def touch(self):
        self.last_seen = time.time()

    def __repr__(self):
        return f"DeviceIdentity({self.device_id.device_id}, type={self.device_id.device_type.value})"


if __name__ == "__main__":
    print("Testing DeviceIdentity...")
    identity = DeviceIdentity.create(DeviceType.DRONE, nickname="Alpha-1",
                                     metadata={"model": "DJI Mavic"})
    print(f"Created: {identity}")
    data = b"Hello, World!"
    signature = identity.sign(data)
    valid = identity.verify(data, signature)
    print(f"Signature valid: {valid}")
    cert = identity.create_certificate()
    valid, dev_id = DeviceIdentity.verify_certificate(cert["certificate"], cert["signature"])
    print(f"Certificate valid: {valid}")
    identity2 = DeviceIdentity.create(DeviceType.SERVER, nickname="Server-1")
    shared1 = identity.derive_shared_secret(identity2.exchange_keypair.public_key)
    shared2 = identity2.derive_shared_secret(identity.exchange_keypair.public_key)
    print(f"Shared secret match: {shared1 == shared2}")
    print("OK")
