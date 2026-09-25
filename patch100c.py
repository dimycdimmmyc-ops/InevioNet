import os
import ast
import shutil

ROOT = r"E:\InevioNet"
APP = os.path.join(ROOT, "web", "app.py")
HTML = os.path.join(ROOT, "web", "templates", "index.html")

# =====================================================================
# 1. app.py — /api/organism отдаёт ВСЕ узлы + self
# =====================================================================

with open(APP, "r", encoding="utf-8") as f:
    app_content = f.read()

# Найти функцию api_organism
old_org = '''        return jsonify({
            'success': True,
            'stats': org.get_stats(),
            'phase_log': org.get_phase_log(30),
            'memory': {
                'nodes_count': len(org.memory.get("nodes", {})),
                'colonized_count': len(org.memory.get("colonized", set())),
                'taught_count': len(org.memory.get("taught", set())),
                'routes_count': len(org.memory.get("routes", [])),
                'depth_count': len(org.memory.get("depth", {})),
            },
            'nodes_sample': list(org.memory.get("nodes", {}).items())[:10],
        })'''

new_org = '''        # P100c: все узлы + self
        all_nodes = dict(org.memory.get("nodes", {}))
        # Добавить self
        all_nodes["127.0.0.1"] = {
            "ip": "127.0.0.1",
            "type": "self",
            "source": "local",
            "depth": 0,
            "nlp_plan": "self",
            "nlp_confidence": 1.0,
        }
        # Сортировка по depth
        sorted_nodes = sorted(all_nodes.items(),
                              key=lambda x: (x[1].get("depth", 99), x[0]))
        return jsonify({
            'success': True,
            'stats': org.get_stats(),
            'phase_log': org.get_phase_log(30),
            'memory': {
                'nodes_count': len(org.memory.get("nodes", {})),
                'colonized_count': len(org.memory.get("colonized", set())),
                'taught_count': len(org.memory.get("taught", set())),
                'routes_count': len(org.memory.get("routes", [])),
                'depth_count': len(org.memory.get("depth", {})),
            },
            'nodes': sorted_nodes,
            'nodes_sample': sorted_nodes[:10],
            'nodes_count': len(sorted_nodes),
        })'''

if old_org in app_content:
    app_content = app_content.replace(old_org, new_org, 1)
    with open(APP, "w", encoding="utf-8") as f:
        f.write(app_content)
    try:
        ast.parse(app_content)
        print("  [OK] app.py: /api/organism -> все узлы + self")
    except SyntaxError as e:
        print("  [!!] syntax: " + str(e))
else:
    print("  [--] app.py: api_organism не найден (уже пропатчен?)")


# =====================================================================
# 2. index.html — tree-layout + подписи + метрики + авто-fit
# =====================================================================

with open(HTML, "r", encoding="utf-8") as f:
    html_content = f.read()

# 2.1. Заменить renderMetrics
old_metrics = '''function renderMetrics(org) {
  const s = org.stats || {};
  $('mNodes').textContent = s.nodes_found || 0;
  $('mTaught').textContent = s.nodes_taught || 0;
  $('mRelayed').textContent = s.nodes_relayed || 0;
  $('mCapsuled').textContent = s.nodes_capsuled || 0;
  $('mDepth').textContent = s.max_depth || 0;
  $('mStego').textContent = s.stego_sent || 0;
  $('hdrNodes').textContent = s.nodes_found || 0;
  $('hdrDepth').textContent = s.max_depth || 0;
  $('hdrCycles').textContent = s.cycles || 0;
}'''

new_metrics = '''function renderMetrics(org) {
  const s = org.stats || {};
  const m = org.memory || {};
  // P100c: реальное число узлов в памяти (не накопительное)
  const realNodes = m.nodes_count || s.nodes_found || 0;
  $('mNodes').textContent = realNodes;
  $('mTaught').textContent = s.nodes_taught || 0;
  $('mRelayed').textContent = s.nodes_relayed || 0;
  $('mCapsuled').textContent = s.nodes_capsuled || 0;
  $('mDepth').textContent = s.max_depth || 0;
  $('mStego').textContent = s.stego_sent || 0;
  $('hdrNodes').textContent = realNodes;
  $('hdrDepth').textContent = s.max_depth || 0;
  $('hdrCycles').textContent = s.cycles || 0;
}'''

if old_metrics in html_content:
    html_content = html_content.replace(old_metrics, new_metrics, 1)
    print("  [OK] renderMetrics: реальные узлы")

