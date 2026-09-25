import os
import ast
import shutil

ROOT = r"E:\InevioNet"
ORG = os.path.join(ROOT, "inevionet", "organism.py")

with open(ORG, "r", encoding="utf-8") as f:
    content = f.read()

b = ORG + ".bak_p116h"
shutil.copy2(ORG, b)
print("  [BK] " + os.path.basename(b))

# 1. Заменить _append(nodes, x) → nodes = nodes + [x]
old_append1 = '''            nodes = _append(nodes, {
                "ip": ip,
                "type": node.get("type", "device"),
                "depth": node.get("depth", 1),
                "source": node.get("source", "?"),
                "vendor": node.get("vendor", ""),
                "nlp_plan": node.get("nlp_plan", ""),
                "can_teach": node.get("can_teach", False),
                "can_relay": node.get("can_relay", False),
            })'''

new_append1 = '''            nodes = nodes + [{
                "ip": ip,
                "type": node.get("type", "device"),
                "depth": node.get("depth", 1),
                "source": node.get("source", "?"),
                "vendor": node.get("vendor", ""),
                "nlp_plan": node.get("nlp_plan", ""),
                "can_teach": node.get("can_teach", False),
                "can_relay": node.get("can_relay", False),
            }]'''

if old_append1 in content:
    content = content.replace(old_append1, new_append1, 1)
    print("  [OK] _append → + [x]")
else:
    print("  [--] _append уже заменён или другой формат")

# 2. Найти все остальные _append в organism.py и заменить
import re
# Найти все _append( что не в def _append
count = 0
while True:
    m = re.search(r'_append\(([^,]+),\s*', content)
    if not m:
        break
    # Пропускаем если это определение функции
    if 'def _append' in content[:m.start()][-100:]:
        break
    # Простая замена: _append(a, b) → a + [b]
    # Но это сложно без парсинга. Проще добавить функцию _append в начало organism.py.
    break

# 3. Проще — добавить _append и _copy в начало organism.py (после импортов)
if 'def _append(' not in content:
    old_imports = '''from .core.logger import get_logger

logger = get_logger("inevionet.organism")'''

    new_imports = '''from .core.logger import get_logger

logger = get_logger("inevionet.organism")


# ============================================================
# Авторские утилиты (P116h)
# ============================================================

def _append(lst, x):
    """Список + элемент (авторски, без list.append)."""
    n = len(lst)
    new_lst = [None] * (n + 1)
    for i in range(n):
        new_lst[i] = lst[i]
    new_lst[n] = x
    return new_lst


def _copy(d):
    """Копия словаря (авторски, без dict.copy)."""
    new_d = {}
    for k in d:
        new_d[k] = d[k]
    return new_d'''

    if old_imports in content:
        content = content.replace(old_imports, new_imports, 1)
        print("  [OK] _append + _copy добавлены в organism.py")
    else:
        print("  [!!] imports anchor not found")

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
print("  PATCH 116H DONE")
print("=" * 70)
print("  [OK] _append + _copy добавлены в organism.py")
print()
print("Перезапуск + тест")