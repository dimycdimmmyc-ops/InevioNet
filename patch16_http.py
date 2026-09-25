# patch16_http.py - добавить /api/capsule/receive
import os
import ast
import shutil
import sys

ROOT = r"E:\InevioNet"
APP = os.path.join(ROOT, "web", "app.py")
CAPSULE = os.path.join(ROOT, "inevionet", "mycelium", "capsule.py")

# --- 1. Добавить endpoint в web/app.py ---
shutil.copy2(APP, APP + ".bak_http")
with open(APP, "r", encoding="utf-8") as f:
    app = f.read()

if "/api/capsule/receive" in app:
    print("[--] receive endpoint exists")
else:
    endpoint = '''
@app.route('/api/capsule/receive', methods=['POST'])
def api_capsule_receive():
    """P16: receive capsule archive and deploy it."""
    try:
        data = request.get_data()
        if not data:
            return jsonify({'success': False, 'error': 'empty'}), 400

        log.info('[Capsule] received %d bytes', len(data))

        import tarfile
        import io
        import tempfile

        # Save archive
        tmp_dir = tempfile.mkdtemp(prefix='inevionet_capsule_')
        archive_path = os.path.join(tmp_dir, 'capsule.tar.gz')
        with open(archive_path, 'wb') as f:
            f.write(data)

        # Extract
        extract_dir = os.path.join(tmp_dir, 'extracted')
        os.makedirs(extract_dir, exist_ok=True)
        with tarfile.open(archive_path, 'r:gz') as tar:
            tar.extractall(extract_dir)

        # Check structure
        inev_dir = os.path.join(extract_dir, 'inevionet')
        if not os.path.isdir(inev_dir):
            return jsonify({'success': False, 'error': 'bad_archive'}), 400

        # Count files
        py_files = []
        for root, dirs, files in os.walk(inev_dir):
            dirs[:] = [d for d in dirs if d != '__pycache__']
            for f in files:
                if f.endswith('.py'):
                    py_files.append(os.path.join(root, f))

        log.info('[Capsule] extracted: %d py files in %s',
                 len(py_files), extract_dir)

        return jsonify({
            'success': True,
            'bytes': len(data),
            'files': len(py_files),
            'extract_dir': extract_dir,
            'note': 'manual_start_required',
        })
    except Exception as e:
        log.error('[Capsule] receive error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


'''
    marker = "@socketio.on('connect')"
    if marker in app:
        app = app.replace(marker, endpoint + marker, 1)
        with open(APP, "w", encoding="utf-8") as f:
            f.write(app)
        try:
            ast.parse(app)
            print("[OK] receive endpoint added")
        except SyntaxError as e:
            print(f"[!!] syntax error: {e}")
            shutil.copy2(APP + ".bak_http", APP)
            sys.exit(1)
    else:
        print("[!!] socketio marker not found")

# --- 2. Исправить порт в deploy_http ---
shutil.copy2(CAPSULE, CAPSULE + ".bak_http")
with open(CAPSULE, "r", encoding="utf-8") as f:
    cap = f.read()

old_http = '''            url = f"http://{host}:8081/api/capsule/receive"'''
new_http = '''            # P16-http: use https on 8080 (matches web.app)
            import ssl as _ssl
            ctx = _ssl._create_unverified_context()
            url = f"https://{host}:8080/api/capsule/receive"'''

if old_http in cap:
    cap = cap.replace(old_http, new_http)
    print("[OK] port 8081 -> 8080")
else:
    print("[--] port already fixed")

old_req = '''            with urllib.request.urlopen(req, timeout=10) as r:'''
new_req = '''            with urllib.request.urlopen(req, timeout=10, context=ctx) as r:'''

if old_req in cap:
    cap = cap.replace(old_req, new_req)
    print("[OK] ssl context added")

with open(CAPSULE, "w", encoding="utf-8") as f:
    f.write(cap)

try:
    ast.parse(cap)
    print("[OK] capsule.py syntax valid")
except SyntaxError as e:
    print(f"[!!] capsule.py syntax error: {e}")
    shutil.copy2(CAPSULE + ".bak_http", CAPSULE)
    sys.exit(1)

print()
print("=" * 70)
print("  PATCH 16-HTTP DONE")
print("=" * 70)
print()
print("Что изменилось:")
print("  [OK] web/app.py: /api/capsule/receive endpoint")
print("  [OK] capsule.py: deploy_http на https://host:8080")
print()
print("Перезапусти сервер: python -m web.app")