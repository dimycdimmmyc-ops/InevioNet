"""InevioNet Steganography Engine - главный движок."""
import time
import random
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field
from enum import Enum

from ..core.logger import get_logger
from ..core.exceptions import SteganographyError, PayloadTooLargeError

from .dns_tunnel import DNSTunnel
from .http_headers import HTTPHeadersTunnel
from .icmp_payload import ICMPPayloadTunnel
from .timing import TimingChannel

logger = get_logger("inevionet.steganography.engine")


class StealthMethod(str, Enum):
    DNS_QNAME = "DNS_QNAME"
    DNS_TXT = "DNS_TXT"
    HTTP_HEADERS = "HTTP_HEADERS"
    HTTP_COOKIE = "HTTP_COOKIE"
    HTTP_USER_AGENT = "HTTP_USER_AGENT"
    ICMP_PAYLOAD = "ICMP_PAYLOAD"
    TIMING = "TIMING"


@dataclass
class StealthResult:
    success: bool
    method: str
    bytes_sent: int = 0
    bytes_received: int = 0
    duration_ms: float = 0.0
    encoded_size: int = 0
    response: Optional[bytes] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def overhead(self) -> float:
        if self.bytes_sent == 0:
            return 0.0
        return ((self.encoded_size - self.bytes_sent) / self.bytes_sent) * 100

    def __repr__(self):
        status = "OK" if self.success else "FAIL"
        return (f"[{status}] StealthResult({self.method}, {self.bytes_sent}B, "
                f"overhead={self.overhead:.1f}%, {self.duration_ms:.1f}ms)")


