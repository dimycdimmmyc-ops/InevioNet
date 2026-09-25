import os
import ast
import shutil

ROOT = r"E:\InevioNet"
DD = os.path.join(ROOT, "inevionet", "network", "dead_drop.py")

with open(DD, "r", encoding="utf-8") as f:
    content = f.read()

b = DD + ".bak_p117b"
shutil.copy2(DD, b)
print("  [BK] " + os.path.basename(b))

# Найти __init__ DeadDrop и добавить recent_cards
old_init = '''        self.my_url: str = ""
        # Уже прочитанные сообщения
        self._seen_ids: set = set()'''

new_init = '''        self.my_url: str = ""
        # P117b: recent_cards для feed
        from collections import deque as _deque
        self.recent_cards = _deque(maxlen=10)
        # Уже прочитанные сообщения
        self._seen_ids: set = set()'''

if old_init in content:
    content = content.replace(old_init, new_init, 1)
    print("  [OK] recent_cards добавлен в __init__")
else:
    print("  [--] anchor not found — пробуем другой")

# Fallback: искать любой __init__ в DeadDrop
if old_init not in content:
    # Ищем "self.my_url"
    lines = content.split("\n")
    for i, line in enumerate(lines):
        if "self.my_url" in line and "=" in line:
            # Добавить после этой строки
            lines.insert(i + 1, "        from collections import deque as _deque")
            lines.insert(i + 2, "        self.recent_cards = _deque(maxlen=10)")
            content = "\n".join(lines)
            print("  [OK] recent_cards добавлен после self.my_url")
            break

# Добавить import deque в начало
if "from collections import deque" not in content[:2000]:
    if "import threading" in content:
        content = content.replace("import threading",
                                   "import threading\nfrom collections import deque", 1)
        print("  [OK] import deque добавлен")

with open(DD, "w", encoding="utf-8") as f:
    f.write(content)

try:
    ast.parse(content)
    print("  [OK] syntax dead_drop.py")
except SyntaxError as e:
    print("  [!!] syntax: " + str(e))
    shutil.copy2(b, DD)
    print("  [--] rolled back")

# Проверка
with open(DD, "r", encoding="utf-8") as f:
    check = f.read()
print("  recent_cards есть: " + str("recent_cards" in check))

print()
print("=" * 70)
print("  PATCH 117B DONE")
print("=" * 70)
print("  [OK] recent_cards в DeadDrop.__init__")
print()
print("Перезапуск + тест")