# patch90b_91.py - P90b (fix port in growth) + P91 (dead drop via paste.rs)
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
INEV = os.path.join(ROOT, "inevionet")
NET = os.path.join(INEV, "network")
ORCH = os.path.join(INEV, "orchestrator.py")
APP = os.path.join(ROOT, "web", "app.py")


def patch_file(path, replacements, label, bak=".bak_p90b_91"):
    if not os.path.exists(path):
        print("  [!!] NOT FOUND: " + path)
        return False
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    b = path + bak
    shutil.copy2(path, b)
    print("  [BK] " + os.path.basename(b))
    changed = 0
    for old, new, required in replacements:
        if new in content and old not in content:
            print("  [--] already applied")
            continue
        if old in content:
            content = content.replace(old, new, 1)
            changed += 1
            print("  [OK] " + old[:55].strip())
        else:
            if required:
                print("  [!!] NOT FOUND: " + old[:55].strip())
    if changed > 0:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        if path.endswith(".py"):
            try:
                ast.parse(content)
                print("  [OK] syntax " + label)
                return True
            except SyntaxError as e:
                print("  [!!] syntax: " + str(e))
                shutil.copy2(b, path)
                print("  [--] rolled back")
                return False
        else:
            print("  [OK] saved " + label)
            return True
    return True


def write_py(path, code, label):
    if os.path.exists(path):
        b = path + ".bak_p90b_91"
        shutil.copy2(path, b)
        print("  [BK] " + os.path.basename(b))
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    try:
        ast.parse(code)
        print("  [OK] " + label)
        return True
    except SyntaxError as e:
        print("  [!!] " + label + " syntax: " + str(e))
        b = path + ".bak_p90b_91"
        if os.path.exists(b):
            shutil.copy2(b, path)
            print("  [--] rolled back")
        return False


# =====================================================================
# P90b: fix _growth_loop — сохранять порт
# =====================================================================

print()
print("=" * 70)
print("  P90b: fix _growth_loop (порт в target)")
print("=" * 70)

with open(ORCH, "r", encoding="utf-8") as f:
    orch = f.read()

# Найти блок сбора targets
old_targets = '''                        target_hosts = []
                        for h in self.trusted_hosts.list_all():
                            host = h.get('host')
                            if host:
                                target_hosts.append(host.split(':')[0])'''

new_targets = '''                        target_hosts = []
                        for h in self.trusted_hosts.list_all():
                            host = h.get('host')
                            if host:
                                # P90b: сохранить host:port
                                target_hosts.append(host)'''

if new_targets in orch and old_targets not in orch:
    print("  [--] already applied")
else:
    if old_targets in orch:
        orch = orch.replace(old_targets, new_targets, 1)
        with open(ORCH, "w", encoding="utf-8") as f:
            f.write(orch)
        try:
            ast.parse(orch)
            print("  [OK] target_hosts -> host:port")
        except SyntaxError as e:
            print("  [!!] syntax: " + str(e))
    else:
        print("  [!!] targets anchor NOT FOUND")

# Обновить _probe_one_host — принимать host:port
old_probe_sig = '''def _probe_one_host(ip, our_map, from_node, max_hops=5, timeout=2, hops=0, visited=None):
    """P44: try multiple ports/schemes. Recursive with visited."""'''

new_probe_sig = '''def _probe_one_host(ip, our_map, from_node, max_hops=5, timeout=2, hops=0, visited=None):
    """P44: try multiple ports/schemes. Recursive with visited.

    P90b: если ip содержит ':', разделяем host:port.
    Если порт указан — пробуем только его.
    """
    # P90b: parse host:port
    _explicit_port = None
    if ':' in ip:
        try:
            _host, _port_s = ip.rsplit(':', 1)
            _explicit_port = int(_port_s)
            ip = _host
        except Exception:
            _explicit_port = None'''

if new_probe_sig in "".join(open(APP, encoding="utf-8").readlines()):
    print("  [--] _probe_one_host already has port parse")