class SteganographyEngine:
    """Универсальный движок стеганографии."""

    def __init__(self, dns_server="8.8.8.8", timeout=10.0):
        self.dns_server = dns_server
        self.timeout = timeout
        self._dns = None
        self._http = None
        self._icmp = None
        self._timing = None
        self._stats = {}

    def _get_dns(self):
        if self._dns is None:
            self._dns = DNSTunnel(server=self.dns_server, timeout=self.timeout)
        return self._dns

    def _get_http(self):
        if self._http is None:
            self._http = HTTPHeadersTunnel(timeout=self.timeout)
        return self._http

    def _get_icmp(self):
        if self._icmp is None:
            self._icmp = ICMPPayloadTunnel()
        return self._icmp

    def _get_timing(self):
        if self._timing is None:
            self._timing = TimingChannel()
        return self._timing

    def send(self, data: bytes, method="HTTP_HEADERS", target="", **kwargs):
        method = method.upper()
        start = time.time()
        try:
            if method == "DNS_QNAME":
                return self._send_dns_qname(data, target or "example.com", start)
            elif method == "DNS_TXT":
                return self._send_dns_txt(data, target or "example.com", start)
            elif method == "HTTP_HEADERS":
                return self._send_http_headers(data, target or "http://httpbin.org/get", start)
            elif method == "HTTP_COOKIE":
                return self._send_http_cookie(data, target or "http://httpbin.org/get", start)
            elif method == "HTTP_USER_AGENT":
                return self._send_http_user_agent(data, target or "http://httpbin.org/get", start)
            elif method == "ICMP_PAYLOAD":
                return self._send_icmp(data, target or "8.8.8.8", start)
            elif method == "TIMING":
                return self._send_timing(data, target, start)
            else:
                return StealthResult(success=False, method=method,
                                     error=f"Unknown method: {method}")
        except Exception as e:
            logger.error(f"Steganography error {method}: {e}")
            return StealthResult(success=False, method=method, error=str(e),
                                 duration_ms=(time.time() - start) * 1000)

    def _send_dns_qname(self, data, domain, start):
        results = self._get_dns().send_qname(data, domain)
        success = all(results) if results else False
        return StealthResult(success=success, method="DNS_QNAME",
                             bytes_sent=len(data),
                             encoded_size=sum(len(c) for c in self._get_dns().encode_qname(data)),
                             duration_ms=(time.time() - start) * 1000,
                             metadata={"chunks": len(results),
                                       "successful_chunks": sum(results),
                                       "domain": domain})

    def _send_dns_txt(self, data, domain, start):
        success = self._get_dns().send_txt(data, domain)
        return StealthResult(success=success, method="DNS_TXT",
                             bytes_sent=len(data),
                             duration_ms=(time.time() - start) * 1000,
                             metadata={"domain": domain})

    def _send_http_headers(self, data, url, start):
        result = self._get_http().send(data, url)
        return StealthResult(success=result.success, method="HTTP_HEADERS",
                             bytes_sent=len(data), encoded_size=len(data) * 2,
                             duration_ms=(time.time() - start) * 1000,
                             metadata={"url": url})

    def _send_http_cookie(self, data, url, start):
        success = self._get_http().send_in_cookie(data, url)
        return StealthResult(success=success, method="HTTP_COOKIE",
                             bytes_sent=len(data),
                             duration_ms=(time.time() - start) * 1000)

    def _send_http_user_agent(self, data, url, start):
        success = self._get_http().send_in_user_agent(data, url)
        return StealthResult(success=success, method="HTTP_USER_AGENT",
                             bytes_sent=len(data),
                             duration_ms=(time.time() - start) * 1000)

    def _send_icmp(self, data, host, start):
        result = self._get_icmp().send(data, host)
        return StealthResult(success=result.success, method="ICMP_PAYLOAD",
                             bytes_sent=result.bytes_sent,
                             duration_ms=(time.time() - start) * 1000,
                             metadata={"rtt_ms": result.rtt_ms, "fallback": result.fallback})

    def _send_timing(self, data, target, start):
        intervals = self._get_timing().encode_bytes_to_intervals(data)
        return StealthResult(success=True, method="TIMING",
                             bytes_sent=len(data),
                             duration_ms=(time.time() - start) * 1000,
                             metadata={"intervals": len(intervals),
                                       "total_time": sum(intervals)})

    def send_auto(self, data, target="", priorities=None):
        priorities = priorities or ["HTTP_HEADERS", "DNS_QNAME", "ICMP_PAYLOAD"]
        last_error = None
        for method in priorities:
            result = self.send(data, method, target)
            if result.success:
                return result
            last_error = result.error
        return StealthResult(success=False, method="AUTO",
                             error=f"All methods failed. Last error: {last_error}")

    def send_parallel(self, data, methods):
        import concurrent.futures
        results = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=len(methods)) as ex:
            futures = {ex.submit(self.send, data, m, t): (m, t) for m, t in methods}
            for f in concurrent.futures.as_completed(futures):
                try:
                    results.append(f.result(timeout=self.timeout * 2))
                except Exception as e:
                    m, t = futures[f]
                    results.append(StealthResult(success=False, method=m, error=str(e)))
        return results

    def get_stats(self):
        return dict(self._stats)

    def close(self):
        if self._http:
            self._http.close()
        if self._icmp:
            self._icmp.close()
        self._dns = None
        self._http = None
        self._icmp = None
        self._timing = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


if __name__ == "__main__":
    print("Testing SteganographyEngine...")
    engine = SteganographyEngine()
    data = b"Hello, InevioNet!"
    print("\n1. DNS QNAME round-trip:")
    dns = engine._get_dns()
    chunks = dns.encode_qname(data)
    decoded = dns.decode_qname(chunks)
    assert decoded == data
    print(f"   OK: {len(data)} bytes -> {len(chunks)} chunks -> {len(decoded)} bytes")
    print("\n2. HTTP Headers round-trip:")
    http = engine._get_http()
    headers, n = http.encode(data)
    decoded = http.decode(headers)
    assert decoded == data
    print(f"   OK: {len(data)} bytes -> {n} headers -> {len(decoded)} bytes")
    print("\n3. Timing round-trip:")
    timing = engine._get_timing()
    intervals = timing.encode_bytes_to_intervals(data)
    decoded = timing.decode_intervals_to_bytes(intervals)
    assert decoded == data
    print(f"   OK: {len(data)} bytes -> {len(intervals)} intervals -> {len(decoded)} bytes")
    engine.close()
    print("\nALL STEGANOGRAPHY TESTS PASSED")
