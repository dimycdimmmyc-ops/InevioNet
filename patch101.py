import os
import ast
import shutil

ROOT = r"E:\InevioNet"
HTML = os.path.join(ROOT, "web", "templates", "index.html")
DD = os.path.join(ROOT, "inevionet", "network", "dead_drop.py")
ORG = os.path.join(ROOT, "inevionet", "organism.py")

# =====================================================================
# ЧАСТЬ 1: MERGE-FIX (P97-fix5) — my_url в feed + auto-subscribe
# =====================================================================

print()
print("=" * 70)
print("  ЧАСТЬ 1: Merge-fix")
print("=" * 70)

with open(DD, "r", encoding="utf-8") as f:
    dd_content = f.read()

# 1.1. feed с my_url + cards
old_feed = '''        feed = json.dumps({
            "node_id": self.node_id,
            "ts": time.time(),
            "my_url": self.my_url,
            "peers": [{"node_id": nid, "url": u} for nid, u in urls],
            "cards": cards,
        }, separators=(",", ":"))'''

new_feed = '''        feed = json.dumps({
            "node_id": self.node_id,
            "ts": time.time(),
            "my_url": self.my_url,
            "peers": [{"node_id": nid, "url": u} for nid, u in urls],
            "cards": cards,
        }, separators=(",", ":"))'''

if old_feed in dd_content:
    print("  [--] feed уже содержит my_url")

# 1.2. auto-subscribe (из sender.my_url)
old_read = '''                        # Читаем peers
                        for p in feed.get("peers", []):
                            if p.get("node_id") and p.get("url"):
                                self.register_peer(p["node_id"], p["url"])
                        # P99: авто-подписка на feed от sender
                        sender = feed.get("node_id", "")
                        my_url = feed.get("my_url", "")
                        if sender and my_url and sender != self.node_id:
                            self.register_peer(sender, my_url)
                except Exception:
                    pass'''

new_read = '''                        # Читаем peers
                        for p in feed.get("peers", []):
                            if p.get("node_id") and p.get("url"):
                                self.register_peer(p["node_id"], p["url"])
                        # P101: авто-подписка на feed от sender (my_url)
                        sender = feed.get("node_id", "")
                        peer_my_url = feed.get("my_url", "")
                        if sender and peer_my_url and sender != self.node_id:
                            # Если у нас есть свежий URL peer — обновить
                            with self._lock:
                                current = self.peer_urls.get(sender, "")
                            if current != peer_my_url:
                                self.register_peer(sender, peer_my_url)
                                logger.info("[DeadDrop] auto-subscribe %s -> %s",
                                            sender, peer_my_url[:60])
                        # P101: читаем cards из feed
                        for card_url in feed.get("cards", []):
                            if card_url and card_url not in self._seen_ids:
                                self._seen_ids.add(card_url)
                                card_text = self._fetch(card_url)
                                if card_text:
                                    card_msg = DropMessage.from_text(card_text)
                                    if card_msg and card_msg.verify():
                                        if (card_msg.receiver == self.node_id or
                                                card_msg.receiver == "broadcast"):
                                            self._handle_message(card_msg)
                except Exception:
                    pass'''

if old_read in dd_content:
    dd_content = dd_content.replace(old_read, new_read, 1)
    with open(DD, "w", encoding="utf-8") as f:
        f.write(dd_content)
    try:
        ast.parse(dd_content)
        print("  [OK] dead_drop.py: auto-subscribe + cards")
    except SyntaxError as e:
        print("  [!!] syntax: " + str(e))
else:
    print("  [--] auto-subscribe уже есть")

# 1.3. Проверим get_inbox — не блокирует ли broadcast
with open(DD, "r", encoding="utf-8") as f:
    dd_content = f.read()
if 'msg.receiver == "broadcast"' in dd_content:
    print("  [OK] broadcast уже пропускается")
else:
    print("  [!!] broadcast не пропускается")

# =====================================================================
# ЧАСТЬ 2: ГРАФ — кластеризация ISP + иерархия parent
# =====================================================================

