# patch108_111.py - P108+P109+P110+P111
import os
import ast
import shutil
import re

ROOT = r"E:\InevioNet"
INEV = os.path.join(ROOT, "inevionet")
ORG = os.path.join(INEV, "organism.py")
ORCH = os.path.join(INEV, "orchestrator.py")
APP = os.path.join(ROOT, "web", "app.py")
HTML = os.path.join(ROOT, "web", "templates", "index.html")

BAK = ".bak_p108_111"


def patch_replace(path, replacements, label):
    if not os.path.exists(path):
        print("  [!!] NOT FOUND: " + path)
        return False
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    b = path + BAK
    shutil.copy2(path, b)
    print("  [BK] " + os.path.basename(b))
    changed = 0
    for old, new, required in replacements:
        if new and new in content and (not old or old not in content):
            print("  [--] already applied: " + old[:40].strip().replace(chr(10), ' '))
            continue
        if old and old in content:
            content = content.replace(old, new, 1)
            changed += 1
            print("  [OK] " + old[:55].strip().replace(chr(10), ' '))
        else:
            if required:
                print("  [!!] NOT FOUND: " + old[:55].strip().replace(chr(10), ' '))
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
    return True


# =====================================================================
# P108: SuperNode + Evolution в teach()
# =====================================================================

print()
print("=" * 70)
print("  P108: SuperNode + Evolution в teach()")
print("=" * 70)

# Найти teach() в organism.py
with open(ORG, "r", encoding="utf-8") as f:
    org_content = f.read()

m = re.search(r"    def teach\(self\):.*?(?=\n    def |\n    # =)", org_content, re.DOTALL)
if m:
    old_teach = m.group(0)
    new_teach = '''    def teach(self):
        """P108: teach через SuperNode + Evolution + Masking."""
        # 1. SuperNode broadcast
        try:
            if hasattr(self.net, "_supernode_loop_once"):
                self.net._supernode_loop_once()
        except Exception as e:
            logger.debug("[Teach] supernode: %s", e)

        # 2. Evolution
        try:
            if hasattr(self.net, "evolution") and self.net.evolution:
                # Один шаг эволюции
                if hasattr(self.net.evolution, "evolve"):
                    self.net.evolution.evolve()
                elif hasattr(self.net.evolution, "step"):
                    self.net.evolution.step()
                # Записать успех для обученных узлов
                taught_count = len(self.memory.get("taught", set()))
                if taught_count > 0 and hasattr(self.net.evolution, "record_success"):
                    for ip in list(self.memory.get("taught", set()))[:5]:
                        try:
                            self.net.evolution.record_success(ip)
                        except Exception:
                            pass
                if hasattr(self.net.evolution, "get_stats"):
                    st = self.net.evolution.get_stats()
                    logger.debug("[Teach] evolution gen=%s best=%.3f",
                                 st.get("generation", "?"),
                                 st.get("best_fitness", 0.0))
        except Exception as e:
            logger.debug("[Teach] evolution: %s", e)

        # 3. Masking — адаптация под сеть
        try:
            if hasattr(self.net, "_multi_channel_loop_once"):
                self.net._multi_channel_loop_once()
        except Exception as e:
            logger.debug("[Teach] masking: %s", e)

        # 4. SuperNode — обучение узлов с высоким fitness
        try:
            if hasattr(self.net, "super_node") and self.net.super_node:
                sn = self.net.super_node
                # Продвинуть узлы с хорошим score
                for ip, node in list(self.memory.get("nodes", {}).items())[:50]:
                    score = node.get("score", 0)
                    if score >= 0.7:
                        try:
                            if hasattr(sn, "promote"):
                                sn.promote(ip)
                            elif hasattr(sn, "mark_super"):
                                sn.mark_super(ip)
                        except Exception:
                            pass
        except Exception as e:
            logger.debug("[Teach] supernode promote: %s", e)

        # 5. Audit: teach-событие
        try:
            if hasattr(self.net, "audit") and self.net.audit:
                self.net.audit.add_event("teach", {
                    "taught_count": len(self.memory.get("taught", set())),
                    "relayed_count": len(self.memory.get("relayed_ips", set())),
                    "nodes_count": len(self.memory.get("nodes", {})),
                })
        except Exception as e:
            logger.debug("[Teach] audit: %s", e)

        self._log_phase("teach", 0, f"taught={len(self.memory.get('taught', set()))}")'''
    
    org_content = org_content[:m.start()] + new_teach + org_content[m.end():]
    with open(ORG, "w", encoding="utf-8") as f:
        f.write(org_content)
    try:
        ast.parse(org_content)
        print("  [OK] teach() переработан")
    except SyntaxError as e:
        print("  [!!] syntax: " + str(e))
