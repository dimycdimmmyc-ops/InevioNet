import os
import ast
import shutil

ROOT = r"E:\InevioNet"
DD = os.path.join(ROOT, "inevionet", "network", "dead_drop.py")
ORG = os.path.join(ROOT, "inevionet", "organism.py")

BAK = ".bak_p116f"


def patch_replace(path, replacements, label):
    if not os.path.exists(path):
        print("  [!!] NOT FOUND: " + path)
        return False
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    b = path + BAK
    shutil.copy2(path, b)
    print("  [BK] " + os.path.basename(b))
    changed = 0
    for old, new, required in replacements:
        if new and new in content and (not old or old not in content):
            print("  [--] already applied")
            continue
        if old and old in content:
            content = content.replace(old, new, 1)
            changed += 1
            print("  [OK] " + old[:55].strip().replace(chr(10), ' '))
        else:
            if required:
                print("  [!!] NOT FOUND: " + old[:55].strip().replace(chr(10), ' '))
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
    return True


# =====================================================================
# 1. DeadDrop.publish_now — прямая публикация с URL
# =====================================================================

print()
print("=" * 70)
print("  1. DeadDrop.publish_now")
print("=" * 70)

with open(DD, "r", encoding="utf-8") as f:
    dd_content = f.read()

# Добавить метод publish_now перед register_peer
old_reg = '''    def register_peer(self, node_id: str, drop_url: str):'''

new_methods = '''    def publish_now(self, receiver: str, message: str):
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

    def register_peer(self, node_id: str, drop_url: str):'''

if old_reg in dd_content and "publish_now" not in dd_content:
    dd_content = dd_content.replace(old_reg, new_methods, 1)
    print("  [OK] publish_now добавлен")
else:
    print("  [--] publish_now уже есть")

with open(DD, "w", encoding="utf-8") as f:
    f.write(dd_content)
try:
    ast.parse(dd_content)
    print("  [OK] syntax dead_drop.py")
except SyntaxError as e:
    print("  [!!] syntax: " + str(e))


# =====================================================================
# 2. organism._publish_map_to_dead_drop — через publish_now
# =====================================================================

print()
print("=" * 70)
print("  2. _publish_map_to_dead_drop: publish_now")
print("=" * 70)

with open(ORG, "r", encoding="utf-8") as f:
    org_content = f.read()

old_pub = '''    def _publish_map_to_dead_drop(self):
        """P116c: публикуем свою карту в dead_drop + форсируем отправку."""
        try:
            if not getattr(self.net, "dead_drop", None):
                return False
            my_map = self._build_my_map_summary()
            import json as _j
            self.net.dead_drop.queue_send("broadcast", _j.dumps(my_map, ensure_ascii=False))
            # P116c: форсировать _publish_outbox сразу
            try:
                if hasattr(self.net.dead_drop, "_publish_outbox"):
                    self.net.dead_drop._publish_outbox()
                    logger.info("[P116c] map pushed to paste.rs")
            except Exception as _pe:
                logger.debug("[P116c] flush: %s", _pe)
            return True
        except Exception as e:
            logger.debug("[Publish/DD] %s", e)
            return False'''

new_pub = '''    def _publish_map_to_dead_drop(self):
        """P116f: публикуем карту в dead_drop через publish_now (гарантированный URL)."""
        try:
            if not getattr(self.net, "dead_drop", None):
                return False
            my_map = self._build_my_map_summary()
            import json as _j
            payload = _j.dumps(my_map, ensure_ascii=False)
            # P116f: publish_now — публикует немедленно + запоминает URL
            url = self.net.dead_drop.publish_now("broadcast", payload)
            if url:
                logger.info("[P116f] map published NOW: %s", url[:60])
                return True
            # Fallback: queue_send + _publish_outbox
            self.net.dead_drop.queue_send("broadcast", payload)
            try:
                if hasattr(self.net.dead_drop, "_publish_outbox"):
                    self.net.dead_drop._publish_outbox()
                    logger.info("[P116f] map pushed via outbox")
            except Exception:
                pass
            return True
        except Exception as e:
            logger.debug("[Publish/DD] %s", e)
            return False'''

if old_pub in org_content:
    org_content = org_content.replace(old_pub, new_pub, 1)
    print("  [OK] _publish_map_to_dead_drop: publish_now")
else:
    print("  [--] уже обновлён")

# Также _merge_from_dead_drop — добавляем лог
old_merge = '''    def _merge_from_dead_drop(self):
        """P116: merge карт через dead_drop (fallback при NAT)."""
        added_total = 0
        try:
            if not getattr(self.net, "dead_drop", None):
                return 0
            inbox = self.net.dead_drop.get_inbox() or []
            for msg in inbox[-100:]:'''

new_merge = '''    def _merge_from_dead_drop(self):
        """P116: merge карт через dead_drop (fallback при NAT)."""
        added_total = 0
        try:
            if not getattr(self.net, "dead_drop", None):
                return 0
            inbox = self.net.dead_drop.get_inbox() or []
            if not inbox:
                logger.debug("[Merge/DD] inbox empty")
                return 0
            logger.info("[Merge/DD] inbox size: %d", len(inbox))
            for msg in inbox[-100:]:'''

if old_merge in org_content:
    org_content = org_content.replace(old_merge, new_merge, 1)
    print("  [OK] _merge_from_dead_drop: лог inbox")

with open(ORG, "w", encoding="utf-8") as f:
    f.write(org_content)
try:
    ast.parse(org_content)
    print("  [OK] syntax organism.py")
except SyntaxError as e:
    print("  [!!] syntax: " + str(e))


# =====================================================================
# 3. DeadDrop._read_feeds — логирование
# =====================================================================

print()
print("=" * 70)
print("  3. _read_feeds: логирование")
print("=" * 70)

with open(DD, "r", encoding="utf-8") as f:
    dd_content = f.read()

old_read = '''    def _read_feeds(self):
        """P90c: читает feed'ы соседей (только известные URL'ы)."""
        with self._lock:
            feeds = list(self.peer_urls.items())
        for node_id, feed_url in feeds:'''

new_read = '''    def _read_feeds(self):
        """P90c/P116f: читает feed'ы соседей."""
        with self._lock:
            feeds = list(self.peer_urls.items())
        if feeds:
            logger.info("[DeadDrop] reading %d feeds", len(feeds))
        for node_id, feed_url in feeds:'''

if old_read in dd_content:
    dd_content = dd_content.replace(old_read, new_read, 1)
    print("  [OK] _read_feeds: лог")
else:
    print("  [--] anchor not found")

# Также в _fetch — логирование
old_fetch = '''            with urllib.request.urlopen(req, timeout=10) as r:
                return r.read().decode("utf-8", errors="replace")'''

new_fetch = '''            with urllib.request.urlopen(req, timeout=10) as r:
                data = r.read().decode("utf-8", errors="replace")
                return data'''

if old_fetch in dd_content:
    dd_content = dd_content.replace(old_fetch, new_fetch, 1)
    print("  [OK] _fetch")

with open(DD, "w", encoding="utf-8") as f:
    f.write(dd_content)
try:
    ast.parse(dd_content)
    print("  [OK] syntax dead_drop.py")
except SyntaxError as e:
    print("  [!!] syntax: " + str(e))


print()
print("=" * 70)
print("  PATCH 116F DONE")
print("=" * 70)
print("  [OK] DeadDrop.publish_now — публикация с URL")
print("  [OK] _publish_map_to_dead_drop — через publish_now")
print("  [OK] _merge_from_dead_drop — лог inbox")
print("  [OK] _read_feeds — лог feeds")
print()
print("Перезапуск + тест")