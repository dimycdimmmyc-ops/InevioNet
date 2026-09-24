"""InevioNet DNS - real queries with payload."""
import socket
import struct
import random
import base64
import time
from typing import Optional, Tuple, List, Dict, Any

from ..core.logger import get_logger

logger = get_logger("inevionet.network.dns")


class DNSType:
    A = 1
    NS = 2
    CNAME = 5
    SOA = 6
    PTR = 12
    MX = 15
    TXT = 16
    AAAA = 28
    SRV = 33
    ANY = 255


class DNSClass:
    IN = 1
    CH = 3
    ANY = 255


class DNSClient:
    def __init__(self, server="8.8.8.8", port=53, timeout=5.0, use_tcp=False):
        self.server = server
        self.port = port
        self.timeout = timeout
        self.use_tcp = use_tcp

    def query(self, domain, qtype=DNSType.A, qclass=DNSClass.IN):
        try:
            packet = self._build_query(domain, qtype, qclass)
            if self.use_tcp:
                data = self._tcp_query(packet)
            else:
                data = self._udp_query(packet)
            if not data:
                return None
            return DNSResponse.parse(data)
        except Exception as e:
            logger.error(f"DNS query error {domain}: {e}")
            return None

    def _build_query(self, domain, qtype, qclass):
        transaction_id = random.randint(1, 65535)
        flags = 0x0100
        header = struct.pack("!HHHHHH", transaction_id, flags, 1, 0, 0, 0)
        qname = self._encode_domain(domain)
        question = qname + struct.pack("!HH", qtype, qclass)
        return header + question

    @staticmethod
    def _encode_domain(domain):
        parts = domain.rstrip(".").split(".")
        result = b""
        for part in parts:
            b = part.encode("utf-8")
            if len(b) > 63:
                raise ValueError(f"Label too long: {part}")
            result += bytes([len(b)]) + b
        result += b"\x00"
        return result

    def _udp_query(self, packet):
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(self.timeout)
        try:
            sock.sendto(packet, (self.server, self.port))
            data, _ = sock.recvfrom(65536)
            return data
        except socket.timeout:
            return None
        except OSError as e:
            logger.error(f"DNS UDP error: {e}")
            return None
        finally:
            sock.close()

    def _tcp_query(self, packet):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        try:
            sock.connect((self.server, self.port))
            prefix = struct.pack("!H", len(packet))
            sock.sendall(prefix + packet)
            len_bytes = self._recv_exactly(sock, 2)
            if not len_bytes:
                return None
            response_len = struct.unpack("!H", len_bytes)[0]
            return self._recv_exactly(sock, response_len)
        except OSError as e:
            logger.error(f"DNS TCP error: {e}")
            return None
        finally:
            sock.close()

    @staticmethod
    def _recv_exactly(sock, size):
        buf = b""
        while len(buf) < size:
            chunk = sock.recv(size - len(buf))
            if not chunk:
                return None
            buf += chunk
        return buf

    def query_a(self, domain):
        response = self.query(domain, DNSType.A)
        if not response:
            return []
        return [r["data"] for r in response.answers if r["type"] == DNSType.A]

    def query_aaaa(self, domain):
        response = self.query(domain, DNSType.AAAA)
        if not response:
            return []
        return [r["data"] for r in response.answers if r["type"] == DNSType.AAAA]

    def query_txt(self, domain):
        response = self.query(domain, DNSType.TXT)
        if not response:
            return []
        return [r["data"] for r in response.answers if r["type"] == DNSType.TXT]

    def query_mx(self, domain):
        response = self.query(domain, DNSType.MX)
        if not response:
            return []
        return [(r["priority"], r["exchange"]) for r in response.answers if r["type"] == DNSType.MX]

    def send_data_via_qname(self, data, domain, max_chunk=40):
        if not data:
            return []
        chunks = [data[i:i+max_chunk] for i in range(0, len(data), max_chunk)]
        results = []
        for i, chunk in enumerate(chunks):
            encoded = base64.b32encode(chunk).decode("ascii").rstrip("=").lower()
            qname = f"{i:03d}-{encoded}.{domain}"
            response = self.query(qname, DNSType.A)
            results.append(response is not None)
            if i < len(chunks) - 1:
                time.sleep(0.05)
        return results


