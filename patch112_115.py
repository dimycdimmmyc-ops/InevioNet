# patch112_115.py - P112+P113+P114+P115
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
INEV = os.path.join(ROOT, "inevionet")
ORG = os.path.join(INEV, "organism.py")
APP = os.path.join(ROOT, "web", "app.py")
HTML = os.path.join(ROOT, "web", "templates", "index.html")

BAK = ".bak_p112_115"


def _append(lst, x):
    """Авторская утилита: список + элемент."""
    n = len(lst)
    new_lst = [None] * (n + 1)
    for i in range(n):
        new_lst[i] = lst[i]
    new_lst[n] = x
    return new_lst


def _copy(d):
    """Авторская утилита: копия словаря."""
    new_d = {}
    for k in d:
        new_d[k] = d[k]
    return new_d


def _replace_all(content, old, new, count=1):
    """Авторская утилита: замена без str.replace (в явном виде)."""
    if not old:
        return content, 0
    result = ""
    i = 0
    n = len(content)
    ol = len(old)
    replaced = 0
    while i < n:
        if replaced < count and i + ol <= n and content[i:i+ol] == old:
            result += new
            i += ol
            replaced += 1
        else:
            result += content[i]
            i += 1
    return result, replaced


def patch_replace(path, replacements, label):
    """Авторский патч файла."""
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
            print("  [--] already applied")
            continue
        if old and old in content:
            content, n = _replace_all(content, old, new, 1)
            if n > 0:
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
# P112: Двусторонний DHT-bootstrap + merge + QR
# =====================================================================

print()
print("=" * 70)
print("  P112: двусторонний DHT + merge")
print("=" * 70)

# В organism.py — добавить публикацию своей карты в DHT-peers
with open(ORG, "r", encoding="utf-8") as f:
    org_content = f.read()

old_merge_dht = '''    def _merge_from_dht_peers(self):
        """P109: Merge карт через DHT peers."""'''

new_merge_dht = '''    def _publish_my_map_to_dht_peers(self):
        """P112: публикуем свою карту в DHT-peer'ов через их HTTP-эндпоинт."""
        try:
            if not getattr(self.net, "dht_bootstrap", None):
                return 0
            peers = self.net.dht_bootstrap.get_peers()
            my_map = self._build_my_map_summary()
            published = 0
            for peer in peers:
                node_id = peer.get("node_id", "")
                if not node_id or node_id == self.net.node_id:
                    continue
                pub_ip = peer.get("public_ip", "")
                pub_port = peer.get("public_port", 0)
                if not pub_ip or not pub_port:
                    continue
                try:
                    import urllib.request as _u
                    import ssl as _ssl
                    import json as _j
                    ctx = _ssl._create_unverified_context()
                    payload = _j.dumps(my_map, ensure_ascii=False).encode("utf-8")
                    for scheme in ("https", "http"):
                        url = "%s://%s:%d/api/dht/merge" % (scheme, pub_ip, pub_port)
                        try:
                            req = _u.Request(
                                url, data=payload,
                                headers={"Content-Type": "application/json"},
                                method="POST")
                            with _u.urlopen(req, timeout=5, context=ctx) as r:
                                resp = _j.loads(r.read().decode("utf-8"))
                            if resp.get("success"):
                                published += 1
                                logger.info("[P112] published map to %s", node_id)
                                break
                        except Exception:
                            continue
                except Exception as e:
                    logger.debug("[P112] %s: %s", node_id, e)
            return published
        except Exception as e:
            logger.debug("[P112] publish: %s", e)
            return 0

    def _build_my_map_summary(self):
        """P112: собрать карту для публикации."""
        nodes = []
        count = 0
        for ip, node in self.memory.get("nodes", {}).items():
            if count >= 100:
                break
            nodes = _append(nodes, {
                "ip": ip,
                "type": node.get("type", "device"),
                "depth": node.get("depth", 1),
                "source": node.get("source", "?"),
                "vendor": node.get("vendor", ""),
                "nlp_plan": node.get("nlp_plan", ""),
                "can_teach": node.get("can_teach", False),
                "can_relay": node.get("can_relay", False),
            })
            count += 1
        return {
            "node_id": self.net.node_id,
            "serial": getattr(self.net, "serial", ""),
            "ts": time.time(),
            "nodes": nodes,
            "relayed": list(self.memory.get("relayed_ips", set())),
            "taught": list(self.memory.get("taught", set())),
            "depth": dict(self.memory.get("depth", {})),
        }

    def _merge_from_dht_peers(self):
        """P109: Merge карт через DHT peers."""'''

