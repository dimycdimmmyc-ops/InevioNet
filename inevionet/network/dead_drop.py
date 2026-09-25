"""InevioNet DeadDrop - P91.

Обмен сообщениями через paste.rs без прямого P2P.

Как работает:
  PC-A -> paste.rs (publish URL) -> PC-B
  PC-B -> paste.rs (publish URL) -> PC-A

Каждый узел:
  1. Периодически публикует свой inbox URL в paste.rs.
  2. Периодически читает paste.rs/feed с URL'ами соседей.
  3. Забирает сообщения из URL'ов.

Автоматически, без ручного вмешательства.
"""
import os
import time
import json
import base64
import hashlib
import hmac
import threading
from collections import deque
import urllib.request
import urllib.parse
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field, asdict

from ..core.logger import get_logger
from ..bootstrap.seed import SEED_SECRET

logger = get_logger("inevionet.network.dead_drop")


# Публичные pastebin для dead drop
PASTEBIN_SERVICES = [
    ("paste.rs", "https://paste.rs/", "PUT"),
    ("dpaste", "https://dpaste.com/api/v2/", "POST"),
    ("ix.io", "http://ix.io", "POST"),
]


@dataclass
class DropMessage:
    """Сообщение в dead drop."""
    msg_id: str = ""
    sender: str = ""
    receiver: str = ""
    payload: str = ""  # base64
    ts: float = 0.0
    signature: str = ""

    def __post_init__(self):
        if not self.msg_id:
            self.msg_id = hashlib.sha256(
                f"{self.sender}:{self.receiver}:{time.time()}".encode()
            ).hexdigest()[:16]
        if self.ts == 0.0:
            self.ts = time.time()

    def sign(self) -> str:
        data = f"{self.msg_id}:{self.sender}:{self.receiver}:{self.payload}:{self.ts}"
        self.signature = hmac.new(
            SEED_SECRET.encode(), data.encode(), hashlib.sha256
        ).hexdigest()[:16]
        return self.signature

    def verify(self) -> bool:
        if not self.signature:
            return False
        data = f"{self.msg_id}:{self.sender}:{self.receiver}:{self.payload}:{self.ts}"
        expected = hmac.new(
            SEED_SECRET.encode(), data.encode(), hashlib.sha256
        ).hexdigest()[:16]
        return hmac.compare_digest(self.signature, expected)

    def to_text(self) -> str:
        """Текст для публикации."""
        d = asdict(self)
        # compact JSON
        return json.dumps(d, separators=(",", ":"))

    @classmethod
    def from_text(cls, text: str) -> Optional["DropMessage"]:
        try:
            d = json.loads(text.strip())
            return cls(**d)
        except Exception:
            return None


