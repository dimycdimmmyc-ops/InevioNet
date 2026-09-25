import os
import shutil

ROOT = r"E:\InevioNet"
HTML = os.path.join(ROOT, "web", "templates", "index.html")

with open(HTML, "r", encoding="utf-8") as f:
    content = f.read()

b = HTML + ".bak_p87gfix"
shutil.copy2(HTML, b)
print("  [BK] " + os.path.basename(b))

# Заменить angle для traceroute
old = "const angle = hops * 22.5 * Math.PI / 180;  // 16 hops = 360"
new = "const angle = hops * 18 * Math.PI / 180;  // P87g: 100 hops = 5 витков"
if old in content:
    content = content.replace(old, new, 1)
    print("  [OK] angle: 22.5 -> 18")
else:
    # Поиск любого angle с traceroute
    import re
    for m in re.finditer(r'const angle = hops \* ([\d.]+)', content):
        print("  [i] найдено: " + m.group(0))

# Убрать SyntaxWarning в JS (backslash в regex)
old_warn = "return c.replace(/,[^,]+\\\)$/, ',' + alpha + ')');"
new_warn = "return c.replace(/,[^,]+\\\\)$/, ',' + alpha + ')');"
if old_warn in content:
    content = content.replace(old_warn, new_warn, 1)
    print("  [OK] regex escape fixed")

with open(HTML, "w", encoding="utf-8") as f:
    f.write(content)
print("  [OK] saved")

# Проверка
with open(HTML, "r", encoding="utf-8") as f:
    check = f.read()
print("  angle 18: " + str("hops * 18" in check))
print("  angle 22.5: " + str("hops * 22.5" in check))