"""🍄 InevioNet Drone Client (P8).

Дрон = спора-разведчик в полёте.

Философия:
  - Дрон САМ сканирует эфир.
  - Дрон САМ закрепляется в сетях.
  - Дрон САМ строит маршрут.
  - Дрон САМ доставляет.
  - Дрон САМ обучается.

Запуск:
  python -m drone.drone_client --node-id drone_01
"""
import os
import sys
import time
import json
import socket
import signal
import argparse
import threading
from pathlib import Path
from typing import Optional, Dict, Any, List


_THIS_DIR = Path(__file__).parent
_ROOT_DIR = _THIS_DIR.parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))

try:
    from drone.signal_hunter import SignalHunter
    from drone.autonomous_mode import AutonomousMode
except ImportError:
    SignalHunter = None
    AutonomousMode = None


DRONE_DATA_DIR = Path(os.environ.get("DRONE_DATA", str(_THIS_DIR / "data")))
DRONE_DATA_DIR.mkdir(parents=True, exist_ok=True)

SEED_URL = os.environ.get("INEVIO_SEED_URL", "").strip() or None
SCAN_INTERVAL = float(os.environ.get("DRONE_SCAN_INTERVAL", "30"))
SYNC_INTERVAL = float(os.environ.get("DRONE_SYNC_INTERVAL", "60"))


import logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] [drone] %(message)s',
    datefmt='%H:%M:%S',
)
log = logging.getLogger("inevionet.drone")


