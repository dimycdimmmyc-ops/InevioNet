# patch45b.py - InevioNet: skip self node_id in probe (FIXED)
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
APP = os.path.join(ROOT, "web", "app.py")


def backup(path):
    if os.path.exists(path):
        b = path + ".bak_p45b"
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
        if os.path.exists(path + ".bak_p45b"):
            shutil.copy2(path + ".bak_p45b", path)


print()
print("=" * 70)
print("  P45b: skip self node_id in probe (FIXED)")
print("=" * 70)
backup(APP)

with open(APP, "r", encoding="utf-8") as f:
    content = f.read()

# 1. _probe_one_host: skip if node_id matches from_node
old1 = '''            with _url.urlopen(req, timeout=timeout, context=ctx) as resp:
                data = _json.loads(resp.read().decode('utf-8'))
            return {
                'success': True,
                'ip': ip,
                'url': url,
                'port': port,
                'scheme': scheme,
                'data': data,
            }'''

new1 = '''            with _url.urlopen(req, timeout=timeout, context=ctx) as resp:
                data = _json.loads(resp.read().decode('utf-8'))
            # P45: skip if it's our own node_id
            their_id = data.get('node_id', '')
            if their_id and their_id == from_node:
                continue  # try next port
            return {
                'success': True,
                'ip': ip,
                'url': url,
                'port': port,
                'scheme': scheme,
                'data': data,
            }'''

if old1 in content:
    content = content.replace(old1, new1, 1)
    print("  [OK] _probe_one_host: skip self")
elif 'P45: skip if it' in content:
    print("  [--] already applied")
else:
    print("  [!!] NOT FOUND (1)")

# 2. POST /api/network/map: return node_id
# Find the exact block by searching for the return in api_network_map
old2 = """    return jsonify({
        'success': True,
        'merged': merged,
        'our_map': topo.export_map(),
        'propagated': propagated,
    })"""

new2 = """    return jsonify({
        'success': True,
        'node_id': n.node_id,
        'merged': merged,
        'our_map': topo.export_map(),
        'propagated': propagated,
    })"""

# Check if already applied by looking for both 'node_id': n.node_id AND 'propagated'
if "        'node_id': n.node_id,\n        'merged': merged," in content:
    print("  [--] already applied (2)")
elif old2 in content:
    content = content.replace(old2, new2, 1)
    print("  [OK] POST /api/network/map: node_id")
else:
    print("  [!!] NOT FOUND (2)")

save_py(APP, content)

print()
print("=" * 70)
print("  PATCH 45b DONE")
print("=" * 70)
print()
print("Перезапусти ОБА сервера:")
print("  python -m web.app")
print("  $env:INEVIO_PORT=8081; python -m web.app")
print()
print("Проверка:")
print("  $json = '{\"target\":\"127.0.0.1\",\"max_hops\":5}'")
print("  $json | Out-File -Encoding ASCII -NoNewline \"$env:TEMP\\body.json\"")
print("  curl.exe -k -X POST https://localhost:8080/api/network/depth -H \"Content-Type: application/json\" -d \"@$env:TEMP\\body.json\"")