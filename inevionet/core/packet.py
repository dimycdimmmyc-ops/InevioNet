"""InevioNet GDPPacket.

GDPPacket — базовый пакет InevioNet.

V6 (Ack-механизм):
  Новые поля:
    expect_ack — отправитель ждёт подтверждения
    ack_id     — для ACK: какой пакет подтверждаем
    ack_for    — для ACK: от кого пришло подтверждение (или кому)

  Новые методы:
    mark_as_ack(original_packet_id, by_node_id, status)
    is_ack()
    extract_ack_id()
    create_ack_packet(original, by_node_id, status)

  В metadata (для совместимости):
    metadata['ack_status']  — 'ok' / 'failed' / 'timeout'
    metadata['ack_rtt_ms']  — RTT до получателя
"""
import json
import time
import struct
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field

from .constants import PacketState, PacketPriority, DEFAULT_CONFIG
from .crypto import random_id, hash_hex, sign_data, verify_signature
from .exceptions import PacketCorruptedError


@dataclass
class GDPPacket:
    packet_id: str = ""
    sender: str = ""
    receiver: str = ""
    payload: bytes = b""
    ttl: int = 25
    max_ttl: int = 35
    created_at: float = 0.0
    expires_at: float = 0.0
    path: List[str] = field(default_factory=list)
    protocol: str = "TCP"
    priority: int = 5
    clones: int = 0
    parent_id: str = ""
    clone_reason: str = ""
    state: str = "created"
    metadata: Dict[str, Any] = field(default_factory=dict)
    attractor: int = 0
    signature: bytes = b""

    # === МАРШРУТИЗАЦИЯ ===
    route_to: Optional[str] = None
    origin: Optional[str] = None
    hop_count: int = 0
    max_hops: int = 8

    # === ACK-МЕХАНИЗМ ===
    expect_ack: bool = False            # отправитель ждёт подтверждения
    ack_id: Optional[str] = None        # для ACK: какой пакет подтверждаем
    ack_for: Optional[str] = None       # для ACK: от кого/кому подтверждение

    def __post_init__(self):
        if not self.packet_id:
            self.packet_id = random_id("pkt")
        if not self.created_at:
            self.created_at = time.time()
        if not self.expires_at:
            self.expires_at = self.created_at + self.ttl
        if self.max_ttl < self.ttl:
            self.max_ttl = self.ttl
        if not self.attractor:
            self.attractor = self._compute_attractor()
        if self.origin is None:
            self.origin = self.sender
        if self.hop_count > self.max_hops:
            self.hop_count = self.max_hops

    def _compute_attractor(self) -> int:
        base = f"{self.sender}:{self.receiver}:{self.protocol}"
        if self.payload:
            base += f":{hash_hex(self.payload, 'sha256', 16)}"
        h = hash_hex(base.encode("utf-8"), "sha256", 8)
        return int(h, 16) % 100

    @property
    def age(self) -> float:
        return time.time() - self.created_at

    @property
    def is_expired(self) -> bool:
        return self.ttl <= 0 or time.time() > self.expires_at

    @property
    def is_alive(self) -> bool:
        return not self.is_expired

    def tick(self, decrement: int = 1):
        self.ttl -= decrement
        self.expires_at = time.time() + self.ttl
        return self

    def heal(self, amount: int = 5):
        self.ttl = min(self.max_ttl, self.ttl + amount)
        self.expires_at = time.time() + self.ttl
        self.metadata["heal_count"] = self.metadata.get("heal_count", 0) + 1
        return self

    def clone(self, reason: str = "", network: str = "") -> "GDPPacket":
        clone = GDPPacket(
            packet_id=f"{self.packet_id}_clone_{self.clones + 1}",
            sender=self.sender, receiver=self.receiver, payload=self.payload,
            ttl=self.max_ttl, max_ttl=self.max_ttl, created_at=time.time(),
            protocol=self.protocol, priority=self.priority,
            clones=self.clones + 1, parent_id=self.packet_id,
            clone_reason=reason, state="cloned",
            metadata=dict(self.metadata), signature=self.signature,
            route_to=self.route_to, origin=self.origin,
            hop_count=0, max_hops=self.max_hops,
            expect_ack=False, ack_id=None, ack_for=None,
        )
        if network:
            clone.metadata["clone_network"] = network
        return clone

    @property
    def is_clone(self) -> bool:
        return "_clone_" in self.packet_id

    def get_original_id(self) -> str:
        return self.packet_id.split("_clone_")[0] if self.is_clone else self.packet_id

    def apply_attractor(self, network: str):
        self.path.append(f"attr_{network}")
        self.ttl = min(self.max_ttl, self.ttl + 2)
        self.expires_at = time.time() + self.ttl
        self.attractor = self._compute_attractor()
        self.metadata["attractor_count"] = self.metadata.get("attractor_count", 0) + 1
        return self

    # ==================================================
    # МАРШРУТИЗАЦИЯ
    # ==================================================
    def is_for_me(self, my_node_id: str) -> bool:
        if not my_node_id:
            return False
        return my_node_id == self.receiver or my_node_id == self.route_to

    def is_loop(self, node_id: str) -> bool:
        if not node_id:
            return False
        return node_id in self.path

    def add_hop(self, node_id: str) -> bool:
        if not node_id:
            return False
        if self.is_loop(node_id):
            return False
        if self.hop_count >= self.max_hops:
            return False
        self.path.append(node_id)
        self.hop_count += 1
        self.ttl = max(0, self.ttl - 1)
        self.expires_at = time.time() + self.ttl
        return True

    def should_relay(self, my_node_id: str) -> bool:
        if not self.route_to:
            return False
        if self.is_for_me(my_node_id):
            return False
        if self.ttl <= 0 or self.is_expired:
            return False
        if self.is_loop(my_node_id):
            return False
        if self.hop_count >= self.max_hops:
            return False
        return True

    def mark_relayed(self, via_node_id: str) -> "GDPPacket":
        self.metadata["relayed_via"] = via_node_id
        self.metadata["relayed_at"] = time.time()
        self.metadata["relay_count"] = self.metadata.get("relay_count", 0) + 1
        return self

    # ==================================================
    # ACK-МЕХАНИЗМ
    # ==================================================
    def is_ack(self) -> bool:
        """Этот пакет — подтверждение?"""
        return bool(self.ack_id)

    def extract_ack_id(self) -> Optional[str]:
        """Если это ACK — вернуть ID подтверждаемого пакета."""
        return self.ack_id if self.is_ack() else None

    def mark_as_ack(
        self,
        original_packet_id: str,
        by_node_id: str,
        status: str = "ok",
    ) -> "GDPPacket":
        """Пометить этот пакет как ACK для другого пакета."""
        self.ack_id = original_packet_id
        self.ack_for = by_node_id
        self.expect_ack = False
        self.metadata["ack_status"] = status
        self.metadata["ack_at"] = time.time()
        return self

    @classmethod
    def create_ack_packet(
        cls,
        original: "GDPPacket",
        by_node_id: str,
        status: str = "ok",
        rtt_ms: float = 0.0,
    ) -> "GDPPacket":
        """Создать ACK-пакет для оригинального пакета.

        Отправитель: by_node_id (тот, кто получил original).
        Получатель: original.sender (тот, кто ждёт подтверждения).
        """
        ack = cls(
            sender=by_node_id,
            receiver=original.sender,
            payload=b"ACK",
            ttl=15,
            max_ttl=15,
            protocol=original.protocol,
            priority=9,  # ACK — важнее обычных пакетов
            metadata={
                "ack_status": status,
                "ack_rtt_ms": rtt_ms,
                "original_packet_id": original.packet_id,
            },
            route_to=original.sender,
            origin=by_node_id,
            max_hops=6,
            expect_ack=False,
        )
        ack.ack_id = original.packet_id
        ack.ack_for = original.sender
        return ack

    # ==================================================
    # ПОДПИСЬ
    # ==================================================
    def sign(self, private_key: bytes):
        data = self._signature_data()
        self.signature = sign_data(private_key, data)
        return self

    def verify(self, public_key: bytes) -> bool:
        if not self.signature:
            return False
        return verify_signature(public_key, self.signature, self._signature_data())

    def _signature_data(self) -> bytes:
        data = {
            "packet_id": self.packet_id, "sender": self.sender,
            "receiver": self.receiver,
            "payload": self.payload.hex() if self.payload else "",
            "created_at": self.created_at, "protocol": self.protocol,
            "priority": self.priority,
            "route_to": self.route_to or "",
            "origin": self.origin or "",
            # ACK в подписи — чтобы нельзя было подделать подтверждение
            "expect_ack": self.expect_ack,
            "ack_id": self.ack_id or "",
            "ack_for": self.ack_for or "",
        }
        return json.dumps(data, sort_keys=True, separators=(",", ":")).encode()

    def set_delivered(self):
        self.state = "delivered"
        self.metadata["delivered_at"] = time.time()
        return self

    def set_failed(self, reason: str = ""):
        self.state = "failed"
        self.metadata["failed_at"] = time.time()
        self.metadata["fail_reason"] = reason
        return self

    # ==================================================
    # СЕРИАЛИЗАЦИЯ
    # ==================================================
    def to_dict(self, include_payload: bool = True) -> Dict[str, Any]:
        data = {
            "packet_id": self.packet_id, "sender": self.sender,
            "receiver": self.receiver, "ttl": self.ttl, "max_ttl": self.max_ttl,
            "created_at": self.created_at, "expires_at": self.expires_at,
            "path": self.path, "protocol": self.protocol,
            "priority": self.priority, "clones": self.clones,
            "parent_id": self.parent_id, "clone_reason": self.clone_reason,
            "state": self.state, "metadata": self.metadata,
            "attractor": self.attractor,
            "signature": self.signature.hex() if self.signature else "",
            "route_to": self.route_to,
            "origin": self.origin,
            "hop_count": self.hop_count,
            "max_hops": self.max_hops,
            # ACK
            "expect_ack": self.expect_ack,
            "ack_id": self.ack_id,
            "ack_for": self.ack_for,
        }
        if include_payload:
            data["payload"] = self.payload.hex() if self.payload else ""
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GDPPacket":
        try:
            return cls(
                packet_id=data["packet_id"], sender=data["sender"],
                receiver=data["receiver"],
                payload=bytes.fromhex(data.get("payload", "")),
                ttl=data.get("ttl", 25), max_ttl=data.get("max_ttl", 35),
                created_at=data.get("created_at", 0),
                expires_at=data.get("expires_at", 0),
                path=data.get("path", []), protocol=data.get("protocol", "TCP"),
                priority=data.get("priority", 5), clones=data.get("clones", 0),
                parent_id=data.get("parent_id", ""),
                clone_reason=data.get("clone_reason", ""),
                state=data.get("state", "created"),
                metadata=data.get("metadata", {}),
                attractor=data.get("attractor", 0),
                signature=bytes.fromhex(data.get("signature", "")),
                route_to=data.get("route_to"),
                origin=data.get("origin"),
                hop_count=data.get("hop_count", 0),
                max_hops=data.get("max_hops", 8),
                expect_ack=bool(data.get("expect_ack", False)),
                ack_id=data.get("ack_id"),
                ack_for=data.get("ack_for"),
            )
        except (KeyError, ValueError) as e:
            raise PacketCorruptedError(f"Corrupted: {e}", original=e)

    def to_json(self, include_payload: bool = True) -> str:
        return json.dumps(self.to_dict(include_payload), ensure_ascii=False,
                          separators=(",", ":"))

    @classmethod
    def from_json(cls, s: str) -> "GDPPacket":
        try:
            return cls.from_dict(json.loads(s))
        except json.JSONDecodeError as e:
            raise PacketCorruptedError(f"JSON error: {e}", original=e)

    def to_bytes(self) -> bytes:
        """Бинарная сериализация.

        Формат: [стандартные поля] + [route block] + [ack block]

        Флаг has_route (1 байт):
          - 0x00: нет маршрута
          - 0x01: route block

        Флаг has_ack (1 байт):
          - 0x00: нет ACK
          - 0x01: ACK block (expect_ack + ack_id + ack_for)

        Route block: route_to_len + route_to + origin_len + origin + hop_count + max_hops
        ACK block:  expect_ack (1) + ack_id_len + ack_id + ack_for_len + ack_for
        """
        parts = []
        pid = self.packet_id.encode("utf-8")
        parts.append(struct.pack("!I", len(pid)))
        parts.append(pid)
        s = self.sender.encode("utf-8")
        parts.append(struct.pack("!I", len(s)))
        parts.append(s)
        r = self.receiver.encode("utf-8")
        parts.append(struct.pack("!I", len(r)))
        parts.append(r)
        parts.append(struct.pack("!I", len(self.payload)))
        parts.append(self.payload)
        parts.append(struct.pack("!II", self.ttl, self.max_ttl))
        parts.append(struct.pack("!d", self.created_at))
        proto = self.protocol.encode("utf-8")[:255]
        parts.append(struct.pack("!B", len(proto)))
        parts.append(proto)
        parts.append(struct.pack("!B", min(255, max(0, int(self.priority)))))
        meta = json.dumps(self.metadata, ensure_ascii=False).encode("utf-8")
        parts.append(struct.pack("!I", len(meta)))
        parts.append(meta)
        parts.append(struct.pack("!I", len(self.signature)))
        parts.append(self.signature)

        # ROUTE BLOCK
        if self.route_to or self.origin or self.hop_count > 0:
            parts.append(struct.pack("!B", 1))
            rt = (self.route_to or "").encode("utf-8")
            parts.append(struct.pack("!I", len(rt)))
            parts.append(rt)
            og = (self.origin or "").encode("utf-8")
            parts.append(struct.pack("!I", len(og)))
            parts.append(og)
            parts.append(struct.pack("!I", self.hop_count))
            parts.append(struct.pack("!I", self.max_hops))
        else:
            parts.append(struct.pack("!B", 0))

        # ACK BLOCK
        if self.expect_ack or self.ack_id or self.ack_for:
            parts.append(struct.pack("!B", 1))
            parts.append(struct.pack("!B", 1 if self.expect_ack else 0))
            aid = (self.ack_id or "").encode("utf-8")
            parts.append(struct.pack("!I", len(aid)))
            parts.append(aid)
            af = (self.ack_for or "").encode("utf-8")
            parts.append(struct.pack("!I", len(af)))
            parts.append(af)
        else:
            parts.append(struct.pack("!B", 0))
        return b"".join(parts)

    @classmethod
    def from_bytes(cls, data: bytes) -> "GDPPacket":
        try:
            offset = 0

            def read_u32():
                nonlocal offset
                v = struct.unpack("!I", data[offset:offset+4])[0]
                offset += 4
                return v

            def read_bytes(n):
                nonlocal offset
                v = data[offset:offset+n]
                offset += n
                return v

            def read_u8():
                nonlocal offset
                v = data[offset]
                offset += 1
                return v

            pid_len = read_u32()
            packet_id = read_bytes(pid_len).decode("utf-8")
            s_len = read_u32()
            sender = read_bytes(s_len).decode("utf-8")
            r_len = read_u32()
            receiver = read_bytes(r_len).decode("utf-8")
            pl_len = read_u32()
            payload = read_bytes(pl_len)
            ttl = read_u32()
            max_ttl = read_u32()
            created_at = struct.unpack("!d", data[offset:offset+8])[0]
            offset += 8
            proto_len = read_u8()
            protocol = read_bytes(proto_len).decode("utf-8")
            priority = read_u8()
            meta_len = read_u32()
            meta = read_bytes(meta_len).decode("utf-8")
            metadata = json.loads(meta) if meta else {}
            sig_len = read_u32()
            signature = read_bytes(sig_len)

            # ROUTE BLOCK
            route_to = None
            origin = None
            hop_count = 0
            max_hops = 8
            if offset < len(data):
                try:
                    has_route = read_u8()
                    if has_route == 1:
                        rt_len = read_u32()
                        rt = read_bytes(rt_len).decode("utf-8")
                        route_to = rt or None
                        og_len = read_u32()
                        og = read_bytes(og_len).decode("utf-8")
                        origin = og or None
                        hop_count = read_u32()
                        max_hops = read_u32()
                except (struct.error, IndexError):
                    pass

            # ACK BLOCK
            expect_ack = False
            ack_id = None
            ack_for = None
            if offset < len(data):
                try:
                    has_ack = read_u8()
                    if has_ack == 1:
                        expect_ack = bool(read_u8())
                        aid_len = read_u32()
                        aid = read_bytes(aid_len).decode("utf-8")
                        ack_id = aid or None
                        af_len = read_u32()
                        af = read_bytes(af_len).decode("utf-8")
                        ack_for = af or None
                except (struct.error, IndexError):
                    pass

            return cls(
                packet_id=packet_id, sender=sender, receiver=receiver,
                payload=payload, ttl=ttl, max_ttl=max_ttl,
                created_at=created_at, protocol=protocol,
                priority=priority, metadata=metadata,
                signature=signature,
                route_to=route_to, origin=origin,
                hop_count=hop_count, max_hops=max_hops,
                expect_ack=expect_ack, ack_id=ack_id, ack_for=ack_for,
            )
        except (struct.error, UnicodeDecodeError, json.JSONDecodeError) as e:
            raise PacketCorruptedError(f"Corrupted: {e}", original=e)

    def summary(self) -> str:
        route_info = ""
        if self.route_to:
            route_info = f" route_to={self.route_to} hops={self.hop_count}/{self.max_hops}"
        ack_info = ""
        if self.is_ack():
            ack_info = f" ACK({self.ack_id[:16]}...)"
        elif self.expect_ack:
            ack_info = " expect_ack"
        return (f"GDPPacket {self.packet_id[:16]}... "
                f"{self.sender} -> {self.receiver}{route_info}{ack_info} "
                f"(TTL={self.ttl}, protocol={self.protocol})")

    def __repr__(self):
        return (f"GDPPacket({self.packet_id!r}, "
                f"{self.sender!r} -> {self.receiver!r}, "
                f"route_to={self.route_to!r}, "
                f"ack_id={self.ack_id!r}, ttl={self.ttl})")

    def __hash__(self):
        return hash(self.packet_id)


