import os
import ast

ROOT = r"E:\InevioNet"
HTML = os.path.join(ROOT, "web", "templates", "index.html")

with open(HTML, "r", encoding="utf-8") as f:
    h = f.read()

# =====================================================================
# 1. Новая вкладка DHT (в правой панели)
# =====================================================================

print()
print("=" * 70)
print("  1. Вкладка DHT")
print("=" * 70)

# Найти вкладки
old_tabs = '''    <div class="tabs">
      <div class="tab active" data-tab="inbox">&#x1F4E5; Входящие <span class="badge" id="inboxBadge" style="display:none">0</span></div>
      <div class="tab" data-tab="send">&#x2709;&#xFE0F; Написать</div>
      <div class="tab" data-tab="contacts">&#x1F465; Контакты</div>
      <div class="tab" data-tab="detail">&#x1F9E0; Детали</div>
    </div>'''

new_tabs = '''    <div class="tabs">
      <div class="tab active" data-tab="inbox">&#x1F4E5; Входящие <span class="badge" id="inboxBadge" style="display:none">0</span></div>
      <div class="tab" data-tab="send">&#x2709;&#xFE0F; Написать</div>
      <div class="tab" data-tab="contacts">&#x1F465; Контакты</div>
      <div class="tab" data-tab="dht">&#x1F310; DHT</div>
      <div class="tab" data-tab="detail">&#x1F9E0; Детали</div>
    </div>'''

if old_tabs in h:
    h = h.replace(old_tabs, new_tabs, 1)
    print("  [OK] tabs: + DHT")
else:
    print("  [!!] tabs не найдены")

# Добавить tab-content для DHT перед tab-detail
old_detail = '''    <div class="tab-content" id="tab-detail">
      <div id="detailPanel">
        <div class="empty">Выберите узел на карте<br>или в списке слева</div>
      </div>
    </div>'''

new_detail = '''    <div class="tab-content" id="tab-dht">
      <div class="section-title" style="margin-bottom:10px">&#x1F310; Моя сеть</div>
      
      <div class="detail-row" style="padding:8px 0">
        <span class="l">Serial</span>
        <span class="v" id="mySerial" style="color:var(--accent)">—</span>
      </div>
      <div class="detail-row" style="padding:8px 0">
        <span class="l">Node ID</span>
        <span class="v" id="myNodeIdDht" style="font-size:11px">—</span>
      </div>
      <div class="detail-row" style="padding:8px 0">
        <span class="l">Public</span>
        <span class="v" id="myPublic" style="font-size:11px">—</span>
      </div>
      <div class="detail-row" style="padding:8px 0">
        <span class="l">NAT</span>
        <span class="v" id="myNat" style="font-size:11px">—</span>
      </div>
      <div class="detail-row" style="padding:8px 0">
        <span class="l">Реле</span>
        <span class="v" id="myRelays" style="color:var(--isp)">0</span>
      </div>
      
      <div class="section-title" style="margin-top:16px;margin-bottom:8px">&#x1F4CB; Мой JSON (для QR/копирования)</div>
      <textarea class="form-textarea" id="myJson" readonly style="min-height:120px;font-size:10px"></textarea>
      <button class="btn btn-primary" onclick="copyMyJson()" style="margin-top:8px">&#x1F4CB; Копировать JSON</button>
      
      <div class="section-title" style="margin-top:20px;margin-bottom:8px">&#x2795; Добавить peer</div>
      <textarea class="form-textarea" id="peerJsonInput" placeholder='Вставьте JSON другого узла' style="min-height:80px;font-size:10px"></textarea>
      <button class="btn btn-success" onclick="addPeerFromJson()" style="margin-top:8px">&#x2795; Добавить в DHT</button>
      
      <div class="section-title" style="margin-top:20px;margin-bottom:8px">
        &#x1F465; Peers DHT <span class="count" id="dhtPeersCount">0</span>
      </div>
      <div class="detail-row" style="padding:6px 0;font-size:11px">
        <span class="l">Всего узлов сети</span>
        <span class="v" id="dhtTotalNodes" style="color:var(--success)">0</span>
      </div>
      <div class="detail-row" style="padding:6px 0;font-size:11px;border-bottom:1px solid var(--border)">
        <span class="l">Всего реле сети</span>
        <span class="v" id="dhtTotalRelays" style="color:var(--isp)">0</span>
      </div>
      <div id="dhtPeersList" style="margin-top:8px"><div class="empty">Нет peers</div></div>
    </div>

    <div class="tab-content" id="tab-detail">
      <div id="detailPanel">
        <div class="empty">Выберите узел на карте<br>или в списке слева</div>
      </div>
    </div>'''

if old_detail in h:
    h = h.replace(old_detail, new_detail, 1)
    print("  [OK] tab-content: + DHT")
else:
    print("  [!!] tab-detail не найден")


# =====================================================================
# 2. JS: функции для DHT
# =====================================================================

print()
print("=" * 70)
print("  2. JS: DHT функции")
print("=" * 70)

