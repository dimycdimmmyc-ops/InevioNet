# patch97.py - P97: Merge карт между организмами
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
ORG = os.path.join(ROOT, "inevionet", "organism.py")

BAK = ".bak_p97"


def patch_by_lines(path, replacements, label):
    if not os.path.exists(path):
        print("  [!!] NOT FOUND: " + path)
        return False
    with open(path, "r", encoding="utf-8") as f:
        lines = f.readlines()
    
    b = path + BAK
    shutil.copy2(path, b)
    print("  [BK] " + os.path.basename(b))
    
    for start, end, new_text in sorted(replacements, key=lambda x: -x[0]):
        new_lines = [l + "\n" for l in new_text.split("\n")]
        if new_lines and new_lines[-1] == "\n":
            new_lines = new_lines[:-1]
        lines[start-1:end] = new_lines
        print("  [OK] lines {}-{} -> {} lines".format(start, end, len(new_lines)))
    
    content = "".join(lines)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    
    try:
        ast.parse(content)
        print("  [OK] syntax " + label)
        return True
    except SyntaxError as e:
        print("  [!!] syntax: " + str(e))
        shutil.copy2(b, path)
        print("  [--] rolled back")
        return False


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
# 1. Добавить методы export_map, merge_remote_map, merge_phase
# =====================================================================

print()
print("=" * 70)
print("  1. Методы merge: export_map, merge_remote_map, merge_phase")
print("=" * 70)

# Найти якорь - def communicate или def expand
with open(ORG, "r", encoding="utf-8") as f:
    lines = f.readlines()

# Найти def expand - вставим merge методы ПЕРЕД ним
anchor_line = None
for i, line in enumerate(lines):
    if line.strip() == "def expand(self):":
        anchor_line = i + 1  # 1-based
        break

if anchor_line:
    merge_methods = '''    # =================================================================
    # P97: MERGE КАРТ (между организмами в разных сетях)
    # =================================================================

    def export_map(self):
        """P97: экспорт карты для отправки другому организму."""
        return {
            "node_id": self.net.node_id,
            "ts": time.time(),
            "nodes": list(self.memory["nodes"].values()),
            "colonized": list(self.memory["colonized"]),
            "depth": dict(self.memory["depth"]),
            "taught": list(self.memory["taught"]),
            "relayed": list(self.memory.get("relayed_ips", set())),
            "capsuled": list(self.memory.get("capsuled_ips", set())),
            "stats": {
                "nodes_found": self.stats.get("nodes_found", 0),
                "nodes_taught": self.stats.get("nodes_taught", 0),
                "nodes_relayed": self.stats.get("nodes_relayed", 0),
                "max_depth": self.stats.get("max_depth", 0),
            },
        }

    def merge_remote_map(self, remote_map):
        """P97: merge карты от другого организма."""
        if not remote_map or not isinstance(remote_map, dict):
            return 0
        remote_id = remote_map.get("node_id", "")
        if remote_id == self.net.node_id:
            return 0  # это мы
        added = 0
        updated = 0
        try:
            # === Nodes ===
            for node in remote_map.get("nodes", []):
                ip = node.get("ip")
                if not ip:
                    continue
                if ip not in self.memory["nodes"]:
                    # Новый узел от другого организма
                    node = dict(node)
                    node["via_organism"] = remote_id
                    node["source"] = "merge:" + str(node.get("source", "?"))
                    node["depth"] = int(node.get("depth", 1)) + 1
                    node["merged_at"] = time.time()
                    with self._lock:
                        self.memory["nodes"][ip] = node
                    added += 1
                else:
                    # Обновить last_seen
                    with self._lock:
                        self.memory["nodes"][ip]["last_seen"] = time.time()
                        self.memory["nodes"][ip]["via_organism"] = remote_id
                    updated += 1
            
            # === Colonized ===
            remote_colonized = set(remote_map.get("colonized", []))
            before = len(self.memory["colonized"])
            with self._lock:
                self.memory["colonized"].update(remote_colonized)
            colonized_added = len(self.memory["colonized"]) - before
            
            # === Taught ===
            remote_taught = set(remote_map.get("taught", []))
            with self._lock:
                self.memory["taught"].update(remote_taught)
            
            # === Relayed ===
            remote_relayed = set(remote_map.get("relayed", []))
            if "relayed_ips" not in self.memory:
                self.memory["relayed_ips"] = set()
            with self._lock:
                self.memory["relayed_ips"].update(remote_relayed)
            
            # === Depth ===
            for ip, d in (remote_map.get("depth") or {}).items():
                cur = self.memory["depth"].get(ip, 999)
                new_d = int(d) + 1
                if new_d < cur:
                    self.memory["depth"][ip] = new_d
                    if new_d > self.stats.get("max_depth", 0):
                        self.stats["max_depth"] = new_d
            
            # === Stats ===
            with self._lock:
                self.stats["maps_merged"] = self.stats.get("maps_merged", 0) + 1
                self.stats["nodes_from_merge"] = self.stats.get("nodes_from_merge", 0) + added
            
            logger.info("[Merge] from %s: +%d new, ~%d upd, colonized+%d",
                        remote_id, added, updated, colonized_added)
            return added
        except Exception as e:
            logger.error("[Merge] %s: %s", remote_id, e)
            return 0

    def merge_phase(self):
        """P97: фаза merge - экспорт + broadcast + приём."""
        try:
            # 1. Экспорт своей карты
            my_map = self.export_map()
            
            # 2. Публикация через dead_drop
            if hasattr(self.net, "dead_drop") and self.net.dead_drop:
                try:
                    self.net.dead_drop.queue_send(
                        receiver="broadcast",
                        message=json.dumps(my_map, default=str))
                except Exception as e:
                    logger.debug("[Merge] broadcast: %s", e)
            
            # 3. Приём чужих карт из dead_drop inbox
            if hasattr(self.net, "dead_drop") and self.net.dead_drop:
                try:
                    inbox = self.net.dead_drop.get_inbox() or []
                    merged = 0
                    for msg in inbox[-50:]:
                        if msg.get("receiver") not in ("broadcast", self.net.node_id):
                            continue
                        try:
                            remote_map = json.loads(msg.get("message", "{}"))
                            if isinstance(remote_map, dict) and "node_id" in remote_map:
                                n = self.merge_remote_map(remote_map)
                                merged += n
                        except Exception:
                            pass
                    if merged:
                        logger.info("[Merge] merged +%d nodes from inbox", merged)
                except Exception as e:
                    logger.debug("[Merge] inbox: %s", e)
            
            self._log_phase("merge", 0, f"maps_merged={self.stats.get('maps_merged', 0)}")
        except Exception as e:
            logger.debug("[Merge] phase: %s", e)

'''
    
    patch_by_lines(ORG, [(anchor_line, anchor_line, merge_methods)], "merge methods")
