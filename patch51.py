# patch51.py - InevioNet: unify user.node_id with net.node_id
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
APP = os.path.join(ROOT, "web", "app.py")


def backup(path):
    if os.path.exists(path):
        b = path + ".bak_p51"
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
        if os.path.exists(path + ".bak_p51"):
            shutil.copy2(path + ".bak_p51", path)


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


# P51a: api_register — sync with net
patch(APP, [
    (
        """@app.route('/api/register', methods=['POST'])
def api_register():
    d = request.json or {}
    try:
        u = get_user_manager().register(d.get('username', '').strip(), d.get('password', ''))
        return jsonify({'success': True, 'user': u.to_dict(), 'node_id': u.node_id})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400""",
        """@app.route('/api/register', methods=['POST'])
def api_register():
    d = request.json or {}
    try:
        u = get_user_manager().register(d.get('username', '').strip(), d.get('password', ''))
        # P51: sync user.node_id with net.node_id
        try:
            n = get_net()
            if u.node_id != n.node_id:
                u.node_id = n.node_id
                get_user_manager()._save()
                log.info('[User] synced %s.node_id -> %s', u.username, n.node_id)
        except Exception as _se:
            log.debug('[User] sync error: %s', _se)
        return jsonify({'success': True, 'user': u.to_dict(), 'node_id': u.node_id})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400""",
        True,
    ),
    # P51b: api_login — sync with net
    (
        """@app.route('/api/login', methods=['POST'])
def api_login():
    d = request.json or {}
    try:
        u = get_user_manager().login(d.get('username', '').strip(), d.get('password', ''))
        return jsonify({'success': True, 'user': u.to_dict(), 'node_id': u.node_id})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 401""",
        """@app.route('/api/login', methods=['POST'])
def api_login():
    d = request.json or {}
    try:
        u = get_user_manager().login(d.get('username', '').strip(), d.get('password', ''))
        # P51: sync user.node_id with net.node_id
        try:
            n = get_net()
            if u.node_id != n.node_id:
                u.node_id = n.node_id
                get_user_manager()._save()
                log.info('[User] synced %s.node_id -> %s', u.username, n.node_id)
        except Exception as _se:
            log.debug('[User] sync error: %s', _se)
        return jsonify({'success': True, 'user': u.to_dict(), 'node_id': u.node_id})
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 401""",
        True,
    ),
    # P51c: api_me — always sync
    (
        """@app.route('/api/me')
def api_me():
    try:
        u = get_user_manager().get_current_user()
        if not u:
            return jsonify({'success': False, 'error': 'not_logged_in'}), 401
        return jsonify({
            'success': True,
            'user': u.to_dict(),
            'contacts': get_user_manager().get_contacts(),
        })
    except Exception:
        return jsonify({'success': False, 'error': 'no_user_manager'}), 401""",
        """@app.route('/api/me')
def api_me():
    try:
        u = get_user_manager().get_current_user()
        if not u:
            return jsonify({'success': False, 'error': 'not_logged_in'}), 401
        # P51: always sync user.node_id with net.node_id
        try:
            n = get_net()
            if u.node_id != n.node_id:
                u.node_id = n.node_id
                get_user_manager()._save()
        except Exception:
            pass
        return jsonify({
            'success': True,
            'user': u.to_dict(),
            'contacts': get_user_manager().get_contacts(),
        })
    except Exception:
        return jsonify({'success': False, 'error': 'no_user_manager'}), 401""",
        True,
    ),
], "P51: unify user.node_id with net.node_id")


print()
print("=" * 70)
print("  PATCH 51 DONE")
print("=" * 70)
print()
print("  [OK] api_register: sync user.node_id <- net.node_id")
print("  [OK] api_login: sync user.node_id <- net.node_id")
print("  [OK] api_me: always sync")
print()
print("Перезапусти ОБА сервера:")
print("  python -m web.app")
print("  $env:INEVIO_PORT=8081; python -m web.app")
print()
print("Потом: выйди из UI (Logout) и зайди заново — node_id обновится.")