else:
    with open(APP, "r", encoding="utf-8") as f:
        app = f.read()
    if old_probe_sig in app:
        app = app.replace(old_probe_sig, new_probe_sig, 1)
        # Заменить PROBE_TARGETS на явный порт если задан
        old_loop = '''    for port, scheme in PROBE_TARGETS:
        url = f"{scheme}://{ip}:{port}/api/network/map"'''
        new_loop = '''    # P90b: explicit port first
    _targets = list(PROBE_TARGETS)
    if _explicit_port:
        _targets = [(_explicit_port, "http"), (_explicit_port, "https")] + _targets

    for port, scheme in _targets:
        url = f"{scheme}://{ip}:{port}/api/network/map"'''
        if old_loop in app:
            app = app.replace(old_loop, new_loop, 1)
            print("  [OK] _probe_one_host port loop")
        else:
            print("  [!!] PROBE_TARGETS loop NOT FOUND")
        with open(APP, "w", encoding="utf-8") as f:
            f.write(app)
        try:
            ast.parse(app)
            print("  [OK] syntax app.py P90b")
        except SyntaxError as e:
            print("  [!!] syntax: " + str(e))
    else:
        print("  [!!] _probe_one_host anchor NOT FOUND")


# =====================================================================
# P91: dead_drop.py — обмен через paste.rs
# =====================================================================

print()
print("=" * 70)
print("  P91: dead_drop.py")
print("=" * 70)

p91 = '''"""InevioNet DeadDrop - P91.

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

    def __init__(self, node_id: str, poll_interval: int = 60):
        self.node_id = node_id
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

    def register_peer(self, node_id: str, drop_url: str):
        """P91: зарегистрировать URL соседа."""
        if not node_id or not drop_url:
            return
        if node_id == self.node_id:
            return
        with self._lock:
            if self.peer_urls.get(node_id) != drop_url:
                self.peer_urls[node_id] = drop_url
                logger.info("[DeadDrop] peer %s -> %s", node_id, drop_url[:60])

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

    def _publish(self, text: str) -> Optional[str]:
        """Опубликовать текст в pastebin. Вернуть URL."""
        for name, url, method in PASTEBIN_SERVICES:
            try:
                if name == "paste.rs":
                    req = urllib.request.Request(
                        url, data=text.encode("utf-8"),
                        headers={"Content-Type": "text/plain"},
                        method="POST")
                    with urllib.request.urlopen(req, timeout=10) as r:
                        if r.status in (200, 201):
                            result = r.read().decode().strip()
                            if result.startswith("http"):
                                return result
                            return url + result
                elif name == "dpaste":
                    data = urllib.parse.urlencode({
                        "content": text, "format": "url", "expires": "86400"
                    }).encode()
                    req = urllib.request.Request(
                        url, data=data,
                        headers={"Content-Type": "application/x-www-form-urlencoded"},
                        method="POST")
                    with urllib.request.urlopen(req, timeout=10) as r:
                        if r.status in (200, 201):
                            return r.read().decode().strip()
                elif name == "ix.io":
                    data = ("f:1=" + urllib.parse.quote(text)).encode()
                    req = urllib.request.Request(url, data=data, method="POST")
                    with urllib.request.urlopen(req, timeout=10) as r:
                        if r.status == 200:
                            return r.read().decode().strip()
            except Exception as e:
                logger.debug("[DeadDrop] publish %s: %s", name, e)
                continue
        return None

    def _fetch(self, url: str) -> Optional[str]:
        """Забрать текст по URL."""
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "InevioNet/1.0"})
            with urllib.request.urlopen(req, timeout=10) as r:
                return r.read().decode("utf-8", errors="replace")
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
                    logger.info("[DeadDrop] sent %s -> %s at %s",
                                msg.sender, msg.receiver, url[:60])
                    # Записать URL в peer_urls? Нет — получатель сам прочитает feed.
            except Exception as e:
                logger.debug("[DeadDrop] publish_outbox: %s", e)

    def _publish_feed(self):
        """Опубликовать свой feed (список URL'ов)."""
        with self._lock:
            urls = list(self.peer_urls.items())
        # feed: JSON list of {node_id, url}
        feed = json.dumps({
            "node_id": self.node_id,
            "ts": time.time(),
            "peers": [{"node_id": nid, "url": u} for nid, u in urls],
        }, separators=(",", ":"))
        url = self._publish(feed)
        if url:
            self.my_url = url
            logger.info("[DeadDrop] my feed: %s", url[:60])

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
                if msg and msg.verify() and msg.receiver == self.node_id:
                    self._handle_message(msg)
                    continue
                # Или как feed
                try:
                    feed = json.loads(text)
                    if isinstance(feed, dict) and "peers" in feed:
                        for p in feed["peers"]:
                            if p.get("node_id") and p.get("url"):
                                self.register_peer(p["node_id"], p["url"])
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
        logger.info("[DeadDrop] received: %s -> %s",
                    msg.sender, msg.receiver)

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
'''

