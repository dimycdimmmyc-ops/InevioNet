import os

ROOT = r"E:\InevioNet"
HTML = os.path.join(ROOT, "web", "templates", "index.html")

# === HTML + CSS ===
HTML_PART = """<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>InevioNet - Живая сеть</title>
<script src="https://cdn.socket.io/4.7.5/socket.io.min.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{
  --bg:#0a0d14;--panel:#11151c;--panel-2:#161b24;--border:#1f2632;
  --text:#e6edf3;--dim:#8b949e;--accent:#58a6ff;
  --self:#58a6ff;--lan:#3fb950;--router:#d29922;--isp:#a371f7;
  --inev:#f0883e;--spore:#f85149;--service:#79c0ff;--wifi:#39c5cf;
  --success:#3fb950;--warn:#d29922;--error:#f85149;
  --radius:10px;--mono:'JetBrains Mono','SF Mono',Consolas,monospace;
}
html,body{height:100%;overflow:hidden}
body{background:var(--bg);color:var(--text);font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;font-size:13px;line-height:1.5;-webkit-font-smoothing:antialiased}
.app{display:grid;grid-template-columns:340px 1fr 360px;grid-template-rows:52px 1fr;height:100vh}
@media(max-width:1400px){.app{grid-template-columns:300px 1fr 320px}}
@media(max-width:1100px){.app{grid-template-columns:280px 1fr}.right{display:none!important}}
@media(max-width:768px){.app{grid-template-columns:1fr}.left{display:none!important}.right{display:none!important}}
.header{grid-column:1/-1;display:flex;align-items:center;justify-content:space-between;padding:0 16px;background:var(--panel);border-bottom:1px solid var(--border);z-index:10}
.brand{display:flex;align-items:center;gap:10px;font-weight:700;font-size:15px;letter-spacing:-.3px}
.brand .logo{width:26px;height:26px;border-radius:7px;background:linear-gradient(135deg,#58a6ff,#a371f7);display:flex;align-items:center;justify-content:center;font-size:14px}
.brand .v{color:var(--dim);font-weight:400;font-size:11px;font-family:var(--mono)}
.status{display:flex;align-items:center;gap:16px;font-size:12px;font-family:var(--mono);color:var(--dim)}
.dot{width:7px;height:7px;border-radius:50%;background:var(--error);transition:.2s}
.dot.on{background:var(--success);box-shadow:0 0 8px var(--success)}
.status .label{color:var(--dim)}
.status .value{color:var(--text);font-weight:600}
.left{background:var(--panel);border-right:1px solid var(--border);overflow-y:auto;padding:14px}
.section{margin-bottom:16px}
.section-title{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.2px;color:var(--dim);margin-bottom:8px;display:flex;align-items:center;gap:6px}
.section-title .count{background:var(--panel-2);padding:1px 6px;border-radius:6px;font-size:10px;color:var(--text);font-family:var(--mono)}
.metrics{display:grid;grid-template-columns:repeat(2,1fr);gap:8px}
.metric{background:var(--panel-2);border:1px solid var(--border);border-radius:var(--radius);padding:10px 12px}
.metric .l{font-size:10px;color:var(--dim);text-transform:uppercase;letter-spacing:.5px;margin-bottom:4px;font-weight:600}
.metric .v{font-size:22px;font-weight:700;font-family:var(--mono);letter-spacing:-.5px;line-height:1}
.metric.blue .v{color:var(--accent)}
.metric.green .v{color:var(--success)}
.metric.orange .v{color:var(--inev)}
.metric.purple .v{color:var(--isp)}
.metric.pink .v{color:var(--spore)}
.node-list{max-height:340px;overflow-y:auto;margin:-4px}
.node-item{display:flex;align-items:center;gap:8px;padding:8px 10px;border-radius:8px;cursor:pointer;transition:.12s;border:1px solid transparent}
.node-item:hover{background:var(--panel-2);border-color:var(--border)}
.node-item.active{background:rgba(88,166,255,.1);border-color:var(--accent)}
.node-item .badge{width:8px;height:8px;border-radius:50%;flex-shrink:0}
.node-item .info{flex:1;min-width:0}
.node-item .ip{font-family:var(--mono);font-size:11px;font-weight:600;color:var(--text);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.node-item .type{font-size:10px;color:var(--dim);margin-top:1px}
.node-item .plan{font-size:9px;font-weight:700;text-transform:uppercase;letter-spacing:.4px;padding:2px 5px;border-radius:4px;font-family:var(--mono)}
.plan-teach{background:rgba(63,185,80,.15);color:var(--success)}
.plan-relay{background:rgba(88,166,255,.15);color:var(--accent)}
.plan-capsule{background:rgba(210,153,34,.15);color:var(--warn)}
.plan-route{background:rgba(139,148,158,.15);color:var(--dim)}
.plan-skip{background:rgba(248,81,73,.15);color:var(--error)}
.canvas-wrap{position:relative;background:radial-gradient(ellipse at center,#0d1219 0%,#0a0d14 70%);overflow:hidden}
canvas{display:block;width:100%;height:100%;cursor:grab}
canvas:active{cursor:grabbing}
.canvas-overlay{position:absolute;top:12px;left:12px;display:flex;gap:6px;z-index:5}
.btn-icon{background:var(--panel);border:1px solid var(--border);border-radius:8px;width:34px;height:34px;display:flex;align-items:center;justify-content:center;cursor:pointer;color:var(--dim);font-size:14px;transition:.15s}
.btn-icon:hover{background:var(--panel-2);color:var(--text);border-color:var(--accent)}
.legend{position:absolute;bottom:12px;left:12px;background:var(--panel);border:1px solid var(--border);border-radius:8px;padding:8px 10px;font-size:10px;display:flex;flex-direction:column;gap:4px;z-index:5}
.legend-row{display:flex;align-items:center;gap:6px;color:var(--dim);font-family:var(--mono)}
.legend-row .d{width:8px;height:8px;border-radius:50%}
.right{background:var(--panel);border-left:1px solid var(--border);overflow-y:auto;padding:14px}
.detail-header{padding-bottom:12px;margin-bottom:12px;border-bottom:1px solid var(--border)}
.detail-ip{font-family:var(--mono);font-size:15px;font-weight:700;color:var(--text);word-break:break-all}
.detail-meta{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}
.tag{font-size:10px;padding:2px 7px;border-radius:5px;background:var(--panel-2);color:var(--dim);font-family:var(--mono);border:1px solid var(--border)}
.tag.blue{color:var(--accent);border-color:rgba(88,166,255,.3);background:rgba(88,166,255,.1)}
.tag.green{color:var(--success);border-color:rgba(63,185,80,.3);background:rgba(63,185,80,.1)}
.tag.orange{color:var(--inev);border-color:rgba(240,136,62,.3);background:rgba(240,136,62,.1)}
.tag.purple{color:var(--isp);border-color:rgba(163,113,247,.3);background:rgba(163,113,247,.1)}
.detail-row{display:flex;justify-content:space-between;align-items:center;padding:7px 0;font-size:12px;border-bottom:1px solid var(--border)}
.detail-row:last-child{border-bottom:none}
.detail-row .l{color:var(--dim)}
.detail-row .v{font-family:var(--mono);color:var(--text);font-weight:600;text-align:right}
.nlp-block{background:var(--panel-2);border:1px solid var(--border);border-radius:var(--radius);padding:12px;margin-top:10px}
.nlp-title{font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:1.2px;color:var(--dim);margin-bottom:10px}
.nlp-bar{height:4px;background:var(--border);border-radius:2px;overflow:hidden;margin-top:6px}
.nlp-bar-fill{height:100%;background:linear-gradient(90deg,var(--accent),var(--isp));transition:width .4s}
.nlp-plan{display:flex;align-items:center;justify-content:space-between;margin-top:10px;padding:8px 10px;background:var(--bg);border-radius:8px}
.nlp-plan .name{font-family:var(--mono);font-weight:700;font-size:13px;text-transform:uppercase;letter-spacing:.5px}
.nlp-plan .conf{font-family:var(--mono);font-size:11px;color:var(--dim)}
.phase-list{font-family:var(--mono);font-size:10px;line-height:1.7;color:var(--dim);max-height:200px;overflow-y:auto}
.phase-item{padding:2px 0;border-bottom:1px solid rgba(31,38,50,.5)}
.phase-item .ph{color:var(--accent);font-weight:600}
.log{font-family:var(--mono);font-size:10px;line-height:1.6;max-height:180px;overflow-y:auto;background:var(--bg);border:1px solid var(--border);border-radius:var(--radius);padding:8px}
.log-entry{padding:2px 4px;border-radius:3px;word-break:break-all}
.log-entry.info{color:var(--accent)}
.log-entry.success{color:var(--success)}
.log-entry.warn{color:var(--warn)}
.log-entry.error{color:var(--error)}
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:transparent}
::-webkit-scrollbar-thumb{background:var(--border);border-radius:3px}
::-webkit-scrollbar-thumb:hover{background:#2d3543}
.empty{color:var(--dim);text-align:center;padding:24px 12px;font-size:11px;font-style:italic}
</style>
</head>
<body>
<div class="app">
  <header class="header">
    <div class="brand">
      <div class="logo">&#x1F331;</div>
      <span>InevioNet</span>
      <span class="v">v{{ version }}</span>
    </div>
    <div class="status">
      <span class="dot" id="statusDot"></span>
      <span id="statusText">Подключение...</span>
      <span class="label">|</span>
      <span><span class="label">узлов:</span> <span class="value" id="hdrNodes">0</span></span>
      <span><span class="label">глубина:</span> <span class="value" id="hdrDepth">0</span></span>
      <span><span class="label">циклов:</span> <span class="value" id="hdrCycles">0</span></span>
      <span><span class="label">NAT:</span> <span class="value" id="hdrNat">-</span></span>
    </div>
  </header>

  <aside class="left">
    <div class="section">
      <div class="section-title">&#x1F4CA; Метрики организма</div>
      <div class="metrics">
        <div class="metric blue"><div class="l">Узлов</div><div class="v" id="mNodes">0</div></div>
        <div class="metric green"><div class="l">Обучено</div><div class="v" id="mTaught">0</div></div>
        <div class="metric purple"><div class="l">Реле</div><div class="v" id="mRelayed">0</div></div>
        <div class="metric orange"><div class="l">Капсул</div><div class="v" id="mCapsuled">0</div></div>
        <div class="metric blue"><div class="l">Глубина</div><div class="v" id="mDepth">0</div></div>
        <div class="metric pink"><div class="l">Стего</div><div class="v" id="mStego">0</div></div>
      </div>
    </div>

    <div class="section">
      <div class="section-title">&#x1F9E0; Фазы НЛП</div>
      <div class="phase-list" id="phaseList"><div class="empty">Нет данных</div></div>
    </div>

    <div class="section">
      <div class="section-title">&#x1F310; Узлы сети <span class="count" id="nodeCount">0</span></div>
      <div class="node-list" id="nodeList"><div class="empty">Нет узлов</div></div>
    </div>

    <div class="section">
      <div class="section-title">&#x1F4DC; Лог</div>
      <div class="log" id="logBox"></div>
    </div>
  </aside>

  <div class="canvas-wrap">
    <canvas id="canvas"></canvas>
    <div class="canvas-overlay">
      <button class="btn-icon" onclick="resetView()" title="Сброс вида">&#x27F2;</button>
      <button class="btn-icon" onclick="fitView()" title="Вписать">&#x26F6;</button>
      <button class="btn-icon" onclick="toggleLayout()" title="Сменить раскладку">&#x21C4;</button>
    </div>
    <div class="legend">
      <div class="legend-row"><span class="d" style="background:var(--self)"></span>SELF</div>
      <div class="legend-row"><span class="d" style="background:var(--lan)"></span>LAN</div>
      <div class="legend-row"><span class="d" style="background:var(--router)"></span>ROUTER</div>
      <div class="legend-row"><span class="d" style="background:var(--isp)"></span>ISP</div>
      <div class="legend-row"><span class="d" style="background:var(--inev)"></span>INEVIONET</div>
      <div class="legend-row"><span class="d" style="background:var(--spore)"></span>SPORE</div>
    </div>
  </div>

  <aside class="right">
    <div id="detailPanel">
      <div class="empty">Выберите узел на карте<br>или в списке слева</div>
    </div>
  </aside>
</div>
"""

