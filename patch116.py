# patch116.py - ФИНАЛЬНЫЙ: serial per-port + DHT<->dead_drop + merge + auth + QR
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
INEV = os.path.join(ROOT, "inevionet")
SERIAL = os.path.join(INEV, "core", "serial.py")
DD = os.path.join(INEV, "network", "dead_drop.py")
ORG = os.path.join(INEV, "organism.py")
APP = os.path.join(ROOT, "web", "app.py")
HTML = os.path.join(ROOT, "web", "templates", "index.html")

BAK = ".bak_p116"


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
            print("  [--] already: " + old[:40].strip().replace(chr(10), ' '))
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
# 1. serial.py — per-port (8080/8081 — разные serial)
# =====================================================================

print()
print("=" * 70)
print("  1. serial.py: per-port")
print("=" * 70)

patch_replace(SERIAL, [
    (
        '''def get_serial_file(data_home: str = None) -> Path:
    """Путь к serial.txt."""
    if data_home is None:
        data_home = os.environ.get("INEVIO_DATA_DIR") or os.path.join(
            os.environ.get("APPDATA", os.path.expanduser("~")),
            "InevioNet", "data")
    return Path(data_home) / "serial.txt"''',
        '''def get_serial_file(data_home: str = None) -> Path:
    """Путь к serial.txt (per-port, P116)."""
    if data_home is None:
        data_home = os.environ.get("INEVIO_DATA_DIR") or os.path.join(
            os.environ.get("APPDATA", os.path.expanduser("~")),
            "InevioNet", "data")
    port = os.environ.get("INEVIO_PORT", "8080")
    return Path(data_home) / ("serial_%s.txt" % port)''',
        True
    ),
], "serial per-port")

# Удалить старый serial.txt
old_file = os.path.join(os.environ.get("APPDATA", ""), "InevioNet", "data", "serial.txt")
if os.path.exists(old_file):
    try:
        os.remove(old_file)
        print("  [OK] удалён старый serial.txt")
    except Exception as e:
        print("  [!!] " + str(e))


# =====================================================================
# 2. dead_drop.py — feed с serial + my_url (для merge через paste.rs)
# =====================================================================

print()
print("=" * 70)
print("  2. dead_drop.py: feed с serial")
print("=" * 70)

with open(DD, "r", encoding="utf-8") as f:
    dd_content = f.read()

# Добавить serial в feed (если ещё нет)
if '"serial": self.serial' not in dd_content:
    # Найти _publish_feed
    old_feed = '''        feed = json.dumps({
            "node_id": self.node_id,
            "ts": time.time(),
            "my_url": self.my_url,
            "peers": [{"node_id": nid, "url": u} for nid, u in urls],
            "cards": cards,
        }, separators=(",", ":"))'''
    
    new_feed = '''        feed = json.dumps({
            "node_id": self.node_id,
            "serial": getattr(self, "serial", ""),
            "ts": time.time(),
            "my_url": self.my_url,
            "peers": [{"node_id": nid, "url": u} for nid, u in urls],
            "cards": cards,
        }, separators=(",", ":"))'''
    
    if old_feed in dd_content:
        dd_content = dd_content.replace(old_feed, new_feed, 1)
        print("  [OK] feed + serial")
    else:
        print("  [--] feed уже с serial")
else:
    print("  [--] feed уже с serial")

# Добавить serial в __init__ DeadDrop
if 'self.serial' not in dd_content:
    old_init = '''    def __init__(self, node_id: str, poll_interval: int = 60):
        self.node_id = node_id
        self.poll_interval = poll_interval'''
    
    new_init = '''    def __init__(self, node_id: str, poll_interval: int = 60, serial: str = ""):
        self.node_id = node_id
        self.serial = serial
        self.poll_interval = poll_interval'''
    
    if old_init in dd_content:
        dd_content = dd_content.replace(old_init, new_init, 1)
        print("  [OK] DeadDrop.__init__ + serial")

with open(DD, "w", encoding="utf-8") as f:
    f.write(dd_content)
