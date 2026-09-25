import os
import ast

ROOT = r"E:\InevioNet"
HTML = os.path.join(ROOT, "web", "templates", "index.html")

with open(HTML, "r", encoding="utf-8") as f:
    h = f.read()


# =====================================================================
# 1. ДЕРЕВО parent->child (заменить rebuildStars)
# =====================================================================

print()
print("=" * 70)
print("  1. rebuildStars -> настоящее дерево")
print("=" * 70)

# Найти rebuildStars (от "function rebuildStars" до закрывающей "}")
import re
m = re.search(r"function rebuildStars\(\) \{.*?\n\}", h, re.DOTALL)
if m:
    old = m.group(0)
    new = '''function rebuildStars() {
  const nodes = (state.organism && (state.organism.nodes || state.organism.nodes_sample)) || [];
  
  // P102: ДЕРЕВО parent->child
  // Группируем по parent
  const childrenOf = {};   // parent_id -> [node, ...]
  const byId = {};
  
  nodes.forEach(item => {
    const ip = item[0];
    const node = item[1];
    byId[ip] = { ip, node, type: node.type || 'device' };
    const parent = node.parent || '127.0.0.1';
    if (!childrenOf[parent]) childrenOf[parent] = [];
    childrenOf[parent].push({ ip, node });
  });
  
  const stars = [];
  const seen = {};
  
  // Рекурсивный обход дерева
  function layoutChildren(parentId, parentX, parentY, depth, startAngle, endAngle) {
    const children = childrenOf[parentId] || [];
    const count = children.length;
    if (count === 0) return;
    const radiusStep = 150;
    const angleStep = (endAngle - startAngle) / Math.max(1, count);
    
    children.forEach((child, i) => {
      const ip = child.ip;
      if (seen[ip]) return;
      seen[ip] = true;
      const node = child.node;
      const type = node.type || 'device';
      
      // Угол в диапазоне
      const angle = startAngle + angleStep * (i + 0.5);
      const radius = radiusStep;
      const x = parentX + Math.cos(angle) * radius;
      const y = parentY + Math.sin(angle) * radius;
      
      let r = 5;
      if (type === 'self') r = 18;
      else if (type === 'inevionet') r = 11;
      else if (type === 'router') r = 9;
      else if (type === 'lan_device') r = 6;
      else if (type === 'isp_router') r = 5;
      else if (type === 'spore') r = 4;
      
      stars.push({
        ip, node, type, depth,
        x, y, r,
        color: colorForType(type),
        pulse: Math.random() * Math.PI * 2,
        parent: parentId,
        label: ip,
      });
      
      // Дети этого ребёнка — в своём угловом секторе
      const childAngleStart = angle - angleStep / 2;
      const childAngleEnd = angle + angleStep / 2;
      layoutChildren(ip, x, y, depth + 1, childAngleStart, childAngleEnd);
    });
  }
  
  // Начинаем с self
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
    layoutChildren(selfItem[0], 0, 0, 1, -Math.PI / 2, Math.PI * 3 / 2);
  }
  
  // Оставшиеся узлы (без parent, не seen) — ISP кластеры
  const orphans = nodes.filter(n => !seen[n[0]]);
  const clusterMap = {};
  orphans.forEach(item => {
    const ip = item[0];
    const node = item[1];
    const type = node.type || 'device';
    if (type === 'isp_router') {
      const parts = ip.split('.');
      const prefix = parts.length === 4 ? parts[0] + '.' + parts[1] + '.' + parts[2] : ip;
      if (!clusterMap[prefix]) clusterMap[prefix] = { prefix, ips: [], type: 'isp_router' };
      clusterMap[prefix].ips.push(ip);
    } else {
      // Без parent — к self
      const angle = Math.random() * Math.PI * 2;
      const radius = 250 + Math.random() * 100;
      stars.push({
        ip, node, type, depth: 2,
        x: Math.cos(angle) * radius, y: Math.sin(angle) * radius,
        r: 5, color: colorForType(type),
        pulse: Math.random() * Math.PI * 2,
        parent: '127.0.0.1', label: ip,
      });
      seen[ip] = true;
    }
  });
  
  // ISP-кластеры — 2-е кольцо (справа/слева от self)
  const clusterKeys = Object.keys(clusterMap).sort();
  clusterKeys.forEach((key, i) => {
    const cl = clusterMap[key];
    const total = clusterKeys.length;
    const angle = (i / Math.max(1, total)) * Math.PI - Math.PI / 2;  // верхняя полуокружность
    const radius = 280;
    const x = Math.cos(angle) * radius;
    const y = Math.sin(angle) * radius;
    const size = Math.min(14, 6 + Math.log2(cl.ips.length + 1) * 2);
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
    print("  [OK] rebuildStars: дерево parent->child")
else:
    print("  [!!] rebuildStars не найден")


# =====================================================================
# 2. ЛИНИИ — по parent (а не все от центра)
# =====================================================================

print()
print("  [--] линии уже по parent (из P101)")


# =====================================================================
# 3. ЭКРАН РЕГИСТРАЦИИ + ЛОГИНА
# =====================================================================

print()
print("=" * 70)
print("  2. Экран регистрации + логина")
print("=" * 70)

# Добавить auth-overlay в HTML перед </body>
old_close = '''<div class="app">'''
new_auth = '''<div class="auth-overlay" id="authOverlay">
  <div class="auth-card">
    <div class="auth-logo">&#x1F331;</div>
    <h1 class="auth-title">InevioNet</h1>
    <p class="auth-sub">Живая сеть</p>
    
    <div class="auth-tabs">
      <button class="auth-tab active" data-tab="login">Вход</button>
      <button class="auth-tab" data-tab="register">Регистрация</button>
    </div>
    
    <div class="auth-form active" id="authLogin">
      <input class="auth-input" id="loginUser" placeholder="Имя пользователя" autocomplete="username">
      <input class="auth-input" id="loginPass" type="password" placeholder="Пароль" autocomplete="current-password">
      <button class="auth-btn" onclick="doLogin()">Войти</button>
    </div>
    
    <div class="auth-form" id="authRegister">
      <input class="auth-input" id="regUser" placeholder="Имя пользователя" autocomplete="username">
      <input class="auth-input" id="regPass" type="password" placeholder="Пароль (мин 4)" autocomplete="new-password">
      <input class="auth-input" id="regPass2" type="password" placeholder="Повторите пароль" autocomplete="new-password">
      <button class="auth-btn auth-btn-success" onclick="doRegister()">Создать аккаунт</button>
    </div>
    
    <div class="auth-error" id="authError"></div>
  </div>
