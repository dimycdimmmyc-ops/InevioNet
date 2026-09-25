import os
import ast
import shutil

ROOT = r"E:\InevioNet"
ORG = os.path.join(ROOT, "inevionet", "organism.py")

with open(ORG, "r", encoding="utf-8") as f:
    content = f.read()

b = ORG + ".bak_p116g"
shutil.copy2(ORG, b)
print("  [BK] " + os.path.basename(b))

# Заменить _publish_map_to_dead_drop на DEBUG-версию
old_pub = '''    def _publish_map_to_dead_drop(self):
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

new_pub = '''    def _publish_map_to_dead_drop(self):
        """P116g: публикуем карту в dead_drop через publish_now."""
        logger.info("[P116g] _publish_map_to_dead_drop START")
        try:
            if not getattr(self.net, "dead_drop", None):
                logger.warning("[P116g] no dead_drop object")
                return False
            logger.info("[P116g] dead_drop OK, building map...")
            my_map = self._build_my_map_summary()
            logger.info("[P116g] map built: %d nodes", len(my_map.get("nodes", [])))
            import json as _j
            payload = _j.dumps(my_map, ensure_ascii=False)
            logger.info("[P116g] payload size: %d bytes", len(payload))
            url = self.net.dead_drop.publish_now("broadcast", payload)
            if url:
                logger.info("[P116g] map published NOW: %s", url[:60])
                return True
            logger.warning("[P116g] publish_now returned None")
            return False
        except Exception as e:
            import traceback
            logger.error("[P116g] FAILED: %s\\n%s", e, traceback.format_exc())
            return False'''

if old_pub in content:
    content = content.replace(old_pub, new_pub, 1)
    print("  [OK] _publish_map_to_dead_drop → DEBUG")
else:
    print("  [!!] anchor not found — заменим по строкам")

# В merge_phase — обернуть вызов в try с логом
old_merge = '''        # P116: публикуем карту в dead_drop
        try:
            self._publish_map_to_dead_drop()
        except Exception as e:
            logger.debug("[P116] publish DD: %s", e)'''

new_merge = '''        # P116g: публикуем карту в dead_drop
        try:
            logger.info("[P116g] calling _publish_map_to_dead_drop...")
            self._publish_map_to_dead_drop()
        except Exception as e:
            import traceback
            logger.error("[P116g] publish DD FAILED: %s\\n%s", e, traceback.format_exc())'''

if old_merge in content:
    content = content.replace(old_merge, new_merge, 1)
    print("  [OK] merge_phase → DEBUG")
else:
    print("  [!!] merge_phase anchor not found")

# Также проверим _publish_map_to_dead_drop — вызвать в scout (после сбора)
old_scout = '''        new_count = len(found)
        total_in_memory = len(self.memory["nodes"])'''

new_scout = '''        # P116g: публикуем карту в dead_drop при каждом scout
        try:
            self._publish_map_to_dead_drop()
        except Exception as _pe:
            logger.debug("[P116g] scout publish: %s", _pe)

        new_count = len(found)
        total_in_memory = len(self.memory["nodes"])'''

if old_scout in content:
    content = content.replace(old_scout, new_scout, 1)
    print("  [OK] scout → publish")

with open(ORG, "w", encoding="utf-8") as f:
    f.write(content)

try:
    ast.parse(content)
    print("  [OK] syntax organism.py")
except SyntaxError as e:
    print("  [!!] syntax: " + str(e))
    shutil.copy2(b, ORG)
    print("  [--] rolled back")

print()
print("=" * 70)
print("  PATCH 116G DONE")
print("=" * 70)
print("  [OK] _publish_map_to_dead_drop: DEBUG + traceback")
print("  [OK] merge_phase: try/except + traceback")
print("  [OK] scout: publish map каждый цикл")
print()
print("Перезапуск + логи P116g")