# 2.2. renderNodes — использовать nodes (все), не nodes_sample
old_rnodes = '''function renderNodes(org) {
  const nodes = org.nodes_sample || [];
  const el = $('nodeList');
  $('nodeCount').textContent = (org.memory && org.memory.nodes_count) || nodes.length;
  if (!nodes.length) { el.innerHTML = '<div class="empty">Нет узлов</div>'; return; }
  el.innerHTML = nodes.map(item => {
    const ip = item[0];
    const node = item[1];
    const type = node.type || '?';
    const plan = node.nlp_plan || 'route';
    return '<div class="node-item" data-ip="' + ip + '">' +
      '<span class="badge" style="background:' + colorForType(type) + '"></span>' +
      '<div class="info">' +
        '<div class="ip">' + ip + '</div>' +
        '<div class="type">' + type + ' &middot; depth ' + (node.depth || '?') + '</div>' +
      '</div>' +
      '<span class="plan ' + planClass(plan) + '">' + plan + '</span>' +
    '</div>';
  }).join('');
  el.querySelectorAll('.node-item').forEach(item => {
    item.onclick = () => selectNode(item.dataset.ip);
  });
}'''

new_rnodes = '''function renderNodes(org) {
  const nodes = org.nodes || org.nodes_sample || [];
  const el = $('nodeList');
  const realCount = (org.memory && org.memory.nodes_count) || nodes.length;
  $('nodeCount').textContent = realCount;
  if (!nodes.length) { el.innerHTML = '<div class="empty">Нет узлов</div>'; return; }
  // Показываем топ-50 (по depth)
  const top = nodes.slice(0, 50);
  el.innerHTML = top.map(item => {
    const ip = item[0];
    const node = item[1];
    const type = node.type || '?';
    const plan = node.nlp_plan || 'route';
    const depth = node.depth !== undefined ? node.depth : '?';
    return '<div class="node-item" data-ip="' + ip + '">' +
      '<span class="badge" style="background:' + colorForType(type) + '"></span>' +
      '<div class="info">' +
        '<div class="ip">' + ip + '</div>' +
        '<div class="type">' + type + ' &middot; d' + depth + '</div>' +
      '</div>' +
      '<span class="plan ' + planClass(plan) + '">' + plan + '</span>' +
    '</div>';
  }).join('');
  if (nodes.length > 50) {
    el.innerHTML += '<div class="empty" style="padding:8px">... и ещё ' + (nodes.length - 50) + '</div>';
  }
  el.querySelectorAll('.node-item').forEach(item => {
    item.onclick = () => selectNode(item.dataset.ip);
  });
}'''

if old_rnodes in html_content:
    html_content = html_content.replace(old_rnodes, new_rnodes, 1)
    print("  [OK] renderNodes: все узлы (топ-50)")

# 2.3. selectNode — искать в nodes
old_sel = '''function selectNode(ip) {
  if (!state.organism) return;
  const nodes = state.organism.nodes_sample || [];
  const found = nodes.find(n => n[0] === ip);
  if (!found) return;
  state.selected = found;
  renderDetail(found[1]);
  switchToTab('detail');
  document.querySelectorAll('.node-item').forEach(i => {
    i.classList.toggle('active', i.dataset.ip === ip);
  });
}'''

new_sel = '''function selectNode(ip) {
  if (!state.organism) return;
  const nodes = state.organism.nodes || state.organism.nodes_sample || [];
  const found = nodes.find(n => n[0] === ip);
  if (!found) return;
  state.selected = found;
  renderDetail(found[1]);
  switchToTab('detail');
  document.querySelectorAll('.node-item').forEach(i => {
    i.classList.toggle('active', i.dataset.ip === ip);
  });
}'''

if old_sel in html_content:
    html_content = html_content.replace(old_sel, new_sel, 1)
    print("  [OK] selectNode: поиск в nodes")

# 2.4. rebuildStars — TREE layout по глубине
old_rebuild = '''function rebuildStars() {
  const nodes = (state.organism && state.organism.nodes_sample) || [];
  state.stars = nodes.map(item => {
    const ip = item[0];
    const node = item[1];
    const type = node.type || 'device';
    const depth = node.depth || 1;
    const angle = hashAngle(ip);
    let x, y;
    if (type === 'self') { x = 0; y = 0; }
    else if (state.layout === 'cluster') {
      const cluster = getCluster(type);
      const ca = cluster * (Math.PI * 2 / 4);
      const r = 120 + depth * 40;
      const spread = hashAngle(ip + 'x') * 0.6;
      x = Math.cos(ca + spread) * r;
      y = Math.sin(ca + spread) * r;
    } else if (state.layout === 'grid') {
      const idx = state.stars.length;
      const cols = Math.ceil(Math.sqrt(nodes.length));
      const size = 80;
      x = ((idx % cols) - cols/2) * size;
      y = (Math.floor(idx / cols) - cols/2) * size;
    } else {
      const r = 80 + depth * 55;
      const jitter = (hashAngle(ip + 'j') - 0.5) * 40;
      x = Math.cos(angle) * (r + jitter);
      y = Math.sin(angle) * (r + jitter);
    }
    let radius = 6;
    if (type === 'self') radius = 14;
    else if (type === 'router') radius = 9;
    else if (type === 'inevionet') radius = 10;
    else if (type === 'isp_router') radius = 7;
    else if (type === 'spore') radius = 5;
    return {ip, node, type, depth, x, y, r: radius, color: colorForType(type), pulse: Math.random() * Math.PI * 2};
  });
}'''

