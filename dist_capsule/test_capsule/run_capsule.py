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
    print(f"[OK] Press Ctrl+C to stop")
    print()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        net.stop()
        print()
        print("[OK] Stopped")