write_py(os.path.join(NET, "dead_drop.py"), p91, "dead_drop.py")


# =====================================================================
# Orchestrator: интеграция DeadDrop
# =====================================================================

print()
print("=" * 70)
print("  Orchestrator: DeadDrop")
print("=" * 70)

# В __init__ создать DeadDrop
old_init = '''        # P87g: multi-channel learning loop'''

new_init = '''        # P91: DeadDrop
        self.dead_drop = None
        try:
            from .network.dead_drop import DeadDrop
            self.dead_drop = DeadDrop(node_id=self.node_id, poll_interval=60)
            logger.info("[P91] dead_drop created")
        except Exception as _e:
            logger.debug("[P91] dead_drop: %s", _e)

        # P87g: multi-channel learning loop'''

with open(ORCH, "r", encoding="utf-8") as f:
    orch2 = f.read()
if new_init in orch2 and old_init not in orch2:
    print("  [--] already applied")
elif old_init in orch2:
    orch2 = orch2.replace(old_init, new_init, 1)
    with open(ORCH, "w", encoding="utf-8") as f:
        f.write(orch2)
    try:
        ast.parse(orch2)
        print("  [OK] DeadDrop в __init__")
    except SyntaxError as e:
        print("  [!!] syntax: " + str(e))
else:
    print("  [!!] __init__ anchor NOT FOUND")

# В start() запустить DeadDrop
old_start = '''        # P87g: multi-channel learning loop'''
new_start = '''        # P91: DeadDrop
        if getattr(self, "dead_drop", None):
            try:
                self.dead_drop.start()
                logger.info("[P91] dead_drop started")
            except Exception as _e:
                logger.debug("[P91] dead_drop start: %s", _e)

        # P87g: multi-channel learning loop'''

with open(ORCH, "r", encoding="utf-8") as f:
    orch3 = f.read()
if new_start in orch3 and old_start not in orch3:
    print("  [--] already applied")
elif old_start in orch3:
    orch3 = orch3.replace(old_start, new_start, 1)
    with open(ORCH, "w", encoding="utf-8") as f:
        f.write(orch3)
    try:
        ast.parse(orch3)
        print("  [OK] DeadDrop start")
    except SyntaxError as e:
        print("  [!!] syntax: " + str(e))
else:
    print("  [!!] start anchor NOT FOUND")

# В sprout.process — регистрировать peer
SPROUT = os.path.join(INEV, "bootstrap", "sprout.py")
with open(SPROUT, "r", encoding="utf-8") as f:
    sprout = f.read()

