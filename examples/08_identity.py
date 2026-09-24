#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Example 8: Device identification and trust."""
from inevionet import InevioNet
from inevionet.identity import (
    DeviceID, DeviceType, DeviceRole,
    DeviceIdentity, DeviceRegistry,
    DiscoveryEngine, TrustEngine,
    DeviceFingerprint, PresenceManager, PresenceStatus)


def main():
    print("=" * 60)
    print("  EXAMPLE 8: IDENTITY AND TRUST")
    print("=" * 60)
    print()

    # 1. Create identity
    print("1. Creating device identity:")
    identity = DeviceIdentity.create(
        device_type=DeviceType.DRONE,
        role=DeviceRole.PEER,
        nickname="Alpha-Drone",
        metadata={"model": "DJI Mavic 3", "battery": 100})
    print(f"   {identity}")
    print(f"   DeviceID: {identity.device_id.device_id}")
    print()

    # 2. Fingerprint
    print("2. Device fingerprint:")
    fp = DeviceFingerprint.collect()
    print(f"   Fingerprint: {fp.fingerprint[:32]}...")
    print(f"   Platform: {fp.hw_info.get('platform')}")
    print(f"   Python: {fp.sw_info.get('python_version')}")
    print()

    # 3. Certificate
    print("3. Self-signed certificate:")
    cert = identity.create_certificate()
    valid, dev_id = DeviceIdentity.verify_certificate(
        cert["certificate"], cert["signature"])
    print(f"   Certificate valid: {valid}")
    if valid:
        print(f"   Verified DeviceID: {dev_id.device_id}")
    print()

    # 4. Registry
    print("4. Device registry:")
    registry = DeviceRegistry(persist=False)
    local_id = registry.register_local(identity)
    print(f"   Local device: {local_id}")
    for i in range(5):
        peer = DeviceIdentity.create(
            device_type=DeviceType.DRONE if i % 2 == 0 else DeviceType.SENSOR,
            nickname=f"Peer-{i}")
        registry.register_peer(peer, trust_score=0.7)
    stats = registry.get_stats()
    print(f"   Total devices: {stats['total_devices']}")
    print(f"   By type: {stats['by_type']}")
    print()

    # 5. Trust engine
    print("5. Trust engine:")
    trust = TrustEngine(local_id=identity.device_id.device_id, persist=False)
    for _ in range(10):
        trust.record_success(identity.device_id.device_id, "dev_peer1")
    for _ in range(3):
        trust.record_failure(identity.device_id.device_id, "dev_peer1")
    score = trust.get_trust(identity.device_id.device_id, "dev_peer1")
    level = trust.get_trust_level(identity.device_id.device_id, "dev_peer1")
    print(f"   Trust score: {score:.4f}")
    print(f"   Trust level: {level.value}")
    print()

    # 6. Presence
    print("6. Presence manager:")
    presence = PresenceManager()
    presence.heartbeat(identity.device_id.device_id)
    for i in range(3):
        presence.heartbeat(f"peer_{i}", PresenceStatus.ONLINE)
    online = presence.get_online()
    print(f"   Online devices: {len(online)}")
    print(f"   Stats: {presence.get_stats()}")
    print()

    # 7. Integration with InevioNet
    print("7. Integration with InevioNet:")
    net = InevioNet("password", node_id="identity_demo", auto_start=True)
    try:
        net.enable_identity(device_type="drone", nickname="identity_demo")
        info = net.get_identity_info()
        print(f"   Device ID: {info['device_id']}")
        print(f"   Device type: {info['device_type']}")
        print(f"   Registry: {info['registry_stats']['total_devices']} devices")
    finally:
        net.stop()
    print()

    print("=" * 60)


if __name__ == "__main__":
    main()
