# patch88fix2.py - P88-fix2: spore layout через номера строк
import os
import shutil

ROOT = r"E:\InevioNet"
HTML = os.path.join(ROOT, "web", "templates", "index.html")

with open(HTML, "r", encoding="utf-8") as f:
    lines = f.readlines()

b = HTML + ".bak_p88fix2"
shutil.copy2(HTML, b)
print("  [BK] " + os.path.basename(b))

# Найти строку "if (nd.type === 'traceroute')" внутри layout()
# Вставить ПЕРЕД ней spore-блок

target_idx = None
for i, line in enumerate(lines):
    if "function layout" in line:
        # Ищем вниз if (nd.type === 'traceroute')
        for j in range(i, min(i + 20, len(lines))):
            if "if (nd.type === 'traceroute')" in lines[j]:
                target_idx = j
                break
        break

if target_idx is None:
    print("  [!!] target NOT FOUND")
else:
    # Проверка - уже есть spore выше?
    already = False
    for k in range(max(0, target_idx - 15), target_idx):
        if "nd.type === 'spore'" in lines[k]:
            already = True
            break

    if already:
        print("  [--] spore layout уже есть")
    else:
        spore_block = """  // P88: споры вокруг WiFi-родителя
  if (nd.type === 'spore') {
    let macParent = null;
    if (nd.via && nd.via.startsWith('wifi_')) {
      const raw = nd.via.slice(5);
      if (raw.length === 12) {
        macParent = raw.slice(0,2)+':'+raw.slice(2,4)+':'+raw.slice(4,6)+':'+raw.slice(6,8)+':'+raw.slice(8,10)+':'+raw.slice(10,12);
      }
    }
    const p = macParent && pm[macParent];
    if (p) {
      const a2 = (h % 360) * Math.PI / 180;
      const r2 = 25 + (h % 15);
      return { x: p.x + Math.cos(a2) * r2, y: p.y + Math.sin(a2) * r2 };
    }
    const r3 = 200 + (h % 60);
    return { x: Math.cos(a) * r3, y: Math.sin(a) * r3 };
  }

"""
        lines.insert(target_idx, spore_block)
        print("  [OK] spore layout вставлен перед строкой " + str(target_idx + 1))

with open(HTML, "w", encoding="utf-8") as f:
    f.writelines(lines)

print("  [OK] saved")

# Проверка
with open(HTML, "r", encoding="utf-8") as f:
    check = f.read()
print("  spore layout: " + str("P88: споры вокруг WiFi-родителя" in check or "spore" in check and "macParent" in check))