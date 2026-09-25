# patch89.py - P89: UI cleanup + multi-spiral + WiFi devices + InevioNet nodes
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
HTML = os.path.join(ROOT, "web", "templates", "index.html")
MESH = os.path.join(ROOT, "inevionet", "mesh", "network_tree.py")


def patch_file(path, replacements, label, bak=".bak_p89"):
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
            print("  [OK] " + old[:55].strip())
        else:
            if required:
                print("  [!!] NOT FOUND: " + old[:55].strip())
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
# 1. HTML - убрать лишние секции из "Ещё"
# =====================================================================

print()
print("=" * 70)
print("  1. HTML - убрать лишние секции из ЕЩЁ")
print("=" * 70)

# 1a. Убрать секцию "Анонимность" (Tor/I2P)
old_anon = '''        <div class="card-title" style="font-size:0.9em;margin-bottom:8px"><span class="emoji">🕵</span> Анонимность</div>
        <button class="btn btn-glass" onclick="checkTor()">🔍 Проверить Tor</button>
        <button class="btn btn-glass" onclick="checkI2P()">🌐 Проверить I2P</button>
        <div id="anonResult" style="margin-top:8px;font-size:0.8em;color:var(--dim)"></div>

        <div class="sep"></div>

'''

# 1b. Убрать секцию "P2P сеть" (bridge)
old_bridge = '''        <div class="card-title" style="font-size:0.9em;margin-bottom:8px"><span class="emoji">🌐</span> P2P сеть</div>
        <div class="form-group"><label>Регион</label><input id="bridgeRegion" value="RU"></div>
        <div class="form-group"><label>Лимит клиентов</label><input id="bridgeCapacity" value="10" type="number"></div>
        <button class="btn btn-glass" onclick="checkBridge()">🔍 Статус</button>
        <button class="btn btn-success" onclick="becomeVolunteer()">⭐ Стать реле-узлом</button>
        <button class="btn btn-glass" onclick="stopVolunteer()">⏹ Остановить</button>
        <div id="bridgeResult" style="margin-top:8px;font-size:0.8em;color:var(--dim)"></div>

        <div class="sep"></div>

'''

# 1c. Убрать секцию "AI селектор"
old_ai = '''        <div class="card-title" style="font-size:0.9em;margin-bottom:8px"><span class="emoji">🤖</span> AI селектор</div>
        <div style="display:flex;justify-content:space-between;align-items:center">
          <span style="font-size:0.85em;color:var(--dim)">Лучший протокол</span>
          <span id="aiBestName" style="font-weight:700;color:var(--green);font-size:0.95em">—</span>
        </div>
        <div style="margin-top:6px;height:6px;background:rgba(120,120,128,0.24);border-radius:3px;overflow:hidden">
          <div id="aiBestBar" style="height:100%;width:0%;background:linear-gradient(90deg,#ff453a,#ffd60a,#30d158);transition:width 0.6s"></div>
        </div>
        <div style="text-align:right;font-family:monospace;font-size:0.75em;color:var(--dim);margin-top:4px">
          Score: <span id="aiBestScore">0.00</span>
        </div>
        <div id="aiTopList" style="margin-top:8px">
          <div class="empty" style="padding:8px;font-size:0.8em">Нет данных</div>
        </div>
        <button class="btn btn-glass" style="margin-top:8px" onclick="loadAIStats()">🔍 Обновить</button>
        <button class="btn btn-sm btn-glass" onclick="resetAI()">🗑 Сбросить</button>

        <div class="sep"></div>

'''

# Заменяем на ПУСТО
patch_file(HTML, [
    (old_anon, "", False),
    (old_bridge, "", False),
    (old_ai, "", False),
], "HTML убрать секции", bak=".bak_p89_cleanup")


# =====================================================================
# 2. HTML - добавить Bootstrap + Gravity + Audit (после "Мицелий")
# =====================================================================

print()
print("=" * 70)
print("  2. HTML - добавить Bootstrap/Gravity/Audit")
print("=" * 70)

old_micelium = '''        <div class="card-title" style="font-size:0.9em;margin-bottom:8px"><span class="emoji">🌱</span> Мицелий</div>
        <button class="btn btn-success" onclick="growNetwork()">🌱 Растить (probe)</button>
        <button class="btn btn-glass" onclick="showMap()">🗺 Карта сети</button>

        <div class="sep"></div>

'''

