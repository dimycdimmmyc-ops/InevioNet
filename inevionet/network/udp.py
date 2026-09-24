"""InevioNet UDP - real sockets, STUN, hole punching."""
import socket
import struct
import time
import threading
from typing import Optional, Tuple, Callable, List

from ..core.logger import get_logger

logger = get_logger("inevionet.network.udp")


STUN_SERVERS = [
    # === РАБОЧИЕ В РФ (проверено вручную) ===
    ("stun.cloudflare.com", 3478),      # ✅ работает
    ("stun.sipnet.ru", 3478),           # ✅ работает
    ("stun.voipbuster.com", 3478),      # ✅ работает
    # === ALTERNATIVES ===
    ("stun.ekiga.net", 3478),
    ("stun.ideasip.com", 3478),
    ("stun.voiparound.com", 3478),
    ("stun.voip.blackberry.com", 3478),
    ("stun.nextcloud.com", 443),
    # === GOOGLE (последними — блокируются в РФ) ===
    ("stun.l.google.com", 19302),
    ("stun1.l.google.com", 19302),
    ("stun2.l.google.com", 19302),
]

STUN_MAGIC_COOKIE = 0x2112A442


def stun_get_public_ip(local_port=0, timeout=5.0, stun_server=None):
    """STUN-запрос с перебором серверов.

    timeout — общий бюджет времени (не на каждый сервер).
    """
    servers = [stun_server] if stun_server else STUN_SERVERS
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        if local_port:
            sock.bind(("", local_port))

        transaction_id = struct.pack("!III", 0x2112A442, 0x12345678, 0x87654321)
        request = struct.pack("!HHI", 0x0001, 0x0000, STUN_MAGIC_COOKIE) + transaction_id

        per_server = min(1.5, timeout / max(1, len(servers)))
        deadline = time.time() + timeout

        for host, port in servers:
            if time.time() >= deadline:
                break
            try:
                sock.settimeout(per_server)
                sock.sendto(request, (host, port))
                response, addr = sock.recvfrom(2048)
                if len(response) < 20:
                    continue
                msg_type = struct.unpack("!H", response[0:2])[0]
                if msg_type != 0x0101:
                    continue
                pos = 20
                while pos < len(response):
                    attr_type, attr_len = struct.unpack("!HH", response[pos:pos+4])
                    attr_value = response[pos+4:pos+4+attr_len]
                    if attr_type == 0x0001:
                        family = attr_value[1]
                        port_v = struct.unpack("!H", attr_value[2:4])[0]
                        if family == 0x01:
                            ip = socket.inet_ntoa(attr_value[4:8])
                            return (ip, port_v)
                    elif attr_type == 0x0020:
                        family = attr_value[1]
                        xport = struct.unpack("!H", attr_value[2:4])[0] ^ (STUN_MAGIC_COOKIE >> 16)
                        if family == 0x01:
                            xip = struct.unpack("!I", attr_value[4:8])[0] ^ STUN_MAGIC_COOKIE
                            ip = socket.inet_ntoa(struct.pack("!I", xip))
                            return (ip, xport)
                    pos += 4 + attr_len
                    if attr_len % 4:
                        pos += 4 - (attr_len % 4)
            except socket.timeout:
                continue
            except OSError:
                continue
    finally:
        sock.close()
    return None


