# patch97fix.py - P97-fix: broadcast + peers
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
DD = os.path.join(ROOT, "inevionet", "network", "dead_drop.py")

BAK = ".bak_p97fix"


def patch_replace(path, replacements, label, bak=BAK):
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
        if new and new in content and (not old or old not in content):
            print("  [--] already applied")
            continue
        if old and old in content:
            content = content.replace(old, new, 1)
            changed += 1
            print("  [OK] " + old[:60].strip().replace(chr(10), ' '))
        else:
            if required:
                print("  [!!] NOT FOUND: " + old[:60].strip().replace(chr(10), ' '))
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
# 1. Пропускать broadcast в _read_feeds
# =====================================================================

print()
print("=" * 70)
print("  1. dead_drop: пропускать broadcast")
print("=" * 70)

old_filter = '''                msg = DropMessage.from_text(text)
                if msg and msg.verify() and msg.receiver == self.node_id:
                    self._handle_message(msg)
                    continue'''

new_filter = '''                msg = DropMessage.from_text(text)
                if msg and msg.verify() and (
                        msg.receiver == self.node_id or
                        msg.receiver == "broadcast"):
                    self._handle_message(msg)
                    continue'''

patch_replace(DD, [(old_filter, new_filter, True)], "broadcast filter")


# =====================================================================
# 2. Auto-register peers из feed
# =====================================================================

print()
print("=" * 70)
print("  2. dead_drop: auto-register peers из feed")
print("=" * 70)

# Смотрим _read_feeds - там уже есть register_peer для feed
# Но нужно чтобы broadcast обрабатывался

# Добавить в _handle_message: если receiver=broadcast, сохранить в inbox
old_handle = '''        with self._lock:
            self.inbox.append({
                "msg_id": msg.msg_id,
                "sender": msg.sender,
                "receiver": msg.receiver,
                "message": payload,
                "ts": msg.ts,
            })
        self._stats["received"] += 1
        logger.info("[DeadDrop] received: %s -> %s",
                    msg.sender, msg.receiver)'''

new_handle = '''        with self._lock:
            self.inbox.append({
                "msg_id": msg.msg_id,
                "sender": msg.sender,
                "receiver": msg.receiver,
                "message": payload,
                "ts": msg.ts,
            })
        self._stats["received"] += 1
        logger.info("[DeadDrop] received: %s -> %s (%d bytes)",
                    msg.sender, msg.receiver, len(payload))'''

patch_replace(DD, [(old_handle, new_handle, False)], "handle log")


# =====================================================================
# 3. merge_phase: не фильтровать по receiver
# =====================================================================

print()
print("=" * 70)
print("  3. merge_phase: проще фильтр")
print("=" * 70)

ORG = os.path.join(ROOT, "inevionet", "organism.py")

old_merge = '''                    for msg in inbox[-50:]:
                        if msg.get("receiver") not in ("broadcast", self.net.node_id):
                            continue'''

new_merge = '''                    for msg in inbox[-50:]:
                        rcv = msg.get("receiver", "")
                        # P97-fix: принимаем broadcast и свои
                        if rcv not in ("broadcast", self.net.node_id, ""):
                            continue'''

patch_replace(ORG, [(old_merge, new_merge, True)], "merge filter")


print()
print("=" * 70)
print("  PATCH 97-FIX DONE")
print("=" * 70)
print("  [OK] dead_drop: broadcast -> inbox")
print("  [OK] dead_drop: log bytes")
print("  [OK] merge_phase: проще фильтр")
print()
print("Перезапуск ОБОИХ (8080 + 8081) + 2-3 мин:")