else:
    print("  [!!] def expand not found")


# =====================================================================
# 2. Добавить json import (если нет)
# =====================================================================

print()
print("=" * 70)
print("  2. Import json")
print("=" * 70)

with open(ORG, "r", encoding="utf-8") as f:
    content = f.read()

if "import json" not in content.split("\n\n")[0]:
    if "import json" not in content[:2000]:
        content = content.replace(
            "import time\nimport threading",
            "import time\nimport json\nimport threading",
            1)
        with open(ORG, "w", encoding="utf-8") as f:
            f.write(content)
        try:
            ast.parse(content)
            print("  [OK] import json added")
        except SyntaxError as e:
            print("  [!!] syntax: " + str(e))
    else:
        print("  [--] json already imported")
else:
    print("  [--] json already imported")


# =====================================================================
# 3. Добавить merge_phase в live()
# =====================================================================

print()
print("=" * 70)
print("  3. merge_phase в live()")
print("=" * 70)

old_live = '''                # === P96-v2: COMMUNICATE через СВОИ каналы ===
                _t3b = time.time()
                self.communicate(found[:20])
                logger.info("[Organism] communicate: %.1fs", time.time() - _t3b)'''

new_live = '''                # === P96-v2: COMMUNICATE через СВОИ каналы ===
                _t3b = time.time()
                self.communicate(found[:20])
                logger.info("[Organism] communicate: %.1fs", time.time() - _t3b)

                # === P97: MERGE карт ===
                _t3c = time.time()
                self.merge_phase()
                logger.info("[Organism] merge: %.1fs", time.time() - _t3c)'''

patch_replace(ORG, [(old_live, new_live, True)], "merge in live")


# =====================================================================
# 4. Добавить в stats: maps_merged, nodes_from_merge
# =====================================================================

print()
print("=" * 70)
print("  4. stats: maps_merged")
print("=" * 70)

old_stats = '''            "stego_sent": 0,
            "mask_applied": 0,
            "webrtc_sent": 0,
            "industrial_probed": 0,
            "started_at": time.time(),'''

new_stats = '''            "stego_sent": 0,
            "mask_applied": 0,
            "webrtc_sent": 0,
            "industrial_probed": 0,
            "maps_merged": 0,
            "nodes_from_merge": 0,
            "started_at": time.time(),'''

patch_replace(ORG, [(old_stats, new_stats, True)], "stats merge")


print()
print("=" * 70)
print("  PATCH 97 DONE")
print("=" * 70)
print("  [OK] export_map() - экспорт карты")
print("  [OK] merge_remote_map() - merge чужой карты")
print("  [OK] merge_phase() - broadcast + приём")
print("  [OK] live(): + фаза merge")
print("  [OK] stats: maps_merged, nodes_from_merge")
print()
print("Перезапуск + 90 сек:")
print("  curl -k https://localhost:8080/api/organism | python -m json.tool")