"""InevioNet Device Fingerprint."""
import hashlib
import platform
import socket
import uuid
import json
import os
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field

from ..core.logger import get_logger

logger = get_logger("inevionet.identity.fingerprint")


@dataclass
class DeviceFingerprint:
    fingerprint: str = ""
    hw_info: Dict[str, Any] = field(default_factory=dict)
    sw_info: Dict[str, Any] = field(default_factory=dict)
    net_info: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def collect(cls):
        hw_info = {
            "platform": platform.system(),
            "platform_release": platform.release(),
            "platform_version": platform.version(),
            "architecture": platform.machine(),
            "processor": platform.processor(),
            "cpu_count": _safe_cpu_count(),
            "uuid": str(uuid.getnode()),
            "hostname": platform.node(),
        }
        sw_info = {
            "python_version": platform.python_version(),
            "python_implementation": platform.python_implementation(),
        }
        net_info = {}
        try:
            net_info["hostname"] = socket.gethostname()
            net_info["fqdn"] = socket.getfqdn()
            try:
                net_info["ip"] = socket.gethostbyname(socket.gethostname())
            except Exception:
                net_info["ip"] = "unknown"
        except Exception:
            net_info["hostname"] = "unknown"
        combined = {"hw": hw_info, "sw": sw_info, "net": net_info}
        combined_str = json.dumps(combined, sort_keys=True)
        fingerprint = hashlib.sha256(combined_str.encode()).hexdigest()
        return cls(fingerprint=fingerprint, hw_info=hw_info,
                   sw_info=sw_info, net_info=net_info)

    def short(self, length=16):
        return self.fingerprint[:length]

    def similarity(self, other):
        keys1 = set(self.hw_info.keys())
        keys2 = set(other.hw_info.keys())
        if not keys1 or not keys2:
            return 0.0
        matches = 0
        total = 0
        for key in keys1 | keys2:
            v1 = self.hw_info.get(key)
            v2 = other.hw_info.get(key)
            if v1 is not None and v2 is not None:
                total += 1
                if v1 == v2:
                    matches += 1
        return matches / total if total > 0 else 0.0

    def to_dict(self):
        return {
            "fingerprint": self.fingerprint,
            "hw_info": self.hw_info,
            "sw_info": self.sw_info,
            "net_info": self.net_info,
        }

    def __repr__(self):
        return f"DeviceFingerprint({self.short()})"


def _safe_cpu_count():
    try:
        return os.cpu_count() or 1
    except Exception:
        return 1


if __name__ == "__main__":
    print("Testing DeviceFingerprint...")
    fp = DeviceFingerprint.collect()
    print(f"Fingerprint: {fp.fingerprint}")
    print(f"Short: {fp.short()}")
    print(f"Platform: {fp.hw_info.get('platform')}")
    print(f"CPU count: {fp.hw_info.get('cpu_count')}")
    print(f"Python: {fp.sw_info.get('python_version')}")
    fp2 = DeviceFingerprint.collect()
    print(f"Stable: {fp.fingerprint == fp2.fingerprint}")
    print(f"Similarity: {fp.similarity(fp2):.4f}")
    print("OK")