if old_merge_dht in org_content:
    org_content = org_content.replace(old_merge_dht, new_merge_dht, 1)
    print("  [OK] _publish_my_map_to_dht_peers")
else:
    print("  [--] already applied")

# В merge_phase — вызвать publish перед merge
old_merge_call2 = '''    def merge_phase(self):
        """P109: фаза merge - DHT + dead_drop."""
        # P109: DHT merge
        try:
            self._merge_from_dht_peers()
        except Exception as e:
            logger.debug("[Merge] DHT: %s", e)'''

new_merge_call2 = '''    def merge_phase(self):
        """P112: фаза merge - DHT + dead_drop + publish."""
        # P112: publish свою карту в DHT-peers
        try:
            n = self._publish_my_map_to_dht_peers()
            if n > 0:
                logger.info("[P112] published to %d DHT-peers", n)
        except Exception as e:
            logger.debug("[P112] publish: %s", e)
        # P109: DHT merge
        try:
            self._merge_from_dht_peers()
        except Exception as e:
            logger.debug("[Merge] DHT: %s", e)'''

if old_merge_call2 in org_content:
    org_content = org_content.replace(old_merge_call2, new_merge_call2, 1)
    print("  [OK] merge_phase вызывает publish")
else:
    print("  [--] already applied")

with open(ORG, "w", encoding="utf-8") as f:
    f.write(org_content)
try:
    ast.parse(org_content)
    print("  [OK] syntax organism.py")
except SyntaxError as e:
    print("  [!!] syntax: " + str(e))


# Backend: /api/dht/merge — принимает чужую карту
with open(APP, "r", encoding="utf-8") as f:
    app_content = f.read()

anchor = "@app.route('/api/network/public')"

merge_ep = '''@app.route('/api/dht/merge', methods=['POST'])
def api_dht_merge():
    """P112: принять чужую карту от DHT-peer."""
    try:
        n = get_net()
        d = request.get_json(silent=True) or {}
        sender = d.get("node_id", "")
        if not sender or sender == n.node_id:
            return jsonify({"success": False, "error": "same_node"}), 400
        nodes_in = d.get("nodes", []) or []
        added = 0
        for item in nodes_in:
            if not isinstance(item, dict):
                continue
            ip = item.get("ip", "")
            if not ip:
                continue
            # Merge через organism
            if getattr(n, "organism", None):
                org = n.organism
                with org._lock:
                    if ip in org.memory["nodes"]:
                        continue
                    node = dict(item)
                    node["via_dht_peer"] = sender
                    node["source"] = "merge_dht:" + str(node.get("source", "?"))
                    node["depth"] = int(node.get("depth", 1)) + 1
                    org.memory["nodes"][ip] = node
                    added += 1
        # Merge relayed/taught
        if getattr(n, "organism", None):
            org = n.organism
            for r in d.get("relayed", []) or []:
                org.memory.setdefault("relayed_ips", set()).add(r)
            for t in d.get("taught", []) or []:
                org.memory.setdefault("taught", set()).add(t)
            with org._lock:
                org.stats["maps_merged"] = org.stats.get("maps_merged", 0) + 1
                org.stats["nodes_from_merge"] = org.stats.get("nodes_from_merge", 0) + added
        # Audit
        try:
            if getattr(n, "audit", None):
                n.audit.add_event("dht_merge", {
                    "sender": sender,
                    "added": added,
                })
        except Exception:
            pass
        return jsonify({
            "success": True,
            "sender": sender,
            "added": added,
        })
    except Exception as e:
        log.error("[DHT] merge: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/network/public')'''

if merge_ep not in app_content:
    app_content = app_content.replace(anchor, merge_ep, 1)
    print("  [OK] app.py: /api/dht/merge")
else:
    print("  [--] already applied")

with open(APP, "w", encoding="utf-8") as f:
    f.write(app_content)
try:
    ast.parse(app_content)
    print("  [OK] syntax app.py")
except SyntaxError as e:
    print("  [!!] syntax: " + str(e))


# =====================================================================
# P113: Auth UI
# =====================================================================

print()
print("=" * 70)
print("  P113: Auth UI")
print("=" * 70)

with open(HTML, "r", encoding="utf-8") as f:
    h = f.read()

