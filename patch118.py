import os
import ast
import re

ROOT = r"E:\InevioNet"
HTML = os.path.join(ROOT, "web", "templates", "index.html")

with open(HTML, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Заменить rebuildStars на более устойчивый
pattern = re.compile(
    r"function rebuildStars\(\) \{.*?\n\}",
    re.DOTALL
)
m = pattern.search(content)

if m:
    new_rebuild = '''function rebuildStars() {
  // P118: читаем из organism.nodes (100), fallback на nodes_sample (10)
  const org = state.organism || {};
  let nodes = org.nodes || org.nodes_sample || [];
  
  // P118: если nodes пусто — пробуем tree
  if (!nodes.length && state.tree && state.tree.root) {
    const flat = [];
    const walk = (n) => {
      flat.push([n.node_id || n.ip || 'unknown', {
        type: n.node_type || n.type || 'device',
        depth: n.depth || 1,
        parent: n.via || null,
        ip: n.ip || '',
        vendor: n.vendor || '',
      }]);
      if (n.children) n.children.forEach(walk);
    };
    walk(state.tree.root);
    nodes = flat;
  }
  
  console.log('[Tree] rebuildStars: nodes=' + nodes.length + ', sample=' + (org.nodes_sample?.length || 0));
  
  // Строим дерево
  const childrenOf = {};
  nodes.forEach(item => {
    const ip = item[0];
    const node = item[1];
    const parent = node.parent || '127.0.0.1';
    if (!childrenOf[parent]) childrenOf[parent] = [];
    childrenOf[parent].push({ ip, node });
  });
  
  const stars = [];
  const seen = {};
  
  // SELF — центр
  const selfItem = nodes.find(n => n[1].type === 'self' || n[0] === '127.0.0.1');
  if (selfItem) {
    seen[selfItem[0]] = true;
    stars.push({
      ip: selfItem[0], node: selfItem[1], type: 'self', depth: 0,
      x: 0, y: 0, r: 20,
      color: colorForType('self'),
      pulse: Math.random() * Math.PI * 2,
      parent: null,
      label: selfItem[0],
    });
  }
  
  // Секторная раскладка
  const sectorA = [];  // LAN/router/service
  const sectorB = [];  // InevioNet
  const ispClusters = {};
  
  nodes.forEach(item => {
    const ip = item[0];
    const node = item[1];
    const type = node.type || 'device';
    if (type === 'self' || seen[ip]) return;
    seen[ip] = true;
    if (type === 'lan_device' || type === 'service' || type === 'router') {
      sectorA.push(item);
    } else if (type === 'inevionet') {
      sectorB.push(item);
    } else if (type === 'isp_router') {
      const parts = ip.split('.');
      const prefix = parts.length === 4 ? parts[0]+'.'+parts[1]+'.'+parts[2] : ip;
      if (!ispClusters[prefix]) ispClusters[prefix] = { prefix, ips: [] };
      ispClusters[prefix].ips.push(ip);
    } else {
      sectorA.push(item);
    }
  });
  
  // LAN — сектор A
  const aCount = sectorA.length;
  sectorA.forEach((item, i) => {
    const ip = item[0];
    const node = item[1];
    const type = node.type || 'device';
    const angle = -Math.PI/4 + (Math.PI/2) * (aCount > 1 ? i/(aCount-1) : 0.5);
    let radius = type === 'router' ? 130 : 220 + (i % 3) * 40;
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
  
  // InevioNet — сектор B
  const bCount = sectorB.length;
  sectorB.forEach((item, i) => {
    const ip = item[0];
    const node = item[1];
    const angle = Math.PI/4 + (Math.PI/2) * (bCount > 1 ? i/(bCount-1) : 0.5);
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
  
  // ISP-кластеры
  const clusterKeys = Object.keys(ispClusters).sort();
  const dCount = clusterKeys.length;
  clusterKeys.forEach((key, i) => {
    const cl = ispClusters[key];
    const angle = Math.PI * (0.5 + (dCount > 1 ? i/(dCount-1) : 0.5) * 0.9);
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
  console.log('[Tree] stars created: ' + stars.length);
}'''
    content = content[:m.start()] + new_rebuild + content[m.end():]
    with open(HTML, "w", encoding="utf-8") as f:
        f.write(content)
    print("  [OK] rebuildStars переписан (P118)")
else:
    print("  [!!] rebuildStars не найден")