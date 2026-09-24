"""P13: Relay Node - volunteer proxy for WebRTC Bridge."""
import asyncio
import socket
import time
import threading
from typing import Optional, Dict, Any
from ..core.logger import get_logger

logger = get_logger("inevionet.network.relay_node")

try:
    from .webrtc_bridge import WebRTCBridge
    from .bridge_broker import BridgeBroker
except ImportError:
    WebRTCBridge = None
    BridgeBroker = None


class RelayNode:
    """P13: Volunteer relay node.

    Registers with broker, accepts WebRTC offers from clients,
    proxies traffic to target services.
    """

    def __init__(self, node_id, broker=None, capacity=10, region="unknown"):
        self.node_id = node_id
        self.broker = broker
        self.capacity = capacity
        self.region = region
        self.bridge = None
        self._running = False
        self._heartbeat_thread = None
        self._stats = {
            "clients_served": 0,
            "bytes_proxied": 0,
            "bytes_relayed": 0,
            "errors": 0,
            "started_at": time.time(),
        }

    def start(self):
        """Start relay node and register with broker."""
        if self._running:
            return
        self._running = True

        # Register with broker
        if self.broker:
            self.broker.register_relay(
                node_id=self.node_id,
                endpoint="webrtc://" + self.node_id,
                capacity=self.capacity,
                region=self.region,
            )
            logger.info("[Relay] Registered with broker: %s", self.node_id)

        # Start heartbeat
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

        logger.info("[Relay] Started: %s (capacity=%d, region=%s)",
                    self.node_id, self.capacity, self.region)

    def stop(self):
        """Stop relay node."""
        self._running = False
        if self.broker:
            self.broker.unregister_relay(self.node_id)
        logger.info("[Relay] Stopped: %s", self.node_id)

    def _heartbeat_loop(self):
        """Send heartbeat to broker every 60 seconds."""
        while self._running:
            time.sleep(60)
            if not self._running:
                break
            if self.broker:
                self.broker.heartbeat(
                    self.node_id,
                    current_load=0)  # Simplified

    async def handle_client(self, offer_str):
        """Handle incoming WebRTC client offer.

        Returns: answer_str for client.
        """
        if WebRTCBridge is None:
            logger.error("[Relay] WebRTCBridge not available")
            return None

        try:
            self.bridge = WebRTCBridge(node_id=self.node_id)

            # Set message handler to proxy traffic
            def on_client_message(data):
                self._proxy_message(data)

            self.bridge.on_message(on_client_message)

            # Accept offer, create answer
            answer_str = await self.bridge.accept_offer(offer_str)
            if answer_str:
                self._stats["clients_served"] += 1
                logger.info("[Relay] Client accepted: %s", self.node_id)
            return answer_str

        except Exception as e:
            logger.error("[Relay] handle_client: %s", e)
            self._stats["errors"] += 1
            return None

    def _proxy_message(self, data):
        """Proxy message from client to target service.

        Data format: JSON with {target, port, payload}
        or raw bytes for default target.
        """
        try:
            self._stats["bytes_proxied"] += len(data) if data else 0

            # Try to parse as JSON command
            import json
            try:
                cmd = json.loads(data)
                target = cmd.get("target", "example.com")
                port = int(cmd.get("port", 80))
                payload = cmd.get("payload", "").encode("utf-8")
            except (json.JSONDecodeError, AttributeError):
                # Fallback: raw data to default target
                target = "example.com"
                port = 80
                payload = data if isinstance(data, bytes) else str(data).encode()

            # Make HTTP request to target
            response = self._fetch(target, port, payload)

            # Send response back through WebRTC
            if self.bridge and response:
                self.bridge.send(json.dumps({
                    "status": "ok",
                    "response_len": len(response),
                    "preview": response[:200].decode("utf-8", errors="replace"),
                }))
                self._stats["bytes_relayed"] += len(response)

        except Exception as e:
            logger.error("[Relay] proxy error: %s", e)
            self._stats["errors"] += 1

    def _fetch(self, target, port, payload) -> Optional[bytes]:
        """Make direct TCP request to target."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10.0)
            s.connect((target, port))
            s.sendall(payload)
            time.sleep(0.5)
            response = s.recv(8192)
            s.close()
            return response
        except Exception as e:
            logger.debug("[Relay] fetch error: %s", e)
            return None

    def get_stats(self):
        return {
            **self._stats,
            "node_id": self.node_id,
            "capacity": self.capacity,
            "region": self.region,
            "running": self._running,
            "uptime_sec": round(time.time() - self._stats["started_at"], 1),
        }

    def __repr__(self):
        status = "RUN" if self._running else "STOP"
        return "RelayNode([" + status + "] " + self.node_id + ")"


if __name__ == "__main__":
    print("Testing RelayNode...")
    from .bridge_broker import BridgeBroker

    broker = BridgeBroker()
    relay = RelayNode(
        node_id="relay_1",
        broker=broker,
        capacity=10,
        region="RU",
    )
    relay.start()
    time.sleep(0.5)

    print("Relay stats:", relay.get_stats())
    print("Broker relays:", len(broker.get_relays()))

    relay.stop()
    print("RelayNode OK")