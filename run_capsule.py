"""InevioNet Capsule - entry point (auto-generated)."""
import sys
import os
import time

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from inevionet.orchestrator import InevioNet

if __name__ == "__main__":
    node_id = os.environ.get("INEVIO_NODE_ID", "capsule_node")
    password = os.environ.get("INEVIO_PASSWORD", "inevio_forever")

    print("=" * 60)
    print(f"  INEVIONET CAPSULE NODE")
    print(f"  node_id: {node_id}")
    print("=" * 60)
    print()

    net = InevioNet(password=password, node_id=node_id, auto_start=True)

    print(f"[OK] Node started: {net.node_id}")

    # P63a: запуск RelayNode на свободном порту от 9100
    relay = None
    try:
        from inevionet.network.relay_node import RelayNode

        # Найти свободный порт
        import socket as _sock
        listen_port = None
        for p in range(9100, 9201):
            try:
                _test = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
                _test.setsockopt(_sock.SOL_SOCKET, _sock.SO_REUSEADDR, 1)
                _test.bind(("0.0.0.0", p))
                _test.close()
                listen_port = p
                break
            except OSError:
                continue

        if listen_port:
            os.environ["INEVIO_RELAY_PORT"] = str(listen_port)
            relay = RelayNode(
                node_id=node_id + "_relay",
                listen_port=listen_port)
            relay.start()
            print(f"[OK] RelayNode started on port {listen_port}")
        else:
            print("[!!] No free port in 9100-9200")
    except Exception as _e:
        print(f"[!!] RelayNode error: {_e}")

    print(f"[OK] Press Ctrl+C to stop")
    print()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        if relay:
            relay.stop()
        net.stop()
        print()
        print("[OK] Stopped")