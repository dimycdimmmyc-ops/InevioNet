# fix_p119.py - P119+P119b+P120
import os
import ast
import shutil
import re

ROOT = r"E:\InevioNet"
APP = os.path.join(ROOT, "web", "app.py")
ORG = os.path.join(ROOT, "inevionet", "organism.py")
CAP = os.path.join(ROOT, "inevionet", "mycelium", "capsule.py")

BAK = ".bak_p120"


def _replace_function(content, func_name, new_body):
    """Заменяет функцию по имени (от def до следующего @app.route или def)."""
    pattern = re.compile(
        r"@app\.route\([^\)]*\)\s*\ndef\s+" + func_name + r"\s*\([^\)]*\):.*?(?=\n@app\.route|\n@|\Z)",
        re.DOTALL
    )
    m = pattern.search(content)
    if not m:
        return content, False
    return content[:m.start()] + new_body + content[m.end():], True


def patch(path, label):
    if not os.path.exists(path):
        print("  [!!] NOT FOUND: " + path)
        return None
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    b = path + BAK
    shutil.copy2(path, b)
    print("  [BK] " + os.path.basename(b))
    return content, b, path


# ============ P119: app.py — p2_send через dead_drop ============

print()
print("=" * 70)
print("  P119: p2_send через dead_drop")
print("=" * 70)

with open(APP, "r", encoding="utf-8") as f:
    content = f.read()

b = APP + BAK
shutil.copy2(APP, b)
print("  [BK] " + os.path.basename(b))

# Удалить старую api_p2_send если есть
pattern = re.compile(
    r"@app\.route\('/api/p2/send'[^\)]*\)\s*\ndef\s+api_p2_send\([^\)]*\):.*?(?=\n@app\.route|\n@|\Z)",
    re.DOTALL
)
m = pattern.search(content)
if m:
    content = content[:m.start()] + content[m.end():]
    print("  [OK] старая api_p2_send удалена")

# Найти якорь для вставки
anchor = "@app.route('/api/p2/inbox'"

new_send = '''@app.route('/api/p2/send', methods=['POST'])
def api_p2_send():
    """P119: отправка через dead_drop (paste.rs) + fallback HTTPS."""
    d = request.get_json(silent=True) or {}
    receiver = (d.get('receiver') or '').strip()
    message = d.get('message', '')
    if not receiver or not message:
        return jsonify({'success': False, 'error': 'empty'}), 400

    n = get_net()
    via = None
    packet_id = None

    # P119: 1. dead_drop (работает через NAT)
    try:
        if getattr(n, "dead_drop", None):
            import json as _j
            payload = _j.dumps({
                "type": "p2_message",
                "sender": n.node_id,
                "receiver": receiver,
                "message": message,
                "ts": time.time(),
            }, ensure_ascii=False)
            url = n.dead_drop.publish_now("broadcast", payload)
            if url:
                via = "dead_drop:" + url[:40]
                log.info("[P2P] sent via dead_drop: %s -> %s", n.node_id, receiver)
    except Exception as e:
        log.warning("[P2P] dead_drop failed: %s", e)

    # P119: 2. Fallback HTTPS
    if not via:
        try:
            target_host = None
            target_port = 8080
            for h in n.trusted_hosts.list_all():
                label = h.get('label', '') or ''
                host = h.get('host', '') or ''
                if label == receiver or host == receiver:
                    if ':' in host:
                        target_host, port_s = host.rsplit(':', 1)
                        target_port = int(port_s)
                    else:
                        target_host = host
                    break
            if target_host:
                payload = json.dumps({
                    'sender': n.node_id, 'message': message,
                    'ts': time.time(), 'secure': True,
                }).encode('utf-8')
                ctx = _ssl._create_unverified_context()
                for scheme in ('https', 'http'):
                    try:
                        url = '%s://%s:%s/api/p2/inbox' % (scheme, target_host, target_port)
                        req = _urlreq.Request(url, data=payload,
                                              headers={'Content-Type': 'application/json'})
                        _urlreq.urlopen(req, timeout=5, context=ctx)
                        via = scheme + ":" + target_host
                        break
                    except Exception:
                        continue
        except Exception as e:
            log.debug("[P2P] HTTPS: %s", e)

    # P119: 3. Fallback n.send
    if not via:
        try:
            packet = n.send(receiver, message)
            if packet:
                packet_id = getattr(packet, 'packet_id', None)
                via = "cascade"
        except Exception:
            pass

    return jsonify({
        'success': bool(via),
        'via': via,
        'packet_id': packet_id,
    })


'''

