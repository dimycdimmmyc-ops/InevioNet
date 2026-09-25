# patch90fix.py - убрать дубликат add_wifi_devices
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
MESH = os.path.join(ROOT, "inevionet", "mesh", "network_tree.py")

with open(MESH, "r", encoding="utf-8") as f:
    content = f.read()

b = MESH + ".bak_p90fix"
shutil.copy2(MESH, b)
print("  [BK] " + os.path.basename(b))

# Считаем вхождения def add_wifi_devices
cnt = content.count("def add_wifi_devices")
print(f"  Найдено определений: {cnt}")

if cnt >= 2:
    # Найти ПОСЛЕДНЕЕ определение и удалить его до следующего def
    # Найдём все позиции
    positions = []
    start = 0
    while True:
        pos = content.find("def add_wifi_devices", start)
        if pos == -1:
            break
        positions.append(pos)
        start = pos + 1

    print(f"  Позиции: {positions}")

    # Удалим последнее (оно дубликат)
    last_pos = positions[-1]
    # Найти начало строки (отступ)
    line_start = content.rfind("\n", 0, last_pos) + 1
    # Найти следующий "def " после last_pos
    next_def = content.find("\n    def ", last_pos + 1)
    if next_def == -1:
        next_def = len(content)
    else:
        next_def += 1  # с начала строки

    # Удаляем от line_start до next_def
    removed = content[line_start:next_def]
    content = content[:line_start] + content[next_def:]
    print(f"  [OK] удалено {len(removed)} байт (последнее определение)")

    with open(MESH, "w", encoding="utf-8") as f:
        f.write(content)

    try:
        ast.parse(content)
        print("  [OK] syntax")
    except SyntaxError as e:
        print(f"  [!!] syntax: {e}")
        shutil.copy2(b, MESH)
        print("  [--] rolled back")

# Проверка
with open(MESH, "r", encoding="utf-8") as f:
    check = f.read()
print(f"  Осталось определений: {check.count('def add_wifi_devices')}")