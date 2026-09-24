"""InevioNet Capsule - quick embedding helpers."""
from typing import Optional, Dict, Any
from .capsule import InevioCapsule


def embed_inevionet(password, app_name="app", node_id=None, mode="standard"):
    """Quick embed InevioNet into an application."""
    capsule = InevioCapsule(
        password=password, node_id=node_id,
        auto_start=True, mode=mode)
    return capsule.embed_in_application(app_name)


def quick_send(password, receiver, data, app_name="quick"):
    """Quick send one message."""
    capsule = InevioCapsule(
        password=password, node_id=f"quick_{app_name}", auto_start=False)
    try:
        capsule.start()
        packet = capsule.send(receiver, data)
        return packet is not None
    finally:
        capsule.stop()


def quick_receive(password, packet_data, app_name="quick"):
    """Quick receive one message."""
    capsule = InevioCapsule(
        password=password, node_id=f"quick_{app_name}", auto_start=False)
    try:
        capsule.start()
        success, data = capsule.receive(packet_data)
        return data if success else None
    finally:
        capsule.stop()


if __name__ == "__main__":
    print("Testing embed helpers...")
    api = embed_inevionet("secret", "demo_app")
    print(f"API created for: {api['app_name']}")
    packet = api["send"]("alice", b"Hello from embed!")
    print(f"Sent: {packet.packet_id[:16] if packet else 'FAIL'}")
    result = quick_send("secret", "bob", "Quick message")
    print(f"Quick send: {result}")
    print("OK")
