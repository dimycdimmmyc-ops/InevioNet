# patch87f.py - P87f: fix CanvasGradient color
import os
import shutil

ROOT = r"E:\InevioNet"
HTML = os.path.join(ROOT, "web", "templates", "index.html")


def patch_file(path, replacements, label, bak=".bak_p87f"):
    if not os.path.exists(path):
        print("  [!!] NOT FOUND: " + path)
        return False
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    b = path + bak
    shutil.copy2(path, b)
    print("  [BK] " + os.path.basename(b))
    changed = 0
    for old, new, required in replacements:
        if new in content and old not in content:
            print("  [--] already applied")
            continue
        if old in content:
            content = content.replace(old, new, 1)
            changed += 1
            print("  [OK] " + old[:60].strip())
        else:
            if required:
                print("  [!!] NOT FOUND: " + old[:60].strip())
    if changed > 0:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print("  [OK] saved " + label)
        return True
    return True


# 1. Заменить col + '80' на функцию colorWithAlpha
old_block = '''    ctx.font = (11 / zoom) + 'px -apple-system,sans-serif';'''

new_block = '''    // P87f: правильный rgba для градиента
    const gradCol = (typeof col === 'string' && col.startsWith('#'))
      ? col + '80'
      : (typeof col === 'string' && col.startsWith('rgb('))
        ? col.replace('rgb(', 'rgba(').replace(')', ',0.5)')
        : 'rgba(136,136,170,0.5)';

    ctx.font = (11 / zoom) + 'px -apple-system,sans-serif';'''

# 2. Заменить использование col + '80' в градиенте
old_gradient = '''    const g = ctx.createRadialGradient(s.x, s.y, 0, s.x, s.y, r * 5);
    g.addColorStop(0, col + '80');
    g.addColorStop(1, 'rgba(0,0,0,0)');'''

new_gradient = '''    const g = ctx.createRadialGradient(s.x, s.y, 0, s.x, s.y, r * 5);
    let gradStop0;
    if (typeof col === 'string' && col.startsWith('#')) {
      gradStop0 = col + '80';
    } else if (typeof col === 'string' && col.startsWith('rgb(')) {
      gradStop0 = col.replace('rgb(', 'rgba(').replace(')', ',0.5)');
    } else {
      gradStop0 = 'rgba(136,136,170,0.5)';
    }
    g.addColorStop(0, gradStop0);
    g.addColorStop(1, 'rgba(0,0,0,0)');'''

patch_file(HTML, [
    (old_gradient, new_gradient, True),
], "gradient fix", bak=".bak_p87f")


print()
print("=" * 70)
print("  PATCH 87f DONE")
print("=" * 70)
print("Ctrl+F5 в браузере.")