# patch89fix2.py - P89-fix2: HTML строго по номерам строк
import os
import shutil

ROOT = r"E:\InevioNet"
HTML = os.path.join(ROOT, "web", "templates", "index.html")

with open(HTML, "r", encoding="utf-8") as f:
    lines = f.readlines()

b = HTML + ".bak_p89fix2"
shutil.copy2(HTML, b)
print("  [BK] " + os.path.basename(b))
print(f"  Всего строк: {len(lines)}")

# Проверим текущие строки 380, 387, 403, 397
for idx in [379, 380, 384, 385, 386, 387, 395, 396, 397, 401, 402, 403, 420, 421]:
    if idx < len(lines):
        print(f"  {idx+1}: {lines[idx].rstrip()[:80]}")

# Определим границы через содержимое (без emoji — по тексту)
# Ищем "card-title" с русским текстом (порченным):
# 380: card-title ... <span class="emoji">...</span> РђРЅРѕРЅРёРјРЅРѕСЃС‚СЊ
# Проверим ASCII-часть: "card-title" + позиция

# Найти строки card-title в диапазоне 358-440
print()
print("  Card-title в диапазоне 358-440:")
for i in range(358, min(440, len(lines))):
    if 'card-title' in lines[i] and 'advanced-toggle' not in lines[i]:
        # Определим какая секция по позиции
        print(f"  {i+1}: {lines[i].rstrip()[:100]}")

# Найдём секции для удаления по НОМЕРАМ (из вывода выше):
# 380 = Анонимность, 387 = P2P Мост, 403 = AI Селектор
# Но лучше найти их по отсутствию эмодзи 🔑 или по позиции

# Найдём строку "РњРёС†РµР»РёР№" (Мицелий) — она НЕ порчена? Нет, тоже порчена.
# Используем позицию: 397 (из прошлого вывода)

# Проверим, что сейчас на строках 380, 387, 397, 403
targets = {}
for i in range(360, min(440, len(lines))):
    line = lines[i]
    if 'card-title' in line and 'advanced-toggle' not in line:
        # Определим тип секции по длине и содержимому
        # Сканеры (366), Анонимность (380), P2P Мост (387), Мицелий (397), AI (403), Капсулы (422), Лог (434)
        targets[i] = line

print()
print("  Найдено card-title:")
for i, line in sorted(targets.items()):
    print(f"  {i+1}: len={len(line)}")

# Определим по позициям из прошлого вывода:
# Сканеры: 366, Анонимность: 380, P2P: 387, Мицелий: 397, AI: 403, Капсулы: 422, Лог: 434
# Но после patch89fix.py могли сдвинуться. Проверим:
print()
print("  Текущие секции (по номерам, найденным по card-title):")

# Ищем card-title и следующие sep"
sections = []
card_indices = sorted(targets.keys())
for ci in card_indices:
    # Найдём следующий sep" после ci
    for j in range(ci, min(ci + 60, len(lines))):
        if 'sep"' in lines[j]:
            sections.append((ci, j))
            break

for s, e in sections:
    print(f"    card {s+1} -> sep {e+1} ({e-s+1} строк)")

# Определим какие удалить: 2-я (Анонимность), 3-я (P2P), 5-я (AI)
# 1-я = Сканеры (оставить)
# 2-я = Анонимность (удалить)
# 3-я = P2P Мост (удалить)
# 4-я = Мицелий (оставить)
# 5-я = AI (удалить)
# 6-я = Капсулы (оставить)
# 7-я = Лог (оставить)