def stun_get_public_ip_via_socket(sock, timeout=5.0, servers=None):
    """STUN через УЖЕ ОТКРЫТЫЙ сокет.

    Возвращает публичный (ip, port) именно ЭТОГО сокета.
    Критично для hole-punching: нужен адрес того сокета,
    через который будем отправлять.
    """
    servers = servers or STUN_SERVERS
    transaction_id = struct.pack("!III", 0x2112A442, 0x12345678, 0x87654321)
    request = struct.pack("!HHI", 0x0001, 0x0000, STUN_MAGIC_COOKIE) + transaction_id
    per_server = min(1.5, timeout / max(1, len(servers)))
    deadline = time.time() + timeout
    try:
        old_timeout = sock.gettimeout()
    except OSError:
        old_timeout = None
    try:
        for host, port in servers:
            if time.time() >= deadline:
                break
            try:
                sock.settimeout(per_server)
                sock.sendto(request, (host, port))
                response, addr = sock.recvfrom(2048)
                if len(response) < 20:
                    continue
                msg_type = struct.unpack("!H", response[0:2])[0]
                if msg_type != 0x0101:
                    continue
                pos = 20
                while pos < len(response):
                    attr_type, attr_len = struct.unpack("!HH", response[pos:pos+4])
                    attr_value = response[pos+4:pos+4+attr_len]
                    if attr_type == 0x0001:
                        family = attr_value[1]
                        port_v = struct.unpack("!H", attr_value[2:4])[0]
                        if family == 0x01:
                            return (socket.inet_ntoa(attr_value[4:8]), port_v)
                    elif attr_type == 0x0020:
                        family = attr_value[1]
                        xport = struct.unpack("!H", attr_value[2:4])[0] ^ (STUN_MAGIC_COOKIE >> 16)
                        if family == 0x01:
                            xip = struct.unpack("!I", attr_value[4:8])[0] ^ STUN_MAGIC_COOKIE
                            return (socket.inet_ntoa(struct.pack("!I", xip)), xport)
                    pos += 4 + attr_len
                    if attr_len % 4:
                        pos += 4 - (attr_len % 4)
            except socket.timeout:
                continue
            except OSError:
                continue
    finally:
        try:
            if old_timeout is not None:
                sock.settimeout(old_timeout)
        except OSError:
            pass
    return None


class UDPClient:
    def __init__(self, local_host="0.0.0.0", local_port=0, timeout=5.0, broadcast=False):
        self.local_host = local_host
        self.local_port = local_port
        self.timeout = timeout
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self._socket.settimeout(timeout)
        if broadcast:
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        try:
            self._socket.bind((local_host, local_port))
            self.local_port = self._socket.getsockname()[1]
        except OSError as e:
            logger.error(f"UDP bind error: {e}")
            raise
        self._bytes_sent = 0
        self._bytes_received = 0

    def send_to(self, data, addr):
        try:
            sent = self._socket.sendto(data, addr)
            self._bytes_sent += sent
            return True
        except OSError as e:
            logger.error(f"UDP send error: {e}")
            return False

    def recv_from(self, buffer_size=65536):
        try:
            data, addr = self._socket.recvfrom(buffer_size)
            self._bytes_received += len(data)
            return data, addr
        except socket.timeout:
            return None, None
        except OSError as e:
            logger.error(f"UDP recv error: {e}")
            return None, None

    def request(self, data, addr, timeout=None):
        if timeout is not None:
            old = self._socket.gettimeout()
            self._socket.settimeout(timeout)
        try:
            if not self.send_to(data, addr):
                return None
            resp, _ = self.recv_from()
            return resp
        finally:
            if timeout is not None:
                self._socket.settimeout(old)

    def close(self):
        if self._socket:
            try:
                self._socket.close()
            except OSError:
                pass
        self._socket = None

    @property
    def local_addr(self):
        return self._socket.getsockname() if self._socket else None

    @property
    def bytes_sent(self):
        return self._bytes_sent

    @property
    def bytes_received(self):
        return self._bytes_received

    def get_public_addr(self):
        """STUN через НАШ сокет (тот же UDP-порт, что для punch'а)."""
        return stun_get_public_ip_via_socket(self._socket, timeout=self.timeout)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class UDPServer:
    def __init__(self, host="0.0.0.0", port=0, on_data=None, reuse_addr=True, broadcast=False):
        self.host = host
        self.port = port
        self.on_data = on_data
        self.reuse_addr = reuse_addr
        self.broadcast = broadcast
        self._socket = None
        self._running = False
        self._thread = None

    def start(self, blocking=True):
        self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        if self.reuse_addr:
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        if self.broadcast:
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        self._socket.bind((self.host, self.port))
        self.port = self._socket.getsockname()[1]
        self._running = True
        logger.info(f"UDP server on {self.host}:{self.port}")
        if blocking:
            self._recv_loop()
        else:
            self._thread = threading.Thread(target=self._recv_loop, daemon=True)
            self._thread.start()

    def _recv_loop(self):
        while self._running:
            try:
                data, addr = self._socket.recvfrom(65536)
                if self.on_data:
                    try:
                        self.on_data(data, addr)
                    except Exception as e:
                        logger.error(f"on_data error: {e}")
            except OSError:
                if self._running:
                    logger.error("UDP recv error")
                break

    def send_to(self, data, addr):
        if not self._socket:
            return False
        try:
            self._socket.sendto(data, addr)
            return True
        except OSError:
            return False

    def stop(self):
        self._running = False
        if self._socket:
            try:
                self._socket.close()
            except OSError:
                pass

    @property
    def is_running(self):
        return self._running

    def __enter__(self):
        self.start(blocking=False)
        return self

    def __exit__(self, *args):
        self.stop()