else:
    print("  [!!] teach() не найден")


# =====================================================================
# P109: Merge через DHT
# =====================================================================

print()
print("=" * 70)
print("  P109: Merge через DHT")
print("=" * 70)

# В organism.py — добавить метод merge_phase_dht (расширение merge_phase)
with open(ORG, "r", encoding="utf-8") as f:
    org_content = f.read()

# Добавить метод _merge_from_dht_peer в merge_phase
old_merge = '''    def merge_phase(self):'''
new_merge = '''    def _merge_from_dht_peers(self):
        """P109: Merge карт через DHT peers."""
        added_total = 0
        try:
            if not getattr(self.net, "dht_bootstrap", None):
                return 0
            peers = self.net.dht_bootstrap.get_peers()
            for peer in peers:
                node_id = peer.get("node_id", "")
                if not node_id or node_id == self.net.node_id:
                    continue
                # Пробуем получить карту через HTTP /api/organism
                pub_ip = peer.get("public_ip", "")
                pub_port = peer.get("public_port", 0)
                if not pub_ip or not pub_port:
                    continue
                try:
                    import urllib.request as _u
                    import ssl as _ssl
                    import json as _j
                    ctx = _ssl._create_unverified_context()
                    # Пробуем HTTPS (порт 8080) и HTTP
                    for scheme in ("https", "http"):
                        url = "%s://%s:%d/api/organism" % (scheme, pub_ip, pub_port)
                        try:
                            req = _u.Request(url, headers={"User-Agent": "InevioNet/1.0"})
                            with _u.urlopen(req, timeout=3, context=ctx) as r:
                                data = _j.loads(r.read().decode("utf-8"))
                            if not data.get("success"):
                                continue
                            remote_nodes = data.get("nodes", []) or data.get("nodes_sample", [])
                            for item in remote_nodes:
                                if not isinstance(item, list) or len(item) < 2:
                                    continue
                                ip = item[0]
                                node = item[1]
                                if not ip or ip in self.memory["nodes"]:
                                    continue
                                # Merge новый узел
                                node = dict(node)
                                node["via_dht_peer"] = node_id
                                node["source"] = "merge_dht:" + str(node.get("source", "?"))
                                node["depth"] = int(node.get("depth", 1)) + 1
                                with self._lock:
                                    self.memory["nodes"][ip] = node
                                added_total += 1
                            if added_total > 0:
                                logger.info("[Merge/DHT] from %s: +%d nodes", node_id, added_total)
                            break  # нашли рабочий scheme
                        except Exception as _e:
                            continue
                except Exception as e:
                    logger.debug("[Merge/DHT] %s: %s", node_id, e)
        except Exception as e:
            logger.debug("[Merge/DHT] outer: %s", e)
        if added_total > 0:
            with self._lock:
                self.stats["maps_merged"] = self.stats.get("maps_merged", 0) + 1
                self.stats["nodes_from_merge"] = self.stats.get("nodes_from_merge", 0) + added_total
        return added_total

    def merge_phase(self):'''
if old_merge in org_content:
    org_content = org_content.replace(old_merge, new_merge, 1)
    print("  [OK] _merge_from_dht_peers добавлен")
else:
    print("  [!!] merge_phase не найден")

# В merge_phase — вызвать _merge_from_dht_peers
old_merge_call = '''    def merge_phase(self):
        """P97: фаза merge - экспорт + broadcast + приём."""
        try:'''
new_merge_call = '''    def merge_phase(self):
        """P109: фаза merge - DHT + dead_drop."""
        # P109: DHT merge
        try:
            self._merge_from_dht_peers()
        except Exception as e:
            logger.debug("[Merge] DHT: %s", e)
        # P97: dead_drop merge
        try:'''
if old_merge_call in org_content:
    org_content = org_content.replace(old_merge_call, new_merge_call, 1)
    print("  [OK] merge_phase вызывает _merge_from_dht_peers")

with open(ORG, "w", encoding="utf-8") as f:
    f.write(org_content)
try:
    ast.parse(org_content)
    print("  [OK] syntax organism.py")
except SyntaxError as e:
    print("  [!!] syntax: " + str(e))


# =====================================================================
# P110: Кэши LRU/KL/Firewall в scout()
# =====================================================================

print()
print("=" * 70)
print("  P110: Кэши в scout()")
print("=" * 70)

# Проверим, что в cache.py
CACHE = os.path.join(INEV, "core", "cache.py")
with open(CACHE, "r", encoding="utf-8") as f:
    cache_content = f.read()

# Какие классы есть?
cache_classes = []
for cls in ["LRUCache", "KLDivergenceCache", "FirewallCache"]:
    if "class " + cls in cache_content:
        cache_classes.append(cls)