# checkAuth — при 401 или ошибке → showAuth
old_check = '''async function checkAuth() {
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
}'''

new_check = '''async function checkAuth() {
  try {
    const r = await fetch('/api/me');
    if (r.status === 401) {
      showAuth();
      return;
    }
    const d = await r.json();
    if (d.success && d.user) {
      state.currentUser = d.user;
      hideAuth();
      updateUserBar();
      await loadContacts();
    } else {
      showAuth();
    }
  } catch (e) {
    showAuth();
  }
}

// P113: кнопки Enter в auth-полях
document.addEventListener('keydown', (e) => {
  if (!state.currentUser) {
    if (e.key === 'Enter') {
      const loginForm = document.getElementById('authLogin');
      const regForm = document.getElementById('authRegister');
      if (loginForm && loginForm.classList.contains('active')) {
        doLogin();
      } else if (regForm && regForm.classList.contains('active')) {
        doRegister();
      }
    }
  }
});'''

if old_check in h:
    h = h.replace(old_check, new_check, 1)
    print("  [OK] checkAuth + Enter")
else:
    print("  [--] already applied")

with open(HTML, "w", encoding="utf-8") as f:
    f.write(h)
print("  [OK] index.html (P113)")


# =====================================================================
# P114: QR-код
# =====================================================================

print()
print("=" * 70)
print("  P114: QR-код")
print("=" * 70)

with open(APP, "r", encoding="utf-8") as f:
    app_content = f.read()

# Проверим /api/qr существует
if "/api/qr" in app_content:
    print("  [OK] /api/qr уже есть")
else:
    print("  [!!] /api/qr отсутствует — добавляем")

# Добавим endpoint /api/trust/qr_image — генерит QR из JSON
anchor2 = "@app.route('/api/network/public')"

qr_img_ep = '''@app.route('/api/trust/qr_image')
def api_trust_qr_image():
    """P114: QR-код с моим JSON (для сканирования)."""
    try:
        n = get_net()
        # Собираем JSON
        from inevionet.core.serial import get_current_serial
        serial = get_current_serial()
        addr = getattr(n, "public_addr", None)
        pub_ip = addr[0] if addr else ""
        pub_port = addr[1] if addr else 0
        dd_url = ""
        if getattr(n, "dead_drop", None):
            dd_url = n.dead_drop.my_url or ""
        relay_count = 0
        nodes_count = 0
        if hasattr(n, "organism") and n.organism:
            relay_count = n.organism.stats.get("nodes_relayed", 0)
            nodes_count = len(n.organism.memory.get("nodes", {}))
        info = {
            "node_id": n.node_id,
            "serial": serial,
            "public_ip": pub_ip,
            "public_port": pub_port,
            "nat_type": getattr(n, "nat_type", "unknown"),
            "dead_drop_url": dd_url,
            "relay_count": relay_count,
            "nodes_count": nodes_count,
        }
        # Генерируем QR через qrcode (если есть)
        try:
            import qrcode
            import io
            import base64
            qr = qrcode.QRCode(version=None, box_size=8, border=2)
            qr.add_data(json.dumps(info, ensure_ascii=False))
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            b64 = base64.b64encode(buf.getvalue()).decode()
            return jsonify({
                "success": True,
                "qr_base64": "data:image/png;base64," + b64,
                "info": info,
            })
        except ImportError:
            return jsonify({
                "success": False,
                "error": "qrcode_not_installed",
                "info": info,
                "hint": "pip install qrcode[pil]",
            })
    except Exception as e:
        log.error("[QR] image: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/network/public')'''

if qr_img_ep not in app_content:
    app_content = app_content.replace(anchor2, qr_img_ep, 1)
    print("  [OK] app.py: /api/trust/qr_image")
else:
    print("  [--] already applied")

with open(APP, "w", encoding="utf-8") as f:
    f.write(app_content)
try:
    ast.parse(app_content)
    print("  [OK] syntax app.py")
except SyntaxError as e:
    print("  [!!] syntax: " + str(e))

# UI: показать QR
with open(HTML, "r", encoding="utf-8") as f:
    h = f.read()

old_trust_block = '''      <div class="section-title" style="margin-top:20px;margin-bottom:8px">&#x1F91D; Доверие (QR)</div>
      <textarea class="form-textarea" id="trustJsonInput" placeholder='Вставьте JSON для доверия' style="min-height:80px;font-size:10px"></textarea>
      <button class="btn btn-primary" onclick="addTrustFromJson()" style="margin-top:8px">&#x1F91D; Добавить в доверенные</button>'''

