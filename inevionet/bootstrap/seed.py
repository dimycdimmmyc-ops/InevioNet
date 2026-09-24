"""InevioNet Seed - одноразовая точка входа."""
import os
import time
import json
import base64
import hashlib
import hmac
from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any

from ..core.logger import get_logger

logger = get_logger("inevionet.bootstrap.seed")

SEED_SECRET = "inevionet_seed_2026"
SEED_TAG = "inevionet_v1"


@dataclass
class Seed:
    node_id: str = ""
    public_ip: str = ""
    public_port: int = 0
    nat_type: str = "unknown"
    created_at: float = 0.0
    expires_at: float = 0.0
    ttl_sec: int = 3600
    label: str = ""
    nonce: str = ""
    signature: str = ""

    def __post_init__(self):
        if self.created_at == 0.0:
            self.created_at = time.time()
        if self.expires_at == 0.0:
            self.expires_at = self.created_at + self.ttl_sec
        if not self.nonce:
            self.nonce = base64.urlsafe_b64encode(os.urandom(8)).decode().rstrip("=")

    def is_expired(self) -> bool:
        return time.time() > self.expires_at

    def remaining_sec(self) -> float:
        return max(0.0, self.expires_at - time.time())

    def _sign_data(self) -> bytes:
        data = {
            "node_id": self.node_id,
            "public_ip": self.public_ip,
            "public_port": self.public_port,
            "created_at": int(self.created_at),
            "expires_at": int(self.expires_at),
            "nonce": self.nonce,
        }
        return json.dumps(data, sort_keys=True).encode("utf-8")

    def sign(self) -> str:
        mac = hmac.new(SEED_SECRET.encode(), self._sign_data(), hashlib.sha256).digest()
        self.signature = base64.urlsafe_b64encode(mac).decode().rstrip("=")
        return self.signature

    def verify(self) -> bool:
        if not self.signature:
            return False
        expected = hmac.new(SEED_SECRET.encode(), self._sign_data(), hashlib.sha256).digest()
        expected_s = base64.urlsafe_b64encode(expected).decode().rstrip("=")
        return hmac.compare_digest(self.signature, expected_s)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), sort_keys=True)

    def to_bytes(self) -> bytes:
        return self.to_json().encode("utf-8")

    def to_text(self) -> str:
        payload_b64 = base64.urlsafe_b64encode(self.to_bytes()).decode().rstrip("=")
        return SEED_TAG + ":" + payload_b64

    @classmethod
    def from_json(cls, s: str) -> "Seed":
        return cls(**json.loads(s))

    @classmethod
    def from_bytes(cls, data: bytes) -> "Seed":
        return cls.from_json(data.decode("utf-8"))

    @classmethod
    def from_text(cls, text: str) -> Optional["Seed"]:
        text = text.strip()
        if not text.startswith(SEED_TAG + ":"):
            return None
        payload_b64 = text[len(SEED_TAG) + 1:]
        padding = "=" * (-len(payload_b64) % 4)
        payload_b64 += padding
        try:
            data = base64.urlsafe_b64decode(payload_b64)
            return cls.from_bytes(data)
        except Exception as e:
            logger.debug("[Seed] parse error: %s", e)
            return None