print()
print("=" * 70)
print("  ЧАСТЬ 2: Граф — кластеризация + иерархия")
print("=" * 70)

with open(HTML, "r", encoding="utf-8") as f:
    html_content = f.read()

# 2.1. Заменить rebuildStars — кластеризация ISP
old_rebuild = '''function rebuildStars() {
  const nodes = (state.organism && (state.organism.nodes || state.organism.nodes_sample)) || [];
  
  // P100c: TREE layout по глубине
  // depth 0 = self (центр)
  // depth 1 = 1-е кольцо
  // depth 2 = 2-е кольцо
  // ...
  
  // Группируем по depth
  const byDepth = {};
  nodes.forEach(item => {
    const d = item[1].depth !== undefined ? item[1].depth : 1;
    if (!byDepth[d]) byDepth[d] = [];
    byDepth[d].push(item);
  });
  
  const depths = Object.keys(byDepth).map(Number).sort((a, b) => a - b);
  const stars = [];
  
  depths.forEach(depth => {
    const group = byDepth[depth];
    const count = group.length;
    
    // Радиус кольца
    let radius;
    if (depth === 0) radius = 0;
    else if (depth === 1) radius = 140;
    else radius = 140 + (depth - 1) * 90;
    
    group.forEach((item, i) => {
      const ip = item[0];
      const node = item[1];
      const type = node.type || 'device';
      
      // Угол: для depth 0 - 0, для остальных - по кругу
      let angle;
      if (depth === 0) {
        angle = 0;
      } else if (count === 1) {
        angle = hashAngle(ip);
      } else {
        angle = (i / count) * Math.PI * 2 + (depth * 0.3);
      }
      
      const x = Math.cos(angle) * radius;
      const y = Math.sin(angle) * radius;
      
      // Радиус точки
      let r = 5;
      if (type === 'self') r = 16;
      else if (type === 'router') r = 8;
      else if (type === 'inevionet') r = 10;
      else if (type === 'isp_router') r = 6;
      else if (type === 'spore') r = 5;
      else if (type === 'lan_device') r = 6;
      
      stars.push({
        ip, node, type, depth,
        x, y, r,
        color: colorForType(type),
        pulse: Math.random() * Math.PI * 2,
        parent: node.parent || (depth > 0 ? '127.0.0.1' : null),
        label: ip,
      });
    });
  });
  
  state.stars = stars;
}'''

