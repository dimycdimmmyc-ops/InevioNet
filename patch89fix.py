# patch89fix.py - P89-fix: HTML структура по номерам строк
import os
import shutil

ROOT = r"E:\InevioNet"
HTML = os.path.join(ROOT, "web", "templates", "index.html")

with open(HTML, "r", encoding="utf-8") as f:
    lines = f.readlines()

b = HTML + ".bak_p89fix"
shutil.copy2(HTML, b)
print("  [BK] " + os.path.basename(b))

# 1. Найти строки для удаления (по содержимому card-title)
# Ищем по emoji-тегам — они не искажены
to_remove = []

for i, line in enumerate(lines):
    # Анонимность — emoji 🕵 (в cp866 это рџ§…)
    if 'рџ§' in line and 'card-title' in line:
        to_remove.append(("anon", i))
    # P2P Мост — emoji 🌐 (рџЊ‰)
    if 'рџЊ‰' in line and 'card-title' in line:
        to_remove.append(("bridge", i))
    # AI Селектор — emoji 🤖 (рџ¤–)
    if 'рџ¤' in line and 'card-title' in line:
        to_remove.append(("ai", i))

print("  Найдено секций для удаления:")
for name, idx in to_remove:
    print(f"    {name}: line {idx+1}")

# 2. Определить границы каждой секции (от card-title до следующего sep")
def find_section_bounds(lines, start_idx):
    """От card-title до следующего sep (включительно) + пустая строка."""
    end = start_idx
    for j in range(start_idx, min(start_idx + 60, len(lines))):
        if 'sep"' in lines[j]:
            end = j
            break
    return (start_idx, end)

sections = []
for name, idx in to_remove:
    s, e = find_section_bounds(lines, idx)
    sections.append((name, s, e))
    print(f"    {name}: {s+1} - {e+1} ({e-s+1} строк)")

# 3. Удалить секции (от последней к первой, чтобы не сбить индексы)
sections.sort(key=lambda x: -x[1])
for name, s, e in sections:
    # Удаляем от s до e + 1 (sep + пустая строка)
    del_end = e + 1
    # Если после sep идёт пустая строка — удалим и её
    if del_end < len(lines) and lines[del_end].strip() == '':
        del_end += 1
    del lines[s:del_end]
    print(f"  [OK] удалено {name}: {e-s+1} строк")

# 4. Найти строку Мицелий для вставки
micelium_idx = None
for i, line in enumerate(lines):
    if 'рџЊ±' in line and 'card-title' in line:
        micelium_idx = i
        break

if micelium_idx is None:
    print("  [!!] Мицелий НЕ найден")
else:
    # Найти конец секции Мицелий (следующий sep)
    s, e = find_section_bounds(lines, micelium_idx)
    insert_idx = e + 1
    if insert_idx < len(lines) and lines[insert_idx].strip() == '':
        insert_idx += 1

    # Вставить Bootstrap + Gravity/Audit
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
    lines.insert(insert_idx, new_block)
    print(f"  [OK] Bootstrap + Gravity/Audit вставлены после строки {insert_idx}")

# 5. Записать
with open(HTML, "w", encoding="utf-8") as f:
    f.writelines(lines)
print("  [OK] saved")

# 6. Проверка
with open(HTML, "r", encoding="utf-8") as f:
    check = f.read()
print("  Анонимность: " + str('рџ§' not in check))
print("  P2P Мост: " + str('рџЊ‰' not in check))
print("  AI Селектор: " + str('рџ¤' not in check))
print("  Bootstrap: " + str('publishSeed' in check))
print("  Gravity: " + str('showGravity' in check))
print("  Audit: " + str('verifyAudit' in check))