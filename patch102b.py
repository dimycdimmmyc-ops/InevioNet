import os
import ast
import shutil

ROOT = r"E:\InevioNet"
ORG = os.path.join(ROOT, "inevionet", "organism.py")
HTML = os.path.join(ROOT, "web", "templates", "index.html")

# =====================================================================
# 1. organism.py: добавлять parent в scout()
# =====================================================================

with open(ORG, "r", encoding="utf-8") as f:
    o = f.read()

# 1.1. LAN/router/service → parent = '127.0.0.1'
old_lan = '''                        found.append({
                            "ip": str(ip),
                            "mac": str(mac) if mac else "",
                            "vendor": str(vendor) if vendor else "",
                            "type": "lan_device", "source": "arp", "depth": 1,
                        })'''

new_lan = '''                        found.append({
                            "ip": str(ip),
                            "mac": str(mac) if mac else "",
                            "vendor": str(vendor) if vendor else "",
                            "type": "lan_device", "source": "arp", "depth": 1,
                            "parent": "127.0.0.1",
                        })'''

if old_lan in o:
    o = o.replace(old_lan, new_lan, 1)
    print("  [OK] LAN -> parent=127.0.0.1")

# 1.2. mDNS/service → parent = '127.0.0.1'
old_mdns = '''                        found.append({
                            "ip": ip, "type": "service",
                            "service": dev.get("server") or dev.get("source"),
                            "source": "mdns", "depth": 1,
                        })'''

new_mdns = '''                        found.append({
                            "ip": ip, "type": "service",
                            "service": dev.get("server") or dev.get("source"),
                            "source": "mdns", "depth": 1,
                            "parent": "127.0.0.1",
                        })'''

if old_mdns in o:
    o = o.replace(old_mdns, new_mdns, 1)
    print("  [OK] mDNS -> parent=127.0.0.1")

# 1.3. trusted → parent = '127.0.0.1'
old_trusted = '''                        found.append({
                            "ip": ip, "type": "inevionet",
                            "node_id": h.get("label"),
                            "source": "trusted", "depth": 1,
                        })'''

new_trusted = '''                        found.append({
                            "ip": ip, "type": "inevionet",
                            "node_id": h.get("label"),
                            "source": "trusted", "depth": 1,
                            "parent": "127.0.0.1",
                        })'''

if old_trusted in o:
    o = o.replace(old_trusted, new_trusted, 1)
    print("  [OK] trusted -> parent=127.0.0.1")

# 1.4. ISP → parent = '127.0.0.1' (для кластеризации)
old_isp = '''                for hop in tr.get("hops", []):
                    ip = hop.get("ip")
                    if ip and ip not in seen_ips:
                        found.append({
                            "ip": ip, "type": "isp_router",
                            "source": "traceroute", "depth": 2,
                        })
                        c_tr += 1
                        seen_ips.add(ip)'''

new_isp = '''                for hop in tr.get("hops", []):
                    ip = hop.get("ip")
                    if ip and ip not in seen_ips:
                        found.append({
                            "ip": ip, "type": "isp_router",
                            "source": "traceroute", "depth": 2,
                            "parent": "127.0.0.1",
                        })
                        c_tr += 1
                        seen_ips.add(ip)'''

if old_isp in o:
    o = o.replace(old_isp, new_isp, 1)
    print("  [OK] ISP -> parent=127.0.0.1")

# 1.5. isp_guess → parent = '127.0.0.1'
old_guess = '''                                found.append({
                                    "ip": guess_ip, "type": "isp_router",
                                    "source": "isp_guess", "depth": 3,
                                })'''

new_guess = '''                                found.append({
                                    "ip": guess_ip, "type": "isp_router",
                                    "source": "isp_guess", "depth": 3,
                                    "parent": "127.0.0.1",
                                })'''

if old_guess in o:
    o = o.replace(old_guess, new_guess, 1)
    print("  [OK] isp_guess -> parent=127.0.0.1")

with open(ORG, "w", encoding="utf-8") as f:
    f.write(o)
try:
    ast.parse(o)
    print("  [OK] organism.py syntax")
except SyntaxError as e:
    print("  [!!] syntax: " + str(e))


# =====================================================================
# 2. index.html: секторная раскладка
# =====================================================================

with open(HTML, "r", encoding="utf-8") as f:
    h = f.read()

