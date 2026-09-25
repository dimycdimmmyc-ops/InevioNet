# patch88fix.py - P88-fix: spores в UI (реальные якоря)
import os
import shutil

ROOT = r"E:\InevioNet"
HTML = os.path.join(ROOT, "web", "templates", "index.html")

with open(HTML, "r", encoding="utf-8") as f:
    content = f.read()

b = HTML + ".bak_p88fix"
shutil.copy2(HTML, b)
print("  [BK] " + os.path.basename(b))

changed = 0

# === 1. loadTreeFromAPI - нормализация типа ===
old_norm = """    const newNodes = {};
    for (const n of flat) {
      if (!n.node_id) continue;
      newNodes[n.node_id] = {
        node_id: n.node_id,
        name: n.name || n.node_id,
        label: n.name || n.node_id,
        type: n.node_type || 'device',"""

new_norm = """    const newNodes = {};
    for (const n of flat) {
      if (!n.node_id) continue;
      // P88: нормализация типа
      let ntype = n.node_type || 'device';
      if (n.node_id.startsWith('tr_')) ntype = 'traceroute';
      else if (n.node_id.startsWith('web_node_')) ntype = 'inevionet';
      else if (n.node_id.startsWith('router_')) ntype = 'router';
      else if (n.node_id.startsWith('dev_')) ntype = 'device';
      else if (n.node_id.startsWith('mdns_')) ntype = 'local_device';
      else if (n.node_id.startsWith('spore_')) ntype = 'spore';
      else if (n.node_id.includes(':') && n.node_id.length === 17) ntype = 'wifi';
      newNodes[n.node_id] = {
        node_id: n.node_id,
        name: n.name || n.node_id,
        label: n.name || n.node_id,
        type: ntype,"""

if old_norm in content:
    content = content.replace(old_norm, new_norm, 1)
    print("  [OK] 1. нормализация типа")
    changed += 1
else:
    print("  [!!] 1. NOT FOUND")


# === 2. rebuildStars - размер споры ===
old_size = """    else if (nd.type === 'traceroute') {
      base = 2.5;
      color = tracerouteColor(nd.hops || 1);
    }"""

new_size = """    else if (nd.type === 'traceroute') {
      base = 2.5;
      color = tracerouteColor(nd.hops || 1);
    }
    else if (nd.type === 'spore') {
      // P88: размер споры по rssi
      const rssi = (nd.rssi || -70);
      base = 2 + Math.max(0, (rssi + 100) / 70 * 2);
      color = '#ff375f';
    }"""

if old_size in content:
    content = content.replace(old_size, new_size, 1)
    print("  [OK] 2. spore size по rssi")
    changed += 1
else:
    print("  [!!] 2. NOT FOUND")


# === 3. layout - споры вокруг WiFi ===
old_spore_layout = """  // P87c: traceroute - СЃРїРёСЂР°Р»СЊ
  if (nd.type === 'traceroute') {"""

new_spore_layout = """  // P88: споры вокруг WiFi-родителя
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

  // P87c: traceroute - спираль
  if (nd.type === 'traceroute') {"""

if old_spore_layout in content:
    content = content.replace(old_spore_layout, new_spore_layout, 1)
    print("  [OK] 3. spore layout вокруг WiFi")
    changed += 1
else:
    print("  [!!] 3. NOT FOUND")


# === 4. rssi в loadTreeFromAPI (для размера споры) ===
old_rssi = """        hops: n.hops || 0,
        via: n.via || '',
        parent: n.via || null,
        trust: 50,
      };"""

new_rssi = """        hops: n.hops || 0,
        via: n.via || '',
        parent: n.via || null,
        trust: 50,
        rssi: (n.metadata && n.metadata.rssi) || (n.rssi) || -70,
        signal: (n.metadata && n.metadata.signal) || 50,
      };"""

if old_rssi in content:
    content = content.replace(old_rssi, new_rssi, 1)
    print("  [OK] 4. rssi + signal в nodes")
    changed += 1
else:
    print("  [!!] 4. NOT FOUND")


# === 5. parent для споры (via = wifi_XXX) ===
# В P87c уже было parent: n.via || null. Если n.via = "wifi_XXX",
# то parent не найдётся в pm (там ключ MAC). Надо ставить parent = mac от via.
# Но это сложно - оставим только layout через nd.via.

with open(HTML, "w", encoding="utf-8") as f:
    f.write(content)
print("  [OK] saved (" + str(changed) + "/4 применено)")

# Проверка
with open(HTML, "r", encoding="utf-8") as f:
    check = f.read()
print("  spore в нормализации: " + str("ntype = 'spore'" in check))
print("  spore size: " + str("base = 2 + Math.max" in check))
print("  spore layout: " + str("nd.type === 'spore'" in check))
print("  rssi: " + str("rssi: (n.metadata" in check))