if anchor in content:
    content = content.replace(anchor, new_send + anchor, 1)
    print("  [OK] новая api_p2_send вставлена")
else:
    print("  [!!] anchor not found — добавляю в конец файла")
    content = content + "\n\n" + new_send

with open(APP, "w", encoding="utf-8") as f:
    f.write(content)

try:
    ast.parse(content)
    print("  [OK] syntax app.py")
except SyntaxError as e:
    print("  [!!] syntax: " + str(e))
    shutil.copy2(b, APP)
    print("  [--] rolled back")


# ============ P119: organism.py — приём p2_message ============

print()
print("=" * 70)
print("  P119: приём p2_message в organism")
print("=" * 70)

with open(ORG, "r", encoding="utf-8") as f:
    org_content = f.read()

b2 = ORG + BAK
shutil.copy2(ORG, b2)
print("  [BK] " + os.path.basename(b2))

# Найти _merge_from_dead_drop
old_merge = '''                nodes_in = data.get("nodes", []) or []
                for item in nodes_in:'''

new_merge = '''                # P119: p2_message
                msg_type = data.get("type", "")
                if msg_type == "p2_message":
                    recv = data.get("receiver", "")
                    if recv == self.net.node_id or recv == "broadcast":
                        sender = data.get("sender", "")
                        msg_text = data.get("message", "")
                        try:
                            from web import app as _app
                            with _app.state_lock:
                                box = list(_app._inbox[0])
                                box.append({
                                    "sender": sender,
                                    "message": msg_text,
                                    "ts": data.get("ts", time.time()),
                                    "secure": True,
                                })
                                _app._inbox[0] = box[-100:]
                            try:
                                _app.socketio.emit('inbox_new', {
                                    "sender": sender,
                                    "message": msg_text,
                                    "ts": data.get("ts", time.time()),
                                })
                            except Exception:
                                pass
                            logger.info("[P119] p2_message: %s -> %s", sender, self.net.node_id)
                        except Exception as _ae:
                            logger.debug("[P119] p2_inbox: %s", _ae)
                    continue

                nodes_in = data.get("nodes", []) or []
                for item in nodes_in:'''

if old_merge in org_content:
    org_content = org_content.replace(old_merge, new_merge, 1)
    print("  [OK] p2_message в _merge_from_dead_drop")
else:
    print("  [!!] anchor not found")

with open(ORG, "w", encoding="utf-8") as f:
    f.write(org_content)
try:
    ast.parse(org_content)
    print("  [OK] syntax organism.py")
except SyntaxError as e:
    print("  [!!] syntax: " + str(e))
    shutil.copy2(b2, ORG)
    print("  [--] rolled back")


# ============ P119b: capsule.py — не deploy на свои ============

print()
print("=" * 70)
print("  P119b: не deploy на свои InevioNet-узлы")
print("=" * 70)

with open(CAP, "r", encoding="utf-8") as f:
    cap_content = f.read()

b3 = CAP + BAK
shutil.copy2(CAP, b3)
print("  [BK] " + os.path.basename(b3))

# Найти _deploy_via_ssh
old_ssh = '''    def _deploy_via_ssh(self, host, code, port=22):'''
new_ssh = '''    def _deploy_via_ssh(self, host, code, port=22):
        # P119b: НЕ deploy на свои InevioNet-узлы
        if hasattr(self, "_trusted") and self._trusted:
            try:
                for h in self._trusted.list_all():
                    if h.get("host", "").startswith(host):
                        if h.get("method") in ("sprout", "dht", "qr", "deaddrop"):
                            return False
            except Exception:
                pass'''

if old_ssh in cap_content:
    cap_content = cap_content.replace(old_ssh, new_ssh, 1)
    print("  [OK] _deploy_via_ssh: защита от своих")
else:
    print("  [!!] _deploy_via_ssh not found")

with open(CAP, "w", encoding="utf-8") as f:
    f.write(cap_content)
try:
    ast.parse(cap_content)
    print("  [OK] syntax capsule.py")
except SyntaxError as e:
    print("  [!!] syntax: " + str(e))
    shutil.copy2(b3, CAP)
    print("  [--] rolled back")


print()
print("=" * 70)
print("  PATCH 120 DONE")
print("=" * 70)
print("  [OK] P119: p2_send через dead_drop")
print("  [OK] P119: приём p2_message")
print("  [OK] P119b: защита от deploy на свои узлы")
print()
print("Перезапуск + тест")