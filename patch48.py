# patch48.py - InevioNet: persistent node_id + auto-trusted update
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
APP = os.path.join(ROOT, "web", "app.py")
ORCH = os.path.join(ROOT, "inevionet", "orchestrator.py")


def backup(path):
    if os.path.exists(path):
        b = path + ".bak_p48"
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
        if os.path.exists(path + ".bak_p48"):
            shutil.copy2(path + ".bak_p48", path)


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
# P48a: persistent node_id (per-port)
# ============================================================
patch(APP, [
    (
        """            net = InevioNet(
                password='inevio_forever',
                node_id='web_node_%d' % random.randint(1000, 9999),
                auto_start=True,
            )""",
        """            # P48: persistent node_id (per-port)
            import pathlib as _pl
            _port = os.environ.get('INEVIO_PORT', '8080')
            _nid_file = _pl.Path(BASE_DIR) / 'data' / ('node_id_%s.txt' % _port)
            if _nid_file.exists():
                _node_id = _nid_file.read_text(encoding='utf-8').strip()
                log.info('[Node] persistent node_id=%s (port %s)', _node_id, _port)
            else:
                _node_id = 'web_node_%d' % random.randint(1000, 9999)
                _nid_file.parent.mkdir(parents=True, exist_ok=True)
                _nid_file.write_text(_node_id, encoding='utf-8')
                log.info('[Node] created new node_id=%s (port %s)', _node_id, _port)

            net = InevioNet(
                password='inevio_forever',
                node_id=_node_id,
                auto_start=True,
            )""",
        True,
    ),
], "P48a: persistent node_id")


# ============================================================
# P48b: auto-trusted update in _growth_loop
# ============================================================
patch(ORCH, [
    (
        """                                    if r.get('success'):
                                        sent += 1
                                        other_map = (r.get('data') or {}).get('our_map') or {}
                                        if other_map:
                                            m = topo.merge(other_map)
                                            total_added_n += m.get('added_nodes', 0)
                                            total_added_e += m.get('added_edges', 0)
                                        logger.info(
                                            '[Growth] FOUND %s (%s:%d)',
                                            r['ip'], r['scheme'], r['port'])""",
        """                                    if r.get('success'):
                                        sent += 1
                                        other_map = (r.get('data') or {}).get('our_map') or {}
                                        if other_map:
                                            m = topo.merge(other_map)
                                            total_added_n += m.get('added_nodes', 0)
                                            total_added_e += m.get('added_edges', 0)
                                        logger.info(
                                            '[Growth] FOUND %s (%s:%d)',
                                            r['ip'], r['scheme'], r['port'])
                                        # P48b: auto-update trusted with actual node_id
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
                                            logger.debug('[Growth] trusted+ error: %s', _te)""",
        True,
    ),
], "P48b: auto-trusted update")


print()
print("=" * 70)
print("  PATCH 48 DONE")
print("=" * 70)
print()
print("  [OK] persistent node_id (per-port: node_id_8080.txt, node_id_8081.txt)")
print("  [OK] auto-trusted update in _growth_loop")
print()
print("Перезапусти ОБА сервера:")
print("  python -m web.app")
print("  $env:INEVIO_PORT=8081; python -m web.app")