if len(sections) >= 7:
    # Удалить в обратном порядке (5, 3, 2)
    to_delete = [4, 2, 1]  # индексы 0-based (5-я=4, 3-я=2, 2-я=1)
    print()
    print("  Удаляем секции:")
    for di in sorted(to_delete, reverse=True):
        s, e = sections[di]
        # Удалить от s до e+1 (sep) + пустая строка если есть
        end = e + 1
        if end < len(lines) and lines[end].strip() == '':
            end += 1
        name = ["Сканеры", "Анонимность", "P2P Мост", "Мицелий", "AI", "Капсулы", "Лог"][di]
        del lines[s:end]
        print(f"  [OK] удалено {name}: {s+1}-{end}")

    # Найти Мицелий (после удаления он сдвинулся)
    # Ищем card-title "РњРёС†РµР»РёР№" — нет, ищем по позиции: 4-я секция = Мицелий
    # После удаления 3 секций, Мицелий должен быть на позиции sections[3][0] - (удалённые до неё)

    # Проще — искать card-title, у которого emoji-код содержит байты Мицелия
    # Или ещё проще — вставить Bootstrap/Gravity ПЕРЕД Капсулами (по позиции)
    # Капсулы = последняя из "старых" card-title перед Лог
    # Найдём card-title "РљР°РїСЃСѓР»С" (Капсулы) — по позиции последний перед Лог

    # Найдём Капсулы = 6-я секция. После удаления 3 она стала 4-й.
    # Найдём card-title, у которого следующий sep содержит "AI" НЕТ...
    # Проще — вставить Bootstrap перед card-title "Капсулы" по позиции.
    # Найдём "РљР°РїСЃСѓР»С" — кириллица порчена, но emoji 🌐 → рџЊђ

    # Самый простой способ — искать по счётчику: 4-я card-title после удаления = Капсулы
    # Тогда вставим перед ней
    card_after = []
    for i, line in enumerate(lines):
        if 'card-title' in line and 'advanced-toggle' not in line:
            card_after.append(i)
    print()
    print(f"  Осталось card-title: {len(card_after)}")

    # 4-я = Капсулы (после удаления: Сканеры, Мицелий, Капсулы, Лог)
    if len(card_after) >= 3:
        # Вставить перед Капсулами (индекс 2, т.к. Сканеры=0, Мицелий=1, Капсулы=2)
        insert_before = card_after[2]
        # Найти пустую строку перед ней или sep"
        # Отступаем на 1-2 строки назад до sep" или пустой
        ins = insert_before
        while ins > 0 and lines[ins-1].strip() != '' and 'sep"' not in lines[ins-1]:
            ins -= 1

        new_block = '''        <div class="card-title" style="font-size:0.9em;margin-bottom:8px"><span class="emoji">\U0001f511</span> Bootstrap</div>
        <button class="btn btn-success" onclick="publishSeed()">Publish Seed</button>
        <button class="btn btn-glass" onclick="bootstrapStatus()">Status</button>
        <div class="form-group" style="margin-top:6px"><label>Seed URL</label><input id="sproutUrl" placeholder="https://paste.rs/..."></div>
        <button class="btn btn-glass" onclick="sproutUrl()">Sprout</button>
        <div id="bootstrapResult" style="margin-top:8px;font-size:0.8em;color:var(--dim)"></div>

        <div class="sep"></div>

        <div class="card-title" style="font-size:0.9em;margin-bottom:8px"><span class="emoji">\U0001f300</span> Gravity + Audit</div>
        <button class="btn btn-glass" onclick="showGravity()">Gravity field</button>
        <button class="btn btn-glass" onclick="showAudit()">Audit log</button>
        <button class="btn btn-glass" onclick="verifyAudit()">Verify Audit</button>
        <div id="gravityResult" style="margin-top:8px;font-size:0.8em;color:var(--dim)"></div>
        <div id="auditResult" style="margin-top:4px;font-size:0.75em;color:var(--dim)"></div>

        <div class="sep"></div>

'''
        lines.insert(ins, new_block)
        print(f"  [OK] Bootstrap + Gravity/Audit вставлены перед строкой {ins+1}")

with open(HTML, "w", encoding="utf-8") as f:
    f.writelines(lines)
print("  [OK] saved")

with open(HTML, "r", encoding="utf-8") as f:
    check = f.read()
print("  publishSeed: " + str('publishSeed' in check))
print("  showGravity: " + str('showGravity' in check))