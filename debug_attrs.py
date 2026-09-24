# debug_attrs.py - добавить /api/debug/attrs
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
APP = os.path.join(ROOT, "web", "app.py")
BAK = ".bak_debug_attrs"


def patch_file(path, replacements, label, bak=BAK):
    if not os.path.exists(path):
        print("  [!!] NOT FOUND: " + path)
        return False
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    b = path + bak
    shutil.copy2(path, b)
    print("  [BK] " + os.path.basename(b))
    changed = 0
    for old, new, required in replacements:
        if new and new in content and (not old or old not in content):
            print("  [--] already applied")
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


anchor = "@app.route('/api/network/public')"

new_ep = '''@app.route('/api/debug/attrs')
def api_debug_attrs():
    """debug: все атрибуты net (stego/industrial/webrtc/mask)."""
    try:
        n = get_net()
        out = {"public": {}, "hidden": {}}
        # Публичные
        for a in dir(n):
            if a.startswith('_'):
                continue
            if any(k in a.lower() for k in ('stego', 'stegan', 'mask', 'industrial',
                                              'webrtc', 'bridge', 'modbus', 'mqtt',
                                              'opcua', 'dnp3', 'scada', 'ambient')):
                try:
                    v = getattr(n, a, None)
                    if callable(v):
                        out["public"][a] = "callable"
                    elif v is None:
                        out["public"][a] = None
                    else:
                        out["public"][a] = type(v).__name__
                except Exception as e:
                    out["public"][a] = "err: %s" % e
        # Скрытые
        for a in dir(n):
            if not a.startswith('_'):
                continue
            if any(k in a.lower() for k in ('stego', 'mask', 'ambient',
                                              'industrial', 'webrtc')):
                try:
                    v = getattr(n, a, None)
                    if callable(v):
                        out["hidden"][a] = "callable"
                    elif v is None:
                        out["hidden"][a] = None
                    else:
                        out["hidden"][a] = type(v).__name__
                except Exception:
                    pass
        return jsonify({"success": True, **out})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/network/public')'''

patch_file(APP, [(anchor, new_ep, True)], "app.py /api/debug/attrs")

print()
print("Перезапуск + curl /api/debug/attrs")