new_rebuild = '''function rebuildStars() {
  const nodes = (state.organism && (state.organism.nodes || state.organism.nodes_sample)) || [];
  
  // P101: КЛАСТЕРИЗАЦИЯ
  // 1. self — центр
  // 2. LAN/router — 1-е кольцо (мало, детально)
  // 3. InevioNet — 1-е кольцо (важные)
  // 4. ISP — КЛАСТЕРЫ по подсети /24 (212.188.16.x -> один узел)
  // 5. Spores — на WiFi
  
  const selfNodes = [];
  const lanNodes = [];
  const inevNodes = [];
  const ispClusters = {};  // prefix -> {ips: [], x, y}
  const sporeNodes = [];
  
  nodes.forEach(item => {
    const ip = item[0];
    const node = item[1];
    const type = node.type || 'device';
    const depth = node.depth !== undefined ? node.depth : 1;
    
    if (type === 'self') {
      selfNodes.push(item);
    } else if (type === 'lan_device' || type === 'service' || type === 'router') {
      lanNodes.push(item);
    } else if (type === 'inevionet') {
      inevNodes.push(item);
    } else if (type === 'isp_router') {
      // P101: кластеризация по подсети /24
      const parts = ip.split('.');
      if (parts.length === 4) {
        const prefix = parts[0] + '.' + parts[1] + '.' + parts[2];
        if (!ispClusters[prefix]) {
          ispClusters[prefix] = { prefix, ips: [], item: null, depth };
        }
        ispClusters[prefix].ips.push(ip);
      } else {
        // fallback
        const prefix = ip;
        if (!ispClusters[prefix]) {
          ispClusters[prefix] = { prefix, ips: [], item: null, depth };
        }
        ispClusters[prefix].ips.push(ip);
      }
    } else if (type === 'spore') {
      sporeNodes.push(item);
    }
  });
  
  const stars = [];
  const centerX = 0, centerY = 0;
  
  // 1. SELF — центр
  selfNodes.forEach(item => {
    stars.push({
      ip: item[0], node: item[1], type: 'self', depth: 0,
      x: 0, y: 0, r: 20,
      color: colorForType('self'),
      pulse: Math.random() * Math.PI * 2,
      parent: null,
      label: item[0],
    });
  });
  
  // 2. LAN — 1-е кольцо (детально)
  lanNodes.forEach((item, i) => {
    const ip = item[0];
    const node = item[1];
    const count = lanNodes.length;
    const angle = (i / Math.max(1, count)) * Math.PI * 2 + 0.3;
    const radius = 130;
    const x = Math.cos(angle) * radius;
    const y = Math.sin(angle) * radius;
    let r = 7;
    if (node.type === 'router') r = 10;
    stars.push({
      ip, node, type: node.type || 'lan_device', depth: 1,
      x, y, r,
      color: colorForType(node.type || 'lan_device'),
      pulse: Math.random() * Math.PI * 2,
      parent: '127.0.0.1',
      label: ip,
    });
  });
  
  // 3. InevioNet — 1-е кольцо (важные, отдельный угол)
  inevNodes.forEach((item, i) => {
    const ip = item[0];
    const node = item[1];
    const count = inevNodes.length;
    const angle = -Math.PI / 2 + (i / Math.max(1, count)) * Math.PI * 2;
    const radius = 200;
    const x = Math.cos(angle) * radius;
    const y = Math.sin(angle) * radius;
    stars.push({
      ip, node, type: 'inevionet', depth: 1,
      x, y, r: 12,
      color: colorForType('inevionet'),
      pulse: Math.random() * Math.PI * 2,
      parent: '127.0.0.1',
      label: ip,
      isCluster: false,
    });
  });
  
  // 4. ISP — КЛАСТЕРЫ (2-е кольцо)
  const clusterKeys = Object.keys(ispClusters).sort();
  const numClusters = clusterKeys.length;
  clusterKeys.forEach((key, i) => {
    const cl = ispClusters[key];
    const angle = (i / Math.max(1, numClusters)) * Math.PI * 2;
    const radius = 320;
    const x = Math.cos(angle) * radius;
    const y = Math.sin(angle) * radius;
    // Размер кластера — по количеству IP
    const size = Math.min(14, 6 + Math.log2(cl.ips.length + 1) * 2);
    stars.push({
      ip: key + '.0',  // виртуальный IP для кластера
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
  
  // 5. Spores — на WiFi (3-е кольцо, если есть)
  sporeNodes.slice(0, 30).forEach((item, i) => {
    const ip = item[0];
    const node = item[1];
    const angle = (i / Math.max(1, Math.min(30, sporeNodes.length))) * Math.PI * 2;
    const radius = 400 + (i % 3) * 30;
    const x = Math.cos(angle) * radius;
    const y = Math.sin(angle) * radius;
    stars.push({
      ip, node, type: 'spore', depth: 3,
      x, y, r: 6,
      color: colorForType('spore'),
      pulse: Math.random() * Math.PI * 2,
      parent: '127.0.0.1',
      label: ip,
    });
  });
  
  state.stars = stars;
  state.totalNodes = nodes.length;
  state.clustersInfo = {
    lan: lanNodes.length,
    inev: inevNodes.length,
    ispClusters: numClusters,
    ispTotal: Object.values(ispClusters).reduce((s, c) => s + c.ips.length, 0),
    spores: sporeNodes.length,
  };
}'''

if old_rebuild in html_content:
    html_content = html_content.replace(old_rebuild, new_rebuild, 1)
    print("  [OK] rebuildStars: кластеризация ISP")
else:
    print("  [!!] rebuildStars не найден")

