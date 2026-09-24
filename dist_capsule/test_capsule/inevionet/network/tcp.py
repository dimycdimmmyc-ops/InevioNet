"""InevioNet TCP - real sockets, no simulation."""
import socket
import ssl
import time
import threading
from typing import Optional, Tuple, Callable, Dict, Any, List

from ..core.logger import get_logger

logger = get_logger("inevionet.network.tcp")


class TCPClient:
    def __init__(self, host, port, timeout=5.0, use_ssl=False, verify_ssl=True):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.use_ssl = use_ssl
        self.verify_ssl = verify_ssl
        self._socket = None
        self._connected = False
        self._bytes_sent = 0
        self._bytes_received = 0

    def connect(self):
        try:
            self._socket = socket.create_connection((self.host, self.port), timeout=self.timeout)
            if self.use_ssl:
                ctx = ssl.create_default_context()
                if not self.verify_ssl:
                    ctx.check_hostname = False
                    ctx.verify_mode = ssl.CERT_NONE
                self._socket = ctx.wrap_socket(self._socket, server_hostname=self.host)
            self._socket.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            self._connected = True
            logger.debug(f"TCP connected to {self.host}:{self.port}")
            return True
        except socket.timeout:
            logger.warning(f"TCP timeout: {self.host}:{self.port}")
            return False
        except (socket.gaierror, OSError) as e:
            logger.error(f"TCP connection failed: {e}")
            return False

    def send(self, data):
        if not self._connected or not self._socket:
            return False
        try:
            self._socket.sendall(data)
            self._bytes_sent += len(data)
            return True
        except socket.timeout:
            return False
        except OSError as e:
            logger.error(f"TCP send error: {e}")
            return False

    def recv(self, buffer_size=65536):
        if not self._connected or not self._socket:
            return None
        try:
            data = self._socket.recv(buffer_size)
            if not data:
                self._connected = False
                return None
            self._bytes_received += len(data)
            return data
        except socket.timeout:
            return b""
        except OSError:
            return None

    def recv_until(self, marker, max_size=1048576):
        if not self._connected or not self._socket:
            return None
        buf = b""
        try:
            while len(buf) < max_size:
                chunk = self._socket.recv(4096)
                if not chunk:
                    break
                buf += chunk
                if marker in buf:
                    break
            self._bytes_received += len(buf)
            return buf
        except Exception as e:
            logger.error(f"TCP recv_until error: {e}")
            return buf if buf else None

    def close(self):
        if self._socket:
            try:
                self._socket.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            try:
                self._socket.close()
            except OSError:
                pass
        self._socket = None
        self._connected = False

    @property
    def is_connected(self):
        return self._connected

    @property
    def bytes_sent(self):
        return self._bytes_sent

    @property
    def bytes_received(self):
        return self._bytes_received

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *args):
        self.close()

    def __repr__(self):
        return f"TCPClient({self.host}:{self.port}, connected={self._connected})"


class TCPServer:
    def __init__(self, host="0.0.0.0", port=0, on_data=None, on_connect=None,
                 on_disconnect=None, reuse_addr=True):
        self.host = host
        self.port = port
        self.on_data = on_data
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect
        self.reuse_addr = reuse_addr
        self._socket = None
        self._running = False
        self._threads = []
        self._clients = {}
        self._lock = threading.Lock()

    def start(self, blocking=True):
        try:
            family = socket.AF_INET6 if ":" in self.host else socket.AF_INET
            self._socket = socket.socket(family, socket.SOCK_STREAM)
            if self.reuse_addr:
                self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._socket.bind((self.host, self.port))
            self._socket.listen(128)
            self.port = self._socket.getsockname()[1]
            self._running = True
            logger.info(f"TCP server on {self.host}:{self.port}")
            if blocking:
                self._accept_loop()
            else:
                t = threading.Thread(target=self._accept_loop, daemon=True)
                t.start()
                self._threads.append(t)
        except OSError as e:
            logger.error(f"TCP server failed: {e}")
            raise

    def _accept_loop(self):
        while self._running and self._socket:
            try:
                client_sock, addr = self._socket.accept()
                with self._lock:
                    self._clients[addr] = client_sock
                if self.on_connect:
                    try:
                        self.on_connect(addr)
                    except Exception as e:
                        logger.error(f"on_connect error: {e}")
                t = threading.Thread(target=self._handle_client, args=(client_sock, addr), daemon=True)
                t.start()
                self._threads.append(t)
            except OSError:
                if self._running:
                    logger.error("TCP accept error")
                break

    def _handle_client(self, client_sock, addr):
        try:
            client_sock.settimeout(60)
            while self._running:
                try:
                    data = client_sock.recv(65536)
                    if not data:
                        break
                    if self.on_data:
                        try:
                            self.on_data(data, addr)
                        except Exception as e:
                            logger.error(f"on_data error: {e}")
                except socket.timeout:
                    continue
                except OSError:
                    break
        finally:
            try:
                client_sock.close()
            except OSError:
                pass
            with self._lock:
                self._clients.pop(addr, None)
            if self.on_disconnect:
                try:
                    self.on_disconnect(addr)
                except Exception:
                    pass

    def stop(self):
        self._running = False
        if self._socket:
            try:
                self._socket.close()
            except OSError:
                pass
        with self._lock:
            for c in self._clients.values():
                try:
                    c.close()
                except OSError:
                    pass
            self._clients.clear()

    def send_to(self, addr, data):
        with self._lock:
            c = self._clients.get(addr)
        if not c:
            return False
        try:
            c.sendall(data)
            return True
        except OSError:
            return False

    def broadcast(self, data):
        count = 0
        with self._lock:
            clients = list(self._clients.values())
        for c in clients:
            try:
                c.sendall(data)
                count += 1
            except OSError:
                pass
        return count

    @property
    def is_running(self):
        return self._running

    @property
    def client_count(self):
        with self._lock:
            return len(self._clients)

    def __enter__(self):
        self.start(blocking=False)
        return self

    def __exit__(self, *args):
        self.stop()


if __name__ == "__main__":
    print("Testing TCPClient...")
    c = TCPClient("example.com", 80, timeout=10)
    if c.connect():
        c.send(b"GET / HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\n\r\n")
        resp = c.recv_until(b"\r\n\r\n", max_size=4096)
        if resp:
            print(f"OK: received {len(resp)} bytes")
            print(f"First line: {resp.split(chr(13).encode()+chr(10).encode())[0].decode('utf-8', errors='ignore')}")
        c.close()
    else:
        print("Connection failed")
    print("TCP module OK")