# Найти rebuildStars (от "function rebuildStars" до "\n}")
import re
m = re.search(r"function rebuildStars\(\) \{.*?\n\}", h, re.DOTALL)
if m:
    old = m.group(0)
    new = '''function rebuildStars() {
  const nodes = (state.organism && (state.organism.nodes || state.organism.nodes_sample)) || [];

  // P102b: СЕКТОРНАЯ раскладка
  // SELF в центре. 4 сектора:
  //   - сектор A (0-90°):    LAN/router/service  (справа-сверху)
  //   - сектор B (90-180°):  INEVIONET           (слева-сверху)
  //   - сектор C (180-270°): Spore               (слева-снизу)
  //   - сектор D (270-360°): ISP-кластеры        (справа-снизу)

  const selfItem = nodes.find(n => n[1].type === 'self' || n[0] === '127.0.0.1');
  const stars = [];

  // SELF
  if (selfItem) {
    stars.push({
      ip: selfItem[0], node: selfItem[1], type: 'self', depth: 0,
      x: 0, y: 0, r: 22,
      color: colorForType('self'),
      pulse: Math.random() * Math.PI * 2,
      parent: null,
      label: selfItem[0],
    });
  }

  // Группируем
  const sectorA = [];  // LAN/router/service
  const sectorB = [];  // InevioNet
  const sectorC = [];  // Spore
  const ispClusters = {};  // prefix -> {prefix, ips}
  const routerNode = nodes.find(n => n[1].type === 'router');

  nodes.forEach(item => {
    const ip = item[0];
    const node = item[1];
    const type = node.type || 'device';
    if (type === 'self') return;
    if (type === 'lan_device' || type === 'service' || type === 'router') {
      sectorA.push(item);
    } else if (type === 'inevionet') {
      sectorB.push(item);
    } else if (type === 'spore') {
      sectorC.push(item);
    } else if (type === 'isp_router') {
      const parts = ip.split('.');
      const prefix = parts.length === 4 ? parts[0]+'.'+parts[1]+'.'+parts[2] : ip;
      if (!ispClusters[prefix]) ispClusters[prefix] = { prefix, ips: [] };
      ispClusters[prefix].ips.push(ip);
    }
  });

  // Сектор A: LAN/router/service — 0-90° (справа-сверху)
  // Сортируем: сначала router, потом lan_device/service
  sectorA.sort((a, b) => {
    const ta = a[1].type === 'router' ? 0 : 1;
    const tb = b[1].type === 'router' ? 0 : 1;
    return ta - tb;
  });
  const aCount = sectorA.length;
  const aStart = -Math.PI / 4;  // -45°
  const aEnd = Math.PI / 4;     // +45°
  sectorA.forEach((item, i) => {
    const ip = item[0];
    const node = item[1];
    const type = node.type || 'lan_device';
    const angle = aStart + (aEnd - aStart) * (aCount > 1 ? i / (aCount - 1) : 0.5);
    // Radius: router 130, lan 200-280
    let radius;
    if (type === 'router') radius = 130;
    else radius = 220 + (i % 3) * 40;
    const x = Math.cos(angle) * radius;
    const y = Math.sin(angle) * radius;
    let r = 6;
    if (type === 'router') r = 12;
    stars.push({
      ip, node, type, depth: 1,
      x, y, r,
      color: colorForType(type),
      pulse: Math.random() * Math.PI * 2,
      parent: '127.0.0.1',
      label: ip,
    });
  });

  // Сектор B: InevioNet — 90-180° (слева-сверху)
  const bCount = sectorB.length;
  const bStart = Math.PI / 4;       // 45°
  const bEnd = 3 * Math.PI / 4;     // 135°
  sectorB.forEach((item, i) => {
    const ip = item[0];
    const node = item[1];
    const angle = bStart + (bEnd - bStart) * (bCount > 1 ? i / (bCount - 1) : 0.5);
    const radius = 200;
    const x = Math.cos(angle) * radius;
    const y = Math.sin(angle) * radius;
    stars.push({
      ip, node, type: 'inevionet', depth: 1,
      x, y, r: 14,
      color: colorForType('inevionet'),
      pulse: Math.random() * Math.PI * 2,
      parent: '127.0.0.1',
      label: ip,
    });
  });

  // Сектор C: Spore — 180-270° (слева-снизу) — но не сейчас

  // Сектор D: ISP-кластеры — 270-360° (справа-снизу) + верхние 90°
  // Ставим ISP-кластеры ПОЛУКРУГОМ снизу (180°-360°)
  const clusterKeys = Object.keys(ispClusters).sort();
  const dCount = clusterKeys.length;
  clusterKeys.forEach((key, i) => {
    const cl = ispClusters[key];
    // Углы: от 90° (внизу) по часовой
    const angle = Math.PI * (0.5 + (dCount > 1 ? i / (dCount - 1) : 0.5) * 0.9);
    const radius = 260 + (i % 4) * 35;
    const x = Math.cos(angle) * radius;
    const y = Math.sin(angle) * radius;
    const size = Math.min(16, 7 + Math.log2(cl.ips.length + 1) * 2);
    stars.push({
      ip: key + '.0',
      node: { type: 'isp_router', depth: 2, ips: cl.ips, count: cl.ips.length, prefix: key },
      type: 'isp_router', depth: 2,
      x, y, r: size,
      color: colorForType('isp_router'),
      pulse: Math.random() * Math.PI * 2,
      parent: '127.0.0.1',
      label: key + '.0/24 (' + cl.ips.length + ')',
      isCluster: true,
      clusterIps: cl.ips,
      clusterCount: cl.ips.length,
    });
  });

  state.stars = stars;
  state.totalNodes = nodes.length;
}'''
    h = h.replace(old, new, 1)
    print("  [OK] rebuildStars: секторная раскладка")
else:
    print("  [!!] rebuildStars не найден")

with open(HTML, "w", encoding="utf-8") as f:
    f.write(h)

print()
print("=" * 70)
print("  PATCH 102B DONE")
print("=" * 70)
print("  [OK] Backend: parent у LAN/mDNS/trusted/ISP")
print("  [OK] Frontend: секторная раскладка")
print("  [OK] Легенда: LAN справа-сверху, InevioNet слева-сверху")
print("  [OK] Легенда: ISP кластеры снизу")
print()
print("Перезапуск + Ctrl+F5")