# 2.2. animate — клик по кластеру раскрывает
old_anim = '''  // Узлы
  state.stars.forEach(s => {
    s.pulse += 0.03;
    const pr = s.r * (1 + Math.sin(s.pulse) * 0.12);
    
    // Glow
    const grad = ctx.createRadialGradient(s.x, s.y, 0, s.x, s.y, pr * 3.5);
    grad.addColorStop(0, s.color + '70');
    grad.addColorStop(1, s.color + '00');
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(s.x, s.y, pr * 3.5, 0, Math.PI * 2);
    ctx.fill();
    
    // Core
    ctx.fillStyle = s.color;
    ctx.beginPath();
    ctx.arc(s.x, s.y, pr, 0, Math.PI * 2);
    ctx.fill();
    
    // Self — белый центр
    if (s.type === 'self') {
      ctx.fillStyle = '#fff';
      ctx.beginPath();
      ctx.arc(s.x, s.y, pr * 0.35, 0, Math.PI * 2);
      ctx.fill();
    }
    
    // P100c: подписи (только для self/router/inevionet, если zoom > 0.5)
    if (state.camera.zoom > 0.5) {
      const showLabel = s.type === 'self' || s.type === 'router' ||
                        s.type === 'inevionet' || s.r >= 6;
      if (showLabel) {
        ctx.font = Math.max(8, 10 / state.camera.zoom) + 'px -apple-system,sans-serif';
        ctx.fillStyle = 'rgba(230,237,243,0.75)';
        ctx.textAlign = 'center';
        ctx.fillText(s.label, s.x, s.y + pr + 12 / state.camera.zoom);
      }
    }
  });'''

new_anim = '''  // Узлы
  state.stars.forEach(s => {
    s.pulse += 0.03;
    const pr = s.r * (1 + Math.sin(s.pulse) * 0.12);
    
    // Glow
    const grad = ctx.createRadialGradient(s.x, s.y, 0, s.x, s.y, pr * 3.5);
    grad.addColorStop(0, s.color + '70');
    grad.addColorStop(1, s.color + '00');
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(s.x, s.y, pr * 3.5, 0, Math.PI * 2);
    ctx.fill();
    
    // Core
    ctx.fillStyle = s.color;
    ctx.beginPath();
    ctx.arc(s.x, s.y, pr, 0, Math.PI * 2);
    ctx.fill();
    
    // Self — белый центр
    if (s.type === 'self') {
      ctx.fillStyle = '#fff';
      ctx.beginPath();
      ctx.arc(s.x, s.y, pr * 0.35, 0, Math.PI * 2);
      ctx.fill();
    }
    
    // P101: кластер ISP — кольцо вокруг
    if (s.isCluster) {
      ctx.strokeStyle = s.color + 'aa';
      ctx.lineWidth = 2 / state.camera.zoom;
      ctx.beginPath();
      ctx.arc(s.x, s.y, pr + 6 / state.camera.zoom, 0, Math.PI * 2);
      ctx.stroke();
      // Число внутри
      ctx.fillStyle = '#fff';
      ctx.font = 'bold ' + Math.max(9, 11 / state.camera.zoom) + 'px -apple-system,sans-serif';
      ctx.textAlign = 'center';
      ctx.textBaseline = 'middle';
      ctx.fillText(s.clusterCount, s.x, s.y + 1 / state.camera.zoom);
      ctx.textBaseline = 'alphabetic';
    }
    
    // P101: подписи
    const showLabel = s.type === 'self' || s.type === 'router' ||
                      s.type === 'inevionet' || s.isCluster ||
                      (s.r >= 6 && state.camera.zoom > 0.4);
    if (showLabel && state.camera.zoom > 0.3) {
      ctx.font = Math.max(9, 11 / state.camera.zoom) + 'px -apple-system,sans-serif';
      ctx.fillStyle = s.type === 'self' ? 'rgba(255,255,255,0.95)' :
                      s.isCluster ? 'rgba(163,113,247,0.95)' :
                      'rgba(230,237,243,0.75)';
      ctx.textAlign = 'center';
      const labelY = s.isCluster ? s.y - pr - 8 / state.camera.zoom :
                                   s.y + pr + 12 / state.camera.zoom;
      ctx.fillText(s.label, s.x, labelY);
    }
  });'''

