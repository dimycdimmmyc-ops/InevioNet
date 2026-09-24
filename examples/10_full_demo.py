#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Example 10: Full demo of all InevioNet capabilities."""
from inevionet import InevioNet


def main():
    print("=" * 70)
    print("  EXAMPLE 10: FULL INEVIONET DEMO")
    print("=" * 70)
    print()

    net = InevioNet(
        password="full_demo_password",
        node_id="full_demo_node",
        mode="standard",
        auto_start=True)

    try:
        # 1. Simple send
        print("1. Simple send:")
        packet = net.send("alice", "Hello, InevioNet!")
        print(f"   Packet: {packet.packet_id[:16] if packet else 'FAIL'}")
        print()

        # 2. Guaranteed delivery
        print("2. Guaranteed delivery:")
        success, packet = net.send_with_guarantee("bob", "Critical message!")
        print(f"   Success: {success}")
        print()

        # 3. Steganography
        print("3. Steganography:")
        packet = net.send("charlie", b"Secret data", use_stealth=True)
        print(f"   Stealth sent: {packet.packet_id[:16] if packet else 'FAIL'}")
        print()

        # 4. Masking
        print("4. Masking:")
        net.enable_masking(dpi_profile="medium")
        analysis = net.probe_node("secure.target.com")
        print(f"   Probed: {analysis['success_rate']:.2%}")
        print()

        # 5. Mycelium
        print("5. Mycelium:")
        results = net.spread_mycelium(["5G-Demo", "WiFi-Demo"])
        for net_name, ok in results.items():
            print(f"   {'OK' if ok else 'FAIL'}: {net_name}")
        print()

        # 6. Evolution
        print("6. Evolution:")
        best = net.evolve(5)
        if best:
            print(f"   Best fitness: {best.fitness:.3f}")
            print(f"   Generation: {best.generation}")
        print()

        # 7. RF scanning
        print("7. RF scanning:")
        env = net.scan_environment()
        print(f"   Signals found: {env['scan']['signals']}")
        print()

        # 8. Mesh topology
        print("8. Mesh topology:")
        mesh = net.build_mesh_topology()
        print(f"   Nodes: {mesh['build'].get('nodes', 0)}")
        print()

        # 9. Ambient masking
        print("9. Ambient masking:")
        net.enable_ambient_masking()
        success, packet = net.send_ambient_masked("ambient_target", "Test")
        print(f"   Ambient send: {success}")
        print()

        # 10. Statistics
        print("10. Full statistics:")
        stats = net.get_stats()
        print(f"    Node ID: {stats['node_id']}")
        print(f"    Sent: {stats['packets_sent']}")
        print(f"    Delivered: {stats['packets_delivered']}")
        print(f"    Failed: {stats['packets_failed']}")
        print(f"    Uptime: {stats['uptime']:.1f}s")

    finally:
        net.stop()

    print()
    print("=" * 70)
    print("  FULL DEMO COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
