# patch87.py - P84-fix + P87
#
# P84-fix: network_tree.build() различает типы (wifi / inevionet / device / traceroute)
# P87:     UI интеграция - звёздное небо рисует дерево из /api/network/tree
#          Радиальная раскладка: hops=0 -> центр, hops=N -> радиус N

import os
import ast
import shutil

ROOT = r"E:\InevioNet"
INEV = os.path.join(ROOT, "inevionet")
MESH = os.path.join(INEV, "mesh")
HTML = os.path.join(ROOT, "web", "templates", "index.html")


def write_py(path, code, label):
    if os.path.exists(path):
        b = path + ".bak_p87"
        shutil.copy2(path, b)
        print("  [BK] " + os.path.basename(b))
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    try:
        ast.parse(code)
        print("  [OK] " + label)
        return True
    except SyntaxError as e:
        print("  [!!] " + label + " syntax: " + str(e))
        b = path + ".bak_p87"
        if os.path.exists(b):
            shutil.copy2(b, path)
            print("  [--] rolled back")
        return False


def patch_file(path, replacements, label, bak=".bak_p87"):
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
        if path.endswith(".py"):
            try:
                ast.parse(content)
                print("  [OK] syntax " + label)
                return True
            except SyntaxError as e:
                print("  [!!] syntax: " + str(e))
                shutil.copy2(b, path)
                print("  [--] rolled back")
                return False
        else:
            print("  [OK] saved " + label)
            return True
    return True


# =====================================================================
# P84-fix: network_tree.py - различать типы
# =====================================================================

print()
print("=" * 70)
print("  P84-fix: network_tree.py")
print("=" * 70)

TREE = os.path.join(MESH, "network_tree.py")

# Заменяем определение типа в build()
old_type = '''        # InevioNet-узлы из topology
        if topology_map:
            nodes = topology_map.get("nodes", {})
            for nid, nd in nodes.items():
                if nid == self.node_id:
                    continue
                ntype = nd.get("type", "external")
                hops = int(nd.get("hops", 1))
                via = nd.get("via", "")
                child = TreeNode(
                    node_id=nid,
                    node_type="inevionet",
                    ip=nd.get("ip", ""),
                    name=nd.get("name", nid),
                    hops=hops,
                    via=via,
                    metadata={"source": "topology"})
                # InevioNet-узлы крепим к root напрямую
                self.root.children.append(child)'''

new_type = '''        # Узлы из topology - различаем тип по node_id
        if topology_map:
            nodes = topology_map.get("nodes", {})
            for nid, nd in nodes.items():
                if nid == self.node_id:
                    continue
                # P84-fix: определение типа
                if nid.startswith("web_node_"):
                    ntype = "inevionet"
                elif nid.startswith("dev_"):
                    ntype = "device"
                elif nid.startswith("router_"):
                    ntype = "router"
                elif nid.startswith("tr_"):
                    ntype = "traceroute"
                elif nid.startswith("mdns_"):
                    ntype = "local_device"
                elif ":" in nid and len(nid) == 17:
                    # MAC-адрес => WiFi-роутер
                    ntype = "wifi"
                else:
                    ntype = nd.get("type", "external")
                hops = int(nd.get("hops", 1))
                via = nd.get("via", "")
                # Источник
                if ntype == "wifi":
                    src = "rf"
                elif ntype == "inevionet":
                    src = "topology"
                else:
                    src = nd.get("source", "topology")
                child = TreeNode(
                    node_id=nid,
                    node_type=ntype,
                    ip=nd.get("ip", ""),
                    name=nd.get("name", nid),
                    hops=hops,
                    via=via,
                    metadata={"source": src})
                self.root.children.append(child)'''

patch_file(TREE, [(old_type, new_type, True)], "network_tree.py P84-fix")


# =====================================================================
# P87: UI - звёздное небо рисует дерево
# =====================================================================

print()
print("=" * 70)
print("  P87: index.html - звёздное небо рисует дерево")
print("=" * 70)

# 1. Заменяем layout() - радиальная раскладка по hops
old_layout = '''function layout(nd, pm) {
  const h = hash(nd.node_id);
  const a = (h % 360) * Math.PI / 180;
  if (nd.type === 'self') return { x:0, y:0 };
  if (nd.type === 'wifi') { const r = 170 + (100 - (nd.signal || 50)) * 2.2; return { x:Math.cos(a)*r, y:Math.sin(a)*r }; }
  if (nd.type === 'spore') { const p = pm[nd.parent] || { x:0, y:0 }; const r2 = 45 + (h % 25); return { x:p.x + Math.cos(a)*r2, y:p.y + Math.sin(a)*r2 }; }
  if (nd.type === 'bluetooth' || nd.type === 'ble') { const r3 = 100 + (h % 40); return { x:Math.cos(a)*r3, y:Math.sin(a)*r3 }; }
  if (nd.type === 'cellular') { const r5 = 220 + (h % 50); return { x:Math.cos(a)*r5, y:Math.sin(a)*r5 }; }
  const r4 = 260 + (h % 60);
  return { x:Math.cos(a)*r4, y:Math.sin(a)*r4 };
}'''