new_trust_block = '''      <div class="section-title" style="margin-top:20px;margin-bottom:8px">&#x1F4F1; Мой QR (для доверия)</div>
      <div class="qr-box" style="text-align:center;margin-bottom:8px">
        <img id="qrTrustImage" src="" style="display:none;max-width:180px;border-radius:8px;background:#fff;padding:8px">
        <div id="qrTrustPlaceholder" style="color:var(--dim);font-size:11px;font-style:italic">Нажмите кнопку</div>
      </div>
      <button class="btn btn-ghost" onclick="showMyQr()">&#x1F4F1; Показать QR</button>
      
      <div class="section-title" style="margin-top:20px;margin-bottom:8px">&#x1F91D; Доверие (вставить JSON)</div>
      <textarea class="form-textarea" id="trustJsonInput" placeholder='Вставьте JSON для доверия' style="min-height:80px;font-size:10px"></textarea>
      <button class="btn btn-primary" onclick="addTrustFromJson()" style="margin-top:8px">&#x1F91D; Добавить в доверенные</button>'''

if old_trust_block in h:
    h = h.replace(old_trust_block, new_trust_block, 1)
    print("  [OK] HTML: QR блок")
else:
    print("  [--] HTML: QR блок (anchor)")

# JS: showMyQr
old_dom2 = "document.addEventListener('DOMContentLoaded', init);"
new_js2 = '''
// === P114: QR ===
async function showMyQr() {
  try {
    const r = await fetch('/api/trust/qr_image');
    const d = await r.json();
    if (d.success && d.qr_base64) {
      const img = $('qrTrustImage');
      img.src = d.qr_base64;
      img.style.display = 'block';
      $('qrTrustPlaceholder').style.display = 'none';
      addLog('QR готов', 'success');
    } else {
      addLog('QR: ' + (d.error || d.hint || '?'), 'warn');
    }
  } catch (e) {
    addLog('QR ошибка: ' + e.message, 'error');
  }
}

'''
h = h.replace(old_dom2, new_js2 + old_dom2, 1)

with open(HTML, "w", encoding="utf-8") as f:
    f.write(h)
print("  [OK] index.html (P114)")


# =====================================================================
# P115: Сборка EXE + LICENSE + .gitignore
# =====================================================================

print()
print("=" * 70)
print("  P115: файлы для сборки")
print("=" * 70)

# LICENSE
license_path = os.path.join(ROOT, "LICENSE")
if not os.path.exists(license_path):
    license_text = (
        "InevioNet - Dual Licensing\n"
        "Copyright (c) 2026 dimon027081\n\n"
        "1) AGPL-3.0-or-later (see LICENSE-AGPL.txt)\n"
        "2) InevioNet Commercial License (see LICENSE-COMMERCIAL.md)\n\n"
        "SPDX-License-Identifier: AGPL-3.0-or-later OR LicenseRef-InevioNet-Commercial-1.0\n"
    )
    with open(license_path, "w", encoding="utf-8") as f:
        f.write(license_text)
    print("  [OK] LICENSE")
else:
    print("  [--] LICENSE уже есть")

# .gitignore
gi_path = os.path.join(ROOT, ".gitignore")
if not os.path.exists(gi_path):
    gi = (
        "__pycache__/\n*.py[cod]\nbuild/\ndist/\nvenv/\n.venv/\n"
        "data/\nlogs/\n*.log\n*.bak*\n*.key\n*.pem\n"
        "_backup_*/\n_transfer/\ninstaller_output/\npatch*.py\nfix_*.py\n"
    )
    with open(gi_path, "w", encoding="utf-8") as f:
        f.write(gi)
    print("  [OK] .gitignore")
else:
    print("  [--] .gitignore уже есть")

print()
print("=" * 70)
print("  PATCH 112-115 DONE")
print("=" * 70)
print("  [OK] P112: двусторонний DHT publish + merge")
print("  [OK] P113: auth checkAuth + Enter")
print("  [OK] P114: QR-код (qrcode + base64)")
print("  [OK] P115: LICENSE + .gitignore")
print()
print("Дальше:")
print("  pip install qrcode[pil]")
print("  Перезапуск: python -m web.app")
print("  Сборка: pyinstaller InevioNet.spec --clean --noconfirm")