class DroneClient:
    """Автономный дрон-клиент."""

    def __init__(self, node_id: str, seed_url: Optional[str] = None):
        self.node_id = node_id
        self.seed_url = seed_url or SEED_URL
        self.running = True
        self.start_time = time.time()

        self.hunter = SignalHunter() if SignalHunter else None
        self.autonomous = AutonomousMode(
            node_id=node_id,
            data_dir=DRONE_DATA_DIR,
        ) if AutonomousMode else None

        self.last_scan = 0.0
        self.last_sync = 0.0
        self.scan_count = 0
        self.signals_found = 0
        self.peers_known: Dict[str, Any] = {}
        self.threads = []

        log.info("=" * 60)
        log.info("  INEVIONET DRONE CLIENT")
        log.info("=" * 60)
        log.info("  Node ID:  %s", self.node_id)
        log.info("  Seed:     %s", self.seed_url or "—")
        log.info("  Data dir: %s", DRONE_DATA_DIR)
        log.info("=" * 60)

    def scan_loop(self):
        log.info("[Drone] scan loop запущен (interval=%.0fs)", SCAN_INTERVAL)
        while self.running:
            try:
                if self.hunter is None:
                    time.sleep(SCAN_INTERVAL)
                    continue
                result = self.hunter.scan_all()
                self.scan_count += 1
                self.last_scan = time.time()
                total = sum(result.get("by_type", {}).values())
                self.signals_found = total
                log.info("[Drone] scan #%d: %d сигналов (%s)",
                         self.scan_count, total, result.get("by_type", {}))
                for sig in result.get("signals", []):
                    nid = sig.get("node_id")
                    if nid:
                        self.peers_known[nid] = sig
                    if self.autonomous:
                        try:
                            self.autonomous.remember_finding(sig)
                        except Exception:
                            pass
                try:
                    findings_path = DRONE_DATA_DIR / "findings.json"
                    findings_path.write_text(
                        json.dumps({
                            "last_scan": self.last_scan,
                            "count": total,
                            "signals": result.get("signals", [])[:200],
                        }, ensure_ascii=False, indent=2),
                        encoding="utf-8",
                    )
                except Exception as e:
                    log.debug("[Drone] save findings: %s", e)
            except Exception as e:
                log.warning("[Drone] scan error: %s", e)

            for _ in range(int(SCAN_INTERVAL)):
                if not self.running:
                    break
                time.sleep(1.0)

    def seed_loop(self):
        if not self.seed_url:
            log.info("[Drone] seed loop не запущен (seed_url пустой)")
            return
        log.info("[Drone] seed loop запущен (url=%s)", self.seed_url)
        while self.running:
            try:
                self._announce_to_seed()
                self._bootstrap_from_seed()
            except Exception as e:
                log.debug("[Drone] seed error: %s", e)
            for _ in range(60):
                if not self.running:
                    break
                time.sleep(1.0)

    def _announce_to_seed(self):
        if not self.seed_url:
            return
        try:
            import urllib.request
            payload = json.dumps({
                "node_id": self.node_id,
                "port": 0,
                "is_super": False,
                "trust": 50.0,
                "version": "1.0.0-drone",
                "capabilities": ["drone", "scan", "relay", "autonomous"],
            }).encode("utf-8")
            req = urllib.request.Request(
                self.seed_url.rstrip("/") + "/api/announce",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("ok"):
                    log.info("[Drone] announce OK (total=%s)",
                             data.get("total_peers"))
        except Exception as e:
            log.debug("[Drone] announce: %s", e)

    def _bootstrap_from_seed(self):
        if not self.seed_url:
            return
        try:
            import urllib.request
            payload = json.dumps({
                "node_id": self.node_id,
                "limit": 50,
            }).encode("utf-8")
            req = urllib.request.Request(
                self.seed_url.rstrip("/") + "/api/bootstrap",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                peers = data.get("peers", []) or []
                for p in peers:
                    nid = p.get("node_id")
                    if nid and nid != self.node_id:
                        self.peers_known[nid] = {
                            "node_id": nid,
                            "ip": p.get("ip"),
                            "port": p.get("port", 8080),
                            "is_super": p.get("is_super", False),
                            "trust": p.get("trust", 50.0),
                            "from_seed": True,
                        }
                if peers:
                    log.info("[Drone] bootstrap: %d пиров (total=%d)",
                             len(peers), len(self.peers_known))
        except Exception as e:
            log.debug("[Drone] bootstrap: %s", e)

    def sync_loop(self):
        if self.autonomous is None:
            log.info("[Drone] sync loop не запущен")
            return
        log.info("[Drone] sync loop запущен (interval=%.0fs)", SYNC_INTERVAL)
        while self.running:
            try:
                online = self._is_online()
                if online:
                    sent = self.autonomous.flush_outbox()
                    if sent > 0:
                        log.info("[Drone] sync: доставлено %d из очереди", sent)
                else:
                    log.debug("[Drone] offline: %d в очереди",
                              self.autonomous.outbox_size())
            except Exception as e:
                log.debug("[Drone] sync error: %s", e)
            for _ in range(int(SYNC_INTERVAL)):
                if not self.running:
                    break
                time.sleep(1.0)

    def _is_online(self) -> bool:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.settimeout(2.0)
            s.connect(("8.8.8.8", 80))
            s.close()
            return True
        except Exception:
            return False

    def get_stats(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "uptime_sec": time.time() - self.start_time,
            "scan_count": self.scan_count,
            "signals_found": self.signals_found,
            "peers_known": len(self.peers_known),
            "last_scan_ago": (time.time() - self.last_scan) if self.last_scan else None,
            "running": self.running,
        }

    def print_status(self):
        s = self.get_stats()
        log.info("─" * 60)
        log.info("  DRONE STATUS")
        log.info("  Node:     %s", s["node_id"])
        log.info("  Uptime:   %.0fs", s["uptime_sec"])
        log.info("  Scans:    %d", s["scan_count"])
        log.info("  Signals:  %d", s["signals_found"])
        log.info("  Peers:    %d", s["peers_known"])
        log.info("─" * 60)

    def start(self):
        for fn, name in (
            (self.scan_loop, "drone_scan"),
            (self.seed_loop, "drone_seed"),
            (self.sync_loop, "drone_sync"),
        ):
            t = threading.Thread(target=fn, daemon=True, name=name)
            t.start()
            self.threads.append(t)
        log.info("[Drone] все циклы запущены")

    def stop(self):
        self.running = False
        log.info("[Drone] остановка...")

    def run_forever(self):
        self.start()

        def _stop(signum, frame):
            self.stop()
            sys.exit(0)

        try:
            signal.signal(signal.SIGINT, _stop)
            signal.signal(signal.SIGTERM, _stop)
        except Exception:
            pass

        while self.running:
            time.sleep(30)
            self.print_status()


def main():
    parser = argparse.ArgumentParser(description="InevioNet Drone Client (P8)")
    parser.add_argument("--node-id", default=None)
    parser.add_argument("--seed-url", default=None)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()

    node_id = args.node_id or f"drone_{int(time.time()) % 100000}"
    drone = DroneClient(node_id=node_id, seed_url=args.seed_url)

    if args.once:
        if drone.hunter:
            result = drone.hunter.scan_all()
            print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    drone.run_forever()


if __name__ == "__main__":
    main()