"""InevioNet Universal Transport - все протоколы в одном + Industrial (MQTT/Modbus/DNP3/OPC-UA)."""
import time
import asyncio
import concurrent.futures
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field

from .tcp import TCPClient
from .udp import UDPClient
from .dns import DNSClient
from .http import HTTPClient
from .icmp import ICMPClient

try:
    from .websocket import WSClient, WEBSOCKETS_AVAILABLE
except ImportError:
    WEBSOCKETS_AVAILABLE = False
    WSClient = None

# Industrial protocols (опционально)
try:
    from ..industrial.mqtt import MQTTClient, PAHO_AVAILABLE as MQTT_AVAILABLE
except ImportError:
    MQTTClient = None
    MQTT_AVAILABLE = False

try:
    from ..industrial.modbus import ModbusTCP
except ImportError:
    ModbusTCP = None

try:
    from ..industrial.dnp3 import DNP3
except ImportError:
    DNP3 = None

try:
    from ..industrial.opcua import OPCUA
except ImportError:
    OPCUA = None

from ..core.logger import get_logger

logger = get_logger("inevionet.network.transport")


@dataclass
class TransportResult:
    success: bool
    protocol: str
    bytes_sent: int = 0
    bytes_received: int = 0
    duration_ms: float = 0.0
    response: Optional[bytes] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __repr__(self):
        status = "OK" if self.success else "FAIL"
        return (f"[{status}] TransportResult({self.protocol}, "
                f"{self.bytes_sent}B sent, {self.bytes_received}B recv, "
                f"{self.duration_ms:.1f}ms)")