try:
    ast.parse(dd_content)
    print("  [OK] syntax dead_drop.py")
except SyntaxError as e:
    print("  [!!] syntax: " + str(e))


# =====================================================================
# 3. organism.py — merge через dead_drop (fallback при NAT)
# =====================================================================

print()
print("=" * 70)
print("  3. organism.py: merge через dead_drop")
print("=" * 70)

with open(ORG, "r", encoding="utf-8") as f:
    org_content = f.read()

# Добавить метод _merge_from_dead_drop
old_publish = '''    def _publish_my_map_to_dht_peers(self):'''

new_method = '''    def _merge_from_dead_drop(self):
        """P116: merge карт через dead_drop (fallback при NAT)."""
        added_total = 0
        try:
            if not getattr(self.net, "dead_drop", None):
                return 0
            inbox = self.net.dead_drop.get_inbox() or []
            for msg in inbox[-100:]:
                receiver = msg.get("receiver", "")
                if receiver not in ("broadcast", self.net.node_id, ""):
                    continue
                payload = msg.get("message", "")
                if not payload:
                    continue
                try:
                    import json as _j
                    data = _j.loads(payload)
                except Exception:
                    continue
                sender = data.get("node_id", "")
                if not sender or sender == self.net.node_id:
                    continue
                nodes_in = data.get("nodes", []) or []
                for item in nodes_in:
                    if not isinstance(item, dict):
                        continue
                    ip = item.get("ip", "")
                    if not ip:
                        continue
                    with self._lock:
                        if ip in self.memory["nodes"]:
                            continue
                        node = dict(item)
                        node["via_dead_drop"] = sender
                        node["source"] = "merge_dd:" + str(node.get("source", "?"))
                        node["depth"] = int(node.get("depth", 1)) + 1
                        self.memory["nodes"][ip] = node
                        added_total += 1
                # Merge relayed/taught
                for r in data.get("relayed", []) or []:
                    self.memory.setdefault("relayed_ips", set()).add(r)
                for t in data.get("taught", []) or []:
                    self.memory.setdefault("taught", set()).add(t)
                if added_total > 0:
                    logger.info("[Merge/DD] from %s: +%d nodes", sender, added_total)
        except Exception as e:
            logger.debug("[Merge/DD] %s", e)
        if added_total > 0:
            with self._lock:
                self.stats["maps_merged"] = self.stats.get("maps_merged", 0) + 1
                self.stats["nodes_from_merge"] = self.stats.get("nodes_from_merge", 0) + added_total
        return added_total

    def _publish_map_to_dead_drop(self):
        """P116: публикуем свою карту в dead_drop (broadcast)."""
        try:
            if not getattr(self.net, "dead_drop", None):
                return False
            my_map = self._build_my_map_summary()
            import json as _j
            self.net.dead_drop.queue_send("broadcast", _j.dumps(my_map, ensure_ascii=False))
            return True
        except Exception as e:
            logger.debug("[Publish/DD] %s", e)
            return False

    def _publish_my_map_to_dht_peers(self):'''

if old_publish in org_content:
    org_content = org_content.replace(old_publish, new_method, 1)
    print("  [OK] _merge_from_dead_drop + _publish_map_to_dead_drop")
else:
    print("  [--] already applied")

