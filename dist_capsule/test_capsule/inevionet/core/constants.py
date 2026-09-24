"""InevioNet Constants."""
import os
import sys
import platform
from enum import Enum
from pathlib import Path

PLATFORM = platform.system()
IS_WINDOWS = PLATFORM == "Windows"
IS_LINUX = PLATFORM == "Linux"
IS_MACOS = PLATFORM == "Darwin"


class DataPaths:
    @staticmethod
    def get_root() -> Path:
        env = os.environ.get("INEVIONET_DATA")
        if env:
            return Path(env)
        if IS_WINDOWS:
            base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
            return Path(base) / "InevioNet"
        elif IS_MACOS:
            return Path.home() / "Library" / "Application Support" / "InevioNet"
        else:
            return Path.home() / ".local" / "share" / "inevionet"

    @staticmethod
    def get_state_dir() -> Path:
        return DataPaths.get_root() / "state"

    @staticmethod
    def get_logs_dir() -> Path:
        return DataPaths.get_root() / "logs"

    @staticmethod
    def get_keys_dir() -> Path:
        return DataPaths.get_root() / "keys"

    @staticmethod
    def get_cache_dir() -> Path:
        return DataPaths.get_root() / "cache"

    @staticmethod
    def ensure_all():
        for d in [DataPaths.get_root(), DataPaths.get_state_dir(),
                  DataPaths.get_logs_dir(), DataPaths.get_keys_dir(),
                  DataPaths.get_cache_dir()]:
            d.mkdir(parents=True, exist_ok=True)


class InevioMode(str, Enum):
    STANDARD = "standard"
    HIGH_RELIABILITY = "high_reliability"
    LOW_LATENCY = "low_latency"
    STEALTH = "stealth"
    INDUSTRIAL = "industrial"
    MILITARY = "military"


class ProtocolType(str, Enum):
    TCP = "tcp"
    UDP = "udp"
    ICMP = "icmp"
    DNS = "dns"
    HTTP = "http"
    HTTPS = "https"
    WEBSOCKET = "websocket"
    QUIC = "quic"


class PacketPriority(int, Enum):
    LOW = 1
    NORMAL = 5
    HIGH = 8
    CRITICAL = 10


class PacketState(str, Enum):
    CREATED = "created"
    SENT = "sent"
    IN_TRANSIT = "in_transit"
    CLONED = "cloned"
    DELIVERED = "delivered"
    FAILED = "failed"
    EXPIRED = "expired"


PROTOCOLS = {
    "TCP": {"name": "TCP", "default_port": 80, "stealth": 0.60, "nat_pass": 0.95,
            "dpi_resist": 0.50, "latency_ms": 20, "max_payload": 1460, "reliable": True},
    "UDP": {"name": "UDP", "default_port": 53, "stealth": 0.70, "nat_pass": 0.70,
            "dpi_resist": 0.60, "latency_ms": 5, "max_payload": 1472, "reliable": False},
    "ICMP": {"name": "ICMP", "default_port": 0, "stealth": 0.95, "nat_pass": 0.70,
             "dpi_resist": 0.90, "latency_ms": 10, "max_payload": 1472, "reliable": False},
    "DNS": {"name": "DNS", "default_port": 53, "stealth": 0.98, "nat_pass": 0.85,
            "dpi_resist": 0.95, "latency_ms": 30, "max_payload": 253, "reliable": False},
    "HTTPS": {"name": "HTTPS", "default_port": 443, "stealth": 0.85, "nat_pass": 0.95,
              "dpi_resist": 0.70, "latency_ms": 50, "max_payload": 8192, "reliable": True},
    "WEBSOCKET": {"name": "WEBSOCKET", "default_port": 443, "stealth": 0.75, "nat_pass": 0.80,
                  "dpi_resist": 0.70, "latency_ms": 25, "max_payload": 65536, "reliable": True},
}

DEFAULT_CONFIG = {
    "version": "1.0.0",
    "mode": "standard",
    "core": {"default_ttl": 25, "max_ttl": 35, "clone_threshold": 3, "max_clones": 10},
    "crypto": {"algorithm": "AES-256-GCM", "kdf": "PBKDF2", "kdf_iterations": 100000,
               "key_length": 32, "salt_length": 32},
    "network": {"connect_timeout_sec": 5, "read_timeout_sec": 30, "keepalive_sec": 60},
    "evolution": {"enabled": True, "population_size": 50, "mutation_rate": 0.01,
                  "crossover_rate": 0.3, "fitness_threshold": 0.95},
    "mycelium": {"enabled": True, "max_spores": 10000, "spore_ttl_sec": 3600},
    "pheromones": {"enabled": True, "evaporation_rate": 0.01, "max_age_sec": 3600},
    "ai": {"enabled": True, "probability_threshold": 0.95, "max_attempts": 10},
    "logging": {"level": "INFO", "console": True, "file": True,
                "max_size_mb": 100, "max_files": 10},
    "web": {"enabled": False, "host": "0.0.0.0", "port": 8080, "websocket_port": 8765},
}


def get_mode_config(mode: str = "standard"):
    import copy
    config = copy.deepcopy(DEFAULT_CONFIG)
    config["mode"] = mode
    if mode == "high_reliability":
        config["core"]["default_ttl"] = 40
        config["ai"]["max_attempts"] = 20
    elif mode == "low_latency":
        config["core"]["default_ttl"] = 10
        config["ai"]["max_attempts"] = 5
    elif mode == "military":
        config["core"]["default_ttl"] = 60
        config["ai"]["max_attempts"] = 50
    return config


def is_root() -> bool:
    try:
        if IS_WINDOWS:
            import ctypes
            return ctypes.windll.shell32.IsUserAnAdmin() != 0
        else:
            return os.geteuid() == 0
    except Exception:
        return False
