"""InevioNet RecursiveProbe - рекурсивное зондирование подсетей.

Известные подсети:
  - своя (192.168.1.x)
  - найденные через свой роутер (SNMP routes)
  - подсети за найденными InevioNet-узлами

Для каждой подсети:
  - ping sweep
  - ARP
  - проверка открытых портов (8080, 8081 — InevioNet)
  - поиск InevioNet-узлов
"""
import os
import time
import socket
import threading
from typing import Dict, Any, List, Set, Optional

from ..core.logger import get_logger

logger = get_logger("inevionet.network.recursive_probe")


INEVIONET_PORTS = [8080, 8081, 8082, 9090, 9100, 9555]


class RecursiveProbe:
    """Рекурсивное зондирование подсетей."""

    def __init__(self, max_depth: int = 3, max_hosts: int = 512):
        self.max_depth = max_depth
        self.max_hosts = max_hosts
        self._stats = {
            "subnets_scanned": 0,
            "hosts_scanned": 0,
            "inevionet_found": 0,
            "started_at": time.time(),
        }
        self._lock = threading.Lock()

    def probe_subnet(self, subnet: str, depth: int = 0) -> Dict[str, Any]:
        """Просканировать подсеть на InevioNet-узлы."""
        if depth > self.max_depth:
            return {"subnet": subnet, "depth": depth, "skipped": True}
        with self._lock:
            self._stats["subnets_scanned"] += 1

        logger.info("[RecursiveProbe] scanning %s.x (depth=%d)", subnet, depth)

        found = []
        hosts = list(range(1, min(255, self.max_hosts + 1)))
        # быстрый probe на InevioNet-порты
        import concurrent.futures

        def probe_one(i):
            ip = subnet + "." + str(i)
            return self._probe_host(ip)

        with concurrent.futures.ThreadPoolExecutor(max_workers=64) as ex:
            results = list(ex.map(probe_one, hosts))

        for r in results:
            if r and r.get("inevionet"):
                found.append(r)
                with self._lock:
                    self._stats["inevionet_found"] += 1

        with self._lock:
            self._stats["hosts_scanned"] += len(hosts)

        return {
            "subnet": subnet,
            "depth": depth,
            "hosts": len(hosts),
            "inevionet_nodes": found,
        }

    def _probe_host(self, ip: str) -> Optional[Dict[str, Any]]:
        """Проверить один хост на InevioNet."""
        for port in INEVIONET_PORTS:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.3)
                if s.connect_ex((ip, port)) == 0:
                    s.close()
                    logger.info("[RecursiveProbe] found InevioNet-like at %s:%d",
                                ip, port)
                    return {"ip": ip, "port": port, "inevionet": True}
                s.close()
            except Exception:
                continue
        return None

    def get_stats(self) -> Dict[str, Any]:
        return {
            **self._stats,
            "uptime_sec": round(time.time() - self._stats["started_at"], 1),
        }
