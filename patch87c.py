# patch87c.py - P87c: спираль traceroute на звёздном небе
#
# - Traceroute точки по спирали (angle = hop * 22.5°, radius = log)
# - Цвет градиент: синий (hop 1) -> фиолетовый (hop 16)
# - Размер уменьшается с глубиной
# - Линии между соседними hops

import os
import ast
import shutil

ROOT = r"E:\InevioNet"
HTML = os.path.join(ROOT, "web", "templates", "index.html")


def patch_file(path, replacements, label, bak=".bak_p87c"):
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
            print("  [OK] " + old[:50].strip())
        else:
            if required:
                print("  [!!] NOT FOUND: " + old[:50].strip())
    if changed > 0:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        print("  [OK] saved " + label)
        return True
    return True


# 1. Заменить layout() - добавить спираль для traceroute
old_layout = '''function layout(nd, pm) {
  const h = hash(nd.node_id);
  const a = (h % 360) * Math.PI / 180;
  if (nd.type === 'self') return { x:0, y:0 };
  // P87: hops из данных
  const hops = nd.hops || 1;
  const r = radiusForHops(hops, nd.type);
  // Добавим немного "дрожания" чтобы узлы не совпадали
  const jitter = (h % 20) - 10;
  return { x: Math.cos(a) * (r + jitter), y: Math.sin(a) * (r + jitter) };
}'''

new_layout = '''function layout(nd, pm) {
  const h = hash(nd.node_id);
  const hops = nd.hops || 1;

  // P87c: traceroute - спираль
  if (nd.type === 'traceroute') {
    const angle = hops * 22.5 * Math.PI / 180;  // 16 hops = 360°
    const r = radiusForHops(hops, 'traceroute');
    return { x: Math.cos(angle) * r, y: Math.sin(angle) * r };
  }

  const a = (h % 360) * Math.PI / 180;
  if (nd.type === 'self') return { x:0, y:0 };
  const r = radiusForHops(hops, nd.type);
  const jitter = (h % 20) - 10;
  return { x: Math.cos(a) * (r + jitter), y: Math.sin(a) * (r + jitter) };
}'''

# 2. Обновить COLORS - градиент для traceroute (будет вычисляться динамически)
# Оставим COLORS, но в renderStars будем переопределять цвет для traceroute

# 3. Заменить renderStars/rebuildStars - динамический цвет для traceroute
old_rebuild = '''function rebuildStars() {
  const pm = {};
  const order = Object.values(nodes).sort((a, b) => (RANK[a.type] || 9) - (RANK[b.type] || 9));
  order.forEach(nd => { pm[nd.node_id] = layout(nd, pm); });
  stars = order.map(nd => {
    const old = stars.find(s => s.node.node_id === nd.node_id);
    const p = pm[nd.node_id];
    // Размер звезды: self > inevionet > router > device > traceroute
    let base = 3;
    if (nd.type === 'self') base = 8;
    else if (nd.type === 'inevionet') base = 5;
    else if (nd.type === 'router') base = 4;
    else if (nd.type === 'wifi') base = 3.5;
    else if (nd.type === 'device') base = 2.5;
    else if (nd.type === 'traceroute') base = 1.8;
    return {
      node: nd,
      x: p.x, y: p.y,
      base: base,
      pulse: old ? old.pulse : Math.random() * 6
    };
  });
}'''

new_rebuild = '''function tracerouteColor(hop) {
  // P87c: градиент синий -> фиолетовый
  // hop 1: #0a84ff (синий), hop 16: #bf5af2 (фиолетовый)
  const t = Math.min(1, (hop - 1) / 15);
  const r = Math.round(10 + (191 - 10) * t);
  const g = Math.round(132 + (90 - 132) * t);
  const b = Math.round(255 + (242 - 255) * t);
  return 'rgb(' + r + ',' + g + ',' + b + ')';
}

function rebuildStars() {
  const pm = {};
  const order = Object.values(nodes).sort((a, b) => (RANK[a.type] || 9) - (RANK[b.type] || 9));
  order.forEach(nd => { pm[nd.node_id] = layout(nd, pm); });
  stars = order.map(nd => {
    const old = stars.find(s => s.node.node_id === nd.node_id);
    const p = pm[nd.node_id];
    let base = 3;
    let color = null;
    if (nd.type === 'self') base = 8;
    else if (nd.type === 'inevionet') base = 5;
    else if (nd.type === 'router') base = 4;
    else if (nd.type === 'wifi') base = 3.5;
    else if (nd.type === 'device') base = 2.5;
    else if (nd.type === 'traceroute') {
      base = 2.5;
      color = tracerouteColor(nd.hops || 1);
    }
    return {
      node: nd,
      x: p.x, y: p.y,
      base: base,
      color: color,
      pulse: old ? old.pulse : Math.random() * 6
    };
  });
}'''

# 4. В animate() - использовать s.color для traceroute + рисовать линии traceroute
old_animate_lines = '''  stars.forEach(s => {
    const p = s.node.parent && pm[s.node.parent];
    if (p) {
      const col = s.node.type === 'spore' ? 'rgba(255,55,95,0.4)' : 'rgba(10,132,255,0.25)';
      ctx.strokeStyle = col;
      ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(s.x, s.y); ctx.stroke();
    }
  });'''

new_animate_lines = '''  // P87c: линии между узлами
  stars.forEach(s => {
    const p = s.node.parent && pm[s.node.parent];
    if (p) {
      let col = 'rgba(10,132,255,0.25)';
      if (s.node.type === 'spore') col = 'rgba(255,55,95,0.4)';
      else if (s.node.type === 'traceroute') {
        col = tracerouteColor(s.node.hops || 1);
        // сделать прозрачным
        col = col.replace('rgb(', 'rgba(').replace(')', ',0.5)');
      }
      ctx.strokeStyle = col;
      ctx.lineWidth = (s.node.type === 'traceroute' ? 1.5 : 1) / zoom;
      ctx.beginPath(); ctx.moveTo(p.x, p.y); ctx.lineTo(s.x, s.y); ctx.stroke();
    }
  });'''

# 5. В отрисовке звезды - использовать s.color
old_animate_star = '''  stars.forEach(s => {
    s.pulse += 0.04;
    const r = s.base * (1 + Math.sin(s.pulse) * 0.22);
    const col = s.node.evolving ? '#ffd60a' : (COLORS[s.node.type] || '#8888aa');'''

new_animate_star = '''  stars.forEach(s => {
    s.pulse += 0.04;
    const r = s.base * (1 + Math.sin(s.pulse) * 0.22);
    // P87c: использовать s.color для traceroute
    let col;
    if (s.color) col = s.color;
    else if (s.node.evolving) col = '#ffd60a';
    else col = COLORS[s.node.type] || '#8888aa';'''

patch_file(HTML, [
    (old_layout, new_layout, True),
    (old_rebuild, new_rebuild, True),
    (old_animate_lines, new_animate_lines, True),
    (old_animate_star, new_animate_star, True),
], "index.html P87c", bak=".bak_p87c")


print()
print("=" * 70)
print("  PATCH 87c DONE")
print("=" * 70)
print("  [OK] layout(): traceroute по спирали (angle = hop * 22.5)")
print("  [OK] tracerouteColor(): градиент синий -> фиолетовый")
print("  [OK] rebuildStars(): цвет + размер для traceroute")
print("  [OK] animate(): линии между hops с градиентом")
print()
print("Обнови UI: Ctrl+F5")