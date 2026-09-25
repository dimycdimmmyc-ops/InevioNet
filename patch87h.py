import os
import shutil

ROOT = r"E:\InevioNet"
HTML = os.path.join(ROOT, "web", "templates", "index.html")

with open(HTML, "r", encoding="utf-8") as f:
    content = f.read()

b = HTML + ".bak_p87h"
shutil.copy2(HTML, b)
print("  [BK] " + os.path.basename(b))

# 1. Шрифт подписи - убрать / zoom
old_font = "ctx.font = (11 / zoom) + 'px -apple-system,sans-serif';"
new_font = "ctx.font = '11px -apple-system,sans-serif';"
if old_font in content:
    content = content.replace(old_font, new_font, 1)
    print("  [OK] font: 11/zoom -> 11")
else:
    print("  [!!] font NOT FOUND")
    import re
    for m in re.finditer(r'ctx\.font = [^;]+;', content):
        print("  [i] " + m.group(0))

# 2. Смещение подписи - тоже убрать / zoom
old_off = "ctx.fillText(s.node.label || s.node.name || s.node.node_id, s.x + r + 6 / zoom, s.y + 3 / zoom);"
new_off = "ctx.fillText(s.node.label || s.node.name || s.node.node_id, s.x + r + 6, s.y + 3);"
if old_off in content:
    content = content.replace(old_off, new_off, 1)
    print("  [OK] text offset: 6/zoom -> 6")
else:
    print("  [!!] text offset NOT FOUND")

with open(HTML, "w", encoding="utf-8") as f:
    f.write(content)
print("  [OK] saved")