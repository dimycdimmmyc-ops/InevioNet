"""DNS Tunnel - data in DNS QNAME and TXT records."""
import base64
import hashlib
import time
from typing import List, Optional, Tuple
from dataclasses import dataclass

from ..core.logger import get_logger
from ..core.exceptions import SteganographyError
from ..network.dns import DNSClient, DNSType

logger = get_logger("inevionet.steganography.dns_tunnel")


class DNSTunnel:
    """
    DNS Tunneling - передача данных через DNS.
    Методы:
    - QNAME: данные в поддоменах
    - TXT: данные в TXT-записях
    """
    MAX_QNAME_CHUNK = 20
    MAX_TXT_CHUNK = 200

    def __init__(self, server="8.8.8.8", timeout=10.0):
        self.server = server
        self.timeout = timeout
        self.client = DNSClient(server=server, timeout=timeout)

    def encode_qname(self, data: bytes, chunk_size=None) -> List[str]:
        """Разбить данные на base32-чанки для QNAME."""
        if not data:
            return []
        size = chunk_size or self.MAX_QNAME_CHUNK
        encoded_chunks = []
        for i in range(0, len(data), size):
            chunk = data[i:i+size]
            encoded = base64.b32encode(chunk).decode("ascii").rstrip("=").lower()
            encoded_chunks.append(encoded)
        return encoded_chunks

    def decode_qname(self, chunks: List[str]) -> bytes:
        """Восстановить данные из base32-чанков."""
        result = b""
        for chunk in chunks:
            padding = (8 - len(chunk) % 8) % 8
            padded = chunk.upper() + "=" * padding
            result += base64.b32decode(padded)
        return result

    def send_qname(self, data: bytes, domain: str, delay=0.05) -> List[bool]:
        """Отправить данные через QNAME."""
        chunks = self.encode_qname(data)
        results = []
        for i, chunk in enumerate(chunks):
            qname = f"{i:03d}-{chunk}.{domain}"
            response = self.client.query(qname, DNSType.A)
            results.append(response is not None)
            if delay > 0 and i < len(chunks) - 1:
                time.sleep(delay)
        logger.debug(f"DNS QNAME: sent {len(chunks)} chunks, {sum(results)} OK")
        return results

    def send_txt(self, data: bytes, domain: str) -> bool:
        """Отправить данные через TXT-поддомен."""
        if len(data) > self.MAX_TXT_CHUNK:
            raise SteganographyError(f"Payload {len(data)} > {self.MAX_TXT_CHUNK}")
        encoded = base64.b32encode(data).decode("ascii").rstrip("=").lower()
        qname = f"{encoded}.{domain}"
        response = self.client.query(qname, DNSType.TXT)
        return response is not None

    def receive_from_txt(self, domain: str) -> Optional[bytes]:
        """Получить данные из TXT-записи домена."""
        records = self.client.query_txt(domain)
        if not records:
            return None
        result = b""
        for txt in records:
            try:
                padding = (8 - len(txt) % 8) % 8
                padded = txt.upper() + "=" * padding
                result += base64.b32decode(padded)
            except Exception:
                continue
        return result if result else None

    def send_with_fallback(self, data: bytes, domains: List[str]) -> Tuple[bool, Optional[str]]:
        """Отправить через несколько доменов."""
        for domain in domains:
            try:
                results = self.send_qname(data, domain)
                if results and all(results):
                    return True, domain
            except Exception as e:
                logger.debug(f"DNS send to {domain} failed: {e}")
                continue
        return False, None

    def __repr__(self):
        return f"DNSTunnel(server={self.server})"


if __name__ == "__main__":
    print("Testing DNSTunnel...")
    tunnel = DNSTunnel()
    data = b"Hello, InevioNet!"
    chunks = tunnel.encode_qname(data)
    print(f"Encoded into {len(chunks)} chunks")
    decoded = tunnel.decode_qname(chunks)
    assert decoded == data, "Decode failed!"
    print(f"OK: round-trip works ({len(decoded)} bytes)")
    print("DNSTunnel module OK")
