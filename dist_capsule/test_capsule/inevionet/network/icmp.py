"""InevioNet ICMP - real ping with raw socket and fallback."""
import os
import sys
import struct
import socket
import subprocess
import platform
import time
from typing import Optional, Tuple, List
from dataclasses import dataclass

from ..core.logger import get_logger
from ..core.constants import IS_WINDOWS, is_root

logger = get_logger("inevionet.network.icmp")


ICMP_ECHO_REQUEST = 8
ICMP_ECHO_REPLY = 0
ICMP_HEADER_FORMAT = "!BBHHH"
ICMP_HEADER_SIZE = 8


def calculate_checksum(data):
    if len(data) % 2:
        data += b"\x00"
    checksum = 0
    for i in range(0, len(data), 2):
        word = (data[i] << 8) + data[i + 1]
        checksum += word
    checksum = (checksum >> 16) + (checksum & 0xFFFF)
    checksum += checksum >> 16
    return ~checksum & 0xFFFF


def build_icmp_packet(identifier, sequence, payload=b""):
    header = struct.pack(ICMP_HEADER_FORMAT, ICMP_ECHO_REQUEST, 0, 0, identifier, sequence)
    packet = header + payload
    checksum = calculate_checksum(packet)
    header = struct.pack(ICMP_HEADER_FORMAT, ICMP_ECHO_REQUEST, 0, checksum, identifier, sequence)
    return header + payload


@dataclass
class ICMPResult:
    host: str
    sequence: int
    rtt_ms: float
    payload: bytes
    ttl: int
    size: int
    fallback: bool = False


class ICMPClient:
    def __init__(self, identifier=None):
        self.identifier = identifier or (os.getpid() & 0xFFFF)
        self.sequence = 0
        self._socket = None
        self._has_raw = False
        self._fallback_mode = False
        self._try_init_raw_socket()

    def _try_init_raw_socket(self):
        try:
            if sys.platform.startswith("linux"):
                try:
                    self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_ICMP)
                    self._has_raw = True
                    logger.info("ICMP: using SOCK_DGRAM")
                    return
                except (OSError, PermissionError):
                    pass
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_ICMP)
            self._has_raw = True
            logger.info("ICMP: using SOCK_RAW")
        except (PermissionError, OSError) as e:
            logger.warning(f"Raw socket unavailable ({e}), using fallback")
            self._has_raw = False
            self._fallback_mode = True

    def _get_ip(self, host):
        try:
            socket.inet_aton(host)
            return host
        except OSError:
            pass
        try:
            return socket.gethostbyname(host)
        except socket.gaierror:
            return None

    def ping(self, host, timeout=3.0, payload=b""):
        ip = self._get_ip(host)
        if not ip:
            return None
        if self._fallback_mode or not self._has_raw:
            return self._ping_fallback(ip, timeout)
        return self._ping_raw(ip, timeout, payload)

    def _ping_raw(self, ip, timeout, payload):
        try:
            self.sequence = (self.sequence + 1) & 0xFFFF
            packet = build_icmp_packet(self.identifier, self.sequence, payload)
            old_timeout = self._socket.gettimeout()
            self._socket.settimeout(timeout)
            start = time.time()
            self._socket.sendto(packet, (ip, 0))
            deadline = start + timeout
            while time.time() < deadline:
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                self._socket.settimeout(remaining)
                try:
                    data, addr = self._socket.recvfrom(65536)
                except socket.timeout:
                    break
                if len(data) < ICMP_HEADER_SIZE:
                    continue
                icmp_data = data
                if len(data) >= 20 + ICMP_HEADER_SIZE:
                    first_byte = data[0]
                    if first_byte >> 4 == 4:
                        ip_header_len = (data[0] & 0x0F) * 4
                        icmp_data = data[ip_header_len:]
                if len(icmp_data) < ICMP_HEADER_SIZE:
                    continue
                icmp_type, icmp_code, _, icmp_id, icmp_seq = struct.unpack(
                    ICMP_HEADER_FORMAT, icmp_data[:ICMP_HEADER_SIZE])
                if icmp_type != ICMP_ECHO_REPLY:
                    continue
                if icmp_id != self.identifier or icmp_seq != self.sequence:
                    continue
                rtt = (time.time() - start) * 1000
                return ICMPResult(host=ip, sequence=icmp_seq, rtt_ms=rtt,
                                  payload=icmp_data[ICMP_HEADER_SIZE:],
                                  ttl=64, size=len(icmp_data))
            return None
        except OSError as e:
            logger.error(f"ICMP ping error: {e}")
            return None
        finally:
            try:
                self._socket.settimeout(old_timeout)
            except Exception:
                pass

    def _ping_fallback(self, ip, timeout):
        try:
            if IS_WINDOWS:
                cmd = ["ping", "-n", "1", "-w", str(int(timeout * 1000)), ip]
            else:
                cmd = ["ping", "-c", "1", "-W", str(int(timeout)), ip]
            start = time.time()
            result = subprocess.run(cmd, capture_output=True, timeout=timeout + 1, text=True,
                                    encoding="utf-8", errors="ignore")
            rtt = (time.time() - start) * 1000
            if result.returncode == 0:
                import re
                rtt_ms = rtt
                if IS_WINDOWS:
                    match = re.search(r"time[<=](\d+)ms", result.stdout)
                    if match:
                        rtt_ms = float(match.group(1))
                else:
                    match = re.search(r"time=([\d.]+)\s*ms", result.stdout)
                    if match:
                        rtt_ms = float(match.group(1))
                return ICMPResult(host=ip, sequence=1, rtt_ms=rtt_ms, payload=b"",
                                  ttl=64, size=64, fallback=True)
            return None
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return None
        except Exception as e:
            logger.error(f"ICMP fallback error: {e}")
            return None

    def send_data(self, host, data, max_payload=1400):
        if len(data) > max_payload:
            data = data[:max_payload]
        result = self.ping(host, timeout=5.0, payload=data)
        return result is not None

    def close(self):
        if self._socket:
            try:
                self._socket.close()
            except OSError:
                pass
            self._socket = None

    @property
    def has_raw(self):
        return self._has_raw

    @property
    def using_fallback(self):
        return self._fallback_mode

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


if __name__ == "__main__":
    print("Testing ICMP...")
    client = ICMPClient()
    print(f"Raw socket: {client.has_raw}")
    result = client.ping("8.8.8.8", timeout=3.0)
    if result:
        print(f"Ping 8.8.8.8: {result.rtt_ms:.1f} ms (fallback={result.fallback})")
    else:
        print("Ping failed")
    client.close()
    print("ICMP module OK")
