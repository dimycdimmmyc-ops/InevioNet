import os
import ast
import shutil

ROOT = r"E:\InevioNet"
APP = os.path.join(ROOT, "web", "app.py")
DD = os.path.join(ROOT, "inevionet", "network", "dead_drop.py")
ORG = os.path.join(ROOT, "inevionet", "organism.py")

BAK = ".bak_p116c"


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
# 1. dead_drop.register_peer — сразу публикует feed
# =====================================================================

print()
print("=" * 70)
print("  1. dead_drop.register_peer → _publish_feed")
print("=" * 70)

with open(DD, "r", encoding="utf-8") as f:
    dd_content = f.read()

old_reg = '''    def register_peer(self, node_id: str, drop_url: str):
        """P91: зарегистрировать URL соседа."""
        if not node_id or not drop_url:
            return
        if node_id == self.node_id:
            return
        with self._lock:
            if self.peer_urls.get(node_id) != drop_url:
                self.peer_urls[node_id] = drop_url
                logger.info("[DeadDrop] peer %s -> %s", node_id, drop_url[:60])'''

new_reg = '''    def register_peer(self, node_id: str, drop_url: str):
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
                logger.debug("[DeadDrop] republish: %s", e)'''

patch_replace(DD, [(old_reg, new_reg, False)], "register_peer publish")


# =====================================================================
# 2. app.py /api/dht/bootstrap — публикация своей карты сразу
# =====================================================================

print()
print("=" * 70)
print("  2. /api/dht/bootstrap: publish map")
print("=" * 70)

with open(APP, "r", encoding="utf-8") as f:
    app_content = f.read()

old_bootstrap2 = '''            elif node_id and not dd_url:
                log.warning("[P116b] NO dead_drop_url in peer %s", node_id)
            # P116: добавляем в trusted_hosts
            pub_ip = parsed.get("public_ip", "")
            pub_port = parsed.get("public_port", 0)
            if node_id and pub_ip and pub_port:
                try:
                    n.trusted_hosts.add("%s:%d" % (pub_ip, int(pub_port)),
                                        label=node_id, method="dht")
                except Exception:
                    pass'''

new_bootstrap2 = '''            elif node_id and not dd_url:
                log.warning("[P116b] NO dead_drop_url in peer %s", node_id)
            # P116c: сразу опубликовать свою карту в dead_drop
            if getattr(n, "organism", None):
                try:
                    n.organism._publish_map_to_dead_drop()
                    log.info("[P116c] map published to dead_drop after bootstrap")
                except Exception as _pe:
                    log.debug("[P116c] publish: %s", _pe)
            # P116: добавляем в trusted_hosts
            pub_ip = parsed.get("public_ip", "")
            pub_port = parsed.get("public_port", 0)
            if node_id and pub_ip and pub_port:
                try:
                    n.trusted_hosts.add("%s:%d" % (pub_ip, int(pub_port)),
                                        label=node_id, method="dht")
                except Exception:
                    pass'''

patch_replace(APP, [(old_bootstrap2, new_bootstrap2, False)], "bootstrap publish map")


# =====================================================================
# 3. organism._publish_map_to_dead_drop — с queue_send сразу
# =====================================================================

print()
print("=" * 70)
print("  3. _publish_map_to_dead_drop: queue + flush")
print("=" * 70)

with open(ORG, "r", encoding="utf-8") as f:
    org_content = f.read()

old_pub = '''    def _publish_map_to_dead_drop(self):
        """P116: публикуем свою карту в dead_drop (broadcast)."""
        try:
            if not getattr(self.net, "dead_drop", None):
                return False
            my_map = self._build_my_map_summary()
            import json as _j
            self.net.dead_drop.queue_send("broadcast", _j.dumps(my_map, ensure_ascii=False))
            return True
        except Exception as e:
            logger.debug("[Publish/DD] %s", e)
            return False'''

new_pub = '''    def _publish_map_to_dead_drop(self):
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

patch_replace(ORG, [(old_pub, new_pub, False)], "publish_map flush")


print()
print("=" * 70)
print("  PATCH 116C DONE")
print("=" * 70)
print("  [OK] register_peer → сразу публикует feed")
print("  [OK] /api/dht/bootstrap → publish map сразу")
print("  [OK] _publish_map_to_dead_drop → flush outbox")
print()
print("Перезапуск обоих + обмен JSON")