"""InevioNet Simple API - для новичков."""
import os
import time
import threading
from typing import Optional, Any, Tuple

from .orchestrator import InevioNet


_DEFAULT_NET = None
_DEFAULT_PASSWORD = os.environ.get("INEVIONET_PASSWORD", "default_password")
_DEFAULT_NODE_ID = os.environ.get("INEVIONET_NODE_ID", "simple_node")
_LOCK = threading.Lock()


def _get_default_net():
    global _DEFAULT_NET
    with _LOCK:
        if _DEFAULT_NET is None or not _DEFAULT_NET._running:
            _DEFAULT_NET = InevioNet(
                password=_DEFAULT_PASSWORD,
                node_id=_DEFAULT_NODE_ID,
                auto_start=True)
        return _DEFAULT_NET


def send(receiver, message, guaranteed=False, stealth=False):
    """Отправить сообщение (одна строка)."""
    net = _get_default_net()
    if guaranteed:
        success, _ = net.send_with_guarantee(receiver, message)
        return success
    packet = net.send(receiver, message, use_stealth=stealth)
    return packet is not None


def receive(timeout=5.0):
    """Получить сообщение."""
    net = _get_default_net()
    time.sleep(0.1)
    if hasattr(net, "received_packets") and net.received_packets:
        last_packet = list(net.received_packets.values())[-1]
        success, data = net.receive(last_packet)
        if success:
            return data
    return None


def run(password=None, node_id=None, mode="standard"):
    """Создать и запустить InevioNet."""
    return InevioNet(
        password=password or _DEFAULT_PASSWORD,
        node_id=node_id or _DEFAULT_NODE_ID,
        mode=mode,
        auto_start=True)


def stop():
    """Остановить глобальный экземпляр."""
    global _DEFAULT_NET
    with _LOCK:
        if _DEFAULT_NET:
            _DEFAULT_NET.stop()
            _DEFAULT_NET = None


class quick:
    """Context manager for quick usage."""

    def __init__(self, password="default", node_id="quick_node"):
        self.password = password
        self.node_id = node_id
        self.net = None

    def __enter__(self):
        self.net = run(self.password, self.node_id)
        return self.net

    def __exit__(self, *args):
        if self.net:
            self.net.stop()


if __name__ == "__main__":
    print("=" * 60)
    print("  INEVIONET SIMPLE API DEMO")
    print("=" * 60)
    print()
    print("1. Send (one line):")
    result = send("alice", "Hello from simple API!")
    print(f"   send('alice', ...) -> {result}")
    print()
    print("2. Context manager:")
    with quick("demo_password") as net:
        print(f"   Node ID: {net.node_id}")
        packet = net.send("bob", "Hi from context!")
        print(f"   Sent: {packet.packet_id[:16] if packet else 'FAIL'}")
    print()
    print("3. Function run():")
    net = run("another_password", "my_node")
    print(f"   {net}")
    net.stop()
    print()
    print("Simple API OK")
