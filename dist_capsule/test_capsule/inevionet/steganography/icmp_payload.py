"""ICMP Payload Steganography."""
import struct
import time
from typing import Optional, List
from dataclasses import dataclass

from ..core.logger import get_logger
from ..core.exceptions import SteganographyError
from ..network.icmp import ICMPClient

logger = get_logger("inevionet.steganography.icmp_payload")


@dataclass
class ICMPStealthResult:
    success: bool
    host: str = ""
    bytes_sent: int = 0
    rtt_ms: float = 0.0
    fallback: bool = False
    error: Optional[str] = None

    def __repr__(self):
        status = "OK" if self.success else "FAIL"
        return f"[{status}] ICMP Stealth ({self.bytes_sent}B, {self.rtt_ms:.1f}ms)"


class ICMPPayloadTunnel:
    """ICMP Payload Tunneling."""
    MAX_PAYLOAD = 1400

    def __init__(self):
        self.client = ICMPClient()

    def send(self, data: bytes, host: str = "8.8.8.8") -> ICMPStealthResult:
        """Отправить данные через ICMP payload."""
        if len(data) > self.MAX_PAYLOAD:
            data = data[:self.MAX_PAYLOAD]
            logger.warning(f"Truncated to {self.MAX_PAYLOAD} bytes")
        try:
            if self.client.has_raw:
                result = self.client.ping(host, timeout=5.0, payload=data)
                if result:
                    return ICMPStealthResult(success=True, host=host,
                                             bytes_sent=len(data),
                                             rtt_ms=result.rtt_ms,
                                             fallback=result.fallback)
                return ICMPStealthResult(success=False, host=host, error="No response")
            else:
                result = self.client.ping(host, timeout=5.0)
                if result:
                    return ICMPStealthResult(success=True, host=host,
                                             bytes_sent=0,
                                             rtt_ms=result.rtt_ms,
                                             fallback=True)
                return ICMPStealthResult(success=False, host=host, error="Fallback failed")
        except Exception as e:
            return ICMPStealthResult(success=False, host=host, error=str(e))

    def send_chunked(self, data: bytes, host: str = "8.8.8.8",
                     chunk_size: int = 1000, delay: float = 0.1) -> List[ICMPStealthResult]:
        """Отправить данные чанками."""
        chunks = [data[i:i+chunk_size] for i in range(0, len(data), chunk_size)]
        results = []
        for i, chunk in enumerate(chunks):
            result = self.send(chunk, host)
            results.append(result)
            if delay > 0 and i < len(chunks) - 1:
                time.sleep(delay)
        return results

    @property
    def has_raw(self):
        return self.client.has_raw

    def close(self):
        self.client.close()

    def __repr__(self):
        return f"ICMPPayloadTunnel(raw={self.has_raw})"


if __name__ == "__main__":
    print("Testing ICMP Payload Tunnel...")
    tunnel = ICMPPayloadTunnel()
    print(f"Raw socket: {tunnel.has_raw}")
    data = b"InevioNet ICMP test!"
    result = tunnel.send(data, "8.8.8.8")
    print(result)
    tunnel.close()
    print("ICMP Payload module OK")