class UniversalTransport:
    def __init__(self, timeout=10.0, use_icmp_raw=False, enable_fallback=True):
        self.timeout = timeout
        self.use_icmp_raw = use_icmp_raw
        self.enable_fallback = enable_fallback
        self._http_client = None
        self._dns_client = None
        self._icmp_client = None
        self._stats = {}

    def _get_http_client(self):
        if self._http_client is None:
            self._http_client = HTTPClient(timeout=self.timeout)
        return self._http_client

    def _get_dns_client(self):
        if self._dns_client is None:
            self._dns_client = DNSClient(timeout=self.timeout)
        return self._dns_client

    def _get_icmp_client(self):
        if self._icmp_client is None:
            self._icmp_client = ICMPClient()
        return self._icmp_client

    def send_via_http(self, data, url="http://httpbin.org/get"):
        start = time.time()
        try:
            client = self._get_http_client()
            success = client.send_data_in_headers(data, url)
            return TransportResult(success=success, protocol="HTTP",
                                   bytes_sent=len(data),
                                   duration_ms=(time.time() - start) * 1000)
        except Exception as e:
            return TransportResult(success=False, protocol="HTTP", error=str(e))

    def send_via_dns(self, data, domain="example.com"):
        start = time.time()
        try:
            client = self._get_dns_client()
            results = client.send_data_via_qname(data, domain)
            duration = (time.time() - start) * 1000
            success = all(results) if results else False
            return TransportResult(success=success, protocol="DNS",
                                   bytes_sent=len(data), duration_ms=duration,
                                   metadata={"chunks": len(results),
                                             "successful": sum(results)})
        except Exception as e:
            return TransportResult(success=False, protocol="DNS", error=str(e))

    def send_via_icmp(self, data, host="8.8.8.8"):
        start = time.time()
        try:
            client = self._get_icmp_client()
            if client.has_raw and len(data) > 0:
                result = client.ping(host, timeout=self.timeout, payload=data)
            else:
                result = client.ping(host, timeout=self.timeout)
            duration = (time.time() - start) * 1000
            return TransportResult(success=result is not None, protocol="ICMP",
                                   bytes_sent=len(data),
                                   bytes_received=len(result.payload) if result else 0,
                                   duration_ms=duration,
                                   metadata={"rtt_ms": result.rtt_ms if result else 0})
        except Exception as e:
            return TransportResult(success=False, protocol="ICMP", error=str(e))

    def send_via_tcp(self, data, host, port):
        start = time.time()
        try:
            with TCPClient(host, port, timeout=self.timeout) as client:
                if not client.is_connected:
                    return TransportResult(success=False, protocol="TCP",
                                           error="Connection failed")
                success = client.send(data)
                response = client.recv() if success else None
                return TransportResult(success=success, protocol="TCP",
                                       bytes_sent=client.bytes_sent,
                                       bytes_received=client.bytes_received,
                                       duration_ms=(time.time() - start) * 1000,
                                       response=response)
        except Exception as e:
            return TransportResult(success=False, protocol="TCP", error=str(e))

    def send_via_udp(self, data, host, port, expect_response=False):
        start = time.time()
        try:
            with UDPClient(timeout=self.timeout) as client:
                success = client.send_to(data, (host, port))
                response = None
                if success and expect_response:
                    response, _ = client.recv_from()
                return TransportResult(success=success, protocol="UDP",
                                       bytes_sent=client.bytes_sent,
                                       bytes_received=client.bytes_received,
                                       duration_ms=(time.time() - start) * 1000,
                                       response=response)
        except Exception as e:
            return TransportResult(success=False, protocol="UDP", error=str(e))

    def send_via_udp_punched(self, data, peer_public, expect_response=True,
                              hole_puncher=None):
        """Отправить данные через уже открытый UDP-канал (hole-punched).

        Если передан hole_puncher (с открытым сокетом) — используем его.
        Иначе — обычный UDP send на peer_public.
        """
        start = time.time()
        try:
            if hole_puncher is not None and getattr(hole_puncher, "peer_addr", None):
                ok = hole_puncher.send(data)
                response = None
                if ok and expect_response:
                    response = hole_puncher.recv(timeout=self.timeout)
                return TransportResult(
                    success=bool(ok), protocol="UDP_PUNCHED",
                    bytes_sent=len(data),
                    bytes_received=len(response) if response else 0,
                    duration_ms=(time.time() - start) * 1000,
                    response=response,
                    metadata={"peer": hole_puncher.peer_addr},
                )
            host, port = peer_public
            return self.send_via_udp(data, host, port,
                                     expect_response=expect_response)
        except Exception as e:
            return TransportResult(success=False, protocol="UDP_PUNCHED",
                                   error=str(e))

    def send_via_websocket(self, data, uri, expect_response=True):
        if not WEBSOCKETS_AVAILABLE:
            return TransportResult(success=False, protocol="WebSocket",
                                   error="websockets not installed")
        start = time.time()
        try:
            with WSClient(uri, timeout=self.timeout) as client:
                if not client.is_connected:
                    return TransportResult(success=False, protocol="WebSocket",
                                           error="Connection failed")
                success = client.send(data)
                response = client.recv() if (success and expect_response) else None
                return TransportResult(success=success, protocol="WebSocket",
                                       bytes_sent=client.bytes_sent,
                                       bytes_received=client.bytes_received,
                                       duration_ms=(time.time() - start) * 1000,
                                       response=response)
        except Exception as e:
            return TransportResult(success=False, protocol="WebSocket", error=str(e))

    # ==================================================
    # INDUSTRIAL PROTOCOLS
    # ==================================================
    def send_via_mqtt(self, data, host, port=1883, topic="inevionet/data",
                      qos=0, use_tls=False):
        """Отправить данные через MQTT."""
        # P11.6-fix-v2: empty host guard
        if not host or str(host).strip().lower() in ("", "unknown", "none", "null"):
            return TransportResult(success=False, protocol="MQTT",
                                   error="empty_host")
        if MQTTClient is None:
            return TransportResult(success=False, protocol="MQTT",
                                   error="MQTTClient not available")
        start = time.time()
        try:
            client_id = "inevionet_%d" % (int(time.time() * 1000) % 100000)
            client = MQTTClient(
                target_host=host, target_port=port,
                client_id=client_id, timeout=self.timeout,
                use_tls=use_tls)
            if not client.connect():
                return TransportResult(success=False, protocol="MQTT",
                                       error="connect_failed")
            try:
                message = data.decode("utf-8", errors="replace")
            except Exception:
                message = data.hex()
            ok = client.publish(topic, message, qos=qos)
            try:
                client.disconnect()
            except Exception:
                pass
            return TransportResult(
                success=ok, protocol="MQTT",
                bytes_sent=len(data),
                duration_ms=(time.time() - start) * 1000,
                metadata={"topic": topic, "qos": qos,
                          "host": host, "port": port,
                          "simulation": not MQTT_AVAILABLE})
        except Exception as e:
            return TransportResult(success=False, protocol="MQTT", error=str(e))

    def send_via_modbus(self, data, host, port=502, slave=1, register=0):
        """Отправить данные через Modbus TCP."""
        if ModbusTCP is None:
            return TransportResult(success=False, protocol="Modbus",
                                   error="ModbusTCP not available")
        start = time.time()
        try:
            client = ModbusTCP(target_host=host, target_port=port,
                               timeout=self.timeout)
            if len(data) % 2:
                data = data + b"\x00"
            values = []
            for i in range(0, len(data), 2):
                values.append((data[i] << 8) | data[i + 1])
            if not values:
                return TransportResult(success=False, protocol="Modbus",
                                       error="empty_data")
            ok = client.write_single_register(slave=slave, address=register,
                                              value=values[0])
            if len(values) > 1:
                try:
                    from ..industrial.modbus import FC_WRITE_MULTIPLE_REGISTERS
                    request = client.encode(
                        FC_WRITE_MULTIPLE_REGISTERS,
                        slave=slave, address=register, values=values)
                    response = client._send_direct(request)
                    ok = response is not None
                except Exception:
                    pass
            return TransportResult(
                success=bool(ok), protocol="Modbus",
                bytes_sent=len(data),
                duration_ms=(time.time() - start) * 1000,
                metadata={"host": host, "port": port,
                          "slave": slave, "register": register,
                          "registers_count": len(values)})
        except Exception as e:
            return TransportResult(success=False, protocol="Modbus", error=str(e))

    def send_via_dnp3(self, data, host, port=20000, destination=1):
        """Отправить данные через DNP3."""
        if DNP3 is None:
            return TransportResult(success=False, protocol="DNP3",
                                   error="DNP3 not available")
        start = time.time()
        try:
            client = DNP3(target_host=host, target_port=port,
                          timeout=self.timeout)
            if len(data) < 2:
                data = data + b"\x00" * (2 - len(data))
            address = 0
            value = (data[0] << 8) | data[1]
            ok = client.write(address=address, value=value,
                              destination=destination)
            try:
                client.close()
            except Exception:
                pass
            return TransportResult(
                success=bool(ok), protocol="DNP3",
                bytes_sent=len(data),
                duration_ms=(time.time() - start) * 1000,
                metadata={"host": host, "port": port,
                          "destination": destination})
        except Exception as e:
            return TransportResult(success=False, protocol="DNP3", error=str(e))

    def send_via_opcua(self, data, host, port=4840, node_id="ns=2;s=InevioNet"):
        """Отправить данные через OPC-UA."""
        if OPCUA is None:
            return TransportResult(success=False, protocol="OPCUA",
                                   error="OPCUA not available")
        start = time.time()
        try:
            endpoint = "opc.tcp://%s:%d" % (host, port)
            client = OPCUA(endpoint=endpoint, timeout=self.timeout)
            packet = client.write_node(node_id=node_id,
                                       value=data.hex())
            payload = packet.data if hasattr(packet, "data") else b""
            if not payload:
                return TransportResult(success=False, protocol="OPCUA",
                                       error="empty_payload")
            tcp_result = self.send_via_tcp(payload, host, port)
            return TransportResult(
                success=tcp_result.success, protocol="OPCUA",
                bytes_sent=len(payload),
                bytes_received=tcp_result.bytes_received,
                duration_ms=(time.time() - start) * 1000,
                metadata={"host": host, "port": port,
                          "node_id": node_id})
        except Exception as e:
            return TransportResult(success=False, protocol="OPCUA", error=str(e))

    def send(self, data, protocol="auto", target="", **kwargs):
        protocol = protocol.upper()
        if protocol == "AUTO":
            return self._send_auto(data, target, **kwargs)
        if protocol == "HTTP" or protocol == "HTTPS":
            return self.send_via_http(data, target or "http://httpbin.org/get")
        elif protocol == "DNS":
            return self.send_via_dns(data, target or "example.com")
        elif protocol == "ICMP":
            return self.send_via_icmp(data, target or "8.8.8.8")
        elif protocol == "TCP":
            host, port = self._parse_hostport(target, 80)
            return self.send_via_tcp(data, host, port)
        elif protocol == "UDP":
            host, port = self._parse_hostport(target, 53)
            return self.send_via_udp(data, host, port, kwargs.get("expect_response", False))
        elif protocol in ("WEBSOCKET", "WS"):
            return self.send_via_websocket(data, target)
        elif protocol == "MQTT":
            host, port = self._parse_hostport(target, 1883)
            topic = kwargs.get("topic", "inevionet/data")
            qos = kwargs.get("qos", 0)
            return self.send_via_mqtt(data, host, port, topic=topic, qos=qos)
        elif protocol == "MODBUS":
            host, port = self._parse_hostport(target, 502)
            slave = kwargs.get("slave", 1)
            register = kwargs.get("register", 0)
            return self.send_via_modbus(data, host, port,
                                        slave=slave, register=register)
        elif protocol == "DNP3":
            host, port = self._parse_hostport(target, 20000)
            destination = kwargs.get("destination", 1)
            return self.send_via_dnp3(data, host, port,
                                      destination=destination)
        elif protocol in ("OPCUA", "OPC-UA"):
            host, port = self._parse_hostport(target, 4840)
            node_id = kwargs.get("node_id", "ns=2;s=InevioNet")
            return self.send_via_opcua(data, host, port, node_id=node_id)
        else:
            return TransportResult(success=False, protocol=protocol,
                                   error=f"Unknown protocol: {protocol}")

    def _send_auto(self, data, target="", **kwargs):
        if target and ":" in target and not target.startswith(("http://", "https://", "ws://", "wss://")):
            try:
                _, port_s = target.rsplit(":", 1)
                port = int(port_s)
                port_proto = {
                    1883: "MQTT", 8883: "MQTT",
                    502: "MODBUS",
                    20000: "DNP3",
                    4840: "OPCUA",
                }
                if port in port_proto:
                    logger.debug("[Transport] auto -> %s (port %d)",
                                 port_proto[port], port)
                    result = self.send(data, port_proto[port], target, **kwargs)
                    if result.success or not self.enable_fallback:
                        return result
            except (ValueError, IndexError):
                pass

        priorities = ["HTTP", "DNS", "ICMP"]
        if target:
            if target.startswith(("http://", "https://")):
                priorities = ["HTTP"]
            elif target.startswith(("ws://", "wss://")):
                priorities = ["WebSocket"]
            elif ":" in target and not target.startswith("http"):
                priorities = ["TCP", "UDP"]
        if not self.enable_fallback:
            priorities = priorities[:1]
        last_result = None
        for proto in priorities:
            result = self.send(data, proto, target, **kwargs)
            if result.success:
                return result
            last_result = result
        return last_result or TransportResult(success=False, protocol="AUTO",
                                              error="All protocols failed")

    def send_parallel(self, data, protocols):
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(protocols)) as executor:
            futures = {executor.submit(self.send, data, proto, target): (proto, target)
                       for proto, target in protocols}
            for future in concurrent.futures.as_completed(futures):
                try:
                    results.append(future.result(timeout=self.timeout * 2))
                except Exception as e:
                    proto, target = futures[future]
                    results.append(TransportResult(success=False, protocol=proto, error=str(e)))
        return results

    @staticmethod
    def _parse_hostport(target, default_port):
        if ":" in target and not target.startswith(("http://", "https://")):
            parts = target.split(":")
            try:
                return parts[0], int(parts[1])
            except (ValueError, IndexError):
                pass
        return target, default_port

    def close(self):
        if self._http_client:
            self._http_client.close()
        if self._icmp_client:
            self._icmp_client.close()
        self._http_client = None
        self._dns_client = None
        self._icmp_client = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


if __name__ == "__main__":
    print("Testing UniversalTransport (with industrial)...")
    t = UniversalTransport(timeout=10.0)
    r = t.send_via_http(b"Hello, InevioNet!")
    print(r)
    r = t.send_via_icmp(b"", host="8.8.8.8")
    print(r)
    r = t.send_via_mqtt(b"Hello MQTT!", host="test.mosquitto.org", port=1883,
                        topic="inevionet/test")
    print(r)
    t.close()
    print("Transport module OK")