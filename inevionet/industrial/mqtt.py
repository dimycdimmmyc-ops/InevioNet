"""InevioNet MQTT - реальный MQTT через paho-mqtt."""
import json
import time
from typing import Optional, Dict, Any, List, Callable

try:
    import paho.mqtt.client as mqtt
    PAHO_AVAILABLE = True
except ImportError:
    PAHO_AVAILABLE = False

from .base import IndustrialProtocol, IndustrialPacket
from ..core.logger import get_logger
from ..core.exceptions import IndustrialProtocolError

logger = get_logger("inevionet.industrial.mqtt")


class MQTTClient(IndustrialProtocol):
    """Реальный MQTT клиент через paho-mqtt."""

    DEFAULT_PORT = 1883
    DEFAULT_TLS_PORT = 8883

    def __init__(self, target_host="test.mosquitto.org", target_port=DEFAULT_PORT,
                 client_id="inevionet_client", timeout=10.0, use_tls=False):
        super().__init__(target_host, target_port, timeout)
        self.client_id = client_id
        self.use_tls = use_tls
        self._client = None
        self._connected = False
        self._message_handlers: Dict[str, Callable] = {}

        if PAHO_AVAILABLE:
            self._client = mqtt.Client(client_id=client_id)
            self._client.on_connect = self._on_connect
            self._client.on_message = self._on_message
            self._client.on_disconnect = self._on_disconnect

            if use_tls:
                self._client.tls_set()
        else:
            logger.warning("paho-mqtt не установлен. MQTT будет в режиме симуляции.")

    def _on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._connected = True
            logger.info(f"MQTT подключен к {self.target_host}:{self.target_port}")
        else:
            logger.error(f"MQTT ошибка подключения: {rc}")

    def _on_message(self, client, userdata, msg):
        topic = msg.topic
        payload = msg.payload.decode('utf-8', errors='ignore')
        logger.debug(f"MQTT получено: {topic} = {payload}")

        if topic in self._message_handlers:
            try:
                self._message_handlers[topic](topic, payload)
            except Exception as e:
                logger.error(f"Ошибка обработчика MQTT: {e}")

    def _on_disconnect(self, client, userdata, rc):
        self._connected = False
        if rc != 0:
            logger.warning(f"MQTT отключен (код: {rc})")

    def connect(self) -> bool:
        """Подключиться к MQTT брокеру."""
        # P11.6-fix-v2: empty host guard
        _th = str(getattr(self, 'target_host', '') or '').strip().lower()
        if _th in ('', 'unknown', 'none', 'null'):
            if not getattr(self, '_empty_host_warned', False):
                logger.warning('[MQTT] пустой host — connect отменён')
                self._empty_host_warned = True
            self._last_error = 'empty_host'
            return False

        if not PAHO_AVAILABLE:
            logger.warning("MQTT симуляция: подключение")
            self._connected = True
            return True

        try:
            self._client.connect(self.target_host, self.target_port, self.timeout)
            self._client.loop_start()
            return True
        except Exception as e:
            logger.error(f"MQTT ошибка подключения: {e}")
            return False

    def disconnect(self):
        """Отключиться от MQTT брокера."""
        if self._client:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception:
                pass
        self._connected = False

    def publish(self, topic: str, message: str, qos: int = 0, retain: bool = False) -> bool:
        """Опубликовать сообщение."""
        if not PAHO_AVAILABLE:
            logger.info(f"MQTT симуляция: publish {topic} = {message}")
            self.stats["packets_sent"] += 1
            return True

        if not self._connected:
            if not self.connect():
                return False

        try:
            result = self._client.publish(topic, message, qos=qos, retain=retain)
            if result.rc == 0:
                self.stats["packets_sent"] += 1
                self.stats["bytes_sent"] += len(message)
                return True
            else:
                logger.error(f"MQTT ошибка публикации: {result.rc}")
                return False
        except Exception as e:
            logger.error(f"MQTT ошибка: {e}")
            return False

    def subscribe(self, topic: str, qos: int = 0, handler: Callable = None) -> bool:
        """Подписаться на топик."""
        if not PAHO_AVAILABLE:
            logger.info(f"MQTT симуляция: subscribe {topic}")
            if handler:
                self._message_handlers[topic] = handler
            return True

        if not self._connected:
            if not self.connect():
                return False

        try:
            self._client.subscribe(topic, qos)
            if handler:
                self._message_handlers[topic] = handler
            return True
        except Exception as e:
            logger.error(f"MQTT ошибка подписки: {e}")
            return False

    def encode(self, operation="publish", **params):
        """Закодировать MQTT пакет для отправки через InevioNet."""
        if operation == "publish":
            topic = params.get("topic", "")
            message = params.get("message", "")
            qos = params.get("qos", 0)
            return self._encode_publish(topic, message, qos)
        elif operation == "subscribe":
            topic = params.get("topic", "")
            qos = params.get("qos", 0)
            return self._encode_subscribe(topic, qos)
        elif operation == "connect":
            return self._encode_connect()
        raise ValueError(f"Неизвестная операция: {operation}")

    def _encode_publish(self, topic, message, qos=0):
        """Закодировать PUBLISH пакет."""
        packet_data = json.dumps({
            "type": "publish",
            "topic": topic,
            "message": message,
            "qos": qos,
            "timestamp": time.time()
        }).encode('utf-8')

        return self.wrap(
            data=packet_data,
            metadata={
                "protocol": "mqtt",
                "target": f"{self.target_host}:{self.target_port}",
                "operation": "publish",
                "topic": topic,
                "qos": qos,
            }
        )

    def _encode_subscribe(self, topic, qos=0):
        """Закодировать SUBSCRIBE пакет."""
        packet_data = json.dumps({
            "type": "subscribe",
            "topic": topic,
            "qos": qos,
            "timestamp": time.time()
        }).encode('utf-8')

        return self.wrap(
            data=packet_data,
            metadata={
                "protocol": "mqtt",
                "target": f"{self.target_host}:{self.target_port}",
                "operation": "subscribe",
                "topic": topic,
                "qos": qos,
            }
        )

    def _encode_connect(self):
        """Закодировать CONNECT пакет."""
        packet_data = json.dumps({
            "type": "connect",
            "client_id": self.client_id,
            "timestamp": time.time()
        }).encode('utf-8')

        return self.wrap(
            data=packet_data,
            metadata={
                "protocol": "mqtt",
                "target": f"{self.target_host}:{self.target_port}",
                "operation": "connect",
                "client_id": self.client_id,
            }
        )

    def decode(self, data):
        """Декодировать MQTT пакет."""
        try:
            return json.loads(data.decode('utf-8'))
        except Exception as e:
            return {"error": str(e)}


if __name__ == "__main__":
    print("Testing MQTT Client...")
    client = MQTTClient("test.mosquitto.org", 1883)

    if client.connect():
        print("OK: connected")
        if client.publish("inevionet/test", "Hello MQTT!", qos=1):
            print("OK: published")
        def handler(topic, msg):
            print(f"MSG {topic}: {msg}")
        client.subscribe("inevionet/test", handler=handler)
        print("OK: subscribed")
        import time
        time.sleep(2)
        client.disconnect()
        print("OK: disconnected")
    else:
        print("FAIL: connection error")

    print("MQTT OK")