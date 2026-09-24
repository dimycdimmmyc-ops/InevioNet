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

    def __init__(self, node_id, broker=None, capacity=10, region="unknown",
                 listen_port=None):
        self.node_id = node_id
        self.broker = broker
        self.capacity = capacity
        self.region = region
        self.listen_port = listen_port        # P62c: TCP-порт для GDPPacket
        self._server_sock = None              # P62c
        self._server_thread = None            # P62c
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

        # P62c: TCP-сервер для GDPPacket
        self.start_server()

        logger.info("[Relay] Started: %s (capacity=%d, region=%s)",
                    self.node_id, self.capacity, self.region)

    def stop(self):
        """Stop relay node."""
        self._running = False
        # P62c: закрыть TCP-сервер
        try:
            if self._server_sock:
                self._server_sock.close()
        except Exception:
            pass
        if self.broker:
            self.broker.unregister_relay(self.node_id)
        logger.info("[Relay] Stopped: %s", self.node_id)

    # ================================================================
    # P62c: GDPPacket relay
    # ================================================================

    def start_server(self):
        """P62c: TCP-сервер для приёма GDPPacket."""
        if not self.listen_port:
            return
        try:
            self._server_sock = socket.socket(
                socket.AF_INET, socket.SOCK_STREAM)
            self._server_sock.setsockopt(
                socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_sock.bind(("0.0.0.0", self.listen_port))
            self._server_sock.listen(16)
            self._server_thread = threading.Thread(
                target=self._server_loop, daemon=True)
            self._server_thread.start()
            logger.info("[Relay] TCP server on port %d", self.listen_port)
        except Exception as e:
            logger.error("[Relay] server start: %s", e)

    def _server_loop(self):
        """P62c: принимать GDPPacket."""
        while self._running:
            try:
                client, addr = self._server_sock.accept()
                threading.Thread(
                    target=self._handle_packet_client,
                    args=(client, addr), daemon=True).start()
            except Exception as e:
                if self._running:
                    logger.debug("[Relay] accept: %s", e)
                break

    def _handle_packet_client(self, client, addr):
        """P62c: обработка одного GDPPacket."""
        try:
            data = client.recv(65536)
            if not data:
                return
            from ..core.packet import GDPPacket
            pkt = GDPPacket.from_bytes(data)
            logger.info("[Relay] packet %s from %s",
                        pkt.packet_id[:16], addr[0])

            # Если пакет для меня — отдать в InevioNet
            if (pkt.route_to == self.node_id
                    or pkt.receiver == self.node_id):
                logger.info("[Relay] for me: %s", pkt.packet_id[:16])
                self._deliver_local(pkt)
            else:
                # Переслать дальше
                next_hop = pkt.route_to or pkt.receiver
                logger.info("[Relay] forward %s -> %s",
                            pkt.packet_id[:16], next_hop)
                self._forward_packet(pkt, next_hop)
        except Exception as e:
            logger.error("[Relay] handle: %s", e)
        finally:
            try:
                client.close()
            except Exception:
                pass

    def _forward_packet(self, pkt, next_hop):
        """P62c: переслать GDPPacket следующему hop.

        P63c: при успехе — mark_transit в PheromoneEngine через HTTP.
        """
        try:
            if ":" in next_hop:
                target, port_s = next_hop.rsplit(":", 1)
                port = int(port_s)
            else:
                target, port = next_hop, 8080
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10.0)
            s.connect((target, port))
            s.sendall(pkt.to_bytes())
            s.close()
            self._stats["bytes_relayed"] += len(pkt.to_bytes())

            # P63c: mark_transit
            try:
                import urllib.request
                import json as _json
                body = _json.dumps({
                    "source": pkt.sender or pkt.origin,
                    "destination": pkt.receiver or next_hop,
                    "via": self.node_id,
                    "path": [pkt.sender or pkt.origin,
                             self.node_id,
                             pkt.receiver or next_hop],
                }).encode()
                req = urllib.request.Request(
                    "http://127.0.0.1:8080/api/relay/transit",
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST")
                urllib.request.urlopen(req, timeout=3)
            except Exception:
                pass

            return True
        except Exception as e:
            logger.debug("[Relay] forward error: %s", e)
            return False

    def _deliver_local(self, pkt):
        """P62c: отдать GDPPacket локальному InevioNet."""
        try:
            import urllib.request
            req = urllib.request.Request(
                "http://127.0.0.1:8080/api/relay/incoming",
                data=pkt.to_bytes(),
                headers={"Content-Type": "application/octet-stream"},
                method="POST")
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            logger.debug("[Relay] deliver error: %s", e)

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