# === JS ===
JS_PART = """
<script>
// === КОНФИГ ===
const CFG = {
  REFRESH_MS: 5000,
  TREE_MS: 10000,
  ORG_MS: 3000,
  COLORS: {
    self:'#58a6ff', lan_device:'#3fb950', router:'#d29922',
    isp_router:'#a371f7', inevionet:'#f0883e', spore:'#f85149',
    service:'#79c0ff', wifi:'#39c5cf', device:'#8b949e'
  }
};

// === СОСТОЯНИЕ ===
const state = {
  organism: null,
  tree: null,
  nodes: {},
  logs: [],
  selected: null,
  camera: {x:0, y:0, zoom:1},
  stars: [],
  layout: 'radial',  // radial | grid | cluster
  dragging: false,
  dragStart: {x:0, y:0},
  canvas: null,
  ctx: null,
  animationId: null
};

// === УТИЛИТЫ ===
function $(id) { return document.getElementById(id); }

function addLog(msg, type) {
  const box = $('logBox');
  if (!box) return;
  const e = document.createElement('div');
  e.className = 'log-entry ' + (type || 'info');
  const t = new Date().toLocaleTimeString('ru-RU');
  e.textContent = '[' + t + '] ' + msg;
  box.appendChild(e);
  while (box.children.length > 100) box.removeChild(box.firstChild);
  box.scrollTop = box.scrollHeight;
}

function colorForType(t) {
  return CFG.COLORS[t] || CFG.COLORS.device;
}

function planClass(plan) {
  return 'plan-' + (plan || 'route');
}

// === API ===
async function fetchOrganism() {
  try {
    const r = await fetch('/api/organism');
    const d = await r.json();
    if (d.success) {
      state.organism = d;
      renderMetrics(d);
      renderPhases(d);
      renderNodes(d);
    }
  } catch (e) {}
}

async function fetchTree() {
  try {
    const r = await fetch('/api/network/tree?force=0');
    const d = await r.json();
    if (d.success && d.root) {
      state.tree = d;
    }
  } catch (e) {}
}

async function fetchPublic() {
  try {
    const r = await fetch('/api/network/public');
    const d = await r.json();
    if (d.success) {
      $('hdrNat').textContent = d.nat_type || '-';
    }
  } catch (e) {}
}

// === РЕНДЕР ===
function renderMetrics(org) {
  const s = org.stats || {};
  const m = org.memory || {};
  $('mNodes').textContent = s.nodes_found || 0;
  $('mTaught').textContent = s.nodes_taught || 0;
  $('mRelayed').textContent = s.nodes_relayed || 0;
  $('mCapsuled').textContent = s.nodes_capsuled || 0;
  $('mDepth').textContent = s.max_depth || 0;
  $('mStego').textContent = s.stego_sent || 0;
  $('hdrNodes').textContent = s.nodes_found || 0;
  $('hdrDepth').textContent = s.max_depth || 0;
  $('hdrCycles').textContent = s.cycles || 0;
}

function renderPhases(org) {
  const phases = (org.phase_log || []).slice().reverse().slice(0, 15);
  const el = $('phaseList');
  if (!phases.length) {
    el.innerHTML = '<div class="empty">Нет данных</div>';
    return;
  }
  el.innerHTML = phases.map(p => {
    const ts = new Date(p.ts * 1000).toLocaleTimeString('ru-RU');
    const extra = p.extra ? ' ' + p.extra : '';
    return '<div class="phase-item"><span class="ph">' + (p.phase || '?') + '</span> ' + ts + extra + '</div>';
  }).join('');
}

function renderNodes(org) {
  const nodes = org.nodes_sample || [];
  const el = $('nodeList');
  $('nodeCount').textContent = (org.memory && org.memory.nodes_count) || nodes.length;
  if (!nodes.length) {
    el.innerHTML = '<div class="empty">Нет узлов</div>';
    return;
  }
  el.innerHTML = nodes.map(item => {
    const ip = item[0];
    const node = item[1];
    const type = node.type || '?';
    const plan = node.nlp_plan || 'route';
    const conf = node.nlp_confidence || 0;
    return '<div class="node-item" data-ip="' + ip + '">' +
      '<span class="badge" style="background:' + colorForType(type) + '"></span>' +
      '<div class="info">' +
        '<div class="ip">' + ip + '</div>' +
        '<div class="type">' + type + ' &middot; depth ' + (node.depth || '?') + '</div>' +
      '</div>' +
      '<span class="plan ' + planClass(plan) + '">' + plan + '</span>' +
    '</div>';
  }).join('');
  
  // Клик по узлу
  el.querySelectorAll('.node-item').forEach(item => {
    item.onclick = () => selectNode(item.dataset.ip);
  });
}

function selectNode(ip) {
  if (!state.organism) return;
  const nodes = state.organism.nodes_sample || [];
  const found = nodes.find(n => n[0] === ip);
  if (!found) return;
  state.selected = found;
  renderDetail(found[1]);
  document.querySelectorAll('.node-item').forEach(i => {
    i.classList.toggle('active', i.dataset.ip === ip);
  });
}

function renderDetail(node) {
  const ip = node.ip || '?';
  const type = node.type || '?';
  const plan = node.nlp_plan || 'route';
  const conf = (node.nlp_confidence || 0).toFixed(2);
  const leading = node.nlp_leading || '?';
  const rapport = (node.nlp_rapport || 0).toFixed(2);
  const controllable = node.nlp_controllable ? 'да' : 'нет';
  const depth = node.depth || '?';
  const source = node.source || '?';
  const vendor = node.vendor || '-';
  
  const planColor = {
    teach: 'var(--success)', relay: 'var(--accent)',
    capsule: 'var(--warn)', route: 'var(--dim)', skip: 'var(--error)'
  }[plan] || 'var(--dim)';
  
  $('detailPanel').innerHTML = 
    '<div class="detail-header">' +
      '<div class="detail-ip">' + ip + '</div>' +
      '<div class="detail-meta">' +
        '<span class="tag blue">' + type + '</span>' +
        '<span class="tag">depth ' + depth + '</span>' +
        '<span class="tag">' + source + '</span>' +
        (vendor !== '-' ? '<span class="tag purple">' + vendor + '</span>' : '') +
      '</div>' +
    '</div>' +
    
    '<div class="nlp-block">' +
      '<div class="nlp-title">&#x1F9E0; НЛП-анализ</div>' +
      '<div class="nlp-plan">' +
        '<span class="name" style="color:' + planColor + '">' + plan.toUpperCase() + '</span>' +
        '<span class="conf">conf ' + conf + '</span>' +
      '</div>' +
      '<div class="nlp-bar"><div class="nlp-bar-fill" style="width:' + (conf * 100) + '%"></div></div>' +
      '<div class="detail-row" style="margin-top:10px"><span class="l">Leading</span><span class="v">' + leading + '</span></div>' +
      '<div class="detail-row"><span class="l">Rapport</span><span class="v">' + rapport + '</span></div>' +
      '<div class="detail-row"><span class="l">Controllable</span><span class="v">' + controllable + '</span></div>' +
    '</div>' +
    
    '<div class="nlp-block">' +
      '<div class="nlp-title">&#x1F50D; Свойства</div>' +
      '<div class="detail-row"><span class="l">IP</span><span class="v">' + ip + '</span></div>' +
      '<div class="detail-row"><span class="l">Type</span><span class="v">' + type + '</span></div>' +
      '<div class="detail-row"><span class="l">Source</span><span class="v">' + source + '</span></div>' +
      '<div class="detail-row"><span class="l">Depth</span><span class="v">' + depth + '</span></div>' +
      '<div class="detail-row"><span class="l">Score</span><span class="v">' + (node.score || 0).toFixed(2) + '</span></div>' +
    '</div>';
}

// === SOCKET ===
function initSocket() {
  if (typeof io === 'undefined') return;
  const socket = io();
  socket.on('connect', () => {
    $('statusDot').classList.add('on');
    $('statusText').textContent = 'Подключено';
    addLog('WebSocket подключён', 'success');
    socket.emit('request_stats');
  });
  socket.on('disconnect', () => {
    $('statusDot').classList.remove('on');
    $('statusText').textContent = 'Отключено';
    addLog('WebSocket отключён', 'error');
  });
  socket.on('server_log', d => {
    const lvl = d.level === 'ERROR' ? 'error' : (d.level === 'WARNING' ? 'warn' : 'info');
    addLog(d.msg, lvl);
  });
}

// === CANVAS ===
function initCanvas() {
  const c = $('canvas');
  state.canvas = c;
  state.ctx = c.getContext('2d');
  resizeCanvas();
  window.addEventListener('resize', resizeCanvas);
  
  // Zoom
  c.addEventListener('wheel', e => {
    e.preventDefault();
    const d = e.deltaY > 0 ? 0.92 : 1.08;
    state.camera.zoom = Math.max(0.15, Math.min(6, state.camera.zoom * d));
  }, {passive: false});
  
  // Pan
  c.addEventListener('mousedown', e => {
    state.dragging = true;
    state.dragStart = {x: e.clientX - state.camera.x, y: e.clientY - state.camera.y};
  });
  window.addEventListener('mousemove', e => {
    if (state.dragging) {
      state.camera.x = e.clientX - state.dragStart.x;
      state.camera.y = e.clientY - state.dragStart.y;
    }
  });
  window.addEventListener('mouseup', () => state.dragging = false);
  
  // Click
  c.addEventListener('click', e => {
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
  });
  
  animate();
}

function resizeCanvas() {
  const c = state.canvas;
  if (!c) return;
  c.width = c.clientWidth * window.devicePixelRatio;
  c.height = c.clientHeight * window.devicePixelRatio;
  if (!state.camera.x && !state.camera.y) {
    state.camera.x = c.width / 2;
    state.camera.y = c.height / 2;
  }
}

function rebuildStars() {
  const nodes = (state.organism && state.organism.nodes_sample) || [];
  const maxDepth = Math.max(1, ...nodes.map(n => n[1].depth || 1));
  const centerX = 0, centerY = 0;
  
  state.stars = nodes.map(item => {
    const ip = item[0];
    const node = item[1];
    const type = node.type || 'device';
    const depth = node.depth || 1;
    const angle = hashAngle(ip);
    
    let x, y;
    if (type === 'self') {
      x = 0; y = 0;
    } else if (state.layout === 'cluster') {
      // Кластеры: LAN / ISP / InevioNet / Spore
      const cluster = getCluster(type);
      const clusterAngle = cluster * (Math.PI * 2 / 4);
      const r = 120 + depth * 40;
      const spread = hashAngle(ip + 'x') * 0.6;
      x = Math.cos(clusterAngle + spread) * r;
      y = Math.sin(clusterAngle + spread) * r;
    } else if (state.layout === 'grid') {
      const i = state.stars.length;
      const cols = Math.ceil(Math.sqrt(nodes.length));
      const size = 80;
      x = ((i % cols) - cols/2) * size;
      y = (Math.floor(i / cols) - cols/2) * size;
    } else {
      // radial (по умолчанию)
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
    
    return {
      ip, node, type, depth,
      x, y, r: radius,
      color: colorForType(type),
      pulse: Math.random() * Math.PI * 2
    };
  });
}

function getCluster(type) {
  if (type === 'lan_device' || type === 'service' || type === 'router') return 0;
  if (type === 'isp_router') return 1;
  if (type === 'inevionet') return 2;
  if (type === 'spore') return 3;
  return 0;
}

function hashAngle(s) {
  let h = 0;
  for (let i = 0; i < s.length; i++) {
    h = ((h << 5) - h) + s.charCodeAt(i);
    h = h & h;
  }
  return (Math.abs(h) % 360) * Math.PI / 180;
}

function animate() {
  const c = state.canvas;
  const ctx = state.ctx;
  if (!c || !ctx) return;
  
  ctx.fillStyle = '#0a0d14';
  ctx.fillRect(0, 0, c.width, c.height);
  
  ctx.save();
  ctx.translate(state.camera.x, state.camera.y);
  ctx.scale(state.camera.zoom, state.camera.zoom);
  
  // Связи: к центру
  const pm = {};
  state.stars.forEach(s => pm[s.ip] = s);
  ctx.lineWidth = 1;
  state.stars.forEach(s => {
    if (s.type === 'self') return;
    const center = pm['self'] || pm[Object.keys(pm)[0]];
    if (!center) return;
    ctx.strokeStyle = s.color + '22';
    ctx.beginPath();
    ctx.moveTo(center.x, center.y);
    ctx.lineTo(s.x, s.y);
    ctx.stroke();
  });
  
  // Узлы
  state.stars.forEach(s => {
    s.pulse += 0.03;
    const pr = s.r * (1 + Math.sin(s.pulse) * 0.12);
    
    // Glow
    const grad = ctx.createRadialGradient(s.x, s.y, 0, s.x, s.y, pr * 4);
    grad.addColorStop(0, s.color + '80');
    grad.addColorStop(1, s.color + '00');
    ctx.fillStyle = grad;
    ctx.beginPath();
    ctx.arc(s.x, s.y, pr * 4, 0, Math.PI * 2);
    ctx.fill();
    
    // Core
    ctx.fillStyle = s.color;
    ctx.beginPath();
    ctx.arc(s.x, s.y, pr, 0, Math.PI * 2);
    ctx.fill();
    
    // White center for self
    if (s.type === 'self') {
      ctx.fillStyle = '#fff';
      ctx.beginPath();
      ctx.arc(s.x, s.y, pr * 0.35, 0, Math.PI * 2);
      ctx.fill();
    }
  });
  
  ctx.restore();
  requestAnimationFrame(animate);
}

// === ДЕЙСТВИЯ ===
function resetView() {
  state.camera.x = state.canvas.width / 2;
  state.camera.y = state.canvas.height / 2;
  state.camera.zoom = 1;
  addLog('Вид сброшен', 'info');
}

function fitView() {
  if (!state.stars.length) return;
  const xs = state.stars.map(s => s.x);
  const ys = state.stars.map(s => s.y);
  const minX = Math.min(...xs), maxX = Math.max(...xs);
  const minY = Math.min(...ys), maxY = Math.max(...ys);
  const w = maxX - minX + 100, h = maxY - minY + 100;
  const zoom = Math.min(state.canvas.width / w, state.canvas.height / h);
  state.camera.zoom = Math.max(0.15, Math.min(3, zoom));
  state.camera.x = state.canvas.width / 2 - (minX + maxX) / 2 * state.camera.zoom;
  state.camera.y = state.canvas.height / 2 - (minY + maxY) / 2 * state.camera.zoom;
  addLog('Вписано в экран', 'info');
}

function toggleLayout() {
  const layouts = ['radial', 'cluster', 'grid'];
  const i = layouts.indexOf(state.layout);
  state.layout = layouts[(i + 1) % layouts.length];
  rebuildStars();
  addLog('Раскладка: ' + state.layout, 'info');
}

// === ИНИЦИАЛИЗАЦИЯ ===
async function init() {
  addLog('InevioNet UI загружен', 'info');
  initCanvas();
  initSocket();
  await fetchOrganism();
  await fetchTree();
  await fetchPublic();
  rebuildStars();
  
  setInterval(fetchOrganism, CFG.ORG_MS);
  setInterval(fetchTree, CFG.TREE_MS);
  setInterval(fetchPublic, 30000);
  setInterval(rebuildStars, 3000);
}

document.addEventListener('DOMContentLoaded', init);
</script>
</body>
</html>
"""

# Записываем
with open(HTML, "w", encoding="utf-8") as f:
    f.write(HTML_PART + JS_PART)

print("  [OK] index.html создан (%d байт)" % os.path.getsize(HTML))
print("  [OK] Новый профессиональный UI")