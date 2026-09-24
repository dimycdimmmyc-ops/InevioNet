#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Example 9: Embedding capsule into application."""
from inevionet import InevioCapsule, embed_inevionet, quick_send, quick_receive


def main():
    print("=" * 60)
    print("  EXAMPLE 9: CAPSULE EMBEDDING")
    print("=" * 60)
    print()

    # 1. Create capsule directly
    print("1. Creating capsule directly:")
    capsule = InevioCapsule("my_password", node_id="capsule_demo", auto_start=True)
    print(f"   {capsule}")
    packet = capsule.send("alice", "Hello from capsule!")
    print(f"   Sent: {packet.packet_id[:16] if packet else 'FAIL'}")
    capsule.stop()
    print()

    # 2. Embed into application
    print("2. Embedding into application:")
    api = embed_inevionet("secret_password", "telegram_bot")
    print(f"   App: {api['app_name']}")
    print(f"   Capsule ID: {api['capsule_id']}")
    print(f"   Available methods: {', '.join([k for k in api.keys() if not k.startswith('_')][:8])}")
    print()

    # 3. Use API
    print("3. Using embedded API:")
    packet = api["send"]("user_123", b"Hello from bot!")
    print(f"   Sent: {packet.packet_id[:16] if packet else 'FAIL'}")
    stats = api["get_stats"]()
    print(f"   Stats: {stats.get('packets_sent', 0)} packets sent")
    print()

    # 4. Quick one-shot send
    print("4. Quick send (one-shot):")
    result = quick_send("secret", "bob", "Quick message")
    print(f"   Result: {result}")
    print()

    # 5. Quick one-shot receive
    print("5. Quick receive:")
    data = quick_receive("secret", b"some packet data")
    print(f"   Data: {data}")
    print()

    # 6. Register handlers
    print("6. Event handlers:")
    capsule = InevioCapsule("password", node_id="handler_demo", auto_start=False)

    def on_send(packet):
        print(f"   [EVENT on_send] {packet.packet_id[:16]}")

    def on_delivery(packet):
        print(f"   [EVENT on_delivery] {packet.packet_id[:16]}")

    capsule.register_handler("on_send", on_send)
    capsule.register_handler("on_delivery", on_delivery)
    capsule.start()
    capsule.send("test", "Test message")
    capsule.stop()
    print()

    print("=" * 60)


if __name__ == "__main__":
    main()
