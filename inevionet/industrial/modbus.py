"""InevioNet Modbus - Modbus TCP/RTU protocol."""
import struct
import socket
from typing import Optional, Dict, Any, List

from .base import IndustrialProtocol, IndustrialPacket
from ..core.logger import get_logger
from ..core.exceptions import IndustrialProtocolError

logger = get_logger("inevionet.industrial.modbus")


FC_READ_COILS = 0x01
FC_READ_DISCRETE_INPUTS = 0x02
FC_READ_HOLDING_REGISTERS = 0x03
FC_READ_INPUT_REGISTERS = 0x04
FC_WRITE_SINGLE_COIL = 0x05
FC_WRITE_SINGLE_REGISTER = 0x06
FC_WRITE_MULTIPLE_COILS = 0x0F
FC_WRITE_MULTIPLE_REGISTERS = 0x10


class ModbusTCP(IndustrialProtocol):
    def __init__(self, target_host="127.0.0.1", target_port=502, timeout=5.0):
        super().__init__(target_host, target_port, timeout)
        self._transaction_id = 0
        import threading
        self._lock = threading.Lock()

    def _next_transaction_id(self):
        with self._lock:
            self._transaction_id = (self._transaction_id + 1) & 0xFFFF
            return self._transaction_id

    def encode(self, function_code, slave=1, **params):
        pdu = struct.pack("!B", function_code)
        if function_code in (FC_READ_COILS, FC_READ_DISCRETE_INPUTS,
                             FC_READ_HOLDING_REGISTERS, FC_READ_INPUT_REGISTERS):
            address = params.get("address", 0)
            count = params.get("count", 1)
            pdu += struct.pack("!HH", address, count)
        elif function_code == FC_WRITE_SINGLE_COIL:
            address = params.get("address", 0)
            value = params.get("value", 0)
            pdu += struct.pack("!HH", address, 0xFF00 if value else 0x0000)
        elif function_code == FC_WRITE_SINGLE_REGISTER:
            address = params.get("address", 0)
            value = params.get("value", 0)
            pdu += struct.pack("!HH", address, value)
        elif function_code == FC_WRITE_MULTIPLE_REGISTERS:
            address = params.get("address", 0)
            values = params.get("values", [])
            pdu += struct.pack("!HH", address, len(values))
            pdu += struct.pack("!B", len(values) * 2)
            for v in values:
                pdu += struct.pack("!H", v)
        else:
            raise IndustrialProtocolError("ModbusTCP", f"Unsupported FC: {function_code}")
        transaction_id = self._next_transaction_id()
        length = len(pdu) + 1
        mbap = struct.pack("!HHHB", transaction_id, 0, length, slave)
        return mbap + pdu

    def decode(self, data):
        if len(data) < 9:
            raise IndustrialProtocolError("ModbusTCP", "Response too short")
        transaction_id, protocol_id, length, unit_id = struct.unpack("!HHHB", data[:7])
        pdu = data[7:]
        function_code = pdu[0]
        if function_code & 0x80:
            return {
                "error": True,
                "function_code": function_code & 0x7F,
                "error_code": pdu[1],
                "transaction_id": transaction_id,
                "unit_id": unit_id,
            }
        result = {
            "error": False,
            "function_code": function_code,
            "transaction_id": transaction_id,
            "unit_id": unit_id,
        }
        if function_code in (FC_READ_HOLDING_REGISTERS, FC_READ_INPUT_REGISTERS):
            byte_count = pdu[1]
            values = []
            for i in range(2, 2 + byte_count, 2):
                values.append(struct.unpack("!H", pdu[i:i+2])[0])
            result["values"] = values
        elif function_code in (FC_READ_COILS, FC_READ_DISCRETE_INPUTS):
            byte_count = pdu[1]
            bits = []
            for i in range(2, 2 + byte_count):
                byte = pdu[i]
                for bit in range(8):
                    bits.append((byte >> bit) & 1)
            result["values"] = bits
        elif function_code in (FC_WRITE_SINGLE_COIL, FC_WRITE_SINGLE_REGISTER):
            result["address"] = struct.unpack("!H", pdu[1:3])[0]
            result["value"] = struct.unpack("!H", pdu[3:5])[0]
        return result

    def read_holding_registers(self, slave=1, address=0, count=1):
        try:
            request = self.encode(FC_READ_HOLDING_REGISTERS, slave=slave,
                                  address=address, count=count)
            response = self._send_direct(request)
            if response:
                result = self.decode(response)
                if not result.get("error"):
                    return result.get("values", [])
            return None
        except Exception as e:
            logger.error(f"Modbus read error: {e}")
            self.stats["errors"] += 1
            return None

    def write_single_register(self, slave=1, address=0, value=0):
        try:
            request = self.encode(FC_WRITE_SINGLE_REGISTER, slave=slave,
                                  address=address, value=value)
            response = self._send_direct(request)
            if response:
                result = self.decode(response)
                return not result.get("error")
            return False
        except Exception as e:
            logger.error(f"Modbus write error: {e}")
            self.stats["errors"] += 1
            return False

    def _send_direct(self, request):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(self.timeout)
                s.connect((self.target_host, self.target_port))
                s.sendall(request)
                self.stats["packets_sent"] += 1
                self.stats["bytes_sent"] += len(request)
                response = s.recv(1024)
                if response:
                    self.stats["packets_received"] += 1
                    self.stats["bytes_received"] += len(response)
                    return response
                return None
        except Exception as e:
            logger.debug(f"Modbus socket error: {e}")
            return None

    def wrap_for_inevionet(self, function_code, slave=1, **params):
        request = self.encode(function_code, slave=slave, **params)
        return self.wrap(
            data=request,
            metadata={
                "protocol": "modbus_tcp",
                "target_host": self.target_host,
                "target_port": self.target_port,
                "slave": slave,
                "function_code": function_code,
            })


