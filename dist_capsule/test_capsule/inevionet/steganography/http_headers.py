"""HTTP Headers Steganography - data in HTTP headers."""
import base64
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from ..core.logger import get_logger
from ..core.exceptions import SteganographyError
from ..network.http import HTTPClient

logger = get_logger("inevionet.steganography.http_headers")


HEADER_PREFIX = "X-InevioNet"


@dataclass
class HTTPStealthResult:
    success: bool
    url: str = ""
    chunks_sent: int = 0
    bytes_sent: int = 0
    duration_ms: float = 0.0
    response: Optional[bytes] = None
    error: Optional[str] = None

    def __repr__(self):
        status = "OK" if self.success else "FAIL"
        return f"[{status}] HTTP Stealth ({self.chunks_sent} chunks, {self.bytes_sent}B)"


class HTTPHeadersTunnel:
    """HTTP Headers Tunneling."""
    MAX_CHUNK = 3500
    DEFAULT_URLS = [
        "http://httpbin.org/get",
        "https://postman-echo.com/get",
        "https://httpbingo.org/get",
    ]

    def __init__(self, timeout=10.0):
        self.timeout = timeout
        self.client = HTTPClient(timeout=timeout)

    def encode(self, data: bytes) -> Tuple[Dict[str, str], int]:
        """Закодировать данные в заголовки."""
        encoded = base64.urlsafe_b64encode(data).decode("ascii")
        chunks = [encoded[i:i+self.MAX_CHUNK] for i in range(0, len(encoded), self.MAX_CHUNK)]
        headers = {
            f"{HEADER_PREFIX}-Chunks": str(len(chunks)),
            f"{HEADER_PREFIX}-Total-Size": str(len(data)),
            f"{HEADER_PREFIX}-Hash": self._hash(data),
            f"{HEADER_PREFIX}-Timestamp": str(int(time.time())),
        }
        for i, chunk in enumerate(chunks):
            headers[f"{HEADER_PREFIX}-Data-{i:04d}"] = chunk
        return headers, len(chunks)

    def decode(self, headers: Dict[str, str]) -> Optional[bytes]:
        """Восстановить данные из заголовков."""
        chunks_count = None
        for k, v in headers.items():
            if k.lower() == f"{HEADER_PREFIX}-chunks".lower():
                try:
                    chunks_count = int(v)
                except ValueError:
                    return None
                break
        if chunks_count is None:
            return None
        encoded = ""
        for i in range(chunks_count):
            key = f"{HEADER_PREFIX}-Data-{i:04d}".lower()
            found = False
            for k, v in headers.items():
                if k.lower() == key:
                    encoded += v
                    found = True
                    break
            if not found:
                return None
        try:
            return base64.urlsafe_b64decode(encoded.encode("ascii"))
        except Exception:
            return None

    def send(self, data: bytes, url: str = None, method="GET") -> HTTPStealthResult:
        """Отправить данные через HTTP-заголовки."""
        start = time.time()
        url = url or self.DEFAULT_URLS[0]
        try:
            headers, chunks = self.encode(data)
            response = self.client.request(method, url, headers=headers)
            duration = (time.time() - start) * 1000
            if response and 200 <= response.status < 300:
                return HTTPStealthResult(success=True, url=url, chunks_sent=chunks,
                                         bytes_sent=len(data), duration_ms=duration,
                                         response=response.body)
            return HTTPStealthResult(success=False, url=url,
                                     error=f"HTTP {response.status if response else 'None'}")
        except Exception as e:
            return HTTPStealthResult(success=False, url=url, error=str(e))

    def send_in_cookie(self, data: bytes, url: str = None) -> bool:
        """Отправить данные в Cookie."""
        url = url or self.DEFAULT_URLS[0]
        encoded = base64.urlsafe_b64encode(data).decode("ascii")
        headers = {"Cookie": f"inevionet_data={encoded}"}
        response = self.client.request("GET", url, headers=headers)
        return response is not None and 200 <= response.status < 300

    def send_in_user_agent(self, data: bytes, url: str = None) -> bool:
        """Отправить данные в User-Agent."""
        url = url or self.DEFAULT_URLS[0]
        encoded = base64.urlsafe_b64encode(data).decode("ascii")
        if len(encoded) > 4000:
            encoded = encoded[:4000]
        headers = {"User-Agent": f"Mozilla/5.0 (InevioNet; {encoded})"}
        response = self.client.request("GET", url, headers=headers)
        return response is not None and 200 <= response.status < 300

    def send_with_fallback(self, data: bytes, method="headers",
                           urls: List[str] = None) -> Tuple[bool, Optional[str]]:
        """Отправить через несколько URL."""
        urls = urls or self.DEFAULT_URLS
        for url in urls:
            try:
                if method == "headers":
                    result = self.send(data, url)
                    if result.success:
                        return True, url
                elif method == "cookie":
                    if self.send_in_cookie(data, url):
                        return True, url
                elif method == "user-agent":
                    if self.send_in_user_agent(data, url):
                        return True, url
            except Exception:
                continue
        return False, None

    @staticmethod
    def _hash(data: bytes) -> str:
        import hashlib
        return hashlib.sha256(data).hexdigest()[:16]

    def close(self):
        self.client.close()

    def __repr__(self):
        return f"HTTPHeadersTunnel(timeout={self.timeout})"


if __name__ == "__main__":
    print("Testing HTTP Headers Tunnel...")
    tunnel = HTTPHeadersTunnel()
    data = b"Hello, InevioNet via HTTP!"
    headers, chunks = tunnel.encode(data)
    print(f"Encoded into {chunks} chunks, {len(headers)} headers")
    decoded = tunnel.decode(headers)
    assert decoded == data, "Decode failed!"
    print(f"OK: round-trip works ({len(decoded)} bytes)")
    print("Testing actual send...")
    result = tunnel.send(data)
    print(result)
    tunnel.close()
    print("HTTP Headers module OK")
