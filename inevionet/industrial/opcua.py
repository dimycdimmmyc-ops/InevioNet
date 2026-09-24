"""InevioNet OPC UA - basic OPC UA encapsulation."""
import struct
import time
from typing import Optional, Dict, Any

from .base import IndustrialProtocol, IndustrialPacket
from ..core.logger import get_logger

logger = get_logger("inevionet.industrial.opcua")


class OPCUA(IndustrialProtocol):
    DEFAULT_PORT = 4840

    def __init__(self, endpoint="opc.tcp://localhost:4840", timeout=10.0):
        if endpoint.startswith("opc.tcp://"):
            host_port = endpoint[10:]
            if ":" in host_port:
                host, port = host_port.split(":")
                port = int(port)
            else:
                host = host_port
                port = self.DEFAULT_PORT
        else:
            host = endpoint
            port = self.DEFAULT_PORT
        super().__init__(host, port, timeout)
        self.endpoint = endpoint

    def encode(self, message_type="HEL", **params):
        body = self._encode_body(message_type, params)
        header = struct.pack("!3sBI", message_type.encode("ascii")[:3],
                             ord("F"), len(body) + 8)
        return header + body

    def _encode_body(self, message_type, params):
        if message_type == "HEL":
            return struct.pack(
                "!IIIII",
                params.get("protocol_version", 0),
                params.get("receive_buffer_size", 65536),
                params.get("send_buffer_size", 65536),
                params.get("max_message_size", 0),
                params.get("max_chunk_count", 0))
        elif message_type == "OPN":
            return struct.pack("!I", params.get("security_mode", 1))
        elif message_type == "MSG":
            return params.get("data", b"")
        return params.get("data", b"")

    def decode(self, data):
        if len(data) < 8:
            return {"error": "too_short"}
        message_type = data[:3].decode("ascii", errors="ignore")
        chunk_type = chr(data[3])
        message_size = struct.unpack("!I", data[4:8])[0]
        return {
            "message_type": message_type,
            "chunk_type": chunk_type,
            "message_size": message_size,
            "body": data[8:],
        }

    def read_node(self, node_id, attribute=13):
        request_data = {
            "type": "ReadRequest",
            "node_id": node_id,
            "attribute": attribute,
            "timestamp": time.time(),
        }
        import json
        body = json.dumps(request_data).encode("utf-8")
        encoded = self.encode("MSG", data=body)
        return self.wrap(
            data=encoded,
            metadata={
                "protocol": "opcua",
                "endpoint": self.endpoint,
                "operation": "read",
                "node_id": node_id,
            })

    def write_node(self, node_id, value, attribute=13):
        request_data = {
            "type": "WriteRequest",
            "node_id": node_id,
            "attribute": attribute,
            "value": value,
            "timestamp": time.time(),
        }
        import json
        body = json.dumps(request_data).encode("utf-8")
        encoded = self.encode("MSG", data=body)
        return self.wrap(
            data=encoded,
            metadata={
                "protocol": "opcua",
                "endpoint": self.endpoint,
                "operation": "write",
                "node_id": node_id,
            })


if __name__ == "__main__":
    print("Testing OPCUA...")
    client = OPCUA("opc.tcp://192.168.1.100:4840")
    print(f"Client: {client}")
    encoded = client.encode("HEL", protocol_version=0)
    print(f"HEL: {len(encoded)} bytes")
    packet = client.read_node("ns=2;s=Temperature")
    print(f"Read packet: {packet}")
    print("OK")