class UDPHolePuncher:
    def __init__(self, local_port=0):
        self.client = UDPClient(local_port=local_port)
        self.public_addr = None

    def discover_public(self):
        self.public_addr = self.client.get_public_addr()
        return self.public_addr

    def punch(self, peer_public, attempts=10, interval=0.5):
        if not peer_public:
            return False
        for i in range(attempts):
            self.client.send_to(b"INEVIONET_PUNCH", peer_public)
            response, addr = self.client.recv_from()
            if response and response.startswith(b"INEVIONET_PONG"):
                return True
            time.sleep(interval)
        return False

    def punch_bidirectional(self, peer_public, attempts=20, interval=0.25):
        """Двусторонний punch: мы шлём PUNCH и одновременно слушаем.

        Возвращает True, если peer ответил PONG (или сам прислал PUNCH).
        После успеха UDPClient остаётся открытым для обмена данными.
        """
        import threading as _th
        if not peer_public:
            return False
        stop = _th.Event()

        def sender():
            for _ in range(attempts):
                if stop.is_set():
                    break
                try:
                    self.client.send_to(b"INEVIONET_PUNCH", peer_public)
                except Exception:
                    pass
                time.sleep(interval)

        t = _th.Thread(target=sender, daemon=True, name="udp_punch_sender")
        t.start()

        deadline = time.time() + attempts * interval + 2.0
        try:
            while time.time() < deadline:
                try:
                    response, addr = self.client.recv_from()
                except Exception:
                    break
                if not response:
                    continue
                if response.startswith(b"INEVIONET_PONG"):
                    stop.set()
                    self.peer_addr = addr
                    return True
                if response.startswith(b"INEVIONET_PUNCH"):
                    # peer тоже шлёт — отвечаем PONG и открываем канал
                    try:
                        self.client.send_to(b"INEVIONET_PONG", addr)
                    except Exception:
                        pass
                    stop.set()
                    self.peer_addr = addr
                    return True
        finally:
            stop.set()
        return False

    def close(self):
        self.client.close()


if __name__ == "__main__":
    print("Testing STUN...")
    result = stun_get_public_ip(timeout=5.0)
    if result:
        print(f"Public address: {result[0]}:{result[1]}")
    else:
        print("STUN did not respond")

    print("Testing UDP DNS query...")
    client = UDPClient(timeout=5.0)
    dns_query = (b"\x12\x34\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00"
                 b"\x07example\x03com\x00\x00\x01\x00\x01")
    resp = client.request(dns_query, ("8.8.8.8", 53), timeout=3.0)
    if resp:
        print(f"DNS response: {len(resp)} bytes")
    client.close()
    print("UDP module OK")
