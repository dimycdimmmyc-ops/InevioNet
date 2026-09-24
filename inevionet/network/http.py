"""InevioNet HTTP - real HTTP/HTTPS with steganography."""
import http.client
import ssl
import base64
import time
import json
from typing import Optional, Dict, Any, Tuple, List
from urllib.parse import urlparse
from dataclasses import dataclass, field

from ..core.logger import get_logger

logger = get_logger("inevionet.network.http")


DEFAULT_FALLBACK_URLS = [
    "http://httpbin.org/get",
    "https://postman-echo.com/get",
    "http://eu.httpbin.org/get",
    "https://httpbingo.org/get",
]

HEADER_PREFIX = "X-InevioNet"


@dataclass
class HTTPResponse:
    status: int
    reason: str
    headers: Dict[str, str]
    body: bytes
    url: str = ""
    method: str = "GET"

    @property
    def is_success(self):
        return 200 <= self.status < 300

    @property
    def text(self):
        try:
            return self.body.decode("utf-8")
        except UnicodeDecodeError:
            return self.body.decode("latin-1", errors="ignore")

    @property
    def json(self):
        try:
            return json.loads(self.text)
        except (json.JSONDecodeError, ValueError):
            return None

    def get_header(self, name, default=""):
        name_lower = name.lower()
        for k, v in self.headers.items():
            if k.lower() == name_lower:
                return v
        return default

    def extract_inevionet_data(self):
        chunks_count_str = self.get_header(f"{HEADER_PREFIX}-Chunks")
        if not chunks_count_str:
            single = self.get_header(f"{HEADER_PREFIX}-Data")
            if single:
                try:
                    return base64.urlsafe_b64decode(single.encode("ascii"))
                except Exception:
                    return None
            return None
        try:
            chunks_count = int(chunks_count_str)
        except ValueError:
            return None
        encoded = ""
        for i in range(chunks_count):
            chunk = self.get_header(f"{HEADER_PREFIX}-Data-{i:04d}")
            if not chunk:
                return None
            encoded += chunk
        try:
            return base64.urlsafe_b64decode(encoded.encode("ascii"))
        except Exception:
            return None


class HTTPClient:
    def __init__(self, timeout=10.0, verify_ssl=False, user_agent="Mozilla/5.0 (InevioNet)",
                 follow_redirects=True, max_redirects=5):
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.user_agent = user_agent
        self.follow_redirects = follow_redirects
        self.max_redirects = max_redirects

    def _get_connection(self, parsed_url):
        host = parsed_url.hostname
        port = parsed_url.port
        is_https = parsed_url.scheme == "https"
        if is_https:
            ctx = ssl.create_default_context()
            if not self.verify_ssl:
                ctx.check_hostname = False
                ctx.verify_mode = ssl.CERT_NONE
            return http.client.HTTPSConnection(host, port=port or 443, timeout=self.timeout, context=ctx)
        return http.client.HTTPConnection(host, port=port or 80, timeout=self.timeout)

    def request(self, method, url, body=None, headers=None):
        headers = dict(headers or {})
        headers.setdefault("User-Agent", self.user_agent)
        headers.setdefault("Accept", "*/*")
        headers.setdefault("Connection", "close")
        try:
            parsed = urlparse(url)
            if not parsed.hostname:
                raise ValueError(f"Invalid URL: {url}")
            path = parsed.path or "/"
            if parsed.query:
                path += "?" + parsed.query
            conn = self._get_connection(parsed)
            conn.request(method, path, body=body, headers=headers)
            response = conn.getresponse()
            data = response.read()
            result = HTTPResponse(status=response.status, reason=response.reason,
                                  headers=dict(response.getheaders()), body=data,
                                  url=url, method=method)
            conn.close()
            if self.follow_redirects and 300 <= response.status < 400:
                location = result.get_header("Location")
                if location and self.max_redirects > 0:
                    if location.startswith("/"):
                        location = f"{parsed.scheme}://{parsed.netloc}{location}"
                    old = self.max_redirects
                    self.max_redirects -= 1
                    redirect_result = self.request(method, location, body, headers)
                    self.max_redirects = old
                    return redirect_result
            return result
        except (http.client.HTTPException, OSError, ssl.SSLError) as e:
            logger.error(f"HTTP error {url}: {e}")
            return None

    def get(self, url, headers=None):
        return self.request("GET", url, headers=headers)

    def post(self, url, body=b"", headers=None):
        return self.request("POST", url, body=body, headers=headers)

    def head(self, url):
        return self.request("HEAD", url)

    def send_data_in_headers(self, data, url="http://httpbin.org/get", method="GET"):
        if not data:
            return False
        encoded = base64.urlsafe_b64encode(data).decode("ascii")
        chunk_size = 3500
        chunks = [encoded[i:i+chunk_size] for i in range(0, len(encoded), chunk_size)]
        headers = {
            f"{HEADER_PREFIX}-Chunks": str(len(chunks)),
            f"{HEADER_PREFIX}-Total-Size": str(len(data)),
            f"{HEADER_PREFIX}-Hash": self._hash_short(data),
            f"{HEADER_PREFIX}-Timestamp": str(int(time.time())),
        }
        for i, chunk in enumerate(chunks):
            headers[f"{HEADER_PREFIX}-Data-{i:04d}"] = chunk
        try:
            response = self.request(method, url, headers=headers)
            if response and 200 <= response.status < 300:
                return True
            return False
        except Exception as e:
            logger.error(f"HTTP headers error: {e}")
            return False

    def send_data_in_cookie(self, data, url="http://httpbin.org/get"):
        encoded = base64.urlsafe_b64encode(data).decode("ascii")
        headers = {"Cookie": f"inevionet_data={encoded}"}
        try:
            response = self.request("GET", url, headers=headers)
            return response is not None and 200 <= response.status < 300
        except Exception as e:
            logger.error(f"HTTP cookie error: {e}")
            return False

    def send_data_in_user_agent(self, data, url="http://httpbin.org/get"):
        encoded = base64.urlsafe_b64encode(data).decode("ascii")
        if len(encoded) > 4000:
            encoded = encoded[:4000]
        headers = {"User-Agent": f"Mozilla/5.0 (InevioNet; {encoded})"}
        try:
            response = self.request("GET", url, headers=headers)
            return response is not None and 200 <= response.status < 300
        except Exception as e:
            logger.error(f"HTTP user-agent error: {e}")
            return False

    def send_with_fallback(self, data, method="headers", urls=None):
        urls = urls or DEFAULT_FALLBACK_URLS
        for url in urls:
            try:
                if method == "headers":
                    success = self.send_data_in_headers(data, url)
                elif method == "cookie":
                    success = self.send_data_in_cookie(data, url)
                elif method == "user-agent":
                    success = self.send_data_in_user_agent(data, url)
                else:
                    success = False
                if success:
                    return True, url
            except Exception:
                continue
        return False, None

    @staticmethod
    def _hash_short(data):
        import hashlib
        return hashlib.sha256(data).hexdigest()[:16]

    def close(self):
        pass


if __name__ == "__main__":
    print("Testing HTTP...")
    client = HTTPClient()
    response = client.get("http://httpbin.org/get")
    if response and response.is_success:
        print(f"Status: {response.status}")
        data = response.json
        if data:
            print(f"Origin: {data.get('origin', 'unknown')}")
    print("Testing steganography...")
    success = client.send_data_in_headers(b"Hello, InevioNet!")
    print(f"Headers send: {success}")
    print("HTTP module OK")
