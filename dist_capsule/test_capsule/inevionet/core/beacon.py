"""InevioNet Beacon - маячек для обнаружения узлов сети."""
import hashlib
import time
from typing import Optional, Dict, Any

class InevioNetBeacon:
    """Маячек InevioNet - уникальная метка для обнаружения узлов."""
    
    # Сигнатура маячка (можно менять для разных версий)
    SIGNATURE = b"INEVIONET_BEACON_v1"
    SECRET_KEY = "inevionet_secret_2026"  # Можно сделать настраиваемым
    
    @classmethod
    def create_beacon(cls, node_id: str, metadata: Dict[str, Any] = None) -> bytes:
        """Создать маячек с меткой узла."""
        payload = {
            "signature": cls.SIGNATURE.decode('utf-8'),
            "node_id": node_id,
            "timestamp": time.time(),
            "version": "1.0.0",
            "metadata": metadata or {},
        }
        import json
        data = json.dumps(payload).encode('utf-8')
        # Добавляем HMAC для проверки подлинности
        import hmac
        mac = hmac.new(cls.SECRET_KEY.encode(), data, hashlib.sha256).digest()
        return cls.SIGNATURE + mac + data
    
    @classmethod
    def parse_beacon(cls, data: bytes) -> Optional[Dict[str, Any]]:
        """Разобрать маячек и проверить подлинность."""
        if not data.startswith(cls.SIGNATURE):
            return None
        
        import hmac
        import json
        
        mac = data[len(cls.SIGNATURE):len(cls.SIGNATURE)+32]
        payload_data = data[len(cls.SIGNATURE)+32:]
        
        # Проверяем HMAC
        expected_mac = hmac.new(cls.SECRET_KEY.encode(), payload_data, hashlib.sha256).digest()
        if not hmac.compare_digest(mac, expected_mac):
            return None
        
        try:
            payload = json.loads(payload_data.decode('utf-8'))
            return payload
        except Exception:
            return None
    
    @classmethod
    def is_inevionet_node(cls, data: bytes) -> bool:
        """Проверить, является ли ответ маячком InevioNet."""
        return cls.parse_beacon(data) is not None
    
    @classmethod
    def embed_in_packet(cls, packet_data: bytes, node_id: str) -> bytes:
        """Вшить маячек в пакет данных."""
        beacon = cls.create_beacon(node_id)
        # Формат: [beacon_length:4][beacon][original_data]
        import struct
        return struct.pack("!I", len(beacon)) + beacon + packet_data
    
    @classmethod
    def extract_from_packet(cls, packet_data: bytes) -> tuple:
        """Извлечь маячек из пакета. Возвращает (beacon_data, original_data)."""
        import struct
        if len(packet_data) < 4:
            return None, packet_data
        
        beacon_length = struct.unpack("!I", packet_data[:4])[0]
        if len(packet_data) < 4 + beacon_length:
            return None, packet_data
        
        beacon_data = packet_data[4:4+beacon_length]
        original_data = packet_data[4+beacon_length:]
        
        if cls.is_inevionet_node(beacon_data):
            return cls.parse_beacon(beacon_data), original_data
        return None, original_data
