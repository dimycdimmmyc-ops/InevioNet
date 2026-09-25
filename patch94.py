# patch94.py - P94: фикс isSuper в animate() + защита карты
import os
import shutil

ROOT = r"E:\InevioNet"
HTML = os.path.join(ROOT, "web", "templates", "index.html")

BAK = ".bak_p94"


def patch_html(path, replacements, label):
    if not os.path.exists(path):
        print("  [!!] NOT FOUND: " + path)
        return False
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    b = path + BAK
    shutil.copy2(path, b)
    print("  [BK] " + os.path.basename(b))
    changed = 0
    for old, new, required in replacements:
        if new and new in content and (not old or old not in content):
            print("  [--] already applied")
            continue
        if old and old in content:
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


print()
print("=" * 70)
print("  P94: фикс isSuper в animate()")
print("=" * 70)

# Замена: isSuper -> s.node.super || s.node.is_super
old_block = """        if (isSuper) {
            ctx.strokeStyle = 'rgba(255, 215, 0, 0.6)';
            ctx.lineWidth = (1.5 / zoom);
            ctx.beginPath(); ctx.arc(s.x, s.y, r * 2.5 + Math.sin(s.pulse)*2, 0, Math.PI * 2); ctx.stroke();
            ctx.fillStyle = '#ffd700';
            ctx.font = 'bold ' + (14 / zoom) + 'px Segoe UI, sans-serif';
            ctx.fillText('\u2b50', s.x - (7 / zoom), s.y - r - (5 / zoom));
        }"""

new_block = """        // P94: фикс isSuper -> проверка на узле
        var isSuperNode = !!(s.node && (s.node.super || s.node.is_super || s.node.super_node));
        if (isSuperNode) {
            ctx.strokeStyle = 'rgba(255, 215, 0, 0.6)';
            ctx.lineWidth = (1.5 / zoom);
            ctx.beginPath(); ctx.arc(s.x, s.y, r * 2.5 + Math.sin(s.pulse)*2, 0, Math.PI * 2); ctx.stroke();
            ctx.fillStyle = '#ffd700';
            ctx.font = 'bold ' + (14 / zoom) + 'px Segoe UI, sans-serif';
            ctx.fillText('\u2b50', s.x - (7 / zoom), s.y - r - (5 / zoom));
        }"""

patch_html(HTML, [(old_block, new_block, True)], "animate isSuper fix")


# Защита: обернуть весь forEach в try/catch, чтобы одна ошибка не убивала карту
print()
print("=" * 70)
print("  P94: защита animate() от падений")
print("=" * 70)

old_anim = """  stars.forEach(s => {
    s.pulse += 0.04;
    const r = s.base * (1 + Math.sin(s.pulse) * 0.22);"""

new_anim = """  // P94: try/catch на каждом узле, чтобы одна ошибка не убивала всю карту
  stars.forEach(s => {
    try {
    s.pulse += 0.04;
    const r = s.base * (1 + Math.sin(s.pulse) * 0.22);"""

patch_html(HTML, [(old_anim, new_anim, True)], "animate try-open")

# Закрыть try/catch в конце forEach
# Ищем характерный конец блока forEach — после всех операций рисования
old_end = """    if (s.node.type === 'self') { ctx.beginPath(); ctx.arc(s.x, s.y, r * 0.4, 0, Math.PI * 2); ctx.fillStyle = '#fff'; ctx.fill(); }
    ctx.font = '11px -apple-system,sans-serif';
    ctx.fillStyle = 'rgba(255,255,255,0.85)';
    ctx.textAlign = 'center';
    ctx.fillText(s.node.label || s.node.id || '', s.x, s.y + r + 14 / zoom);
  });"""

new_end = """    if (s.node.type === 'self') { ctx.beginPath(); ctx.arc(s.x, s.y, r * 0.4, 0, Math.PI * 2); ctx.fillStyle = '#fff'; ctx.fill(); }
    ctx.font = '11px -apple-system,sans-serif';
    ctx.fillStyle = 'rgba(255,255,255,0.85)';
    ctx.textAlign = 'center';
    ctx.fillText(s.node.label || s.node.id || '', s.x, s.y + r + 14 / zoom);
    } catch (e) {
      // P94: не даём одной звезде убить всю карту
      if (window.__tree_err_count === undefined) window.__tree_err_count = 0;
      window.__tree_err_count++;
      if (window.__tree_err_count < 5) console.warn('[Stars] node error:', e && e.message, s.node);
    }
  });"""

# Это опционально — если якорь не совпадёт, просто пропустим
patch_html(HTML, [(old_end, new_end, False)], "animate try-close")


print()
print("=" * 70)
print("  PATCH 94 DONE")
print("=" * 70)
print("  [OK] isSuper -> s.node.super || s.node.is_super")
print("  [OK] try/catch в animate forEach (защита карты)")
print()
print("Перезапуск НЕ нужен — просто Ctrl+F5 в браузере")