class SeedPublisher:
    def __init__(self, timeout=10.0):
        self.timeout = timeout

    def publish(self, seed: Seed) -> Optional[str]:
        if not seed.signature:
            seed.sign()
        text = seed.to_text()
        for name, fn in [
            ("paste.rs", self._publish_pasters),
            ("sprunge.us", self._publish_sprunge),
            ("0x0.st", self._publish_0x0),
            ("termbin", self._publish_termbin),
            ("transfer.sh", self._publish_transfer),
            ("dpaste", self._publish_dpaste),
            ("ix.io", self._publish_ixio),
        ]:
            try:
                url = fn(text)
                if url:
                    logger.info("[Seed] published to %s: %s", name, url)
                    return url
            except Exception as e:
                logger.debug("[Seed] %s error: %s", name, e)
        return None

    def _publish_pasters(self, text: str) -> Optional[str]:
        """paste.rs - простой POST, возвращает URL в теле ответа."""
        import urllib.request
        req = urllib.request.Request(
            "https://paste.rs/",
            data=text.encode("utf-8"),
            headers={"Content-Type": "text/plain"},
            method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            if r.status in (200, 201):
                return r.read().decode().strip()
        return None

    def _publish_sprunge(self, text: str) -> Optional[str]:
        """sprunge.us - POST form."""
        import urllib.request
        import urllib.parse
        data = urllib.parse.urlencode({"sprunge": text}).encode()
        req = urllib.request.Request(
            "http://sprunge.us",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            if r.status == 200:
                return r.read().decode().strip()
        return None

    def _publish_0x0(self, text: str) -> Optional[str]:
        """0x0.st - POST multipart."""
        import urllib.request
        boundary = "----InevioNetBoundary"
        body = (
            "--" + boundary + "\r\n"
            "Content-Disposition: form-data; name=\"file\"; filename=\"seed.txt\"\r\n"
            "Content-Type: text/plain\r\n\r\n"
            + text + "\r\n"
            "--" + boundary + "--\r\n"
        ).encode("utf-8")
        req = urllib.request.Request(
            "https://0x0.st",
            data=body,
            headers={"Content-Type": "multipart/form-data; boundary=" + boundary},
            method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            if r.status == 200:
                return r.read().decode().strip()
        return None

    def _publish_termbin(self, text: str) -> Optional[str]:
        """termbin.com - TCP сокет на порт 9999."""
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(self.timeout)
            s.connect(("termbin.com", 9999))
            s.sendall(text.encode("utf-8"))
            s.shutdown(socket.SHUT_WR)
            data = b""
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                data += chunk
            s.close()
            result = data.decode("utf-8", errors="replace").strip()
            if result.startswith("http"):
                return result
            # termbin возвращает просто ID, дополняем
            if result and "/" not in result:
                return "https://termbin.com/" + result
            return result if result else None
        except Exception as e:
            import logging
            logging.debug("[Seed] termbin error: %s", e)
            return None

    def _publish_transfer(self, text: str) -> Optional[str]:
        import urllib.request
        filename = "seed_" + str(int(time.time())) + ".txt"
        url = "https://transfer.sh/" + filename
        req = urllib.request.Request(url, data=text.encode("utf-8"),
            headers={"Content-Type": "text/plain"}, method="PUT")
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            if r.status == 200:
                return r.read().decode().strip()
        return None

    def _publish_dpaste(self, text: str) -> Optional[str]:
        import urllib.request
        import urllib.parse
        data = urllib.parse.urlencode({
            "content": text, "format": "url", "expires": "3600",
        }).encode()
        req = urllib.request.Request("https://dpaste.com/api/v2/",
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            if r.status in (200, 201):
                return r.read().decode().strip()
        return None

    def _publish_ixio(self, text: str) -> Optional[str]:
        import urllib.request
        import urllib.parse
        req = urllib.request.Request("https://ix.io",
            data=("f:1=" + urllib.parse.quote(text)).encode(), method="POST")
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            if r.status == 200:
                return r.read().decode().strip()
        return None


class SeedFetcher:
    def __init__(self, timeout=10.0):
        self.timeout = timeout

    def fetch(self, url: str) -> Optional[Seed]:
        try:
            import urllib.request
            req = urllib.request.Request(url, headers={"User-Agent": "InevioNet/1.0"})
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                data = r.read().decode("utf-8", errors="replace")
            seed = Seed.from_text(data)
            if seed and seed.verify() and not seed.is_expired():
                logger.info("[Seed] fetched valid seed from %s", url)
                return seed
            return None
        except Exception as e:
            logger.debug("[Seed] fetch error: %s", e)
            return None

    def fetch_multi(self, urls: list) -> "Optional[Seed]":
        """P75a: попробовать несколько URL, вернуть первый валидный."""
        for url in urls:
            seed = self.fetch(url)
            if seed:
                return seed
        return None

    def guess_urls_from_text(self, text: str) -> list:
        """P75a: вытащить все URL из текста (для Telegram)."""
        import re
        urls = re.findall(r"https?://[^\s]+", text)
        return urls