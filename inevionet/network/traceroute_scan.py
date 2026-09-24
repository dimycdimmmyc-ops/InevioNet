"""InevioNet TracerouteScan - глубина через интернет.

Запускает traceroute до внешних целей. Каждый hop -> узел дерева.
Глубина 10-15 реальна. Работает без доступа к роутеру.

Цели: 8.8.8.8, 1.1.1.1, ya.ru, google.com.
"""
import os
import re
import time
import subprocess
import threading
from typing import List, Dict, Any, Optional

from ..core.logger import get_logger

logger = get_logger("inevionet.network.traceroute_scan")


# P95: сокращённый список для Organism (10 targets - быстро)
DEFAULT_TARGETS = [
    "8.8.8.8", "8.8.4.4",
    "1.1.1.1",
    "77.88.8.8",
    "9.9.9.9",
    "ya.ru",
    "mts.ru",
    "google.com",
    "github.com",
    "cloudflare.com",
]

# Регулярки для парсинга вывода traceroute
HOP_PATTERNS = [
    # Linux/Unix: " 1  192.168.1.1  1.234 ms"
    re.compile(r"^\s*(\d+)\s+([\d.]+|\*)\s+([\d.]+)\s*ms"),
    # Windows: "  1     1 ms     1 ms     1 ms  192.168.1.1"
    re.compile(r"^\s*(\d+)\s+.*?\s+([\d.]+)\s*$"),
    # Windows с timeout: "  1     *        *        *     Request timed out."
    re.compile(r"^\s*(\d+)\s+.*?timed out"),
]


class TracerouteScan:
    """Traceroute до внешних целей."""

    def __init__(self, timeout: float = 30.0, max_hops: int = 20):
        self.timeout = timeout
        self.max_hops = max_hops
        self._stats = {
            "scans": 0,
            "hops_total": 0,
            "unique_routers": set(),
            "started_at": time.time(),
        }
        self._lock = threading.Lock()

    def scan(self, target: str = "8.8.8.8") -> Dict[str, Any]:
        """Traceroute до цели."""
        with self._lock:
            self._stats["scans"] += 1

        logger.info("[Traceroute] %s (max %d hops)", target, self.max_hops)

        hops = []
        try:
            if os.name == "nt":
                # Windows: tracert -h 20 -w 1000 target
                cmd = ["tracert", "-h", str(self.max_hops),
                       "-w", "1000", "-d", target]
                r = subprocess.run(
                    cmd, capture_output=True, timeout=self.timeout,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
                output = r.stdout.decode("cp866", errors="replace")
            else:
                # Linux: traceroute -n -m 20 -w 1 target
                cmd = ["traceroute", "-n", "-m", str(self.max_hops),
                       "-w", "1", target]
                r = subprocess.run(
                    cmd, capture_output=True, timeout=self.timeout)
                output = r.stdout.decode("utf-8", errors="replace")
        except subprocess.TimeoutExpired:
            logger.warning("[Traceroute] timeout for %s", target)
            return {"target": target, "hops": hops, "error": "timeout"}
        except Exception as e:
            logger.error("[Traceroute] error: %s", e)
            return {"target": target, "hops": hops, "error": str(e)}

        # Парсинг вывода
        for line in output.splitlines():
            for pat in HOP_PATTERNS:
                m = pat.match(line)
                if m:
                    try:
                        hop_num = int(m.group(1))
                        ip = m.group(2) if m.lastindex >= 2 else "*"
                        if ip == "*":
                            break
                        hops.append({
                            "hop": hop_num,
                            "ip": ip,
                            "target": target,
                        })
                        with self._lock:
                            self._stats["hops_total"] += 1
                            self._stats["unique_routers"].add(ip)
                    except Exception:
                        pass
                    break

        # dedupe по IP, но сохранить минимальный hop
        seen = {}
        for h in hops:
            ip = h["ip"]
            if ip not in seen or h["hop"] < seen[ip]["hop"]:
                seen[ip] = h
        hops = sorted(seen.values(), key=lambda x: x["hop"])

        return {"target": target, "hops": hops, "error": None}

    def scan_multi(self, targets: List[str] = None) -> Dict[str, Any]:
        """Traceroute до нескольких целей."""
        if not targets:
            targets = DEFAULT_TARGETS
        all_hops = {}
        for t in targets:
            try:
                result = self.scan(t)
                for h in result.get("hops", []):
                    ip = h["ip"]
                    if ip not in all_hops or h["hop"] < all_hops[ip]["hop"]:
                        all_hops[ip] = h
            except Exception as e:
                logger.debug("[Traceroute] %s: %s", t, e)
        return {
            "targets": targets,
            "hops": sorted(all_hops.values(), key=lambda x: x["hop"]),
            "unique_routers": len(all_hops),
        }

    def get_stats(self) -> Dict[str, Any]:
        return {
            "scans": self._stats["scans"],
            "hops_total": self._stats["hops_total"],
            "unique_routers": len(self._stats["unique_routers"]),
            "started_at": self._stats["started_at"],
        }
