"""InevioNet Capsule - universal embeddable capsule."""
import os
import json
import time
import threading
from typing import Optional, Dict, Any, Union, Callable, List, Tuple

from ..core.crypto import InevioCrypto, random_id
from ..core.packet import GDPPacket, create_packet
from ..core.logger import get_logger
from ..core.constants import DataPaths
from ..core.exceptions import (InevioException, CryptoError, NetworkError, DeliveryError)
from ..network.transport import UniversalTransport
from ..steganography.engine import SteganographyEngine
from ..mycelium.engine import MyceliumEngine
from ..ai.selector import ProtocolSelector
from ..ai.recursion import WeightedRecursion
from ..evolution.engine import EvolutionEngine

logger = get_logger("inevionet.capsule")


class InevioCapsule:
    """Universal embeddable capsule for InevioNet."""

    def __init__(self, password, node_id=None, auto_start=True,
                 mode="standard", config=None):
        self.password = password
        self.node_id = node_id or f"capsule_{random_id('', 6)}"
        self.mode = mode
        self.config = config or {}
        self.crypto = InevioCrypto(password)
        self.transport = UniversalTransport(timeout=10.0)
        self.stealth = SteganographyEngine()
        self.mycelium = MyceliumEngine(node_id=self.node_id)
        self.selector = ProtocolSelector()
        self.recursion = WeightedRecursion(max_depth=5)
        self.evolution = EvolutionEngine(population_size=20)
        self._handlers: Dict[str, List[Callable]] = {
            "on_send": [], "on_receive": [],
            "on_delivery": [], "on_error": [],
            "on_mycelium_spread": [],
        }
        self._running = False
        self._lock = threading.Lock()
        self.stats = {
            "packets_sent": 0, "packets_received": 0,
            "packets_delivered": 0, "packets_failed": 0,
            "bytes_sent": 0, "bytes_received": 0,
            "start_time": time.time(), "uptime": 0.0,
        }
        self.received_packets: Dict[str, GDPPacket] = {}
        self.sent_packets: Dict[str, GDPPacket] = {}
        logger.info(f"InevioCapsule created: node_id={self.node_id}")
        if auto_start:
            self.start()

    def start(self):
        if self._running:
            return
        self._running = True
        try:
            self.evolution.initialize()
        except Exception as e:
            logger.error(f"Evolution init error: {e}")
        self.mycelium.start()
        logger.info(f"InevioCapsule started: {self.node_id}")

    def stop(self):
        if not self._running:
            return
        self._running = False
        self.mycelium.stop()
        self.transport.close()
        self.stealth.close()
        logger.info("InevioCapsule stopped")

    def send(self, receiver, payload, protocol=None, priority=5,
             encrypt=True, spread_mycelium=False, metadata=None):
        try:
            data_bytes = self._prepare_payload(payload)
            if encrypt:
                data_bytes = self.crypto.encrypt(data_bytes)
                is_encrypted = True
            else:
                is_encrypted = False
            if protocol is None or protocol.lower() == "auto":
                protocol = self.selector.select() or "HTTPS"
            packet = create_packet(
                sender=self.node_id, receiver=receiver,
                payload=data_bytes, protocol=protocol,
                priority=priority, metadata=metadata or {})
            packet._is_encrypted = is_encrypted
            packet.sign(self.crypto.get_signing_keypair().private_key)
            result = self.transport.send(
                data=packet.to_bytes(),
                protocol=self._map_protocol(protocol),
                target=self._get_target(protocol))
            with self._lock:
                self.stats["packets_sent"] += 1
                self.stats["bytes_sent"] += len(data_bytes)
                if result.success:
                    self.stats["packets_delivered"] += 1
                    self.selector.record_success(protocol, result.duration_ms / 1000)
                else:
                    self.stats["packets_failed"] += 1
                    self.selector.record_failure(protocol)
                self.sent_packets[packet.packet_id] = packet
            if spread_mycelium:
                count = self.mycelium.spread_packet(packet)
                self._trigger_event("on_mycelium_spread",
                                     {"packet_id": packet.packet_id, "count": count})
            self._trigger_event("on_send", packet)
            if result.success:
                self._trigger_event("on_delivery", packet)
            return packet
        except Exception as e:
            logger.error(f"Send error: {e}")
            self._trigger_event("on_error", {"error": str(e)})
            return None

    def send_text(self, receiver, text, **kwargs):
        return self.send(receiver, text.encode("utf-8"), **kwargs)

    def send_json(self, receiver, data, **kwargs):
        return self.send(receiver, json.dumps(data, ensure_ascii=False), **kwargs)

    def send_stealth(self, data, method="HTTP_HEADERS", target=""):
        try:
            data_bytes = self._prepare_payload(data)
            result = self.stealth.send(data_bytes, method=method, target=target)
            if result.success:
                with self._lock:
                    self.stats["packets_sent"] += 1
                    self.stats["bytes_sent"] += len(data_bytes)
                    self.stats["packets_delivered"] += 1
            return result.success
        except Exception as e:
            logger.error(f"Stealth error: {e}")
            return False

    def receive(self, packet_data, auto_decrypt=True):
        try:
            packet = self._parse_packet(packet_data)
            if not packet:
                return False, None
            payload = packet.payload
            if auto_decrypt and getattr(packet, "_is_encrypted", False):
                try:
                    payload = self.crypto.decrypt(payload)
                except CryptoError as e:
                    logger.warning(f"Decrypt error: {e}")
                    return False, None
            decoded = self._decode_payload(payload)
            with self._lock:
                self.stats["packets_received"] += 1
                self.stats["bytes_received"] += len(packet.payload)
                self.received_packets[packet.packet_id] = packet
            self.mycelium.record_success(
                source=packet.sender, destination=packet.receiver,
                protocol=packet.protocol)
            self._trigger_event("on_receive", packet)
            return True, decoded
        except Exception as e:
            logger.error(f"Receive error: {e}")
            self._trigger_event("on_error", {"error": str(e)})
            return False, None

    def embed_in_application(self, app_name="app", namespace=None):
        namespace = namespace or f"inevionet_{app_name}"
        api = {
            "capsule_id": self.node_id, "app_name": app_name,
            "namespace": namespace, "version": "1.0.0",
            "timestamp": time.time(),
            "send": self.send, "send_text": self.send_text,
            "send_json": self.send_json, "send_stealth": self.send_stealth,
            "receive": self.receive,
            "start": self.start, "stop": self.stop,
            "get_stats": self.get_stats,
            "on_send": lambda h: self.register_handler("on_send", h),
            "on_receive": lambda h: self.register_handler("on_receive", h),
            "on_delivery": lambda h: self.register_handler("on_delivery", h),
            "on_error": lambda h: self.register_handler("on_error", h),
            "crypto": self.crypto, "transport": self.transport,
            "mycelium": self.mycelium, "selector": self.selector,
        }
        logger.info(f"Capsule embedded into {app_name} as {namespace}")
        return api

    def register_handler(self, event, handler):
        if event in self._handlers:
            self._handlers[event].append(handler)
        else:
            self._handlers[event] = [handler]

    def _trigger_event(self, event, data):
        for handler in self._handlers.get(event, []):
            try:
                handler(data)
            except Exception as e:
                logger.error(f"Handler error {event}: {e}")

    def _prepare_payload(self, payload):
        if isinstance(payload, bytes):
            return payload
        elif isinstance(payload, str):
            return payload.encode("utf-8")
        elif isinstance(payload, dict):
            return json.dumps(payload, ensure_ascii=False).encode("utf-8")
        return str(payload).encode("utf-8")

    def _decode_payload(self, payload):
        try:
            text = payload.decode("utf-8")
            if text.startswith(("{", "[")):
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    pass
            return text
        except UnicodeDecodeError:
            return payload

    def _parse_packet(self, data):
        if isinstance(data, GDPPacket):
            return data
        if isinstance(data, str):
            try:
                data = bytes.fromhex(data)
            except ValueError:
                try:
                    return GDPPacket.from_json(data)
                except Exception:
                    return None
        if isinstance(data, bytes):
            try:
                return GDPPacket.from_bytes(data)
            except Exception:
                try:
                    return GDPPacket.from_json(data.decode("utf-8"))
                except Exception:
                    return None
        return None

    def _map_protocol(self, protocol):
        mapping = {"TCP": "TCP", "UDP": "UDP", "HTTPS": "HTTP",
                   "HTTP": "HTTP", "DNS": "DNS", "ICMP": "ICMP",
                   "WEBSOCKET": "WebSocket"}
        return mapping.get(protocol.upper(), "HTTP")

    def _get_target(self, protocol):
        targets = {"HTTPS": "http://httpbin.org/get",
                   "HTTP": "http://httpbin.org/get",
                   "DNS": "example.com", "ICMP": "8.8.8.8"}
        return targets.get(protocol.upper(), "http://httpbin.org/get")

    def get_stats(self):
        with self._lock:
            self.stats["uptime"] = time.time() - self.stats["start_time"]
            base = dict(self.stats)
        return {
            **base, "node_id": self.node_id, "mode": self.mode,
            "running": self._running,
            "sent_count": len(self.sent_packets),
            "received_count": len(self.received_packets),
            "selector": self.selector.get_stats(),
            "mycelium": self.mycelium.get_stats(),
        }

    def save_state(self, filepath=None):
        if filepath is None:
            filepath = str(DataPaths.get_state_dir() / f"capsule_{self.node_id}.json")
        state = {"node_id": self.node_id, "mode": self.mode,
                 "stats": self.stats, "timestamp": time.time()}
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
            logger.info(f"State saved: {filepath}")
        except Exception as e:
            logger.error(f"Save state error: {e}")

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()

    def __repr__(self):
        return f"InevioCapsule(node_id={self.node_id}, running={self._running})"


if __name__ == "__main__":
    print("Testing InevioCapsule...")
    capsule = InevioCapsule("test_password", node_id="test_capsule", auto_start=True)
    print(f"Capsule: {capsule}")
    packet = capsule.send("alice", "Hello!")
    print(f"Sent: {packet.packet_id[:16] if packet else 'FAIL'}")
    api = capsule.embed_in_application("demo_app")
    print(f"API keys: {list(api.keys())[:5]}")
    capsule.stop()
    print("OK")
