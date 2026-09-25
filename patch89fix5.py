# patch89fix5.py - P89-fix5: вставить Bootstrap + Gravity после Мицелия
import os
import shutil

ROOT = r"E:\InevioNet"
HTML = os.path.join(ROOT, "web", "templates", "index.html")

with open(HTML, "r", encoding="utf-8") as f:
    lines = f.readlines()

b = HTML + ".bak_p89fix5"
shutil.copy2(HTML, b)
print("  [BK] " + os.path.basename(b))

# Проверим, есть ли уже
has_bootstrap = any('publishSeed' in line for line in lines)
if has_bootstrap:
    print("  [--] Bootstrap уже есть")
else:
    # Найти секцию Мицелий (по growNetwork)
    micelium_end = None
    for i, line in enumerate(lines):
        if 'growNetwork' in line:
            # Найти следующий sep после этой строки
            for j in range(i, min(i + 20, len(lines))):
                if 'sep"' in lines[j]:
                    micelium_end = j + 1  # после sep
                    break
            break

    if micelium_end is None:
        print("  [!!] Мицелий НЕ найден")
    else:
        # Пропустить пустую строку если есть
        if micelium_end < len(lines) and lines[micelium_end].strip() == '':
            micelium_end += 1
        # Ещё одна пустая
        if micelium_end < len(lines) and lines[micelium_end].strip() == '':
            micelium_end += 1

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
        lines.insert(micelium_end, new_block)
        print(f"  [OK] вставлено после строки {micelium_end}")

        with open(HTML, "w", encoding="utf-8") as f:
            f.writelines(lines)
        print("  [OK] saved")

# Проверка
with open(HTML, "r", encoding="utf-8") as f:
    check = f.read()
print("  publishSeed: " + str('publishSeed' in check))
print("  showGravity: " + str('showGravity' in check))
print("  verifyAudit: " + str('verifyAudit' in check))