"""P13: I2P transport via SAM Bridge (127.0.0.1:7656)."""
import socket
import struct
import time
import threading
from typing import Optional, Tuple
from ..core.logger import get_logger

logger = get_logger("inevionet.network.i2p_transport")


class I2PTransport:
    """P13: РњР°СЂС€СЂСѓС‚РёР·Р°С†РёСЏ С‡РµСЂРµР· I2P SAM bridge.

    SAM (Simple Anonymous Messaging) - TCP РїСЂРѕС‚РѕРєРѕР» РЅР° 127.0.0.1:7656.
    I2P router РµРіРѕ РѕС‚РєСЂС‹РІР°РµС‚ Р°РІС‚РѕРјР°С‚РёС‡РµСЃРєРё РїСЂРё Р·Р°РїСѓСЃРєРµ.
    """

    DEFAULT_HOST = "127.0.0.1"
    DEFAULT_PORT = 7656
    DEFAULT_TIMEOUT = 30.0

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT,
                 timeout=DEFAULT_TIMEOUT, session_name="inevionet"):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.session_name = session_name
        self._available = None
        self._session_id = None

    def is_available(self) -> bool:
        """РџСЂРѕРІРµСЂРёС‚СЊ, Р·Р°РїСѓС‰РµРЅ Р»Рё I2P router СЃ SAM bridge."""
        if self._available is not None:
            return self._available
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(3.0)
            s.connect((self.host, self.port))
            # РћС‚РїСЂР°РІР»СЏРµРј SAM HELLO
            s.sendall(b"HELLO VERSION MIN=3.0 MAX=3.3\n")
            resp = s.recv(4096).decode("utf-8", errors="replace")
            s.close()
            if "HELLO REPLY RESULT=OK" in resp:
                self._available = True
                logger.info("[I2P] SAM available at %s:%d", self.host, self.port)
            else:
                self._available = False
                logger.debug("[I2P] SAM HELLO failed: %s", resp[:100])
        except Exception as e:
            self._available = False
            logger.debug("[I2P] SAM unavailable: %s", e)
        return self._available

    def _create_session(self):
        """РЎРѕР·РґР°С‚СЊ SAM STREAM session."""
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(self.timeout)
        s.connect((self.host, self.port))

        # HELLO
        s.sendall(b"HELLO VERSION MIN=3.0 MAX=3.3\n")
        resp = s.recv(4096).decode("utf-8", errors="replace")
        if "HELLO REPLY RESULT=OK" not in resp:
            raise Exception("SAM HELLO failed: " + resp[:100])

        # SESSION CREATE
        cmd = ("SESSION CREATE STYLE=STREAM ID=" + self.session_name +
               " DESTINATION=TRANSIENT\n")
        s.sendall(cmd.encode("utf-8"))
        resp = s.recv(4096).decode("utf-8", errors="replace")
        if "SESSION STATUS RESULT=OK" not in resp:
            raise Exception("SESSION CREATE failed: " + resp[:200])

        logger.info("[I2P] Session created: %s", self.session_name)
        return s

    def send(self, data: bytes, target_host: str, target_port: int = 80):
        """РћС‚РїСЂР°РІРёС‚СЊ РґР°РЅРЅС‹Рµ С‡РµСЂРµР· I2P.

        target_host РґРѕР»Р¶РµРЅ Р±С‹С‚СЊ .i2p Р°РґСЂРµСЃРѕРј РёР»Рё base64 destination.
        """
        if not self.is_available():
            return False, None
        try:
            s = self._create_session()

            # STREAM CONNECT
            cmd = ("STREAM CONNECT ID=" + self.session_name +
                   " DESTINATION=" + target_host +
                   " SILENT=false\n")
            s.sendall(cmd.encode("utf-8"))

            # Р–РґС‘Рј STREAM STATUS
            time.sleep(0.5)
            s.settimeout(10.0)
            try:
                resp = s.recv(4096).decode("utf-8", errors="replace")
                if "STREAM STATUS RESULT=OK" not in resp:
                    logger.debug("[I2P] STREAM CONNECT failed: %s", resp[:200])
                    s.close()
                    return False, None
            except socket.timeout:
                pass

            # РћС‚РїСЂР°РІР»СЏРµРј РґР°РЅРЅС‹Рµ
            s.sendall(data)
            time.sleep(0.3)

            # РџРѕР»СѓС‡Р°РµРј РѕС‚РІРµС‚
            s.settimeout(5.0)
            try:
                response = s.recv(8192)
            except socket.timeout:
                response = b""

            s.close()
            return True, response

        except Exception as e:
            logger.debug("[I2P] send error: %s", e)
            return False, None

    def get_stats(self):
        return {
            "available": self.is_available(),
            "host": self.host,
            "port": self.port,
            "session": self.session_name,
        }

    def __repr__(self):
        status = "OK" if self._available else "OFF"
        return "I2PTransport([" + status + "] " + self.host + ":" + str(self.port) + ")"


if __name__ == "__main__":
    print("Testing I2PTransport...")
    t = I2PTransport()
    print("Available:", t.is_available())
    if t.is_available():
        print("Sending test to i2p-projekt.i2p...")
        ok, resp = t.send(b"GET / HTTP/1.0\r\n\r\n", "i2p-projekt.i2p", 80)
        print("Send:", ok, "Response:", len(resp) if resp else 0)
    print("I2PTransport OK")