# ==================================================
# ФАБРИКИ
# ==================================================
def create_packet(sender, receiver, payload, protocol="TCP", priority=5,
                  ttl=25, metadata=None, route_to=None, origin=None,
                  max_hops=8, expect_ack=False) -> GDPPacket:
    return GDPPacket(
        sender=sender, receiver=receiver, payload=payload,
        protocol=protocol, priority=priority, ttl=ttl,
        max_ttl=DEFAULT_CONFIG["core"]["max_ttl"],
        metadata=metadata or {},
        route_to=route_to, origin=origin,
        max_hops=max_hops, expect_ack=expect_ack)


def create_text_packet(sender, receiver, text, **kwargs) -> GDPPacket:
    return create_packet(sender, receiver, text.encode("utf-8"), **kwargs)


def create_relay_packet(sender, receiver, payload, route_to,
                        origin=None, ttl=20, max_hops=8,
                        protocol="TCP", priority=8,
                        metadata=None, expect_ack=False) -> GDPPacket:
    md = dict(metadata or {})
    md["is_relay"] = True
    return create_packet(
        sender=sender, receiver=receiver, payload=payload,
        protocol=protocol, priority=priority, ttl=ttl,
        metadata=md,
        route_to=route_to, origin=origin or sender,
        max_hops=max_hops, expect_ack=expect_ack)