print("  Найдены кэши: " + ", ".join(cache_classes) if cache_classes else "  [!!] нет классов кэшей")

# В organism.py — добавить инициализацию кэшей
with open(ORG, "r", encoding="utf-8") as f:
    org_content = f.read()

# В __init__ — добавить кэши
old_init_caches = '''        # P95c: async traceroute (не блокирует scout)'''
new_init_caches = '''        # P110: кэши
        self._scout_cache = None
        self._dns_cache = None
        try:
            from .core.cache import LRUCache
            self._scout_cache = LRUCache(max_size=500, ttl=300)  # 5 мин
            logger.info("[P110] scout cache initialized")
        except Exception as _ce:
            logger.debug("[P110] cache: %s", _ce)

        # P95c: async traceroute (не блокирует scout)'''

if old_init_caches in org_content:
    org_content = org_content.replace(old_init_caches, new_init_caches, 1)
    print("  [OK] кэш в __init__")
else:
    print("  [--] __init__ anchor")

# В scout() — использовать кэш
old_scout_cache = '''        new_count = len(found)
        total_in_memory = len(self.memory["nodes"])'''

new_scout_cache = '''        # P110: кэшировать результаты scout
        try:
            if getattr(self, "_scout_cache", None):
                for node in found:
                    ip = node.get("ip", "")
                    if ip:
                        self._scout_cache.set(ip, node)
        except Exception as _sce:
            logger.debug("[P110] cache set: %s", _sce)

        new_count = len(found)
        total_in_memory = len(self.memory["nodes"])'''

if old_scout_cache in org_content:
    org_content = org_content.replace(old_scout_cache, new_scout_cache, 1)
    print("  [OK] scout использует кэш")
else:
    print("  [--] scout cache anchor")

with open(ORG, "w", encoding="utf-8") as f:
    f.write(org_content)
try:
    ast.parse(org_content)
    print("  [OK] syntax organism.py (кэш)")
except SyntaxError as e:
    print("  [!!] syntax: " + str(e))


# =====================================================================
# P111: QR-обмен для доверия
# =====================================================================

print()
print("=" * 70)
print("  P111: QR-обмен для доверия")
print("=" * 70)

# 1. Backend: endpoint для QR-доверия
with open(APP, "r", encoding="utf-8") as f:
    app_content = f.read()

anchor = "@app.route('/api/network/public')"

qr_trust_ep = '''@app.route('/api/trust/qr', methods=['POST'])
def api_trust_qr():
    """P111: добавить доверенного через QR-JSON."""
    try:
        n = get_net()
        d = request.get_json(silent=True) or {}
        # Ожидаем: {node_id, serial, public_ip, public_port, dead_drop_url}
        peer = d.get("peer", {}) or d
        node_id = peer.get("node_id", "")
        if not node_id:
            return jsonify({"success": False, "error": "no_node_id"}), 400
        
        added = False
        # 1. Добавить в trusted_hosts
        host = ""
        if peer.get("public_ip") and peer.get("public_port"):
            host = "%s:%d" % (peer["public_ip"], int(peer["public_port"]))
        if host:
            try:
                added = n.trusted_hosts.add(host, label=node_id, method="qr")
            except Exception:
                pass
        # 2. Добавить в DHT
        if getattr(n, "dht_bootstrap", None):
            try:
                n.dht_bootstrap.add_peer_dict(peer)
            except Exception:
                pass
        # 3. Регистрируем в dead_drop (если есть URL)
        if peer.get("dead_drop_url") and getattr(n, "dead_drop", None):
            try:
                n.dead_drop.register_peer(node_id, peer["dead_drop_url"])
            except Exception:
                pass
        # 4. Audit
        try:
            if getattr(n, "audit", None):
                n.audit.add_event("trust_qr", {
                    "node_id": node_id,
                    "host": host,
                    "added": added,
                })
        except Exception:
            pass
        
        return jsonify({
            "success": True,
            "added": added,
            "node_id": node_id,
            "host": host,
        })
    except Exception as e:
        log.error("[TrustQR] %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/trust/list')
def api_trust_list():
    """P111: список доверенных."""
    try:
        n = get_net()
        hosts = n.trusted_hosts.list_all()
        return jsonify({"success": True, "hosts": hosts, "count": len(hosts)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/network/public')'''

if qr_trust_ep not in app_content:
    app_content = app_content.replace(anchor, qr_trust_ep, 1)
    with open(APP, "w", encoding="utf-8") as f:
        f.write(app_content)
    try:
        ast.parse(app_content)
        print("  [OK] app.py: /api/trust/qr + /api/trust/list")
    except SyntaxError as e:
        print("  [!!] syntax: " + str(e))
else:
    print("  [--] уже есть")