new_layout = '''// P87: радиальная раскладка по hops
function radiusForHops(hops, type) {
  // Логарифмическая шкала для глубины 0-20
  if (hops === 0) return 0;
  // WiFi-роутеры - кольцо 1 (соседи)
  if (type === 'wifi') return 140;
  // Обычная логарифмическая шкала
  const base = 70;
  const growth = 1.12;
  return base * Math.pow(growth, Math.min(hops, 20) - 1);
}

function layout(nd, pm) {
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

# 2. Заменяем загрузку - nodes подтягиваются из /api/network/tree
old_load = '''socket.on('nodes_update', d => {
  nodes = d.nodes || {};
  const pm = {};
  const order = Object.values(nodes).sort((a, b) => (RANK[a.type] || 9) - (RANK[b.type] || 9));
  order.forEach(nd => { pm[nd.node_id] = layout(nd, pm); });
  stars = order.map(nd => {
    const old = stars.find(s => s.node.node_id === nd.node_id);
    const p = pm[nd.node_id];
    return { node: nd, x:p.x, y:p.y, base:(nd.type === 'self' ? 7 : 3 + (nd.trust || 50) / 25), pulse: old ? old.pulse : Math.random() * 6 };
  });
  const count = Object.keys(nodes).length;
  document.getElementById('statNodes').textContent = count;
  document.getElementById('hdrNodes').textContent = count;
  document.getElementById('statInfected').textContent = d.infected || 0;
  document.getElementById('hdrInfected').textContent = d.infected || 0;
});'''

new_load = '''// P87: fetch дерева из /api/network/tree
async function loadTreeFromAPI() {
  try {
    const r = await fetch('/api/network/tree?force=0');
    const d = await r.json();
    if (!d.success || !d.root) return;

    // Обходим дерево, собираем плоский список узлов
    const flat = [];
    const walk = (node) => {
      flat.push(node);
      if (node.children) node.children.forEach(walk);
    };
    walk(d.root);

    // Преобразуем в формат nodes для layout
    const newNodes = {};
    for (const n of flat) {
      if (!n.node_id) continue;
      newNodes[n.node_id] = {
        node_id: n.node_id,
        name: n.name || n.node_id,
        label: n.name || n.node_id,
        type: n.node_type || 'device',
        ip: n.ip || '',
        mac: n.mac || '',
        hops: n.hops || 0,
        via: n.via || '',
        parent: n.via || null,
        trust: 50,
      };
    }
    nodes = newNodes;
    rebuildStars();

    const count = flat.length;
    const el1 = document.getElementById('statNodes');
    const el2 = document.getElementById('hdrNodes');
    if (el1) el1.textContent = count;
    if (el2) el2.textContent = count;

    // Depth в statInfected (временно)
    const depth = d.stats && d.stats.max_depth ? d.stats.max_depth : 0;
    const el3 = document.getElementById('statInfected');
    const el4 = document.getElementById('hdrInfected');
    if (el3) el3.textContent = depth;
    if (el4) el4.textContent = depth;
  } catch (e) {
    console.debug('loadTree error:', e);
  }
}

function rebuildStars() {
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
}

// Socket: nodes_update
socket.on('nodes_update', d => {
  // P87: подтягиваем дерево, а не только nodes
  loadTreeFromAPI();
});

// Периодически обновляем дерево каждые 30 сек
setInterval(loadTreeFromAPI, 30000);
// При загрузке
setTimeout(loadTreeFromAPI, 2000);'''

# 3. Расширяем COLORS - добавляем traceroute, local_device, wifi
old_colors = "const COLORS = { self:'#30d158', wifi:'#0a84ff', bluetooth:'#64d2ff', peer:'#bf5af2', spore:'#ff375f', ble:'#5ac8fa', cellular:'#ffd60a', industrial:'#ff9f0a', super:'#ffffff' };"
new_colors = "const COLORS = { self:'#30d158', wifi:'#0a84ff', bluetooth:'#64d2ff', peer:'#bf5af2', spore:'#ff375f', ble:'#5ac8fa', cellular:'#ffd60a', industrial:'#ff9f0a', super:'#ffffff', inevionet:'#ffd60a', router:'#30d158', device:'#ffffff', traceroute:'#bf5af2', local_device:'#5ac8fa' };"

# 4. Расширяем RANK
old_rank = "const RANK = { self:0, wifi:1, super:2, spore:3, ble:4, bluetooth:5, cellular:6, industrial:7, peer:8 };"
new_rank = "const RANK = { self:0, inevionet:1, router:2, wifi:3, super:4, device:5, local_device:6, spore:7, ble:8, bluetooth:9, cellular:10, traceroute:11, industrial:12, peer:13 };"

patch_file(HTML, [
    (old_colors, new_colors, True),
    (old_rank, new_rank, True),
    (old_layout, new_layout, True),
    (old_load, new_load, True),
], "index.html P87", bak=".bak_p87")


print()
print("=" * 70)
print("  PATCH 87 DONE")
print("=" * 70)
print("  [OK] P84-fix: network_tree.py - wifi/inevionet/device/traceroute")
print("  [OK] P87: index.html - звёздное небо рисует дерево")
print()
print("Перезапусти: python -m web.app")
print()
print("И открой UI заново (Ctrl+F5 для сброса кэша)")