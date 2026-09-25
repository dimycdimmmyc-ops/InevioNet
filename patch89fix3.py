# patch89fix3.py - P89-fix3: удалить 3 секции из ЕЩЁ
import os
import shutil

ROOT = r"E:\InevioNet"
HTML = os.path.join(ROOT, "web", "templates", "index.html")

with open(HTML, "r", encoding="utf-8") as f:
    lines = f.readlines()

b = HTML + ".bak_p89fix3"
shutil.copy2(HTML, b)
print("  [BK] " + os.path.basename(b))

# Найти все card-title + следующий sep
sections = []
for i, line in enumerate(lines):
    if 'card-title' in line and 'advanced-toggle' not in line:
        # Найти следующий sep
        for j in range(i, min(i + 60, len(lines))):
            if 'sep"' in lines[j]:
                sections.append((i, j))
                break

print(f"  Найдено секций: {len(sections)}")
for idx, (s, e) in enumerate(sections):
    # Определим по emoji-позиции (первые 3 символа после emoji)
    # Определим по позиции:
    # 0: Сканеры, 1: Анонимность, 2: P2P, 3: Мицелий, 4: AI, 5: Bootstrap, 6: Gravity, 7: Капсулы
    # Но сейчас порядок может быть другим
    # Определим по индексу строки
    print(f"    [{idx}] line {s+1} -> sep {e+1}")

# Найдём секции для удаления: Анонимность, P2P, AI
# По прошлому выводу: 380 (Анонимность), 387 (P2P), 403 (AI)
# Но после patch89fix2 могли быть вставки — проверим по номерам

# Анонимность: содержит checkTor()
# P2P: содержит bridgeRegion
# AI: содержит aiBestName

to_delete = []
for idx, (s, e) in enumerate(sections):
    block = ''.join(lines[s:e+1])
    if 'checkTor' in block or 'checkI2P' in block:
        to_delete.append(('Анонимность', s, e))
    elif 'bridgeRegion' in block or 'becomeVolunteer' in block:
        to_delete.append(('P2P Мост', s, e))
    elif 'aiBestName' in block or 'loadAIStats' in block:
        to_delete.append(('AI Селектор', s, e))

print()
print(f"  К удалению: {len(to_delete)}")
for name, s, e in to_delete:
    print(f"    {name}: {s+1}-{e+1}")

# Удалить в обратном порядке (от конца к началу)
to_delete.sort(key=lambda x: -x[1])
for name, s, e in to_delete:
    end = e + 1
    if end < len(lines) and lines[end].strip() == '':
        end += 1
    del lines[s:end]
    print(f"  [OK] удалено {name}: {e-s+1} строк")

with open(HTML, "w", encoding="utf-8") as f:
    f.writelines(lines)
print("  [OK] saved")

# Проверка
with open(HTML, "r", encoding="utf-8") as f:
    check = f.read()
print("  checkTor: " + str('checkTor' not in check))
print("  bridgeRegion: " + str('bridgeRegion' not in check))
print("  aiBestName: " + str('aiBestName' not in check))
print("  publishSeed: " + str('publishSeed' in check))