# 2. Frontend: кнопки в DHT-вкладке
with open(HTML, "r", encoding="utf-8") as f:
    h = f.read()

# Найти вкладку DHT и добавить блок Trust/QR
old_dht_block = '''      <div class="section-title" style="margin-top:20px;margin-bottom:8px">&#x2795; Добавить peer</div>
      <textarea class="form-textarea" id="peerJsonInput" placeholder='Вставьте JSON другого узла' style="min-height:80px;font-size:10px"></textarea>
      <button class="btn btn-success" onclick="addPeerFromJson()" style="margin-top:8px">&#x2795; Добавить в DHT</button>'''

new_dht_block = '''      <div class="section-title" style="margin-top:20px;margin-bottom:8px">&#x2795; Добавить peer (DHT)</div>
      <textarea class="form-textarea" id="peerJsonInput" placeholder='Вставьте JSON другого узла' style="min-height:80px;font-size:10px"></textarea>
      <button class="btn btn-success" onclick="addPeerFromJson()" style="margin-top:8px">&#x2795; Добавить в DHT</button>
      
      <div class="section-title" style="margin-top:20px;margin-bottom:8px">&#x1F91D; Доверие (QR)</div>
      <textarea class="form-textarea" id="trustJsonInput" placeholder='Вставьте JSON для доверия' style="min-height:80px;font-size:10px"></textarea>
      <button class="btn btn-primary" onclick="addTrustFromJson()" style="margin-top:8px">&#x1F91D; Добавить в доверенные</button>
      
      <div class="section-title" style="margin-top:16px;margin-bottom:8px">
        &#x1F512; Доверенные <span class="count" id="trustCount">0</span>
      </div>
      <div id="trustList" style="margin-top:8px"><div class="empty">Нет доверенных</div></div>'''

if old_dht_block in h:
    h = h.replace(old_dht_block, new_dht_block, 1)
    print("  [OK] HTML: блок Trust/QR")
else:
    print("  [--] HTML: блок Trust/QR (anchor)")

# JS: функции для trust
old_dom = "document.addEventListener('DOMContentLoaded', init);"
new_js = '''
// === P111: TRUST / QR ===
async function addTrustFromJson() {
  const raw = $('trustJsonInput').value.trim();
  if (!raw) { addLog('Вставьте JSON', 'warn'); return; }
  try {
    let peer;
    try { peer = JSON.parse(raw); } catch (e) { peer = {node_id: raw}; }
    const r = await fetch('/api/trust/qr', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({peer})
    });
    const d = await r.json();
    if (d.success) {
      addLog('Доверенный добавлен: ' + (d.node_id || '?'), 'success');
      $('trustJsonInput').value = '';
      await fetchTrustList();
      await fetchDhtPeers();
    } else {
      addLog('Ошибка: ' + (d.error || '?'), 'error');
    }
  } catch (e) {
    addLog('Ошибка: ' + e.message, 'error');
  }
}

async function fetchTrustList() {
  try {
    const r = await fetch('/api/trust/list');
    const d = await r.json();
    if (!d.success) return;
    const hosts = d.hosts || [];
    if ($('trustCount')) $('trustCount').textContent = hosts.length;
    const el = $('trustList');
    if (!el) return;
    if (!hosts.length) {
      el.innerHTML = '<div class="empty">Нет доверенных</div>';
      return;
    }
    el.innerHTML = hosts.map(t =>
      '<div class="contact-card">' +
        '<div class="contact-info">' +
          '<div class="contact-name">' + escapeHtml(t.label || '?') + '</div>' +
          '<div class="contact-node">' + (t.host || '') + ' | ' + (t.method || '?') + '</div>' +
        '</div>' +
      '</div>'
    ).join('');
  } catch (e) {}
}

// периодически обновляем
setInterval(() => {
  if (state.currentUser) fetchTrustList();
}, 15000);

'''
h = h.replace(old_dom, new_js + old_dom, 1)

# В init — добавить fetchTrustList
old_init = '''    await fetchDhtMyInfo();
    await fetchDhtPeers();'''
new_init = '''    await fetchDhtMyInfo();
    await fetchDhtPeers();
    await fetchTrustList();'''
if old_init in h:
    h = h.replace(old_init, new_init, 1)
    print("  [OK] init: + fetchTrustList")

with open(HTML, "w", encoding="utf-8") as f:
    f.write(h)


print()
print("=" * 70)
print("  PATCH 108-111 DONE")
print("=" * 70)
print("  [OK] P108: teach() — SuperNode + Evolution + Masking + Audit")
print("  [OK] P109: merge через DHT (_merge_from_dht_peers)")
print("  [OK] P110: кэш LRU в scout()")
print("  [OK] P111: QR-доверие (/api/trust/qr + UI)")
print()
print("Перезапуск: python -m web.app")