# patch94fix.py - P94-fix: откат + правильная замена isSuper
import os
import shutil

ROOT = r"E:\InevioNet"
HTML = os.path.join(ROOT, "web", "templates", "index.html")
BAK = HTML + ".bak_p94"

print()
print("=" * 70)
print("  P94-fix: откат + правильная замена")
print("=" * 70)

# 1. Откатить из bak_p94 (убрать битый try)
if os.path.exists(BAK):
    shutil.copy2(BAK, HTML)
    print("  [OK] откат из bak_p94")
else:
    print("  [!!] bak_p94 не найден — продолжаем без отката")

# 2. Прочитать
with open(HTML, "r", encoding="utf-8") as f:
    content = f.read()

# 3. Замена isSuper -> isSuperNode
old = """        if (isSuper) {
            ctx.strokeStyle = 'rgba(255, 215, 0, 0.6)';
            ctx.lineWidth = (1.5 / zoom);
            ctx.beginPath(); ctx.arc(s.x, s.y, r * 2.5 + Math.sin(s.pulse)*2, 0, Math.PI * 2); ctx.stroke();
            ctx.fillStyle = '#ffd700';
            ctx.font = 'bold ' + (14 / zoom) + 'px Segoe UI, sans-serif';
            ctx.fillText('⭐', s.x - (7 / zoom), s.y - r - (5 / zoom));
        }"""

new = """        var isSuperNode = !!(s.node && (s.node.super || s.node.is_super || s.node.super_node));
        if (isSuperNode) {
            ctx.strokeStyle = 'rgba(255, 215, 0, 0.6)';
            ctx.lineWidth = (1.5 / zoom);
            ctx.beginPath(); ctx.arc(s.x, s.y, r * 2.5 + Math.sin(s.pulse)*2, 0, Math.PI * 2); ctx.stroke();
            ctx.fillStyle = '#ffd700';
            ctx.font = 'bold ' + (14 / zoom) + 'px Segoe UI, sans-serif';
            ctx.fillText('\u2b50', s.x - (7 / zoom), s.y - r - (5 / zoom));
        }"""

if new in content and old not in content:
    print("  [--] isSuper fix уже применён")
elif old in content:
    content = content.replace(old, new, 1)
    print("  [OK] isSuper -> isSuperNode")
else:
    print("  [!!] isSuper блок НЕ найден")

# 4. Записать
with open(HTML, "w", encoding="utf-8") as f:
    f.write(content)

# 5. Проверка баланса try/catch
try_c = content.count("try {") + content.count("try{")
catch_c = content.count("catch (") + content.count("catch(")
print(f"  try: {try_c}  catch: {catch_c}")

# 6. Проверка на незакрытый try в области stars.forEach
lines = content.split("\n")
in_forEach = False
try_stack = 0
for i, line in enumerate(lines):
    if "stars.forEach" in line:
        in_forEach = True
        try_stack = 0
    if in_forEach:
        try_stack += line.count("try {")
        try_stack -= line.count("catch")
        if line.strip() == "});" and i > 560:
            if try_stack != 0:
                print(f"  [!!] ВНИМАНИЕ: try/catch дисбаланс в forEach (line {i+1}), try_stack={try_stack}")
            else:
                print(f"  [OK] try/catch в forEach сбалансирован")
            in_forEach = False
            break

print()
print("=" * 70)
print("  PATCH 94-FIX DONE")
print("=" * 70)
print()
print("Дальше:")
print("  1. Ctrl+Shift+R (жёсткое обновление)")
print("  2. F12 → Console → нет ошибок?")