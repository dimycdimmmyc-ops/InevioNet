# patch95f.py - P95f: scout (memory fallback) + логика работы с памятью
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
ORG = os.path.join(ROOT, "inevionet", "organism.py")

BAK = ".bak_p95f"


def patch_file(path, replacements, label, bak=BAK):
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
# 1. live(): работать с памятью, если found=0
# =====================================================================

print()
print("=" * 70)
print("  1. live(): memory fallback")
print("=" * 70)

old_live = '''                _t2 = time.time()
                found = self.scout()
                logger.info("[Organism] scout: %.1fs, found=%d", time.time() - _t2, len(found))

                if found:
                    _t3 = time.time()
                    for node in found:
                        plan = self.assess(node)
                        if plan.get("action"):
                            self.colonize(node, plan)
                    logger.info("[Organism] colonize: %.1fs", time.time() - _t3)'''

new_live = '''                _t2 = time.time()
                found = self.scout()
                logger.info("[Organism] scout: %.1fs, found=%d (new)",
                            time.time() - _t2, len(found))

                # P95f: если новых нет - работаем с памятью
                if not found:
                    # Берём узлы из памяти - приоритет: не колонизированные, gateway, router
                    all_nodes = list(self.memory["nodes"].values())
                    # Сортируем: сначала gateway, потом router, потом всё остальное
                    all_nodes.sort(key=lambda n: (
                        not n.get("is_gateway", False),
                        not n.get("type") in ("router", "isp_router"),
                        n.get("ip", "") in self.memory["colonized"],
                    ))
                    # Batch 100, не все сразу
                    found = all_nodes[:100]
                    logger.info("[Organism] memory fallback: %d nodes (total in memory: %d)",
                                len(found), len(self.memory["nodes"]))

                _t3 = time.time()
                new_colonized = 0
                for node in found:
                    plan = self.assess(node)
                    if plan.get("action"):
                        was_colonized = node["ip"] in self.memory["colonized"]
                        self.colonize(node, plan)
                        if not was_colonized:
                            new_colonized += 1
                logger.info("[Organism] colonize: %.1fs, new=%d",
                            time.time() - _t3, new_colonized)'''

patch_file(ORG, [(old_live, new_live, True)], "live memory fallback")


# =====================================================================
# 2. colonize(): не дублировать в память
# =====================================================================

print()
print("=" * 70)
print("  2. colonize(): не дублировать")
print("=" * 70)

old_col = '''        with self._lock:
            self.memory["colonized"].add(ip)
            self.stats["nodes_colonized"] += 1
            my_depth = self.memory["depth"].get(ip, 0)
            new_depth = my_depth + 1
            self.memory["depth"][ip] = new_depth
            if new_depth > self.stats["max_depth"]:
                self.stats["max_depth"] = new_depth'''

new_col = '''        with self._lock:
            already = ip in self.memory["colonized"]
            self.memory["colonized"].add(ip)
            if not already:
                self.stats["nodes_colonized"] += 1
            my_depth = self.memory["depth"].get(ip, 0)
            new_depth = my_depth + 1
            self.memory["depth"][ip] = new_depth
            if new_depth > self.stats["max_depth"]:
                self.stats["max_depth"] = new_depth'''

patch_file(ORG, [(old_col, new_col, True)], "colonize no duplicate")


# =====================================================================
# 3. scout(): считать новые (unseen) узлы явно
# =====================================================================

print()
print("=" * 70)
print("  3. scout(): явно считать новые")
print("=" * 70)

old_log = '''        logger.info("[Scout] lan=%d mdns=%d router=%d traceroute=%d trusted=%d total=%d",
                    c_lan, c_mdns, c_router, c_tr,
                    len([f for f in found if f.get("source") == "trusted"]),
                    len(found))
        self._log_phase("scout", 0, f"found={len(found)}")
        return found'''

new_log = '''        new_count = len(found)
        total_in_memory = len(self.memory["nodes"])
        logger.info("[Scout] new=%d (lan=%d mdns=%d router=%d traceroute=%d trusted=%d), "
                    "total_in_memory=%d",
                    new_count, c_lan, c_mdns, c_router, c_tr,
                    len([f for f in found if f.get("source") == "trusted"]),
                    total_in_memory)
        self._log_phase("scout", 0, f"new={new_count}, memory={total_in_memory}")
        return found'''

patch_file(ORG, [(old_log, new_log, True)], "scout count new")


print()
print("=" * 70)
print("  PATCH 95f DONE")
print("=" * 70)
print("  [OK] live(): memory fallback (работает с памятью, если found=0)")
print("  [OK] colonize(): не дублировать в память")
print("  [OK] scout(): явно считать new vs memory")
print()
print("Перезапуск + 60 сек:")
print("  curl -k https://localhost:8080/api/organism | python -m json.tool")