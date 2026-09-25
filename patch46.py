# patch46.py - InevioNet: P2P messaging through trusted_hosts
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
ORCH = os.path.join(ROOT, "inevionet", "orchestrator.py")
APP = os.path.join(ROOT, "web", "app.py")


def backup(path):
    if os.path.exists(path):
        b = path + ".bak_p46"
        shutil.copy2(path, b)
        print(f"  [BK] {os.path.basename(b)}")


def save_py(path, code):
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    try:
        ast.parse(code)
        print(f"  [OK] syntax: {os.path.basename(path)}")
    except SyntaxError as e:
        print(f"  [!!] syntax error: {e}")
        if os.path.exists(path + ".bak_p46"):
            shutil.copy2(path + ".bak_p46", path)


def patch(path, replacements, name):
    print()
    print("=" * 70)
    print(f"  {name}")
    print("=" * 70)
    backup(path)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    changed = 0
    for old, new, required in replacements:
        if new in content and old not in content:
            print(f"  [--] already applied")
            continue
        if old in content:
            content = content.replace(old, new, 1)
            print(f"  [OK] {old[:60].strip()}...")
            changed += 1
        else:
            if required:
                print(f"  [!!] NOT FOUND: {old[:60].strip()}...")
    if changed > 0:
        save_py(path, content)


# ============================================================
# P46a. orchestrator.py: _resolve_target -> trusted_hosts
# ============================================================
patch(ORCH, [
    (
        '''        # discovery
        try:
            if self._discovery is not None:
                for ann in self._discovery.get_discovered():
                    if ann.device_id == r and ann.endpoint:
                        return ann.endpoint
        except Exception:
            pass''',
        '''        # P46: lookup in trusted_hosts (by label=node_id or host)
        try:
            for h in self.trusted_hosts.list_all():
                label = h.get('label', '') or ''
                host = h.get('host', '') or ''
                if (label == r or host == r
                        or (label and label.startswith(r))
                        or (host and host.startswith(r))):
                    if ':' in host and not host.startswith('http'):
                        return "https://" + host
                    elif host.startswith('http'):
                        return host
                    else:
                        return "https://" + host + ":8080"
        except Exception:
            pass
        # discovery
        try:
            if self._discovery is not None:
                for ann in self._discovery.get_discovered():
                    if ann.device_id == r and ann.endpoint:
                        return ann.endpoint
        except Exception:
            pass''',
        True,
    ),
    # P46d: direct HTTP in try_delivery
    (
        '''            try:
                # P12-Fix-12: self — сразу POST /api/relay
                if _is_self:''',
        '''            # P46: direct HTTP to peer (if target is http/https)
            if target and (target.startswith('http://') or target.startswith('https://')):
                try:
                    import urllib.request as _url
                    import ssl as _ssl
                    import json as _json
                    ctx = _ssl._create_unverified_context()
                    msg_data = {
                        'sender': self.node_id,
                        'message': self._decode_payload(packet.payload)
                            if hasattr(self, '_decode_payload')
                            else str(packet.payload),
                        'ts': time.time(),
                        'secure': True,
                    }
                    payload = _json.dumps(msg_data, ensure_ascii=False).encode()
                    url = target.rstrip('/') + '/api/p2/inbox'
                    req = _url.Request(
                        url, data=payload,
                        headers={'Content-Type': 'application/json'},
                        method='POST')
                    with _url.urlopen(req, timeout=5, context=ctx) as resp:
                        if resp.status == 200:
                            logger.info('[P2P] direct HTTP to %s OK', target)
                            if self.evolution:
                                self.evolution.reward('protocol', 'HTTP', True)
                            return True, 0.99
                except Exception as _he:
                    logger.debug('[P2P] direct HTTP: %s', _he)

            try:
                # P12-Fix-12: self — сразу POST /api/relay
                if _is_self:''',
        True,
    ),
], "P46a/d: _resolve_target + direct HTTP")


# ============================================================
# P46b. web/app.py: api_p2_send -> trusted_hosts
# ============================================================
patch(APP, [
    (
        '''    n = get_net()
    nodes = snapshot()
    target = None
    for nid, nd in nodes.items():
        if nid == receiver or nd.get('name') == receiver or nid.startswith(receiver):
            target = nd
            break

    delivered_via = None
    if target and target.get('ip') and target['ip'] not in ('127.0.0.1', 'unknown'):''',
        '''    n = get_net()
    nodes = snapshot()

    # P46: first lookup in trusted_hosts (by label=node_id or host)
    target_host = None
    target_port = 8080
    try:
        for h in n.trusted_hosts.list_all():
            label = h.get('label', '') or ''
            host = h.get('host', '') or ''
            if (label == receiver or host == receiver
                    or (label and label.startswith(receiver))
                    or (host and host.startswith(receiver))):
                if ':' in host:
                    parts = host.split(':')
                    target_host = parts[0]
                    try:
                        target_port = int(parts[1])
                    except Exception:
                        target_port = 8080
                else:
                    target_host = host
                    target_port = 8080
                log.info('[P2P] trusted match: %s -> %s:%d',
                         receiver, target_host, target_port)
                break
    except Exception as _te:
        log.debug('[P2P] trusted lookup: %s', _te)

    # Fallback: search in snapshot
    target = None
    if not target_host:
        for nid, nd in nodes.items():
            if nid == receiver or nd.get('name') == receiver or nid.startswith(receiver):
                target = nd
                break
        if target and target.get('ip') and target['ip'] not in ('127.0.0.1', 'unknown'):
            target_host = target['ip']
            target_port = target.get('port', 8080)

    delivered_via = None
    if target_host:''',
        True,
    ),
    # Use target_host in HTTP send
    (
        '''        payload = json.dumps({
            'sender': n.node_id,
            'message': message,
            'ts': time.time(),
            'secure': True,
        }).encode('utf-8')
        ctx = _ssl._create_unverified_context()
        for scheme in ('https', 'http'):
            url = '%s://%s:%s/api/p2/inbox' % (scheme, target['ip'], target.get('port', 8080))''',
        '''        payload = json.dumps({
            'sender': n.node_id,
            'message': message,
            'ts': time.time(),
            'secure': True,
        }).encode('utf-8')
        ctx = _ssl._create_unverified_context()
        for scheme in ('https', 'http'):
            url = '%s://%s:%s/api/p2/inbox' % (scheme, target_host, target_port)''',
        True,
    ),
], "P46b: api_p2_send trusted_hosts")


print()
print("=" * 70)
print("  PATCH 46 DONE — P2P MESSAGING")
print("=" * 70)
print()
print("  [OK] _resolve_target: trusted_hosts lookup")
print("  [OK] send_with_guarantee: direct HTTP to peer")
print("  [OK] api_p2_send: trusted_hosts lookup")
print()
print("Перезапусти ОБА сервера:")
print("  python -m web.app")
print("  $env:INEVIO_PORT=8081; python -m web.app")
print()
print("Тест:")
print("  # PC-A -> PC-B (node_id web_node_XXX из /api/me на 8081)")
print("  curl.exe -k -X POST https://localhost:8080/api/p2/send -H \"Content-Type: application/json\" -d '{\\\"receiver\\\":\\\"web_node_XXX\\\",\\\"message\\\":\\\"hello\\\"}'")
print("  # Проверка inbox на 8081")
print("  curl.exe -k https://localhost:8081/api/p2/inbox")