# Добавить JS-функции перед "document.addEventListener('DOMContentLoaded', init);"
old_dom = "document.addEventListener('DOMContentLoaded', init);"
new_js = '''
// === DHT (P103b) ===
async function fetchDhtMyInfo() {
  try {
    const r = await fetch('/api/dht/my_info');
    const d = await r.json();
    if (!d.success) return;
    const info = d.info || {};
    const myJson = d.json || '';
    if ($('mySerial')) $('mySerial').textContent = info.serial || '—';
    if ($('myNodeIdDht')) $('myNodeIdDht').textContent = info.node_id || '—';
    if ($('myPublic')) $('myPublic').textContent = (info.public_ip || '') + ':' + (info.public_port || '');
    if ($('myNat')) $('myNat').textContent = info.nat_type || '—';
    if ($('myRelays')) $('myRelays').textContent = info.relay_count || 0;
    if ($('myJson')) $('myJson').value = myJson;
  } catch (e) {}
}

async function fetchDhtPeers() {
  try {
    const r = await fetch('/api/dht/peers');
    const d = await r.json();
    if (!d.success) return;
    const peers = d.peers || [];
    const stats = d.stats || {};
    if ($('dhtPeersCount')) $('dhtPeersCount').textContent = peers.length;
    if ($('dhtTotalNodes')) $('dhtTotalNodes').textContent = stats.total_nodes || 0;
    if ($('dhtTotalRelays')) $('dhtTotalRelays').textContent = stats.total_relays || 0;
    const el = $('dhtPeersList');
    if (!el) return;
    if (!peers.length) {
      el.innerHTML = '<div class="empty">Нет peers. Скопируй свой JSON и передай другому узлу.</div>';
      return;
    }
    el.innerHTML = peers.map(p =>
      '<div class="contact-card">' +
        '<div class="contact-info">' +
          '<div class="contact-name">' + escapeHtml(p.serial || '?') + ' → ' + (p.node_id || '?') + '</div>' +
          '<div class="contact-node">' + (p.public_ip || '') + ':' + (p.public_port || '') + ' | реле: ' + (p.relay_count || 0) + '</div>' +
        '</div>' +
      '</div>'
    ).join('');
  } catch (e) {}
}

async function copyMyJson() {
  const el = $('myJson');
  if (!el || !el.value) return;
  try {
    await navigator.clipboard.writeText(el.value);
    addLog('JSON скопирован. Передай другому узлу.', 'success');
  } catch (e) {
    el.select();
    document.execCommand('copy');
    addLog('JSON скопирован (fallback)', 'success');
  }
}

async function addPeerFromJson() {
  const raw = $('peerJsonInput').value.trim();
  if (!raw) { addLog('Вставьте JSON', 'warn'); return; }
  try {
    const r = await fetch('/api/dht/bootstrap', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({json: raw})
    });
    const d = await r.json();
    if (d.success) {
      if (d.added) {
        addLog('Peer добавлен в DHT!', 'success');
        $('peerJsonInput').value = '';
        await fetchDhtPeers();
      } else {
        addLog('Peer уже был в DHT', 'warn');
      }
    } else {
      addLog('Ошибка: ' + (d.error || '?'), 'error');
    }
  } catch (e) {
    addLog('Ошибка: ' + e.message, 'error');
  }
}

// Обновлять DHT каждые 10 сек
setInterval(() => {
  if (state.currentUser) {
    fetchDhtMyInfo();
    fetchDhtPeers();
  }
}, 10000);

'''
h = h.replace(old_dom, new_js + old_dom, 1)

# Обновить init — добавить DHT
old_init = '''async function init() {
  addLog('InevioNet UI загружен', 'info');
  initTabs();
  initCanvas();
  initSocket();
  await checkAuth();
  await fetchOrganism();
  await fetchPublic();
  if (state.currentUser) {
    await loadInbox();
    await loadContacts();
  }
  rebuildStars();
  setTimeout(fitView, 500);'''

new_init = '''async function init() {
  addLog('InevioNet UI загружен', 'info');
  initTabs();
  initCanvas();
  initSocket();
  await checkAuth();
  await fetchOrganism();
  await fetchPublic();
  if (state.currentUser) {
    await loadInbox();
    await loadContacts();
    await fetchDhtMyInfo();
    await fetchDhtPeers();
  }
  rebuildStars();
  setTimeout(fitView, 500);'''

if old_init in h:
    h = h.replace(old_init, new_init, 1)
    print("  [OK] init: + DHT fetch")

# Обновить initTabs — при переключении на DHT делать fetch
old_initTabs = '''function initTabs() {
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
}'''

new_initTabs = '''function initTabs() {
  document.querySelectorAll('.tab').forEach(tab => {
    tab.onclick = () => {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      tab.classList.add('active');
      const name = tab.dataset.tab;
      $('tab-' + name).classList.add('active');
      if (name === 'inbox') { state.inboxCount = 0; updateInboxBadge(); loadInbox(); }
      if (name === 'contacts') loadContacts();
      if (name === 'dht') { fetchDhtMyInfo(); fetchDhtPeers(); }
    };
  });
}'''

if old_initTabs in h:
    h = h.replace(old_initTabs, new_initTabs, 1)
    print("  [OK] initTabs: + DHT")

with open(HTML, "w", encoding="utf-8") as f:
    f.write(h)

print()
print("=" * 70)
print("  PATCH 103B DONE")
print("=" * 70)
print("  [OK] Вкладка DHT в правой панели")
print("  [OK] Serial + node_id + public + NAT + реле")
print("  [OK] Кнопка Копировать JSON")
print("  [OK] Поле вставки JSON peer")
print("  [OK] Список peers DHT")
print("  [OK] Общая статистика (total_nodes, total_relays)")
print()
print("Ctrl+F5 в браузере")