def create_ack_packet(original, by_node_id, status="ok", rtt_ms=0.0):
    """Удобная обёртка над GDPPacket.create_ack_packet."""
    return GDPPacket.create_ack_packet(original, by_node_id, status, rtt_ms)


# ==================================================
# ТЕСТЫ
# ==================================================
if __name__ == "__main__":
    print("Testing GDPPacket (v6 + ACK)...")
    p = create_text_packet("alice", "bob", "Hello!", expect_ack=True)
    print(p.summary())
    assert p.expect_ack is True
    assert p.ack_id is None

    # JSON round-trip
    p2 = GDPPacket.from_json(p.to_json())
    assert p2.packet_id == p.packet_id
    assert p2.expect_ack is True
    assert p2.ack_id is None
    print("OK: JSON + expect_ack")

    # Binary round-trip
    p3 = GDPPacket.from_bytes(p.to_bytes())
    assert p3.packet_id == p.packet_id
    assert p3.expect_ack is True
    print("OK: binary + expect_ack")

    # ACK packet
    ack = create_ack_packet(p, by_node_id="bob", status="ok", rtt_ms=42.5)
    print(ack.summary())
    assert ack.is_ack() is True
    assert ack.ack_id == p.packet_id
    assert ack.ack_for == "alice"
    assert ack.receiver == "alice"
    assert ack.sender == "bob"
    assert ack.metadata["ack_status"] == "ok"
    print("OK: ACK creation")

    # ACK binary round-trip
    ack2 = GDPPacket.from_bytes(ack.to_bytes())
    assert ack2.is_ack() is True
    assert ack2.ack_id == p.packet_id
    assert ack2.ack_for == "alice"
    assert ack2.metadata["ack_status"] == "ok"
    assert ack2.metadata["ack_rtt_ms"] == 42.5
    print("OK: ACK binary round-trip")

    # Relay + ACK
    rp = create_relay_packet(
        "a", "b", b"hi", route_to="c", expect_ack=True)
    assert rp.route_to == "c"
    assert rp.expect_ack is True
    rp2 = GDPPacket.from_bytes(rp.to_bytes())
    assert rp2.route_to == "c"
    assert rp2.expect_ack is True
    print("OK: relay + ack")

    # Обратная совместимость: старый пакет без ACK
    old = create_text_packet("x", "y", "old")
    old_bytes = old.to_bytes()
    old2 = GDPPacket.from_bytes(old_bytes)
    assert old2.expect_ack is False
    assert old2.ack_id is None
    print("OK: backward compat")

    print("ALL TESTS PASSED")