class ModbusRTU(IndustrialProtocol):
    def __init__(self, target_host="127.0.0.1", target_port=502, timeout=5.0):
        super().__init__(target_host, target_port, timeout)

    def calculate_crc16(self, data):
        crc = 0xFFFF
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ 0xA001
                else:
                    crc >>= 1
        return crc

    def encode(self, function_code, slave=1, **params):
        pdu = struct.pack("!BB", slave, function_code)
        if function_code == FC_READ_HOLDING_REGISTERS:
            address = params.get("address", 0)
            count = params.get("count", 1)
            pdu += struct.pack("!HH", address, count)
        elif function_code == FC_WRITE_SINGLE_REGISTER:
            address = params.get("address", 0)
            value = params.get("value", 0)
            pdu += struct.pack("!HH", address, value)
        else:
            raise IndustrialProtocolError("ModbusRTU", f"Unsupported FC: {function_code}")
        crc = self.calculate_crc16(pdu)
        pdu += struct.pack("<H", crc)
        return pdu

    def decode(self, data):
        if len(data) < 4:
            raise IndustrialProtocolError("ModbusRTU", "Response too short")
        slave = data[0]
        function_code = data[1]
        if function_code & 0x80:
            return {
                "error": True,
                "slave": slave,
                "function_code": function_code & 0x7F,
                "error_code": data[2],
            }
        result = {
            "error": False,
            "slave": slave,
            "function_code": function_code,
        }
        if function_code == FC_READ_HOLDING_REGISTERS:
            byte_count = data[2]
            values = []
            for i in range(3, 3 + byte_count, 2):
                values.append(struct.unpack("!H", data[i:i+2])[0])
            result["values"] = values
        return result


if __name__ == "__main__":
    print("Testing Modbus...")
    client = ModbusTCP("192.168.1.100", 502)
    request = client.encode(FC_READ_HOLDING_REGISTERS, slave=1, address=0, count=10)
    print(f"Request: {len(request)} bytes")
    print(f"HEX: {request.hex()}")
    packet = client.wrap_for_inevionet(FC_READ_HOLDING_REGISTERS, slave=1,
                                        address=0, count=10)
    print(f"Wrapped: {packet}")
    rtu = ModbusRTU()
    request_rtu = rtu.encode(FC_READ_HOLDING_REGISTERS, slave=1, address=0, count=10)
    print(f"RTU request: {request_rtu.hex()}")
    crc = rtu.calculate_crc16(request_rtu[:-2])
    print(f"CRC: {crc:04X}")
    print("OK")