# В merge_phase — вызвать оба
old_merge = '''    def merge_phase(self):
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

new_merge = '''    def merge_phase(self):
        """P116: фаза merge - DHT + dead_drop."""
        # P116: публикуем карту в dead_drop
        try:
            self._publish_map_to_dead_drop()
        except Exception as e:
            logger.debug("[P116] publish DD: %s", e)
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
            logger.debug("[Merge] DHT: %s", e)
        # P116: dead_drop merge (fallback при NAT)
        try:
            n = self._merge_from_dead_drop()
            if n > 0:
                logger.info("[P116] merged +%d nodes from dead_drop", n)
        except Exception as e:
            logger.debug("[Merge] DD: %s", e)'''

if old_merge in org_content:
    org_content = org_content.replace(old_merge, new_merge, 1)
    print("  [OK] merge_phase: + dead_drop")
else:
    print("  [--] merge_phase уже обновлён")

with open(ORG, "w", encoding="utf-8") as f:
    f.write(org_content)
try:
    ast.parse(org_content)
    print("  [OK] syntax organism.py")
except SyntaxError as e:
    print("  [!!] syntax: " + str(e))


# =====================================================================
# 4. app.py — endpoints: DHT merge + trust + QR + auth
# =====================================================================

print()
print("=" * 70)
print("  4. app.py: endpoints")
print("=" * 70)

with open(APP, "r", encoding="utf-8") as f:
    app_content = f.read()

anchor = "@app.route('/api/network/public')"

endpoints = '''@app.route('/api/dht/merge', methods=['POST'])
def api_dht_merge():
    """P116: принять чужую карту от DHT-peer / dead_drop."""
    try:
        n = get_net()
        d = request.get_json(silent=True) or {}
        sender = d.get("node_id", "")
        if not sender or sender == n.node_id:
            return jsonify({"success": False, "error": "same_node"}), 400
        nodes_in = d.get("nodes", []) or []
        added = 0
        if getattr(n, "organism", None):
            org = n.organism
            with org._lock:
                for item in nodes_in:
                    if not isinstance(item, dict):
                        continue
                    ip = item.get("ip", "")
                    if not ip or ip in org.memory["nodes"]:
                        continue
                    node = dict(item)
                    node["via_dht_peer"] = sender
                    node["source"] = "merge_dht:" + str(node.get("source", "?"))
                    node["depth"] = int(node.get("depth", 1)) + 1
                    org.memory["nodes"][ip] = node
                    added += 1
                for r in d.get("relayed", []) or []:
                    org.memory.setdefault("relayed_ips", set()).add(r)
                for t in d.get("taught", []) or []:
                    org.memory.setdefault("taught", set()).add(t)
                if added > 0:
                    org.stats["maps_merged"] = org.stats.get("maps_merged", 0) + 1
                    org.stats["nodes_from_merge"] = org.stats.get("nodes_from_merge", 0) + added
        try:
            if getattr(n, "audit", None):
                n.audit.add_event("dht_merge", {"sender": sender, "added": added})
        except Exception:
            pass
        return jsonify({"success": True, "sender": sender, "added": added})
    except Exception as e:
        log.error("[DHT] merge: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/dht/my_info')
def api_dht_my_info():
    """P116: полная информация о себе."""
    try:
        n = get_net()
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
        return jsonify({"success": True, "info": info, "json": json.dumps(info, ensure_ascii=False)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/dht/bootstrap', methods=['POST'])
def api_dht_bootstrap():
    """P116: добавить peer через JSON + зарегистрировать в dead_drop."""
    try:
        n = get_net()
        d = request.get_json(silent=True) or {}
        peer_json = d.get("json", "")
        peer_dict = d.get("peer", {})
        if not getattr(n, "dht_bootstrap", None):
            return jsonify({"success": False, "error": "no_dht"})
        added = False
        parsed = {}
        if peer_json:
            # Парсим строку
            try:
                parsed = json.loads(peer_json)
            except Exception:
                parsed = {}
            added = n.dht_bootstrap.add_peer_json(peer_json)
        elif peer_dict:
            parsed = peer_dict
            added = n.dht_bootstrap.add_peer_dict(peer_dict)
        # P116: регистрируем в dead_drop
        if parsed:
            node_id = parsed.get("node_id", "")
            dd_url = parsed.get("dead_drop_url", "")
            if node_id and dd_url and getattr(n, "dead_drop", None):
                try:
                    n.dead_drop.register_peer(node_id, dd_url)
                    log.info("[P116] registered in dead_drop: %s -> %s", node_id, dd_url[:50])
                except Exception as _e:
                    log.debug("[P116] register: %s", _e)
            # P116: добавляем в trusted_hosts
            pub_ip = parsed.get("public_ip", "")
            pub_port = parsed.get("public_port", 0)
            if node_id and pub_ip and pub_port:
                try:
                    n.trusted_hosts.add("%s:%d" % (pub_ip, int(pub_port)),
                                        label=node_id, method="dht")
                except Exception:
                    pass
        return jsonify({
            "success": True,
            "added": added,
            "peers": n.dht_bootstrap.get_peers_count(),
        })
    except Exception as e:
        log.error("[DHT] bootstrap: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/dht/peers')
def api_dht_peers():
    """P116: список DHT peers."""
    try:
        n = get_net()
        if not getattr(n, "dht_bootstrap", None):
            return jsonify({"success": True, "peers": [], "count": 0})
        return jsonify({
            "success": True,
            "peers": n.dht_bootstrap.get_peers(),
            "count": n.dht_bootstrap.get_peers_count(),
            "stats": n.dht_bootstrap.get_stats(),
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/trust/qr', methods=['POST'])
def api_trust_qr():
    """P116: добавить доверенного через QR-JSON."""
    try:
        n = get_net()
        d = request.get_json(silent=True) or {}
        peer = d.get("peer", {}) or d
        node_id = peer.get("node_id", "")
        if not node_id:
            return jsonify({"success": False, "error": "no_node_id"}), 400
        added = False
        host = ""
        if peer.get("public_ip") and peer.get("public_port"):
            host = "%s:%d" % (peer["public_ip"], int(peer["public_port"]))
        if host:
            try:
                added = n.trusted_hosts.add(host, label=node_id, method="qr")
            except Exception:
                pass
        if getattr(n, "dht_bootstrap", None):
            try:
                n.dht_bootstrap.add_peer_dict(peer)
            except Exception:
                pass
        if peer.get("dead_drop_url") and getattr(n, "dead_drop", None):
            try:
                n.dead_drop.register_peer(node_id, peer["dead_drop_url"])
            except Exception:
                pass
        try:
            if getattr(n, "audit", None):
                n.audit.add_event("trust_qr", {"node_id": node_id, "host": host, "added": added})
        except Exception:
            pass
        return jsonify({"success": True, "added": added, "node_id": node_id, "host": host})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/trust/list')
def api_trust_list():
    try:
        n = get_net()
        hosts = n.trusted_hosts.list_all()
        return jsonify({"success": True, "hosts": hosts, "count": len(hosts)})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/trust/qr_image')
def api_trust_qr_image():
    """P116: QR-код с моим JSON."""
    try:
        n = get_net()
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
            return jsonify({"success": True, "qr_base64": "data:image/png;base64," + b64, "info": info})
        except ImportError:
            return jsonify({"success": False, "error": "qrcode_not_installed", "info": info, "hint": "pip install qrcode[pil]"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/network/public')'''

if "/api/dht/merge" not in app_content:
    app_content = app_content.replace(anchor, endpoints, 1)
    with open(APP, "w", encoding="utf-8") as f:
        f.write(app_content)
    try:
        ast.parse(app_content)
        print("  [OK] app.py: endpoints добавлены")
    except SyntaxError as e:
        print("  [!!] syntax: " + str(e))
else:
    print("  [--] endpoints уже есть")


# =====================================================================
# 5. index.html — auth + QR + DHT-вкладка (если ещё нет)
# =====================================================================

print()
print("=" * 70)
print("  5. index.html: auth + QR")
print("=" * 70)

with open(HTML, "r", encoding="utf-8") as f:
    h = f.read()

# Добавить checkAuth с Enter (если нет)
if "P113: кнопки Enter" not in h:
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

// P116: кнопки Enter в auth-полях
document.addEventListener('keydown', (e) => {
  if (!state.currentUser && e.key === 'Enter') {
    const loginForm = document.getElementById('authLogin');
    const regForm = document.getElementById('authRegister');
    if (loginForm && loginForm.classList.contains('active')) {
      doLogin();
    } else if (regForm && regForm.classList.contains('active')) {
      doRegister();
    }
  }
});'''

    if old_check in h:
        h = h.replace(old_check, new_check, 1)
        print("  [OK] checkAuth + Enter")

# Добавить showMyQr (если нет)
if "showMyQr" not in h:
    old_dom = "document.addEventListener('DOMContentLoaded', init);"
    new_js = '''
// === P116: QR ===
async function showMyQr() {
  try {
    const r = await fetch('/api/trust/qr_image');
    const d = await r.json();
    if (d.success && d.qr_base64) {
      const img = $('qrTrustImage');
      if (img) {
        img.src = d.qr_base64;
        img.style.display = 'block';
      }
      const ph = $('qrTrustPlaceholder');
      if (ph) ph.style.display = 'none';
      addLog('QR готов', 'success');
    } else {
      addLog('QR: ' + (d.error || d.hint || '?'), 'warn');
    }
  } catch (e) {
    addLog('QR ошибка: ' + e.message, 'error');
  }
}

'''
    h = h.replace(old_dom, new_js + old_dom, 1)
    print("  [OK] showMyQr")

with open(HTML, "w", encoding="utf-8") as f:
    f.write(h)
print("  [OK] index.html обновлён")


# =====================================================================
# 6. orchestrator.py — DeadDrop с serial
# =====================================================================

print()
print("=" * 70)
print("  6. orchestrator.py: DeadDrop с serial")
print("=" * 70)

ORCH = os.path.join(INEV, "orchestrator.py")
with open(ORCH, "r", encoding="utf-8") as f:
    orch_content = f.read()

old_dd_init = '''            from .network.dead_drop import DeadDrop
            self.dead_drop = DeadDrop(node_id=self.node_id, poll_interval=60)'''

new_dd_init = '''            from .network.dead_drop import DeadDrop
            self.dead_drop = DeadDrop(
                node_id=self.node_id,
                poll_interval=60,
                serial=getattr(self, "serial", ""),
            )'''

if old_dd_init in orch_content:
    orch_content = orch_content.replace(old_dd_init, new_dd_init, 1)
    with open(ORCH, "w", encoding="utf-8") as f:
        f.write(orch_content)
    try:
        ast.parse(orch_content)
        print("  [OK] DeadDrop с serial")
    except SyntaxError as e:
        print("  [!!] syntax: " + str(e))
else:
    print("  [--] DeadDrop уже с serial")


# =====================================================================
# 7. LICENSE + .gitignore
# =====================================================================

print()
print("=" * 70)
print("  7. LICENSE + .gitignore")
print("=" * 70)

license_path = os.path.join(ROOT, "LICENSE")
if not os.path.exists(license_path):
    with open(license_path, "w", encoding="utf-8") as f:
        f.write("InevioNet - Dual Licensing\nCopyright (c) 2026 dimon027081\n\n1) AGPL-3.0-or-later\n2) InevioNet Commercial License\n\nSPDX-License-Identifier: AGPL-3.0-or-later OR LicenseRef-InevioNet-Commercial-1.0\n")
    print("  [OK] LICENSE")

gi_path = os.path.join(ROOT, ".gitignore")
if not os.path.exists(gi_path):
    with open(gi_path, "w", encoding="utf-8") as f:
        f.write("__pycache__/\n*.py[cod]\nbuild/\ndist/\nvenv/\n.venv/\ndata/\nlogs/\n*.log\n*.bak*\n*.key\n*.pem\n_backup_*/\n_transfer/\ninstaller_output/\npatch*.py\nfix_*.py\n")
    print("  [OK] .gitignore")


print()
print("=" * 70)
print("  PATCH 116 DONE")
print("=" * 70)
print("  [OK] serial per-port (8080/8081 — разные)")
print("  [OK] dead_drop: feed с serial + DeadDrop.serial")
print("  [OK] organism: merge через dead_drop (fallback NAT)")
print("  [OK] app.py: /api/dht/merge + /bootstrap + /trust/*")
print("  [OK] index.html: checkAuth + showMyQr")
print("  [OK] LICENSE + .gitignore")
print()
print("Перезапуск: python -m web.app")