</div>

<div class="app">'''
h = h.replace(old_close, new_auth, 1)

# Добавить CSS
old_css = '''.empty{color:var(--dim);text-align:center;padding:24px 12px;font-size:11px;font-style:italic}'''
new_css = '''.empty{color:var(--dim);text-align:center;padding:24px 12px;font-size:11px;font-style:italic}
.auth-overlay{position:fixed;inset:0;background:rgba(5,7,10,0.95);backdrop-filter:blur(20px);z-index:9999;display:none;align-items:center;justify-content:center;padding:20px}
.auth-overlay.show{display:flex}
.auth-card{background:var(--panel);border:1px solid var(--border);border-radius:16px;padding:32px 28px;width:100%;max-width:380px}
.auth-logo{font-size:42px;text-align:center;margin-bottom:6px}
.auth-title{text-align:center;font-size:22px;font-weight:700;letter-spacing:-.5px;background:linear-gradient(135deg,#58a6ff,#a371f7);-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}
.auth-sub{text-align:center;font-size:11px;color:var(--dim);margin-bottom:20px;font-family:var(--mono)}
.auth-tabs{display:flex;background:var(--bg);border-radius:8px;padding:3px;margin-bottom:16px}
.auth-tab{flex:1;padding:8px;background:transparent;border:none;color:var(--dim);cursor:pointer;border-radius:6px;font-size:12px;font-weight:600;font-family:inherit;transition:.15s}
.auth-tab.active{background:var(--accent);color:#000}
.auth-form{display:none;flex-direction:column;gap:10px}
.auth-form.active{display:flex}
.auth-input{background:var(--bg);border:1px solid var(--border);border-radius:8px;padding:11px 13px;color:var(--text);font-size:13px;font-family:inherit}
.auth-input:focus{outline:none;border-color:var(--accent)}
.auth-btn{background:var(--accent);color:#000;border:none;border-radius:8px;padding:11px;font-size:13px;font-weight:700;font-family:inherit;cursor:pointer;transition:.15s;margin-top:4px}
.auth-btn:hover{background:#79b8ff}
.auth-btn-success{background:var(--success)}
.auth-btn-success:hover{background:#4fc965}
.auth-error{color:var(--error);font-size:12px;text-align:center;margin-top:12px;min-height:16px}
.user-avatar{width:28px;height:28px;border-radius:50%;background:linear-gradient(135deg,var(--accent),var(--isp));display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:700;color:#000}'''
h = h.replace(old_css, new_css, 1)


# =====================================================================
# 4. JS: авторизация + QR + контакты
# =====================================================================

print()
print("=" * 70)
print("  3. JS: авторизация + QR + контакты")
print("=" * 70)

# Добавить JS-код перед "document.addEventListener('DOMContentLoaded', init);"
old_dom = "document.addEventListener('DOMContentLoaded', init);"
new_js = '''
// === AUTH (P102) ===
function showAuth() {
  $('authOverlay').classList.add('show');
}
function hideAuth() {
  $('authOverlay').classList.remove('show');
}
function setAuthTab(name) {
  document.querySelectorAll('.auth-tab').forEach(t => t.classList.toggle('active', t.dataset.tab === name));
  document.querySelectorAll('.auth-form').forEach(f => f.classList.remove('active'));
  $('auth' + name.charAt(0).toUpperCase() + name.slice(1)).classList.add('active');
}
async function doLogin() {
  const u = $('loginUser').value.trim();
  const p = $('loginPass').value;
  if (!u || !p) { $('authError').textContent = 'Заполните поля'; return; }
  try {
    const r = await fetch('/api/login', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:u, password:p})});
    const d = await r.json();
    if (d.success) {
      state.currentUser = d.user;
      hideAuth();
      updateUserBar();
      await loadContacts();
      addLog('Добро пожаловать, ' + u, 'success');
    } else {
      $('authError').textContent = d.error || 'Ошибка';
    }
  } catch (e) { $('authError').textContent = e.message; }
}
async function doRegister() {
  const u = $('regUser').value.trim();
  const p = $('regPass').value;
  const p2 = $('regPass2').value;
  if (!u || !p) { $('authError').textContent = 'Заполните поля'; return; }
  if (p !== p2) { $('authError').textContent = 'Пароли не совпадают'; return; }
  if (p.length < 4) { $('authError').textContent = 'Пароль минимум 4 символа'; return; }
  try {
    const r = await fetch('/api/register', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({username:u, password:p})});
    const d = await r.json();
    if (d.success) {
      state.currentUser = d.user;
      hideAuth();
      updateUserBar();
      await loadContacts();
      addLog('Аккаунт создан: ' + u, 'success');
    } else {
      $('authError').textContent = d.error || 'Ошибка';
    }
  } catch (e) { $('authError').textContent = e.message; }
}
async function doLogout() {
  await fetch('/api/logout', {method:'POST'});
  state.currentUser = null;
  showAuth();
  $('loginUser').value = '';
  $('loginPass').value = '';
}
function updateUserBar() {
  const u = state.currentUser;
  if (u) {
    $('myUsername').textContent = u.username || '-';
    $('myNodeId').textContent = u.node_id || '-';
  }
}
async function checkAuth() {
  try {
    const r = await fetch('/api/me');
    if (r.status === 401) { showAuth(); return; }
    const d = await r.json();
    if (d.success) {
      state.currentUser = d.user;
      hideAuth();
      updateUserBar();
      await loadContacts();
    } else {
      showAuth();
    }
  } catch (e) { showAuth(); }
}
async function generateQR() {
  try {
    const r = await fetch('/api/qr');
    if (r.status === 401) { showAuth(); return; }
    const d = await r.json();
    if (d.success && d.qr_url) {
      const img = $('qrImage');
      img.src = d.qr_url + '?t=' + Date.now();
      img.style.display = 'block';
      img.onload = () => addLog('QR готов', 'success');
      img.onerror = () => addLog('QR не загрузился', 'error');
      $('qrPlaceholder').style.display = 'none';
    } else {
      addLog('Ошибка QR: ' + (d.error || '?'), 'error');
    }
  } catch (e) { addLog('QR: ' + e.message, 'error'); }
}
function copyMyNodeId() {
  const nid = $('myNodeId').textContent;
  if (nid && nid !== '-' && navigator.clipboard) {
    navigator.clipboard.writeText(nid);
    addLog('Node ID скопирован: ' + nid, 'success');
  }
}
async function addContactFromQR() {
  const raw = $('qrImportData').value.trim();
  if (!raw) { addLog('Вставьте JSON', 'warn'); return; }
  try {
    const qr = JSON.parse(raw);
    const r = await fetch('/api/contacts', {method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({qr_data: qr})});
    const d = await r.json();
    if (d.success) {
      addLog(d.added ? 'Контакт добавлен' : 'Уже есть', d.added ? 'success' : 'warn');
      $('qrImportData').value = '';
      await loadContacts();
    } else {
      addLog('Ошибка: ' + (d.error || '?'), 'error');
    }
  } catch (e) { addLog('Неверный JSON: ' + e.message, 'error'); }
}

// auth tabs
document.querySelectorAll('.auth-tab').forEach(t => {
  t.onclick = () => setAuthTab(t.dataset.tab);
});

'''
h = h.replace(old_dom, new_js + old_dom, 1)

# Обновить init() — добавить checkAuth
old_init = '''async function init() {
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
  }
  rebuildStars();
  setTimeout(fitView, 500);'''

if old_init in h:
    h = h.replace(old_init, new_init, 1)
    print("  [OK] init: checkAuth первым")

# Убрать старый fetchMe (больше не нужен — checkAuth делает то же)
old_fetchme = '''async function fetchMe() {
  try {
    const r = await fetch('/api/me');
    const d = await r.json();
    if (d.success) {
      state.currentUser = d.user;
      $('myUsername').textContent = d.user.username || '-';
      $('myNodeId').textContent = d.user.node_id || '-';
    }
  } catch (e) {}
}'''
h = h.replace(old_fetchme, '', 1)

# Финальная запись
with open(HTML, "w", encoding="utf-8") as f:
    f.write(h)

print()
print("=" * 70)
print("  PATCH 102 DONE")
print("=" * 70)
print("  [OK] rebuildStars: настоящее дерево parent->child")
print("  [OK] Экран регистрации + логина")
print("  [OK] QR + контакты + user bar")
print()
print("Перезапуск + Ctrl+F5")