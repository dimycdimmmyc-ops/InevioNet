"""🍄 InevioNet Autonomous Mode (P8).

Дрон автономен:
  - Работает БЕЗ интернета.
  - Копит сообщения в outbox.
  - Синхронизируется при появлении сети.
  - Помнит всё (findings, peers).

Философия:
  - Закон 1: узел в эфире = узел живой.
  - Закон 3: найденный узел не исчезает.
  - Закон 5: сеть помнит всё.
"""
import json
import time
import threading
from pathlib import Path
from typing import Dict, Any, List, Optional

import logging
log = logging.getLogger("inevionet.drone.autonomous")


class AutonomousMode:
    """Офлайн-режим + очередь + синхронизация."""

    MAX_OUTBOX = 500
    OUTBOX_TTL = 7 * 24 * 3600.0

    def __init__(self, node_id: str, data_dir: Path):
        self.node_id = node_id
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.outbox_file = self.data_dir / "outbox.json"
        self.inbox_file = self.data_dir / "inbox.json"
        self.findings_file = self.data_dir / "findings.json"

        self._outbox: List[Dict[str, Any]] = []
        self._inbox: List[Dict[str, Any]] = []
        self._lock = threading.RLock()

        self._load()

    # ==============================================================
    # OUTBOX
    # ==============================================================
    def add_to_outbox(self, receiver: str, message: str,
                      metadata: Optional[Dict[str, Any]] = None) -> bool:
        if not receiver or message is None:
            return False
        with self._lock:
            self._outbox.append({
                "receiver": receiver,
                "message": message,
                "metadata": metadata or {},
                "ts": time.time(),
                "attempts": 0,
            })
            self._prune_outbox()
            self._save_outbox()
        return True

    def outbox_size(self) -> int:
        with self._lock:
            return len(self._outbox)

    def flush_outbox(self, sender_callback=None) -> int:
        if sender_callback is None:
            return 0
        sent = 0
        with self._lock:
            remaining = []
            for item in self._outbox:
                try:
                    ok = sender_callback(item["receiver"], item["message"])
                    if ok:
                        sent += 1
                    else:
                        item["attempts"] = item.get("attempts", 0) + 1
                        if item["attempts"] < 5:
                            remaining.append(item)
                except Exception as e:
                    log.debug("[Autonomous] flush item: %s", e)
                    remaining.append(item)
            self._outbox = remaining
            self._save_outbox()
        return sent

    def _prune_outbox(self):
        now = time.time()
        self._outbox = [
            item for item in self._outbox
            if now - item.get("ts", 0) < self.OUTBOX_TTL
        ]
        if len(self._outbox) > self.MAX_OUTBOX:
            self._outbox = self._outbox[-self.MAX_OUTBOX:]

    def _save_outbox(self):
        try:
            self.outbox_file.write_text(
                json.dumps(self._outbox[-self.MAX_OUTBOX:], ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            log.debug("[Autonomous] save outbox: %s", e)

    def _load_outbox(self):
        if not self.outbox_file.exists():
            return
        try:
            data = json.loads(self.outbox_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                self._outbox = data
        except Exception as e:
            log.debug("[Autonomous] load outbox: %s", e)

    # ==============================================================
    # INBOX
    # ==============================================================
    def add_to_inbox(self, sender: str, message: str,
                     metadata: Optional[Dict[str, Any]] = None) -> bool:
        if not sender or message is None:
            return False
        with self._lock:
            self._inbox.append({
                "sender": sender,
                "message": message,
                "metadata": metadata or {},
                "ts": time.time(),
            })
            if len(self._inbox) > self.MAX_OUTBOX:
                self._inbox = self._inbox[-self.MAX_OUTBOX:]
            self._save_inbox()
        return True

    def get_inbox(self, limit: int = 50) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self._inbox[-limit:])

    def _save_inbox(self):
        try:
            self.inbox_file.write_text(
                json.dumps(self._inbox[-self.MAX_OUTBOX:], ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            log.debug("[Autonomous] save inbox: %s", e)

    def _load_inbox(self):
        if not self.inbox_file.exists():
            return
        try:
            data = json.loads(self.inbox_file.read_text(encoding="utf-8"))
            if isinstance(data, list):
                self._inbox = data
        except Exception as e:
            log.debug("[Autonomous] load inbox: %s", e)

    # ==============================================================
    # MEMORY
    # ==============================================================
    def remember_finding(self, signal: Dict[str, Any]) -> bool:
        if not signal:
            return False
        try:
            data = {}
            if self.findings_file.exists():
                try:
                    data = json.loads(
                        self.findings_file.read_text(encoding="utf-8"))
                except Exception:
                    data = {}
            findings = data.get("findings", [])
            findings.append({"signal": signal, "ts": time.time()})
            findings = findings[-1000:]
            data["findings"] = findings
            data["last_update"] = time.time()
            self.findings_file.write_text(
                json.dumps(data, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return True
        except Exception as e:
            log.debug("[Autonomous] remember: %s", e)
            return False

    # ==============================================================
    # STATS
    # ==============================================================
    def get_stats(self) -> Dict[str, Any]:
        return {
            "outbox": self.outbox_size(),
            "inbox": len(self._inbox),
            "findings_file": str(self.findings_file) if self.findings_file.exists() else None,
            "data_dir": str(self.data_dir),
        }

    def _load(self):
        self._load_outbox()
        self._load_inbox()
        log.info("[Autonomous] загружено: outbox=%d inbox=%d",
                 len(self._outbox), len(self._inbox))