class DeadDrop:
    """Dead drop через paste.rs.

    Каждый узел:
      - публикует свой drop URL (inbox)
      - читает drop URL других узлов
      - обменивается сообщениями
    """

    def __init__(self, node_id: str, poll_interval: int = 60, serial: str = ""):
        self.node_id = node_id
        self.serial = serial
        self.poll_interval = poll_interval
        self._running = False
        self._thread = None
        self._lock = threading.Lock()

        # URL'ы узлов (node_id -> drop_url)
        self.peer_urls: Dict[str, str] = {}
        # Входящие сообщения
        self.inbox: List[Dict[str, Any]] = []
        # Исходящие (ожидают публикации)
        self.outbox: List[DropMessage] = []
        # Мой публичный drop URL
        self.my_url: str = ""
        from collections import deque as _deque
        self.recent_cards = _deque(maxlen=10)
        # P117b: recent_cards для feed
        from collections import deque as _deque
        self.recent_cards = _deque(maxlen=10)
        # Уже прочитанные сообщения
        self._seen_ids: set = set()

        self._stats = {
            "published": 0,
            "received": 0,
            "sent": 0,
            "errors": 0,
        }

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._loop, daemon=True, name="dead_drop")
        self._thread.start()
        logger.info("[DeadDrop] started for %s (interval=%ds)",
                    self.node_id, self.poll_interval)

    def stop(self):
        self._running = False
        logger.info("[DeadDrop] stopped")

    def queue_send(self, receiver: str, message: str):
        """P91: положить сообщение в outbox для отправки."""
        payload_b64 = base64.b64encode(message.encode("utf-8")).decode()
        msg = DropMessage(
            sender=self.node_id,
            receiver=receiver,
            payload=payload_b64,
        )
        msg.sign()
        with self._lock:
            self.outbox.append(msg)
        logger.info("[DeadDrop] queued: %s -> %s", self.node_id, receiver)

    def publish_now(self, receiver: str, message: str):
        """P116f: публикует немедленно, возвращает URL или None."""
        try:
            msg = DropMessage(
                sender=self.node_id,
                receiver=receiver,
                payload=base64.b64encode(message.encode("utf-8")).decode(),
            )
            msg.sign()
            url = self._publish(msg.to_text())
            if url:
                self._stats["sent"] += 1
                with self._lock:
                    self.recent_cards.append(url)
                logger.info("[DeadDrop] PUBLISH_NOW: %s -> %s at %s",
                            self.node_id, receiver, url[:60])
                return url
            logger.warning("[DeadDrop] PUBLISH_NOW: _publish returned None")
            return None
        except Exception as e:
            logger.error("[DeadDrop] publish_now: %s", e)
            return None

    def register_peer(self, node_id: str, drop_url: str):
        """P91/P116c: зарегистрировать URL соседа + сразу обновить feed."""
        if not node_id or not drop_url:
            return
        if node_id == self.node_id:
            return
        changed = False
        with self._lock:
            if self.peer_urls.get(node_id) != drop_url:
                self.peer_urls[node_id] = drop_url
                changed = True
                logger.info("[DeadDrop] peer %s -> %s", node_id, drop_url[:60])
        # P116c: сразу опубликовать feed с новым peer
        if changed:
            try:
                self._publish_feed()
                logger.info("[DeadDrop] feed republished (peer added)")
            except Exception as e:
                logger.debug("[DeadDrop] republish: %s", e)

    def _loop(self):
        # первый запуск — через 10 сек
        time.sleep(10)
        while self._running:
            try:
                # 1. Опубликовать свои исходящие
                self._publish_outbox()
                # 2. Опубликовать свой inbox URL (feed)
                self._publish_feed()
                # 3. Прочитать feed соседей
                self._read_feeds()
            except Exception as e:
                logger.debug("[DeadDrop] loop: %s", e)
                self._stats["errors"] += 1
            time.sleep(self.poll_interval)

    def _publish(self, text: str):
        """P117: публикует через ротацию paste-сервисов."""
        # P117: список сервисов (ротация)
        services = [
            ("paste.rs", self._publish_paste_rs),
            ("dpaste.com", self._publish_dpaste),
            ("termbin.com", self._publish_termbin),
            ("sprunge.us", self._publish_sprunge),
            ("ix.io", self._publish_ix_io),
        ]
        # Начинаем с последнего успешного
        last = getattr(self, "_last_paste_service", 0)
        # Пробуем все, начиная с last
        for offset in range(len(services)):
            idx = (last + offset) % len(services)
            name, fn = services[idx]
            try:
                url = fn(text)
                if url:
                    self._last_paste_service = idx
                    logger.debug("[DeadDrop] published via %s: %s", name, url[:60])
                    return url
            except Exception as e:
                logger.debug("[DeadDrop] %s failed: %s", name, e)
                continue
        logger.warning("[DeadDrop] ALL paste services failed")
        return None

    def _publish_paste_rs(self, text: str):
        """paste.rs"""
        req = urllib.request.Request(
            "https://paste.rs", data=text.encode("utf-8"),
            headers={"Content-Type": "text/plain"}, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            if r.status in (200, 201):
                result = r.read().decode().strip()
                if result.startswith("http"):
                    return result
                return "https://paste.rs/" + result
        return None

    def _publish_dpaste(self, text: str):
        """dpaste.com (POST form)"""
        data = urllib.parse.urlencode({
            "content": text,
            "format": "url",
            "expires": "86400",
        }).encode()
        req = urllib.request.Request(
            "https://dpaste.com/api/v2/", data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            if r.status in (200, 201):
                return r.read().decode().strip()
        return None

    def _publish_termbin(self, text: str):
        """termbin.com (netcat-style, TCP)"""
        import socket as _sock
        s = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
        s.settimeout(10)
        try:
            s.connect(("termbin.com", 9999))
            s.sendall(text.encode("utf-8"))
            s.shutdown(_sock.SHUT_WR)
            data = b""
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                data += chunk
            result = data.decode("utf-8", errors="replace").strip()
            if result.startswith("http"):
                return result
            return None
        finally:
            s.close()

    def _publish_sprunge(self, text: str):
        """sprunge.us"""
        data = urllib.parse.urlencode({"sprunge": text}).encode()
        req = urllib.request.Request(
            "http://sprunge.us", data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            if r.status == 200:
                result = r.read().decode().strip()
                if result.startswith("http"):
                    return result
        return None

    def _publish_ix_io(self, text: str):
        """ix.io (POST form)"""
        data = urllib.parse.urlencode({"f:1": text}).encode()
        req = urllib.request.Request(
            "http://ix.io", data=data, method="POST")
        with urllib.request.urlopen(req, timeout=10) as r:
            if r.status == 200:
                result = r.read().decode().strip()
                if result.startswith("http"):
                    return result
        return None

    def _fetch(self, url: str) -> Optional[str]:
        """Забрать текст по URL."""
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "InevioNet/1.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                data = r.read().decode("utf-8", errors="replace")
                return data
        except Exception as e:
            logger.debug("[DeadDrop] fetch %s: %s", url[:60], e)
            return None

    def _publish_outbox(self):
        """Опубликовать исходящие сообщения."""
        with self._lock:
            messages = list(self.outbox)
            self.outbox.clear()
        for msg in messages:
            try:
                url = self._publish(msg.to_text())
                if url:
                    self._stats["sent"] += 1
                    # P97-fix3: запомнить URL карты
                    try:
                        with self._lock:
                            self.recent_cards.append(url)
                    except Exception:
                        pass
                    logger.info("[DeadDrop] sent %s -> %s at %s",
                                msg.sender, msg.receiver, url[:60])
                    # Записать URL в peer_urls? Нет — получатель сам прочитает feed.
            except Exception as e:
                logger.debug("[DeadDrop] publish_outbox: %s", e)

    def _publish_feed(self):
        """P97-fix3: feed с cards (URL последних карт)."""
        with self._lock:
            urls = list(self.peer_urls.items())
            cards = list(self.recent_cards)[-5:] if hasattr(self, "recent_cards") else []
        feed = json.dumps({
            "node_id": self.node_id,
            "serial": getattr(self, "serial", ""),
            "ts": time.time(),
            "my_url": self.my_url,
            "peers": [{"node_id": nid, "url": u} for nid, u in urls],
            "cards": cards,
        }, separators=(",", ":"))
        url = self._publish(feed)
        if url:
            self.my_url = url
            logger.info("[DeadDrop] my feed: %s (peers=%d, cards=%d)",
                        url[:60], len(urls), len(cards))
    def _read_feeds(self):
        """Прочитать feed'ы соседей (только известные URL'ы)."""
        with self._lock:
            feeds = list(self.peer_urls.items())
        for node_id, feed_url in feeds:
            try:
                text = self._fetch(feed_url)
                if not text:
                    continue
                # Попробовать как DropMessage
                msg = DropMessage.from_text(text)
                if msg and msg.verify() and (
                        msg.receiver == self.node_id or
                        msg.receiver == "broadcast"):
                    self._handle_message(msg)
                    continue
                # Или как feed
                try:
                    feed = json.loads(text)
                    if isinstance(feed, dict):
                        # P97-fix3: читаем cards
                        for card_url in feed.get("cards", []):
                            if card_url and card_url not in self._seen_ids:
                                self._seen_ids.add(card_url)
                                card_text = self._fetch(card_url)
                                if card_text:
                                    card_msg = DropMessage.from_text(card_text)
                                    if card_msg and card_msg.verify():
                                        if (card_msg.receiver == self.node_id or
                                                card_msg.receiver == "broadcast"):
                                            self._handle_message(card_msg)
                                            continue
                        # Читаем peers
                        for p in feed.get("peers", []):
                            if p.get("node_id") and p.get("url"):
                                self.register_peer(p["node_id"], p["url"])
                        # P101: авто-подписка на feed от sender (my_url)
                        sender = feed.get("node_id", "")
                        peer_my_url = feed.get("my_url", "")
                        if sender and peer_my_url and sender != self.node_id:
                            # Если у нас есть свежий URL peer — обновить
                            with self._lock:
                                current = self.peer_urls.get(sender, "")
                            if current != peer_my_url:
                                self.register_peer(sender, peer_my_url)
                                logger.info("[DeadDrop] auto-subscribe %s -> %s",
                                            sender, peer_my_url[:60])
                        # P101: читаем cards из feed
                        for card_url in feed.get("cards", []):
                            if card_url and card_url not in self._seen_ids:
                                self._seen_ids.add(card_url)
                                card_text = self._fetch(card_url)
                                if card_text:
                                    card_msg = DropMessage.from_text(card_text)
                                    if card_msg and card_msg.verify():
                                        if (card_msg.receiver == self.node_id or
                                                card_msg.receiver == "broadcast"):
                                            self._handle_message(card_msg)
                except Exception:
                    pass
            except Exception as e:
                logger.debug("[DeadDrop] read %s: %s", node_id, e)

    def _handle_message(self, msg: DropMessage):
        """Обработать входящее сообщение."""
        if msg.msg_id in self._seen_ids:
            return
        self._seen_ids.add(msg.msg_id)
        try:
            payload = base64.b64decode(msg.payload).decode("utf-8")
        except Exception:
            payload = msg.payload
        with self._lock:
            self.inbox.append({
                "msg_id": msg.msg_id,
                "sender": msg.sender,
                "receiver": msg.receiver,
                "message": payload,
                "ts": msg.ts,
            })
        self._stats["received"] += 1
        logger.info("[DeadDrop] received: %s -> %s (%d bytes)",
                    msg.sender, msg.receiver, len(payload))

    def get_inbox(self) -> List[Dict[str, Any]]:
        with self._lock:
            return list(self.inbox)

    def clear_inbox(self):
        with self._lock:
            self.inbox.clear()

    def get_stats(self) -> Dict[str, Any]:
        return {
            **self._stats,
            "running": self._running,
            "peers": len(self.peer_urls),
            "inbox_size": len(self.inbox),
            "outbox_size": len(self.outbox),
            "my_url": self.my_url,
        }
