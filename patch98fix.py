# patch98fix.py - P98-fix: NLP после регистрации в памяти
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
ORG = os.path.join(ROOT, "inevionet", "organism.py")

BAK = ".bak_p98fix"


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


# 1. Найти NLP-блок и заменить: анализировать memory["nodes"], не found
print()
print("=" * 70)
print("  1. NLP: анализировать memory после регистрации")
print("=" * 70)

# Смотрим текущий код
with open(ORG, "r", encoding="utf-8") as f:
    content = f.read()

# Найти блок P98 в scout
old_nlp = '''        # P98: НЛП-анализ найденных узлов (для агентов спор)
        try:
            from .nlp.pipeline import spore_analyze_node
            nlp_count = 0
            for node in found:
                try:
                    nlp_res = spore_analyze_node(node)
                    node["nlp_plan"] = nlp_res.get("plan", "route")
                    node["nlp_confidence"] = nlp_res.get("confidence", 0.5)
                    node["nlp_rapport"] = nlp_res.get("rapport")
                    node["nlp_controllable"] = nlp_res.get("controllable")
                    node["nlp_leading"] = nlp_res.get("leading")
                    if "nlp_plan" in node and node["nlp_plan"] != "route":
                        nlp_count += 1
                except Exception as e:
                    logger.debug("[NLP] %s: %s", node.get("ip"), e)
            if nlp_count:
                logger.info("[NLP] analyzed %d nodes, non-route plans=%d",
                            len(found), nlp_count)
        except ImportError:
            logger.debug("[NLP] pipeline not available")
        except Exception as e:
            logger.debug("[NLP] scout: %s", e)
'''

new_nlp = '''        # P98-fix: НЛП-анализ через memory["nodes"] (после регистрации)
        try:
            from .nlp.pipeline import spore_analyze_node
            nlp_count = 0
            analyzed = 0
            with self._lock:
                for ip, node in list(self.memory["nodes"].items()):
                    # Пропускаем уже проанализированные
                    if node.get("nlp_plan"):
                        continue
                    try:
                        nlp_res = spore_analyze_node(node)
                        node["nlp_plan"] = nlp_res.get("plan", "route")
                        node["nlp_confidence"] = nlp_res.get("confidence", 0.5)
                        node["nlp_rapport"] = nlp_res.get("rapport")
                        node["nlp_controllable"] = nlp_res.get("controllable")
                        node["nlp_leading"] = nlp_res.get("leading")
                        analyzed += 1
                        if node["nlp_plan"] != "route":
                            nlp_count += 1
                    except Exception as e:
                        logger.debug("[NLP] %s: %s", ip, e)
            if analyzed:
                logger.info("[NLP] analyzed %d nodes in memory, non-route=%d",
                            analyzed, nlp_count)
        except ImportError:
            logger.debug("[NLP] pipeline not available")
        except Exception as e:
            logger.debug("[NLP] scout: %s", e)
'''

patch_replace(ORG, [(old_nlp, new_nlp, True)], "NLP через memory")


# 2. Также: если узел уже проанализирован, не перезаписывать при регистрации
print()
print("=" * 70)
print("  2. Регистрация: не перезаписывать nlp_* поля")
print("=" * 70)

# Проверим, есть ли такой код
if 'node.get("nlp_plan")' in content and 'memory["nodes"][node["ip"]] = {' in content:
    # Найдём блок регистрации
    old_reg = '''                self.memory["nodes"][node["ip"]] = {
                    **node,
                    "discovered_at": time.time(),
                    "last_seen": time.time(),
                    "score": 0.0,
                    "can_teach": False, "can_relay": False, "can_capsule": False,
                }'''
    
    new_reg = '''                # P98-fix: сохранить nlp_* поля если уже есть
                _existing = self.memory["nodes"].get(node["ip"], {})
                _entry = {
                    **node,
                    "discovered_at": _existing.get("discovered_at", time.time()),
                    "last_seen": time.time(),
                    "score": _existing.get("score", 0.0),
                    "can_teach": _existing.get("can_teach", False),
                    "can_relay": _existing.get("can_relay", False),
                    "can_capsule": _existing.get("can_capsule", False),
                }
                # Сохранить NLP-поля
                for _k in ("nlp_plan", "nlp_confidence", "nlp_rapport",
                           "nlp_controllable", "nlp_leading"):
                    if _k in _existing and _k not in _entry:
                        _entry[_k] = _existing[_k]
                self.memory["nodes"][node["ip"]] = _entry'''
    
    if old_reg in content:
        patch_replace(ORG, [(old_reg, new_reg, False)], "registration preserves nlp")
    else:
        print("  [--] registration block not found (skip)")
else:
    print("  [--] already handled or different structure")


print()
print("=" * 70)
print("  PATCH 98-FIX DONE")
print("=" * 70)
print()
print("Проверка:")
print("  Стоп + перезапуск")
print("  Ждём 60 сек")
print("  python _check_nlp_plans.py")