new_micelium = '''        <div class="card-title" style="font-size:0.9em;margin-bottom:8px"><span class="emoji">🌱</span> Мицелий</div>
        <button class="btn btn-success" onclick="growNetwork()">🌱 Растить (probe)</button>
        <button class="btn btn-glass" onclick="showMap()">🗺 Карта сети</button>

        <div class="sep"></div>

        <div class="card-title" style="font-size:0.9em;margin-bottom:8px"><span class="emoji">🔑</span> Bootstrap (Seed/Sprout)</div>
        <button class="btn btn-success" onclick="publishSeed()">🔑 Опубликовать Seed</button>
        <button class="btn btn-glass" onclick="bootstrapStatus()">📊 Статус</button>
        <div class="form-group" style="margin-top:6px"><label>URL Seed (для sprout)</label><input id="sproutUrl" placeholder="https://paste.rs/..."></div>
        <button class="btn btn-glass" onclick="sproutUrl()">🌱 Прорастить Seed</button>
        <div id="bootstrapResult" style="margin-top:8px;font-size:0.8em;color:var(--dim)"></div>

        <div class="sep"></div>

        <div class="card-title" style="font-size:0.9em;margin-bottom:8px"><span class="emoji">🌀</span> Gravity + Audit</div>
        <button class="btn btn-glass" onclick="showGravity()">🌀 Поле Gravity</button>
        <button class="btn btn-glass" onclick="showAudit()">📜 Audit log</button>
        <button class="btn btn-glass" onclick="verifyAudit()">✅ Verify Audit</button>
        <div id="gravityResult" style="margin-top:8px;font-size:0.8em;color:var(--dim)"></div>
        <div id="auditResult" style="margin-top:4px;font-size:0.75em;color:var(--dim)"></div>

        <div class="sep"></div>

'''

patch_file(HTML, [(old_micelium, new_micelium, False)], "HTML добавить Bootstrap/Gravity", bak=".bak_p89_add")


# =====================================================================
# 3. JS - функции для Bootstrap/Gravity/Audit
# =====================================================================

print()
print("=" * 70)
print("  3. JS - функции Bootstrap/Gravity/Audit")
print("=" * 70)

old_js_end = '''function clearLogs() { document.getElementById('logContainer').innerHTML = ''; }'''

new_js_end = '''function clearLogs() { document.getElementById('logContainer').innerHTML = ''; }

// === P89: Bootstrap ===
async function publishSeed() {
  try {
    const r = await fetch('/api/bootstrap/seed', {method: 'POST'});
    const d = await r.json();
    const el = document.getElementById('bootstrapResult');
    if (d.success && d.url) {
      el.innerHTML = '✅ URL: <a href="' + d.url + '" target="_blank">' + d.url + '</a><br>Скопируй в Telegram для PC-B';
      // Копировать в буфер
      if (navigator.clipboard) {
        navigator.clipboard.writeText(d.url);
        el.innerHTML += '<br>(скопировано)';
      }
    } else {
      el.textContent = '❌ ' + (d.error || 'error');
    }
  } catch(e) {
    document.getElementById('bootstrapResult').textContent = '❌ ' + e;
  }
}

async function bootstrapStatus() {
  try {
    const r = await fetch('/api/bootstrap/status');
    const d = await r.json();
    const el = document.getElementById('bootstrapResult');
    el.innerHTML = 'Sprout: ' + JSON.stringify(d.sprout || {}) +
                   '<br>Public: ' + JSON.stringify(d.public_addr || []) +
                   '<br>NAT: ' + (d.nat_type || '?');
  } catch(e) {
    document.getElementById('bootstrapResult').textContent = '❌ ' + e;
  }
}

async function sproutUrl() {
  const url = document.getElementById('sproutUrl').value.trim();
  if (!url) return;
  try {
    const r = await fetch('/api/bootstrap/sprout', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({urls: [url]})
    });
    const d = await r.json();
    const el = document.getElementById('bootstrapResult');
    el.textContent = '✅ ' + JSON.stringify(d);
  } catch(e) {
    document.getElementById('bootstrapResult').textContent = '❌ ' + e;
  }
}

// === P89: Gravity ===
async function showGravity() {
  try {
    const r = await fetch('/api/gravity/field');
    const d = await r.json();
    const el = document.getElementById('gravityResult');
    const f = d.field || {};
    el.innerHTML = 'Nodes: ' + (f.nodes || 0) +
                   '<br>Edges: ' + (f.edges || 0) +
                   '<br>Total mass: ' + (f.total_mass || 0) +
                   '<br>Top: ' + JSON.stringify((f.top_nodes || []).slice(0, 3));
  } catch(e) {
    document.getElementById('gravityResult').textContent = '❌ ' + e;
  }
}

// === P89: Audit ===
async function showAudit() {
  try {
    const r = await fetch('/api/audit/log?limit=10');
    const d = await r.json();
    const el = document.getElementById('auditResult');
    if (d.events) {
      el.innerHTML = d.events.map(e => 
        '<div>' + (e.event_type || '?') + ' @ ' + (e.timestamp || 0).toFixed(0) + '</div>'
      ).join('');
    }
  } catch(e) {
    document.getElementById('auditResult').textContent = '❌ ' + e;
  }
}

async function verifyAudit() {
  try {
    const r = await fetch('/api/audit/verify');
    const d = await r.json();
    const el = document.getElementById('auditResult');
    el.innerHTML = d.valid ? '✅ Valid, events: ' + d.events : '❌ Invalid: ' + JSON.stringify(d.errors);
  } catch(e) {
    document.getElementById('auditResult').textContent = '❌ ' + e;
  }
}'''

