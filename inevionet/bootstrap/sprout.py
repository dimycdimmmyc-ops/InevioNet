"""InevioNet Sprout - прорастание."""
import time
import threading
from typing import Optional, List, Dict, Any

from ..core.logger import get_logger

logger = get_logger("inevionet.bootstrap.sprout")


class Sprout:
    def __init__(self, orchestrator):
        self.orch = orchestrator

    def process(self, seed) -> bool:
        if not seed.verify():
            logger.debug("[Sprout] bad signature: %s", seed.node_id)
            return False
        if seed.is_expired():
            logger.debug("[Sprout] expired: %s", seed.node_id)
            return False
        if seed.node_id == getattr(self.orch, "node_id", ""):
            return False
        host = str(seed.public_ip) + ":" + str(seed.public_port)
        try:
            ok = self.orch.trusted_hosts.add(host, label=seed.node_id, method="sprout")
            if not ok:
                return False
        except Exception as e:
            logger.debug("[Sprout] trust error: %s", e)
            return False
        try:
            self.orch.mycelium.pheromones.mark_transit(
                source=self.orch.node_id,
                destination=seed.node_id,
                via=seed.node_id,
                path=[self.orch.node_id, seed.node_id])
        except Exception as e:
            logger.debug("[Sprout] pheromone: %s", e)
        logger.info("[Sprout] sprouted %s at %s (nat=%s)",
                    seed.node_id, host, seed.nat_type)

        # P77g: audit sprout
        try:
            if getattr(self.orch, "audit", None):
                self.orch.audit.add_event("sprout", {
                    "peer_node": seed.node_id,
                    "peer_addr": host,
                    "nat_type": seed.nat_type,
                })
        except Exception:
            pass

        # P91: register peer в DeadDrop
        try:
            if getattr(self.orch, "dead_drop", None) and seed.node_id:
                # Публикуем свой URL для peer'а
                self.orch.dead_drop.queue_send(
                    seed.node_id,
                    "hello from " + self.orch.node_id)
        except Exception as _de:
            logger.debug("[P91] dead_drop queue: %s", _de)

        # P71b: auto-punch в фоне
        try:
            import threading as _th
            def _auto_punch():
                try:
                    from ..network.udp import UDPHolePuncher
                    p = UDPHolePuncher()
                    p.discover_public()
                    result = p.punch_bidirectional(
                        (seed.public_ip, seed.public_port),
                        attempts=20, interval=0.25)
                    p.close()
                    if result:
                        logger.info("[Sprout] auto-punched %s", seed.node_id)
                        try:
                            self.orch.gravity.add_mass(seed.node_id, 1.0)
                        except Exception:
                            pass
                except Exception as _pe:
                    logger.debug("[Sprout] auto-punch: %s", _pe)
            _th.Thread(target=_auto_punch, daemon=True,
                       name="sprout_punch").start()
        except Exception as _e:
            logger.debug("[Sprout] auto-punch thread: %s", _e)

        return True


class SproutEngine:
    def __init__(self, orchestrator, check_interval=300):
        self.orch = orchestrator
        self.check_interval = check_interval
        self._sprout = Sprout(orchestrator)
        self._running = False
        self._thread = None
        self._pending_urls: List[str] = []
        self._sprouted: List[str] = []
        self._stats = {"fetched": 0, "sprouted": 0, "failed": 0,
                       "started_at": time.time()}

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True, name="sprout_engine")
        self._thread.start()
        logger.info("[Sprout] engine started")

    def stop(self):
        self._running = False
        logger.info("[Sprout] engine stopped")

    def add_url(self, url: str):
        if url and url not in self._pending_urls:
            self._pending_urls.append(url)
            logger.info("[Sprout] queued url: %s", url)

    def add_urls_multi(self, text_or_urls):
        """P75: добавить несколько URL (из текста или списка)."""
        from .seed import SeedFetcher
        if isinstance(text_or_urls, str):
            urls = SeedFetcher().guess_urls_from_text(text_or_urls)
            if not urls and text_or_urls.startswith("http"):
                urls = [text_or_urls]
        else:
            urls = list(text_or_urls)
        for u in urls:
            self.add_url(u)
        return len(urls)

    def add_seed(self, seed):
        if self._sprout.process(seed):
            self._stats["sprouted"] += 1
            self._sprouted.append(seed.node_id)
            return True
        self._stats["failed"] += 1
        return False

    def _loop(self):
        from .seed import SeedFetcher
        fetcher = SeedFetcher()
        while self._running:
            try:
                urls = list(self._pending_urls)
                self._pending_urls.clear()
                for url in urls:
                    seed = fetcher.fetch(url)
                    self._stats["fetched"] += 1
                    if seed:
                        if self._sprout.process(seed):
                            self._stats["sprouted"] += 1
                            self._sprouted.append(seed.node_id)
                        else:
                            self._stats["failed"] += 1
                    else:
                        self._stats["failed"] += 1
            except Exception as e:
                logger.debug("[Sprout] loop error: %s", e)
            time.sleep(self.check_interval)

    def get_stats(self) -> Dict[str, Any]:
        return {
            **self._stats,
            "running": self._running,
            "pending": len(self._pending_urls),
            "sprouted_ids": self._sprouted[-20:],
            "uptime_sec": round(time.time() - self._stats["started_at"], 1),
        }