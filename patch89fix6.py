# patch89fix6.py - вставить Bootstrap + Gravity между Мицелием и Капсулами
import os
import shutil

ROOT = r"E:\InevioNet"
HTML = os.path.join(ROOT, "web", "templates", "index.html")

with open(HTML, "r", encoding="utf-8") as f:
    lines = f.readlines()

b = HTML + ".bak_p89fix6"
shutil.copy2(HTML, b)
print("  [BK] " + os.path.basename(b))

# Проверим, что уже нет в HTML (только в JS)
# Ищем 'onclick="publishSeed' или 'id="sproutUrl"'
has_html = False
for line in lines:
    if 'onclick="publishSeed' in line or 'id="sproutUrl"' in line:
        has_html = True
        break

if has_html:
    print("  [--] Bootstrap HTML уже есть")
else:
    # Найти строку "🌱 Мицелий" (по growNetwork)
    micelium_idx = None
    for i, line in enumerate(lines):
        if 'onclick="growNetwork' in line:
            micelium_idx = i
            break

    if micelium_idx is None:
        print("  [!!] Мицелий НЕ найден")
    else:
        # Найти следующий sep после micelium_idx
        sep_idx = None
        for j in range(micelium_idx, min(micelium_idx + 15, len(lines))):
            if 'sep"' in lines[j]:
                sep_idx = j
                break

        if sep_idx is None:
            print("  [!!] sep после Мицелия НЕ найден")
        else:
            # Вставить ПОСЛЕ sep_idx
            insert_idx = sep_idx + 1
            # Пропустить пустые
            while insert_idx < len(lines) and lines[insert_idx].strip() == '':
                insert_idx += 1

            new_block = '''        <div class="card-title" style="font-size:0.9em;margin-bottom:8px"><span class="emoji">\U0001f511</span> Bootstrap</div>
        <button class="btn btn-success" onclick="publishSeed()">\U0001f511 Опубликовать Seed</button>
        <button class="btn btn-glass" onclick="bootstrapStatus()">\U0001f4ca Статус</button>
        <div class="form-group" style="margin-top:6px"><label>URL Seed</label><input id="sproutUrl" placeholder="https://paste.rs/..."></div>
        <button class="btn btn-glass" onclick="sproutUrl()">\U0001f331 Прорастить</button>
        <div id="bootstrapResult" style="margin-top:8px;font-size:0.8em;color:var(--dim)"></div>

        <div class="sep"></div>

        <div class="card-title" style="font-size:0.9em;margin-bottom:8px"><span class="emoji">\U0001f300</span> Gravity + Audit</div>
        <button class="btn btn-glass" onclick="showGravity()">\U0001f300 Поле Gravity</button>
        <button class="btn btn-glass" onclick="showAudit()">\U0001f4dc Audit log</button>
        <button class="btn btn-glass" onclick="verifyAudit()">\u2705 Verify Audit</button>
        <div id="gravityResult" style="margin-top:8px;font-size:0.8em;color:var(--dim)"></div>
        <div id="auditResult" style="margin-top:4px;font-size:0.75em;color:var(--dim)"></div>

        <div class="sep"></div>

'''
            lines.insert(insert_idx, new_block)
            print(f"  [OK] вставлено в строку {insert_idx}")
            print(f"  [i] между: {lines[insert_idx-3].strip()[:50]} и {lines[insert_idx+len(new_block.splitlines())].strip()[:50]}")

            with open(HTML, "w", encoding="utf-8") as f:
                f.writelines(lines)
            print("  [OK] saved")

# Проверка HTML
with open(HTML, "r", encoding="utf-8") as f:
    check = f.read()
print("  onclick=publishSeed: " + str('onclick="publishSeed' in check))
print("  id=sproutUrl: " + str('id="sproutUrl"' in check))
print("  onclick=showGravity: " + str('onclick="showGravity' in check))
print("  onclick=verifyAudit: " + str('onclick="verifyAudit' in check))