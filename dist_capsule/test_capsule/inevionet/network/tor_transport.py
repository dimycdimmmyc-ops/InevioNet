"""P13: Tor transport - SOCKS5 proxy routing."""
import socket
import struct
import time
from typing import Optional, Tuple
from ..core.logger import get_logger

logger = get_logger("inevionet.network.tor_transport")


class TorTransport:
    """P13: РњР°СЂС€СЂСѓС‚РёР·Р°С†РёСЏ С‡РµСЂРµР· Tor SOCKS5 (127.0.0.1:9050)."""

    DEFAULT_HOST = "127.0.0.1"
    DEFAULT_PORT = 9050
    DEFAULT_TIMEOUT = 30.0

    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT,
                 timeout=DEFAULT_TIMEOUT):
        self.host = host
        self.port = port
        self.timeout = timeout
        self._available = None

    def is_available(self) -> bool:
        """РџСЂРѕРІРµСЂРёС‚СЊ РґРѕСЃС‚СѓРїРµРЅ Р»Рё Tor SOCKS5."""
        if self._available is not None:
            return self._available
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(2.0)
            s.connect((self.host, self.port))
            s.close()
            self._available = True
            logger.info("[Tor] SOCKS5 available at %s:%d", self.host, self.port)
        except Exception as e:
            self._available = False
            logger.debug("[Tor] SOCKS5 unavailable: %s", e)
        return self._available

    def _socks5_handshake(self, sock, target_host, target_port):
        """SOCKS5 handshake + CONNECT request."""
        # 1. Greeting: version 5, 1 method (no auth)
        sock.sendall(b"\x05\x01\x00")
        resp = sock.recv(2)
        if len(resp) != 2 or resp[0] != 0x05 or resp[1] != 0x00:
            raise Exception("SOCKS5 greeting failed")

        # 2. CONNECT request
        # Format: VER CMD RSV ATYP DST.ADDR DST.PORT
        try:
            # Try as domain name
            host_bytes = target_host.encode("ascii")
            if len(host_bytes) > 255:
                raise ValueError("host too long")
            req = (b"\x05\x01\x00\x03" +
                   bytes([len(host_bytes)]) +
                   host_bytes +
                   struct.pack(">H", target_port))
        except (UnicodeEncodeError, ValueError):
            # Fallback to IP
            ip_bytes = socket.inet_aton(target_host)
            req = (b"\x05\x01\x00\x01" + ip_bytes +
                   struct.pack(">H", target_port))

        sock.sendall(req)
        resp = sock.recv(10)
        if len(resp) < 2 or resp[0] != 0x05 or resp[1] != 0x00:
            raise Exception(f"SOCKS5 CONNECT failed: {resp.hex()}")
        return True

    def connect(self, target_host, target_port):
        """РћС‚РєСЂС‹С‚СЊ TCP-СЃРѕРµРґРёРЅРµРЅРёРµ С‡РµСЂРµР· Tor."""
        if not self.is_available():
            return None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self.timeout)
            sock.connect((self.host, self.port))
            self._socks5_handshake(sock, target_host, target_port)
            return sock
        except Exception as e:
            logger.debug("[Tor] connect error: %s", e)
            return None

    def send(self, data: bytes, target_host: str, target_port: int):
        """РћС‚РїСЂР°РІРёС‚СЊ РґР°РЅРЅС‹Рµ С‡РµСЂРµР· Tor. Returns (success, response)."""
        sock = self.connect(target_host, target_port)
        if not sock:
            return False, None
        try:
            sock.sendall(data)
            time.sleep(0.3)
            sock.settimeout(5.0)
            try:
                response = sock.recv(4096)
            except socket.timeout:
                response = b""
            return True, response
        except Exception as e:
            logger.debug("[Tor] send error: %s", e)
            return False, None
        finally:
            try:
                sock.close()
            except Exception:
                pass

    def get_stats(self):
        return {
            "available": self.is_available(),
            "host": self.host,
            "port": self.port,
            "timeout": self.timeout,
        }

    def __repr__(self):
        status = "OK" if self._available else "OFF"
        return f"TorTransport([{status}] {self.host}:{self.port})"


if __name__ == "__main__":
    print("Testing TorTransport...")
    t = TorTransport()
    print(f"Available: {t.is_available()}")
    if t.is_available():
        ok, resp = t.send(b"GET / HTTP/1.0\r\nHost: check.torproject.org\r\n\r\n",
                          "check.torproject.org", 80)
        print(f"Send: {ok}, Response: {len(resp) if resp else 0} bytes")
    print("TorTransport OK")