if old_anim in html_content:
    html_content = html_content.replace(old_anim, new_anim, 1)
    print("  [OK] animate: кластеры + подписи")

# 2.3. Клик по кластеру — показать все IP (alert или в деталях)
old_click = '''  c.addEventListener('click', e => {
    if (state.dragging) return;
    const rect = c.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const wx = (mx - state.camera.x) / state.camera.zoom;
    const wy = (my - state.camera.y) / state.camera.zoom;
    for (const s of state.stars) {
      const dx = s.x - wx, dy = s.y - wy;
      if (dx*dx + dy*dy < (s.r + 6) * (s.r + 6)) {
        selectNode(s.ip);
        return;
      }
    }
  });'''

new_click = '''  c.addEventListener('click', e => {
    if (state.dragging) return;
    const rect = c.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const wx = (mx - state.camera.x) / state.camera.zoom;
    const wy = (my - state.camera.y) / state.camera.zoom;
    for (const s of state.stars) {
      const dx = s.x - wx, dy = s.y - wy;
      if (dx*dx + dy*dy < (s.r + 8) * (s.r + 8)) {
        // P101: клик по кластеру ISP — показать IP
        if (s.isCluster) {
          renderClusterDetail(s);
          switchToTab('detail');
        } else {
          selectNode(s.ip);
        }
        return;
      }
    }
  });'''

if old_click in html_content:
    html_content = html_content.replace(old_click, new_click, 1)
    print("  [OK] click: кластеры")

# 2.4. renderClusterDetail
old_sel = '''function renderDetail(node) {'''

new_sel = '''function renderClusterDetail(cluster) {
  const ips = cluster.clusterIps || [];
  const list = ips.slice(0, 50).map(ip => '<div class="detail-row"><span class="l">' + ip + '</span><span class="v">ISP</span></div>').join('');
  $('detailPanel').innerHTML =
    '<div class="detail-header">' +
      '<div class="detail-ip">' + cluster.node.prefix + '.0/24</div>' +
      '<div class="detail-meta">' +
        '<span class="tag purple">ISP CLUSTER</span>' +
        '<span class="tag">' + cluster.clusterCount + ' hosts</span>' +
      '</div>' +
    '</div>' +
    '<div class="nlp-block">' +
      '<div class="nlp-title">&#x1F310; Узлы кластера</div>' +
      list +
      (ips.length > 50 ? '<div class="empty" style="padding:8px">... +' + (ips.length - 50) + '</div>' : '') +
    '</div>';
}

function renderDetail(node) {'''

if old_sel in html_content:
    html_content = html_content.replace(old_sel, new_sel, 1)
    print("  [OK] renderClusterDetail")

# 2.5. toggleLayout — tree / radial / grid (tree по умолчанию)
old_layout = '''function toggleLayout() {
  const layouts = ['tree', 'radial', 'grid'];
  const i = layouts.indexOf(state.layout);
  state.layout = layouts[(i + 1) % layouts.length];
  rebuildStars();
  setTimeout(fitView, 200);
  addLog('Раскладка: ' + state.layout, 'info');
}'''

new_layout = '''function toggleLayout() {
  // P101: только tree (кластеры)
  const layouts = ['tree'];
  state.layout = 'tree';
  rebuildStars();
  setTimeout(fitView, 200);
  addLog('Раскладка: tree (ISP кластеры)', 'info');
}'''

if old_layout in html_content:
    html_content = html_content.replace(old_layout, new_layout, 1)
    print("  [OK] toggleLayout: только tree")

with open(HTML, "w", encoding="utf-8") as f:
    f.write(html_content)

print()
print("=" * 70)
print("  PATCH 101 + 97-FIX5 DONE")
print("=" * 70)
print("  [OK] Merge: auto-subscribe + cards в feed")
print("  [OK] Граф: ISP-кластеры по /24")
print("  [OK] Граф: клик по кластеру -> список IP")
print("  [OK] Граф: числа внутри кластеров")
print()
print("Стоп + перезапуск + Ctrl+F5")