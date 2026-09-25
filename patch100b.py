import os

ROOT = r"E:\InevioNet"
HTML = os.path.join(ROOT, "web", "templates", "index.html")

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
.app{display:grid;grid-template-columns:300px 1fr 380px;grid-template-rows:52px 1fr;height:100vh}
@media(max-width:1500px){.app{grid-template-columns:280px 1fr 340px}}
@media(max-width:1200px){.app{grid-template-columns:260px 1fr 320px}}
@media(max-width:1000px){.app{grid-template-columns:1fr;grid-template-rows:52px 1fr}.left{display:none!important}.right{position:fixed;right:0;top:52px;bottom:0;width:380px;z-index:50}.right.hidden{display:none!important}}
@media(max-width:640px){.app{grid-template-columns:1fr}.right{width:100%}}
.header{grid-column:1/-1;display:flex;align-items:center;justify-content:space-between;padding:0 16px;background:var(--panel);border-bottom:1px solid var(--border);z-index:10}
.brand{display:flex;align-items:center;gap:10px;font-weight:700;font-size:15px;letter-spacing:-.3px}
.brand .logo{width:26px;height:26px;border-radius:7px;background:linear-gradient(135deg,#58a6ff,#a371f7);display:flex;align-items:center;justify-content:center;font-size:14px}
.brand .v{color:var(--dim);font-weight:400;font-size:11px;font-family:var(--mono)}
.status{display:flex;align-items:center;gap:16px;font-size:12px;font-family:var(--mono);color:var(--dim);flex-wrap:wrap}
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
.node-list{max-height:280px;overflow-y:auto;margin:-4px}
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
.right{background:var(--panel);border-left:1px solid var(--border);overflow:hidden;display:flex;flex-direction:column}
.tabs{display:flex;background:var(--panel-2);border-bottom:1px solid var(--border);flex-shrink:0}
.tab{flex:1;padding:10px 6px;text-align:center;cursor:pointer;font-size:11px;font-weight:600;color:var(--dim);border-bottom:2px solid transparent;transition:.15s;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.tab:hover{color:var(--text);background:rgba(88,166,255,.05)}
.tab.active{color:var(--accent);border-bottom-color:var(--accent)}
.tab .badge{display:inline-block;background:var(--error);color:#fff;font-size:9px;padding:1px 5px;border-radius:8px;margin-left:4px;font-family:var(--mono)}
.tab-content{flex:1;overflow-y:auto;padding:14px;display:none}
.tab-content.active{display:block}
.msg-list{display:flex;flex-direction:column;gap:8px}
.msg-card{background:var(--panel-2);border:1px solid var(--border);border-radius:var(--radius);padding:10px 12px}
.msg-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;font-size:11px}
.msg-from{font-family:var(--mono);font-weight:700;color:var(--accent)}
.msg-time{color:var(--dim);font-family:var(--mono);font-size:10px}
.msg-text{font-size:12px;color:var(--text);word-break:break-word;line-height:1.5}
.contact-card{display:flex;justify-content:space-between;align-items:center;background:var(--panel-2);border:1px solid var(--border);border-radius:var(--radius);padding:10px 12px;margin-bottom:6px}
.contact-info{flex:1;min-width:0}
.contact-name{font-weight:600;font-size:12px;color:var(--text)}
.contact-node{font-family:var(--mono);font-size:10px;color:var(--dim);margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.btn{width:100%;padding:10px 14px;border:none;border-radius:var(--radius);font-size:13px;font-weight:600;font-family:inherit;cursor:pointer;transition:.15s;display:flex;align-items:center;justify-content:center;gap:6px;margin-bottom:8px}
.btn:active{transform:scale(.98)}
.btn-primary{background:var(--accent);color:#000}
.btn-primary:hover{background:#79b8ff}
.btn-success{background:var(--success);color:#000}
.btn-success:hover{background:#4fc965}
.btn-ghost{background:var(--panel-2);color:var(--text);border:1px solid var(--border)}
.btn-ghost:hover{background:var(--border)}
.btn-sm{padding:6px 10px;font-size:11px;width:auto;margin-bottom:0}
.btn-icon-sm{background:transparent;border:none;color:var(--error);cursor:pointer;font-size:16px;padding:4px 8px}
.form-group{margin-bottom:10px}
.form-label{display:block;font-size:11px;color:var(--dim);font-weight:600;text-transform:uppercase;letter-spacing:.5px;margin-bottom:5px}
.form-input,.form-textarea{width:100%;padding:9px 11px;background:var(--bg);border:1px solid var(--border);border-radius:8px;color:var(--text);font-family:inherit;font-size:13px;transition:.15s}
.form-input:focus,.form-textarea:focus{outline:none;border-color:var(--accent)}
.form-textarea{resize:vertical;min-height:70px;font-family:var(--mono);font-size:12px}
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
.phase-list{font-family:var(--mono);font-size:10px;line-height:1.7;color:var(--dim);max-height:160px;overflow-y:auto}
.phase-item{padding:2px 0;border-bottom:1px solid rgba(31,38,50,.5)}
.phase-item .ph{color:var(--accent);font-weight:600}
.log{font-family:var(--mono);font-size:10px;line-height:1.6;max-height:140px;overflow-y:auto;background:var(--bg);border:1px solid var(--border);border-radius:var(--radius);padding:8px}
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
.qr-box{background:var(--bg);border:1px solid var(--border);border-radius:var(--radius);padding:14px;text-align:center;margin-bottom:10px}
.qr-box img{max-width:180px;border-radius:8px}
.user-bar{display:flex;justify-content:space-between;align-items:center;background:var(--panel-2);border:1px solid var(--border);border-radius:var(--radius);padding:10px 12px;margin-bottom:12px;font-size:12px}
.user-name{font-weight:700;color:var(--text)}
.user-node{font-family:var(--mono);font-size:10px;color:var(--dim);margin-top:2px}
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
    <div class="tabs">
      <div class="tab active" data-tab="inbox">&#x1F4E5; Входящие <span class="badge" id="inboxBadge" style="display:none">0</span></div>
      <div class="tab" data-tab="send">&#x2709;&#xFE0F; Написать</div>
      <div class="tab" data-tab="contacts">&#x1F465; Контакты</div>
      <div class="tab" data-tab="detail">&#x1F9E0; Детали</div>
    </div>

    <div class="tab-content active" id="tab-inbox">
      <div class="msg-list" id="inboxList"><div class="empty">Пока пусто</div></div>
    </div>

    <div class="tab-content" id="tab-send">
      <div class="form-group">
        <label class="form-label">Кому</label>
        <input class="form-input" id="sendReceiver" placeholder="node_id, IP или контакт">
      </div>
      <div class="form-group">
        <label class="form-label">Сообщение</label>
        <textarea class="form-textarea" id="sendMessage" placeholder="Введите текст..."></textarea>
      </div>
      <button class="btn btn-primary" onclick="sendMessage()">&#x1F4E4; Отправить</button>
      <div id="sendResult" style="margin-top:8px;font-size:11px;color:var(--dim)"></div>
      
      <div style="margin-top:20px;padding-top:16px;border-top:1px solid var(--border)">
        <div class="form-label" style="margin-bottom:10px">&#x1F4E1; Быстрые действия</div>
        <button class="btn btn-ghost btn-sm" onclick="quickPing()" style="width:100%;margin-bottom:6px">Проверить доступность</button>
        <button class="btn btn-ghost btn-sm" onclick="quickBootstrap()" style="width:100%;margin-bottom:6px">Опубликовать Seed</button>
        <button class="btn btn-ghost btn-sm" onclick="showBootstrapStatus()" style="width:100%">Статус Bootstrap</button>
      </div>
    </div>

    <div class="tab-content" id="tab-contacts">
      <div class="user-bar">
        <div>
          <div class="user-name" id="myUsername">-</div>
          <div class="user-node" id="myNodeId">-</div>
        </div>
        <button class="btn-icon" onclick="copyMyNodeId()" title="Скопировать ID">&#x1F4CB;</button>
      </div>
      
      <div class="section-title" style="margin-bottom:10px">&#x1F465; Контакты <span class="count" id="contactsCount">0</span></div>
      <div id="contactsList"><div class="empty">Нет контактов</div></div>
      
      <div style="margin-top:16px;padding-top:16px;border-top:1px solid var(--border)">
        <div class="form-label" style="margin-bottom:6px">Добавить контакт (JSON из QR)</div>
        <textarea class="form-textarea" id="qrImportData" placeholder='{"username":"...","node_id":"..."}' style="min-height:60px;font-size:11px"></textarea>
        <button class="btn btn-ghost" onclick="addContactFromQR()" style="margin-top:8px">&#x2795; Добавить</button>
      </div>
      
      <div style="margin-top:16px;padding-top:16px;border-top:1px solid var(--border)">
        <div class="form-label" style="margin-bottom:6px">&#x1F4F1; Мой QR-код</div>
        <div class="qr-box">
          <img id="qrImage" src="" style="display:none">
          <div id="qrPlaceholder" style="color:var(--dim);font-size:11px;font-style:italic">Нажмите кнопку</div>
        </div>
        <button class="btn btn-ghost" onclick="generateQR()">&#x1F3A8; Показать QR</button>
      </div>
    </div>

    <div class="tab-content" id="tab-detail">
      <div id="detailPanel">
        <div class="empty">Выберите узел на карте<br>или в списке слева</div>
      </div>
    </div>
  </aside>
</div>
"""

JS_PART = """
<script>
const CFG = {
  REFRESH_MS: 5000,
  TREE_MS: 10000,
  ORG_MS: 3000,
  INBOX_MS: 8000,
  COLORS: {
    self:'#58a6ff', lan_device:'#3fb950', router:'#d29922',
    isp_router:'#a371f7', inevionet:'#f0883e', spore:'#f85149',
    service:'#79c0ff', wifi:'#39c5cf', device:'#8b949e'
  }
};

const state = {
  organism: null,
  tree: null,
  nodes: {},
  selected: null,
  camera: {x:0, y:0, zoom:1},
  stars: [],
  layout: 'radial',
  dragging: false,
  dragStart: {x:0, y:0},
  canvas: null,
  ctx: null,
  currentUser: null,
  inboxCount: 0,
  lastInboxLen: 0
};

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

function colorForType(t) { return CFG.COLORS[t] || CFG.COLORS.device; }
function planClass(p) { return 'plan-' + (p || 'route'); }

// === TABS ===
function initTabs() {
  document.querySelectorAll('.tab').forEach(tab => {
    tab.onclick = () => {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      tab.classList.add('active');
      const name = tab.dataset.tab;
      $('tab-' + name).classList.add('active');
      if (name === 'inbox') { state.inboxCount = 0; updateInboxBadge(); loadInbox(); }
      if (name === 'contacts') loadContacts();
    };
  });
}

function switchToTab(name) {
  document.querySelectorAll('.tab').forEach(t => {
    t.classList.toggle('active', t.dataset.tab === name);
  });
  document.querySelectorAll('.tab-content').forEach(c => {
    c.classList.toggle('active', c.id === 'tab-' + name);
  });
}

function updateInboxBadge() {
  const b = $('inboxBadge');
  if (!b) return;
  if (state.inboxCount > 0) {
    b.textContent = state.inboxCount;
    b.style.display = 'inline-block';
  } else {
    b.style.display = 'none';
  }
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

async function fetchPublic() {
  try {
    const r = await fetch('/api/network/public');
    const d = await r.json();
    if (d.success) $('hdrNat').textContent = d.nat_type || '-';
  } catch (e) {}
}

async function fetchMe() {
  try {
    const r = await fetch('/api/me');
    const d = await r.json();
    if (d.success) {
      state.currentUser = d.user;
      $('myUsername').textContent = d.user.username || '-';
      $('myNodeId').textContent = d.user.node_id || '-';
    }
  } catch (e) {}
}

// === RENDER ===
function renderMetrics(org) {
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
}

function renderPhases(org) {
  const phases = (org.phase_log || []).slice().reverse().slice(0, 15);
  const el = $('phaseList');
  if (!phases.length) { el.innerHTML = '<div class="empty">Нет данных</div>'; return; }
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
}

function selectNode(ip) {
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
    teach:'var(--success)', relay:'var(--accent)',
    capsule:'var(--warn)', route:'var(--dim)', skip:'var(--error)'
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

// === INBOX ===
async function loadInbox() {
  try {
    const r = await fetch('/api/p2/inbox');
    const d = await r.json();
    const msgs = d.messages || [];
    const el = $('inboxList');
    if (!msgs.length) {
      el.innerHTML = '<div class="empty">Пока пусто</div>';
      return;
    }
    el.innerHTML = msgs.slice().reverse().map(m => {
      const t = new Date((m.ts || 0) * 1000).toLocaleTimeString('ru-RU');
      return '<div class="msg-card">' +
        '<div class="msg-head">' +
          '<span class="msg-from">' + (m.sender || '?') + '</span>' +
          '<span class="msg-time">' + t + '</span>' +
        '</div>' +
        '<div class="msg-text">' + escapeHtml(m.message || '') + '</div>' +
      '</div>';
    }).join('');
  } catch (e) {}
}

function escapeHtml(s) {
  const div = document.createElement('div');
  div.textContent = s;
  return div.innerHTML;
}

// === SEND ===
async function sendMessage() {
  const receiver = $('sendReceiver').value.trim();
  const message = $('sendMessage').value.trim();
  if (!receiver || !message) {
    $('sendResult').innerHTML = '<span style="color:var(--error)">Заполните все поля</span>';
    return;
  }
  $('sendResult').textContent = 'Отправка...';
  try {
    const r = await fetch('/api/p2/send', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({receiver, message})
    });
    const d = await r.json();
    if (d.success) {
      $('sendResult').innerHTML = '<span style="color:var(--success)">Отправлено' +
        (d.via ? ' через ' + d.via : '') + '</span>';
      $('sendMessage').value = '';
      addLog('Отправлено ' + receiver, 'success');
    } else {
      $('sendResult').innerHTML = '<span style="color:var(--error)">' + (d.error || 'Ошибка') + '</span>';
    }
  } catch (e) {
    $('sendResult').innerHTML = '<span style="color:var(--error)">' + e.message + '</span>';
  }
}

async function quickPing() {
  const target = $('sendReceiver').value.trim();
  if (!target) { $('sendResult').textContent = 'Введите получателя'; return; }
  $('sendResult').textContent = 'Проверка ' + target + '...';
  try {
    const r = await fetch('/api/probe', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({target})
    });
    const d = await r.json();
    $('sendResult').textContent = 'OK: ' + JSON.stringify(d).slice(0, 100);
  } catch (e) {
    $('sendResult').textContent = 'Ошибка: ' + e.message;
  }
}

async function quickBootstrap() {
  $('sendResult').textContent = 'Публикация Seed...';
  try {
    const r = await fetch('/api/bootstrap/seed', {method: 'POST'});
    const d = await r.json();
    if (d.success && d.url) {
      $('sendResult').innerHTML = 'Seed: <a href="' + d.url + '" target="_blank" style="color:var(--accent)">' + d.url + '</a>';
      if (navigator.clipboard) navigator.clipboard.writeText(d.url);
    } else {
      $('sendResult').textContent = 'Ошибка: ' + (d.error || '?');
    }
  } catch (e) {
    $('sendResult').textContent = 'Ошибка: ' + e.message;
  }
}

async function showBootstrapStatus() {
  try {
    const r = await fetch('/api/bootstrap/status');
    const d = await r.json();
    $('sendResult').textContent = 'NAT: ' + (d.nat_type || '?') +
      ' | Public: ' + JSON.stringify(d.public_addr || []) +
      ' | Sprout: ' + JSON.stringify(d.sprout || {}).slice(0, 80);
  } catch (e) {}
}

// === CONTACTS ===
async function loadContacts() {
  try {
    const r = await fetch('/api/contacts');
    const d = await r.json();
    const contacts = d.contacts || [];
    $('contactsCount').textContent = contacts.length;
    const el = $('contactsList');
    if (!contacts.length) {
      el.innerHTML = '<div class="empty">Нет контактов</div>';
      return;
    }
    el.innerHTML = contacts.map(c =>
      '<div class="contact-card">' +
        '<div class="contact-info">' +
          '<div class="contact-name">' + escapeHtml(c.username || '?') + '</div>' +
          '<div class="contact-node">' + (c.node_id || '') + '</div>' +
        '</div>' +
        '<button class="btn-icon-sm" onclick="removeContact(\\'' + c.node_id + '\\')" title="Удалить">&#x2715;</button>' +
      '</div>'
    ).join('');
  } catch (e) {}
}

async function removeContact(nodeId) {
  try {
    await fetch('/api/contacts/' + nodeId, {method: 'DELETE'});
    loadContacts();
    addLog('Контакт удалён: ' + nodeId, 'info');
  } catch (e) {}
}

async function addContactFromQR() {
  const raw = $('qrImportData').value.trim();
  if (!raw) return;
  try {
    const qr = JSON.parse(raw);
    const r = await fetch('/api/contacts', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({qr_data: qr})
    });
    const d = await r.json();
    if (d.success) {
      addLog(d.added ? 'Контакт добавлен' : 'Уже есть', d.added ? 'success' : 'warn');
      $('qrImportData').value = '';
      loadContacts();
    }
  } catch (e) {
    addLog('Неверный JSON', 'error');
  }
}

async function generateQR() {
  try {
    const r = await fetch('/api/qr');
    const d = await r.json();
    if (d.success && d.qr_url) {
      const img = $('qrImage');
      img.src = d.qr_url + '?t=' + Date.now();
      img.style.display = 'block';
      $('qrPlaceholder').style.display = 'none';
    }
  } catch (e) {}
}

function copyMyNodeId() {
  const nid = $('myNodeId').textContent;
  if (nid && nid !== '-' && navigator.clipboard) {
    navigator.clipboard.writeText(nid);
    addLog('Node ID скопирован', 'success');
  }
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
  socket.on('inbox_new', m => {
    state.inboxCount++;
    updateInboxBadge();
    loadInbox();
    addLog('Новое сообщение от ' + (m.sender || '?'), 'success');
  });
}

// === CANVAS ===
function initCanvas() {
  const c = $('canvas');
  state.canvas = c;
  state.ctx = c.getContext('2d');
  resizeCanvas();
  window.addEventListener('resize', resizeCanvas);
  c.addEventListener('wheel', e => {
    e.preventDefault();
    const d = e.deltaY > 0 ? 0.92 : 1.08;
    state.camera.zoom = Math.max(0.15, Math.min(6, state.camera.zoom * d));
  }, {passive: false});
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
  window.addEventListener('mouseup', () => { setTimeout(() => state.dragging = false, 50); });
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
}

// === ACTIONS ===
function resetView() {
  state.camera.x = state.canvas.width / 2;
  state.camera.y = state.canvas.height / 2;
  state.camera.zoom = 1;
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
}

function toggleLayout() {
  const layouts = ['radial', 'cluster', 'grid'];
  const i = layouts.indexOf(state.layout);
  state.layout = layouts[(i + 1) % layouts.length];
  rebuildStars();
  addLog('Раскладка: ' + state.layout, 'info');
}

// === INIT ===
async function init() {
  addLog('InevioNet UI загружен', 'info');
  initTabs();
  initCanvas();
  initSocket();
  await fetchMe();
  await fetchOrganism();
  await fetchPublic();
  await loadInbox();
  await loadContacts();
  rebuildStars();
  setInterval(fetchOrganism, CFG.ORG_MS);
  setInterval(fetchPublic, 30000);
  setInterval(loadInbox, CFG.INBOX_MS);
  setInterval(rebuildStars, 3000);
}

document.addEventListener('DOMContentLoaded', init);
</script>
</body>
</html>
"""

with open(HTML, "w", encoding="utf-8") as f:
    f.write(HTML_PART + JS_PART)

print("  [OK] index.html обновлён (%d байт)" % os.path.getsize(HTML))
print("  [OK] + Входящие, Написать, Контакты, QR, Детали узла")