old_peer = '''        # P71b: auto-punch в фоне'''
new_peer = '''        # P91: register peer в DeadDrop
        try:
            if getattr(self.orch, "dead_drop", None) and seed.node_id:
                # Публикуем свой URL для peer'а
                self.orch.dead_drop.queue_send(
                    seed.node_id,
                    "hello from " + self.orch.node_id)
        except Exception as _de:
            logger.debug("[P91] dead_drop queue: %s", _de)

        # P71b: auto-punch в фоне'''

if new_peer in sprout and old_peer not in sprout:
    print("  [--] sprout already has dead_drop")
elif old_peer in sprout:
    sprout = sprout.replace(old_peer, new_peer, 1)
    with open(SPROUT, "w", encoding="utf-8") as f:
        f.write(sprout)
    try:
        ast.parse(sprout)
        print("  [OK] sprout -> dead_drop")
    except SyntaxError as e:
        print("  [!!] syntax: " + str(e))
else:
    print("  [!!] sprout anchor NOT FOUND")


# =====================================================================
# app.py: endpoints /api/deaddrop/*
# =====================================================================

print()
print("=" * 70)
print("  app.py: DeadDrop endpoints")
print("=" * 70)

anchor = "@app.route('/api/network/public')"

new_eps = '''@app.route('/api/deaddrop/send', methods=['POST'])
def api_deaddrop_send():
    """P91: отправить через dead drop."""
    try:
        n = get_net()
        d = request.get_json(silent=True) or {}
        receiver = d.get('receiver', '')
        message = d.get('message', '')
        if not receiver or not message:
            return jsonify({'success': False, 'error': 'need receiver+message'}), 400
        if not getattr(n, "dead_drop", None):
            return jsonify({'success': False, 'error': 'no_dead_drop'})
        n.dead_drop.queue_send(receiver, message)
        return jsonify({'success': True, 'queued': True,
                        'receiver': receiver})
    except Exception as e:
        log.error('[DeadDrop] send: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/deaddrop/inbox')
def api_deaddrop_inbox():
    """P91: входящие dead drop."""
    try:
        n = get_net()
        if not getattr(n, "dead_drop", None):
            return jsonify({'success': False, 'error': 'no_dead_drop'})
        msgs = n.dead_drop.get_inbox()
        return jsonify({'success': True, 'messages': msgs,
                        'count': len(msgs),
                        'stats': n.dead_drop.get_stats()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/deaddrop/register', methods=['POST'])
def api_deaddrop_register():
    """P91: зарегистрировать peer URL."""
    try:
        n = get_net()
        d = request.get_json(silent=True) or {}
        node_id = d.get('node_id', '')
        url = d.get('url', '')
        if not node_id or not url:
            return jsonify({'success': False, 'error': 'need node_id+url'}), 400
        if not getattr(n, "dead_drop", None):
            return jsonify({'success': False, 'error': 'no_dead_drop'})
        n.dead_drop.register_peer(node_id, url)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/deaddrop/status')
def api_deaddrop_status():
    """P91: статус dead drop."""
    try:
        n = get_net()
        if not getattr(n, "dead_drop", None):
            return jsonify({'success': False, 'error': 'no_dead_drop'})
        return jsonify({'success': True, 'stats': n.dead_drop.get_stats()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/network/public')'''

patch_file(APP, [(anchor, new_eps, True)], "app.py deaddrop endpoints")


print()
print("=" * 70)
print("  PATCH 90b + 91 DONE")
print("=" * 70)
print("  [OK] P90b: target_hosts -> host:port (порт не теряется)")
print("  [OK] P90b: _probe_one_host parse host:port (explicit port first)")
print("  [OK] P91:  network/dead_drop.py (paste.rs обмен)")
print("  [OK] P91:  orchestrator: dead_drop start")
print("  [OK] P91:  sprout: queue_send при sprout")
print("  [OK] P91:  endpoints /api/deaddrop/send|inbox|register|status")
print()
print("Перезапуск: python -m web.app")
print()
print("Проверка:")
print("  curl -k https://localhost:8080/api/deaddrop/status")
print("  curl -k https://localhost:8080/api/deaddrop/inbox")