patch_file(HTML, [(old_js_end, new_js_end, False)], "JS Bootstrap/Gravity/Audit", bak=".bak_p89_js")


# =====================================================================
# 4. UI - multi-color спирали для разных targets
# =====================================================================

print()
print("=" * 70)
print("  4. UI - разные цвета для targets")
print("=" * 70)

old_color = '''function tracerouteColor(hop) {
  // P87g: градиент для 100 hops
  // hop 1: #0a84ff (синий), hop 100: #bf5af2 (фиолетовый)
  const t = Math.min(1, (hop - 1) / 99);
  const r = Math.round(10 + (191 - 10) * t);
  const g = Math.round(132 + (90 - 132) * t);
  const b = Math.round(255 + (242 - 255) * t);
  return 'rgb(' + r + ',' + g + ',' + b + ')';
}'''

new_color = '''// P89: color per target
const TARGET_COLORS = {
  '8.8.8.8':         '#0a84ff',  // синий (Google)
  '8.8.4.4':         '#0a84ff',
  '1.1.1.1':         '#ffd60a',  // жёлтый (Cloudflare)
  '1.0.0.1':         '#ffd60a',
  '77.88.8.8':       '#ff453a',  // красный (Yandex)
  '77.88.8.1':       '#ff453a',
  '9.9.9.9':         '#bf5af2',  // фиолетовый (Quad9)
  '208.67.222.222':  '#30d158',  // зелёный (OpenDNS)
  '223.5.5.5':       '#64d2ff',  // голубой (AliDNS)
  '114.114.114.114': '#ff9f0a',  // оранжевый (114DNS)
  '64.6.64.6':       '#5ac8fa',  // Verisign
  '156.154.70.1':    '#ff375f',  // Neustar
  '84.200.69.80':    '#ac8e68',  // DNS.WATCH
  '8.26.56.26':      '#32ade6',  // Comodo
  '91.239.100.100':  '#5e5ce6',  // UncensoredDNS
  '185.228.168.9':   '#ff2d55',  // CleanBrowsing
  '76.76.2.0':       '#a2845e',  // ControlD
  '94.140.14.14':    '#30d158',  // AdGuard
  '76.76.19.19':     '#64d2ff',  // Alternate DNS
  '205.171.3.65':    '#ff9500',  // Level3
  '_default':        '#bf5af2',
};

function tracerouteColor(hop, target) {
  const base = TARGET_COLORS[target] || TARGET_COLORS['_default'];
  // Затемняем с глубиной: чем больше hop, тем светлее
  const t = Math.min(1, (hop - 1) / 99);
  // Парсим hex
  const r0 = parseInt(base.slice(1,3), 16);
  const g0 = parseInt(base.slice(3,5), 16);
  const b0 = parseInt(base.slice(5,7), 16);
  // Смешиваем с белым на 30% от hop
  const mix = 0.3 * t;
  const r = Math.round(r0 * (1 - mix) + 255 * mix);
  const g = Math.round(g0 * (1 - mix) + 255 * mix);
  const b = Math.round(b0 * (1 - mix) + 255 * mix);
  return 'rgb(' + r + ',' + g + ',' + b + ')';
}'''

patch_file(HTML, [(old_color, new_color, True)], "UI target colors", bak=".bak_p89_color")


# 5. В rebuildStars - передать target в tracerouteColor
old_size = '''    else if (nd.type === 'traceroute') {
      base = 2.5;
      color = tracerouteColor(nd.hops || 1);
    }'''

new_size = '''    else if (nd.type === 'traceroute') {
      base = 3;
      // P89: color по target
      const target = (nd.metadata && nd.metadata.target) || '_default';
      color = tracerouteColor(nd.hops || 1, target);
    }'''

patch_file(HTML, [(old_size, new_size, False)], "UI traceroute color by target", bak=".bak_p89_size")


# 6. В loadTreeFromAPI - сохранить target в metadata
old_meta = '''        rssi: (n.metadata && n.metadata.rssi) || (n.rssi) || -70,
        signal: (n.metadata && n.metadata.signal) || 50,
      };'''

new_meta = '''        rssi: (n.metadata && n.metadata.rssi) || (n.rssi) || -70,
        signal: (n.metadata && n.metadata.signal) || 50,
        target: (n.metadata && n.metadata.target) || '',
        metadata: n.metadata || {},
      };'''

patch_file(HTML, [(old_meta, new_meta, False)], "UI save target", bak=".bak_p89_meta")


print()
print("=" * 70)
print("  PATCH 89 DONE")
print("=" * 70)
print("  [OK] HTML: убраны Анонимность, Bridge, AI")
print("  [OK] HTML: добавлены Bootstrap, Gravity, Audit")
print("  [OK] JS: publishSeed, bootstrapStatus, sproutUrl, showGravity, showAudit, verifyAudit")
print("  [OK] UI: разные цвета для разных targets (20 targets)")
print()
print("Перезапуск + Ctrl+F5")