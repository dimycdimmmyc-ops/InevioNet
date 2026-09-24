"""InevioNet Polymorphic Encoder."""
import time
import hashlib
import random
from typing import List, Dict, Optional
from dataclasses import dataclass


@dataclass
class Fragment:
    fragment_id: str = ""
    sequence: int = 0
    total_fragments: int = 1
    protocol: str = "HTTP"
    data: bytes = b""
    checksum: str = ""

    def __post_init__(self):
        if not self.fragment_id:
            self.fragment_id = f"frag_{int(time.time()*1000)}_{random.randint(1000,9999)}"
        if not self.checksum and self.data:
            self.checksum = hashlib.sha256(self.data).hexdigest()[:16]

    def verify_checksum(self):
        if not self.data:
            return True
        return hashlib.sha256(self.data).hexdigest()[:16] == self.checksum

    def to_dict(self):
        return {
            "fragment_id": self.fragment_id,
            "sequence": self.sequence,
            "total": self.total_fragments,
            "protocol": self.protocol,
            "data": self.data.hex(),
            "checksum": self.checksum,
        }

    @classmethod
    def from_dict(cls, data):
        return cls(
            fragment_id=data["fragment_id"],
            sequence=data["sequence"],
            total_fragments=data["total"],
            protocol=data["protocol"],
            data=bytes.fromhex(data["data"]),
            checksum=data.get("checksum", ""),
        )

    def __repr__(self):
        return f"Fragment({self.fragment_id[:12]}, {self.sequence}/{self.total_fragments}, {self.protocol})"


class PolymorphicEncoder:
    PROTOCOLS = ["HTTP", "HTTPS", "DNS", "ICMP", "TLS", "WebSocket", "QUIC", "NTP"]

    def __init__(self, min_size=20, max_size=500, randomize_protocols=True):
        self.min_size = min_size
        self.max_size = max_size
        self.randomize_protocols = randomize_protocols

    def encode(self, data, fragments_count=None, max_fragment_size=None):
        if not data:
            return []
        max_size = max_fragment_size or self.max_size
        if fragments_count:
            fragment_size = max(1, len(data) // fragments_count)
            fragment_size = max(self.min_size, min(max_size, fragment_size))
        else:
            fragment_size = random.randint(self.min_size, max_size)
        chunks = [data[i:i+fragment_size] for i in range(0, len(data), fragment_size)]
        total = len(chunks)
        fragments = []
        for i, chunk in enumerate(chunks):
            if self.randomize_protocols:
                protocol = random.choice(self.PROTOCOLS)
            else:
                protocol = self.PROTOCOLS[i % len(self.PROTOCOLS)]
            fragments.append(Fragment(
                sequence=i, total_fragments=total,
                protocol=protocol, data=chunk))
        return fragments

    def decode(self, fragments):
        if not fragments:
            return b""
        sorted_frags = sorted(fragments, key=lambda f: f.sequence)
        for frag in sorted_frags:
            if not frag.verify_checksum():
                raise ValueError(f"Fragment {frag.fragment_id} corrupted")
        return b"".join(f.data for f in sorted_frags)

    def estimate_detection_probability(self, fragments, base_detection_prob=0.3):
        if not fragments:
            return 0.0
        p_single = base_detection_prob / len(fragments)
        p_all = 1.0 - (1.0 - p_single) ** len(fragments)
        return p_all

    def get_stats(self, fragments):
        if not fragments:
            return {"count": 0}
        protocols_used = {}
        total_size = 0
        for frag in fragments:
            protocols_used[frag.protocol] = protocols_used.get(frag.protocol, 0) + 1
            total_size += len(frag.data)
        return {
            "count": len(fragments),
            "total_size": total_size,
            "protocols": protocols_used,
            "unique_protocols": len(protocols_used),
            "avg_fragment_size": total_size / len(fragments) if fragments else 0,
            "estimated_detection": self.estimate_detection_probability(fragments),
        }

    def __repr__(self):
        return f"PolymorphicEncoder(protocols={len(self.PROTOCOLS)}, size={self.min_size}-{self.max_size})"


if __name__ == "__main__":
    print("Testing PolymorphicEncoder...")
    enc = PolymorphicEncoder()
    data = b"Test data " * 50
    frags = enc.encode(data)
    print(f"Fragments: {len(frags)}")
    restored = enc.decode(frags)
    assert restored == data
    print("Round-trip OK")
    stats = enc.get_stats(frags)
    print(f"Stats: {stats}")
    print("OK")