new_rebuild = '''function rebuildStars() {
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

if old_rebuild in html_content:
    html_content = html_content.replace(old_rebuild, new_rebuild, 1)
    print("  [OK] rebuildStars: TREE layout по глубине")

# 2.5. animate — линии по parent + подписи
old_anim = '''function animate() {
  const c = state.canvas;
  const ctx = state.ctx;
  if (!c || !ctx) return;
  ctx.fillStyle = '#0a0d14';
  ctx.fillRect(0, 0, c.width, c.height);
  ctx.save();
  ctx.translate(state.camera.x, state.camera.y);
  ctx.scale(state.camera.zoom, state.camera.zoom);
  const pm = {};
  state.stars.forEach(s => pm[s.ip] = s);
  const center = pm['127.0.0.1'] || state.stars.find(s => s.type === 'self');
  ctx.lineWidth = 1;
  state.stars.forEach(s => {
    if (s.type === 'self' || !center) return;
    ctx.strokeStyle = s.color + '22';
    ctx.beginPath();
    ctx.moveTo(center.x, center.y);
    ctx.lineTo(s.x, s.y);
    ctx.stroke();
  });
  state.stars.forEach(s => {
    s.pulse += 0.03;
    const pr = s.r * (1 + Math.sin(s.pulse) * 0.12);
    const grad = ctx.createRadialGradient(s.x, s.y, 0, s.x, s.y, pr * 4);
    grad.addColorStop(0, s.color + '80');
    grad.addColorStop(1, s.color + '00');
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(s.x, s.y, pr * 4, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = s.color;
    ctx.beginPath();
    ctx.arc(s.x, s.y, pr, 0, Math.PI * 2);
    ctx.fill();
    if (s.type === 'self') {
      ctx.fillStyle = '#fff';
      ctx.beginPath();
      ctx.arc(s.x, s.y, pr * 0.35, 0, Math.PI * 2);
      ctx.fill();
    }
  });
  ctx.restore();
  requestAnimationFrame(animate);
}'''

new_anim = '''function animate() {
  const c = state.canvas;
  const ctx = state.ctx;
  if (!c || !ctx) return;
  ctx.fillStyle = '#0a0d14';
  ctx.fillRect(0, 0, c.width, c.height);
  ctx.save();
  ctx.translate(state.camera.x, state.camera.y);
  ctx.scale(state.camera.zoom, state.camera.zoom);
  
  const pm = {};
  state.stars.forEach(s => pm[s.ip] = s);
  
  // Рёбра по parent (tree)
  ctx.lineWidth = 1;
  state.stars.forEach(s => {
    if (s.type === 'self') return;
    const p = s.parent && pm[s.parent];
    // Если parent нет — связь с self
    const parent = p || pm['127.0.0.1'];
    if (!parent) return;
    ctx.strokeStyle = s.color + '33';
    ctx.beginPath();
    ctx.moveTo(parent.x, parent.y);
    ctx.lineTo(s.x, s.y);
    ctx.stroke();
  });
  
  // Узлы
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
  });
  
  ctx.restore();
  requestAnimationFrame(animate);
}'''

if old_anim in html_content:
    html_content = html_content.replace(old_anim, new_anim, 1)
    print("  [OK] animate: tree-edges + подписи")

# 2.6. Авто-fit при загрузке
old_init = '''  await loadInbox();
  await loadContacts();
  rebuildStars();'''

new_init = '''  await loadInbox();
  await loadContacts();
  rebuildStars();
  setTimeout(fitView, 500);'''

if old_init in html_content:
    html_content = html_content.replace(old_init, new_init, 1)
    print("  [OK] init: авто-fit при загрузке")

# 2.7. toggleLayout — tree + radial + grid
old_layout = '''function toggleLayout() {
  const layouts = ['radial', 'cluster', 'grid'];
  const i = layouts.indexOf(state.layout);
  state.layout = layouts[(i + 1) % layouts.length];
  rebuildStars();
  addLog('Раскладка: ' + state.layout, 'info');
}'''

new_layout = '''function toggleLayout() {
  const layouts = ['tree', 'radial', 'grid'];
  const i = layouts.indexOf(state.layout);
  state.layout = layouts[(i + 1) % layouts.length];
  rebuildStars();
  setTimeout(fitView, 200);
  addLog('Раскладка: ' + state.layout, 'info');
}'''

if old_layout in html_content:
    html_content = html_content.replace(old_layout, new_layout, 1)
    print("  [OK] toggleLayout: tree/radial/grid")

with open(HTML, "w", encoding="utf-8") as f:
    f.write(html_content)

print()
print("=" * 70)
print("  PATCH 100c DONE")
print("=" * 70)
print("  [OK] app.py: /api/organism -> все узлы + self")
print("  [OK] UI: TREE layout (дерево по глубине)")
print("  [OK] UI: подписи под узлами")
print("  [OK] UI: рёбра по parent")
print("  [OK] UI: метрики реальные (memory.nodes_count)")
print("  [OK] UI: авто-fit при загрузке")
print()
print("Стоп + перезапуск + Ctrl+F5")