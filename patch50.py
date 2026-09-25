# patch50.py - InevioNet: skip self in growth trusted
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
ORCH = os.path.join(ROOT, "inevionet", "orchestrator.py")


def backup(path):
    if os.path.exists(path):
        b = path + ".bak_p50"
        shutil.copy2(path, b)
        print(f"  [BK] {os.path.basename(b)}")


print()
print("=" * 70)
print("  P50: skip self in growth trusted")
print("=" * 70)
backup(ORCH)

with open(ORCH, "r", encoding="utf-8") as f:
    content = f.read()

# Add self-check before trusted+ in _growth_loop
old = '''                                        # P48b: auto-update trusted with actual node_id
                                        try:
                                            their_id = (r.get('data') or {}).get('node_id', '')
                                            if their_id and r.get('ip'):
                                                self.trusted_hosts.add(
                                                    f"{r['ip']}:{r['port']}",
                                                    label=their_id,
                                                    method='auto-discovered')
                                                logger.info(
                                                    '[Growth] trusted+ %s:%d (%s)',
                                                    r['ip'], r['port'], their_id)
                                        except Exception as _te:
                                            logger.debug('[Growth] trusted+ error: %s', _te)'''

new = '''                                        # P50: skip self before adding to trusted
                                        _their_id = (r.get('data') or {}).get('node_id', '')
                                        if _their_id == self.node_id:
                                            logger.debug(
                                                '[Growth] skip self %s (port %d)',
                                                _their_id, r.get('port', 0))
                                        else:
                                            # P48b: auto-update trusted with actual node_id
                                            try:
                                                if _their_id and r.get('ip'):
                                                    self.trusted_hosts.add(
                                                        f"{r['ip']}:{r['port']}",
                                                        label=_their_id,
                                                        method='auto-discovered')
                                                    logger.info(
                                                        '[Growth] trusted+ %s:%d (%s)',
                                                        r['ip'], r['port'], _their_id)
                                            except Exception as _te:
                                                logger.debug('[Growth] trusted+ error: %s', _te)'''

if old in content:
    content = content.replace(old, new, 1)
    print("  [OK] skip self in trusted+")
elif 'P50: skip self before adding' in content:
    print("  [--] already applied")
else:
    print("  [!!] NOT FOUND")

# Also add self-check in _probe_one_host (web/app.py)
APP = os.path.join(ROOT, "web", "app.py")
backup(APP)
with open(APP, "r", encoding="utf-8") as f:
    app = f.read()

old_app = '''            # P45: skip if it's our own node_id
            their_id = data.get('node_id', '')
            if their_id and their_id == from_node:
                continue  # try next port'''

new_app = '''            # P45/P50: skip if it's our own node_id
            their_id = data.get('node_id', '')
            if their_id and their_id == from_node:
                continue  # try next port
            if not their_id:
                # P50: no node_id in response -> skip
                continue'''

if old_app in app:
    app = app.replace(old_app, new_app, 1)
    try:
        ast.parse(app)
        with open(APP, "w", encoding="utf-8") as f:
            f.write(app)
        print("  [OK] _probe_one_host: skip empty node_id")
    except SyntaxError as e:
        print(f"  [!!] syntax error: {e}")
        shutil.copy2(APP + ".bak_p50", APP)
elif 'P50: no node_id in response' in app:
    print("  [--] already applied")
else:
    print("  [!!] NOT FOUND in app.py")

print()
print("=" * 70)
print("  PATCH 50 DONE")
print("=" * 70)
print()
print("Перезапусти ОБА сервера:")
print("  python -m web.app")
print("  $env:INEVIO_PORT=8081; python -m web.app")
print()
print("Проверка: в логах НЕ должно быть 'trusted+ 127.0.0.1:8080 (web_node_8192)'")