class DNSResponse:
    def __init__(self, transaction_id, flags, questions, answers, authorities, additionals):
        self.transaction_id = transaction_id
        self.flags = flags
        self.questions = questions
        self.answers = answers
        self.authorities = authorities
        self.additionals = additionals

    @property
    def rcode(self):
        return self.flags & 0x000F

    @property
    def is_success(self):
        return self.rcode == 0

    @classmethod
    def parse(cls, data):
        if len(data) < 12:
            raise ValueError("Response too short")
        transaction_id, flags, qdcount, ancount, nscount, arcount = struct.unpack("!HHHHHH", data[:12])
        offset = 12
        questions = []
        for _ in range(qdcount):
            qname, offset = cls._parse_name(data, offset)
            qtype, qclass = struct.unpack("!HH", data[offset:offset+4])
            offset += 4
            questions.append({"name": qname, "type": qtype, "class": qclass})
        answers = []
        for _ in range(ancount):
            record, offset = cls._parse_rr(data, offset)
            answers.append(record)
        return cls(transaction_id, flags, questions, answers, [], [])

    @staticmethod
    def _parse_name(data, offset):
        parts = []
        jumps = 0
        original_offset = offset
        while offset < len(data):
            length = data[offset]
            if length == 0:
                offset += 1
                break
            if (length & 0xC0) == 0xC0:
                if offset + 1 >= len(data):
                    break
                pointer = struct.unpack("!H", data[offset:offset+2])[0] & 0x3FFF
                if jumps == 0:
                    original_offset = offset + 2
                offset = pointer
                jumps += 1
                if jumps > 10:
                    break
                continue
            offset += 1
            part = data[offset:offset+length].decode("utf-8", errors="ignore")
            parts.append(part)
            offset += length
        name = ".".join(parts)
        if jumps > 0:
            return name, original_offset
        return name, offset

    @classmethod
    def _parse_rr(cls, data, offset):
        name, offset = cls._parse_name(data, offset)
        rtype, rclass, ttl, rdlength = struct.unpack("!HHIH", data[offset:offset+10])
        offset += 10
        rdata = data[offset:offset+rdlength]
        if rtype == DNSType.A:
            value = socket.inet_ntoa(rdata)
        elif rtype == DNSType.AAAA:
            value = socket.inet_ntop(socket.AF_INET6, rdata)
        elif rtype == DNSType.TXT:
            txt_parts = []
            pos = 0
            while pos < len(rdata):
                length = rdata[pos]
                txt_parts.append(rdata[pos+1:pos+1+length].decode("utf-8", errors="ignore"))
                pos += 1 + length
            value = "".join(txt_parts)
        elif rtype == DNSType.CNAME:
            value, _ = cls._parse_name(data, offset)
        elif rtype == DNSType.MX:
            priority = struct.unpack("!H", rdata[:2])[0]
            exchange, _ = cls._parse_name(data, offset + 2)
            return {"name": name, "type": rtype, "class": rclass, "ttl": ttl,
                    "priority": priority, "exchange": exchange}, offset + rdlength
        else:
            value = rdata.hex()
        return {"name": name, "type": rtype, "class": rclass, "ttl": ttl, "data": value}, offset + rdlength


if __name__ == "__main__":
    print("Testing DNS...")
    client = DNSClient("8.8.8.8")
    ips = client.query_a("example.com")
    if ips:
        print(f"A records: {ips}")
    txt = client.query_txt("google.com")
    if txt:
        print(f"TXT: {txt[0][:60]}...")
    print("DNS module OK")
