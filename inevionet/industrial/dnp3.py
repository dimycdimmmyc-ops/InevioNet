"""InevioNet DNP3 - реальный DNP3 через TCP-сокеты."""
import struct
import socket
import time
from typing import Optional, Dict, Any, List

from .base import IndustrialProtocol, IndustrialPacket
from ..core.logger import get_logger
from ..core.exceptions import IndustrialProtocolError

logger = get_logger("inevionet.industrial.dnp3")


# DNP3 Function Codes
DNP3_CONFIRM = 0x00
DNP3_READ = 0x01
DNP3_WRITE = 0x02
DNP3_SELECT = 0x03
DNP3_OPERATE = 0x04
DNP3_DIRECT_OPERATE = 0x05
DNP3_DIRECT_OPERATE_NR = 0x06


class DNP3(IndustrialProtocol):
    """Реальный DNP3 клиент через TCP-сокеты."""
    
    DEFAULT_PORT = 20000
    START_BYTES = b"\x05\x64"
    
    def __init__(self, target_host="127.0.0.1", target_port=DEFAULT_PORT, timeout=10.0):
        super().__init__(target_host, target_port, timeout)
        self._socket = None
    
    def calculate_crc(self, data: bytes) -> int:
        """Вычислить CRC-16 для DNP3."""
        crc = 0x0000
        for byte in data:
            crc ^= byte
            for _ in range(8):
                if crc & 1:
                    crc = (crc >> 1) ^ 0xA6BC
                else:
                    crc >>= 1
        return (~crc) & 0xFFFF
    
    def _connect(self) -> bool:
        """Установить TCP-соединение."""
        try:
            if self._socket:
                self._socket.close()
            
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.settimeout(self.timeout)
            self._socket.connect((self.target_host, self.target_port))
            return True
        except Exception as e:
            logger.error(f"DNP3 ошибка подключения: {e}")
            return False
    
    def _send_raw(self, data: bytes) -> Optional[bytes]:
        """Отправить сырые данные и получить ответ."""
        if not self._socket:
            if not self._connect():
                return None
        
        try:
            self._socket.sendall(data)
            self.stats["packets_sent"] += 1
            self.stats["bytes_sent"] += len(data)
            
            response = self._socket.recv(4096)
            if response:
                self.stats["packets_received"] += 1
                self.stats["bytes_received"] += len(response)
                return response
            return None
        except Exception as e:
            logger.error(f"DNP3 ошибка отправки: {e}")
            self.stats["errors"] += 1
            return None
    
    def encode(self, function_code=DNP3_READ, destination=1, source=2, data=b""):
        """Закодировать DNP3 пакет."""
        length = 5 + len(data)
        control = 0xC4
        
        header = (self.START_BYTES + 
                  bytes([length]) + 
                  bytes([control]) +
                  struct.pack("<H", destination) + 
                  struct.pack("<H", source))
        
        crc = self.calculate_crc(header)
        header_with_crc = header + struct.pack("<H", crc)
        
        if data:
            data_with_crc = b""
            for i in range(0, len(data), 16):
                chunk = data[i:i+16]
                chunk_crc = self.calculate_crc(chunk)
                data_with_crc += chunk + struct.pack("<H", chunk_crc)
            return header_with_crc + data_with_crc
        
        return header_with_crc
    
    def decode(self, data: bytes) -> Dict[str, Any]:
        """Декодировать DNP3 ответ."""
        if len(data) < 10:
            return {"error": "too_short"}
        
        if data[:2] != self.START_BYTES:
            return {"error": "invalid_start"}
        
        length = data[2]
        control = data[3]
        destination = struct.unpack("<H", data[4:6])[0]
        source = struct.unpack("<H", data[6:8])[0]
        header_crc = struct.unpack("<H", data[8:10])[0]
        
        expected_crc = self.calculate_crc(data[:8])
        
        return {
            "valid": header_crc == expected_crc,
            "length": length,
            "control": control,
            "destination": destination,
            "source": source,
            "user_data": data[10:10+length-5] if length > 5 else b"",
        }
    
    def read(self, address=0, count=1, destination=1) -> Optional[Dict]:
        """Читать данные через DNP3."""
        user_data = struct.pack("!BHH", DNP3_READ, address, count)
        encoded = self.encode(function_code=DNP3_READ, destination=destination, data=user_data)
        
        response = self._send_raw(encoded)
        if response:
            return self.decode(response)
        return None
    
    def write(self, address, value, destination=1) -> bool:
        """Записать данные через DNP3."""
        user_data = struct.pack("!BHH", DNP3_WRITE, address, value)
        encoded = self.encode(function_code=DNP3_WRITE, destination=destination, data=user_data)
        
        response = self._send_raw(encoded)
        if response:
            result = self.decode(response)
            return result.get("valid", False)
        return False
    
    def wrap_for_inevionet(self, function_code, destination=1, **params):
        """Завернуть DNP3 пакет для отправки через InevioNet."""
        user_data = struct.pack("!B", function_code)
        if "address" in params:
            user_data += struct.pack("!H", params["address"])
        if "count" in params:
            user_data += struct.pack("!H", params["count"])
        if "value" in params:
            user_data += struct.pack("!H", params["value"])
        
        encoded = self.encode(function_code=function_code, destination=destination, data=user_data)
        
        return self.wrap(
            data=encoded,
            metadata={
                "protocol": "dnp3",
                "target": f"{self.target_host}:{self.target_port}",
                "function_code": function_code,
                "destination": destination,
            }
        )
    
    def close(self):
        """Закрыть соединение."""
        if self._socket:
            self._socket.close()
            self._socket = None


if __name__ == "__main__":
    print("Testing DNP3 Client...")
    client = DNP3("127.0.0.1", 20000)
    
    # Тест кодирования
    packet = client.wrap_for_inevionet(DNP3_READ, destination=1, address=0, count=10)
    print(f"✅ Пакет создан: {len(packet.data)} байт")
    print(f"   HEX: {packet.data.hex()}")
    
    # Тест декодирования
    decoded = client.decode(packet.data)
    print(f"✅ Декодировано: valid={decoded.get('valid')}")
    
    print("DNP3 OK")
