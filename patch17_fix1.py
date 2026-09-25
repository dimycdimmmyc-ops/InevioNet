# patch17_fix1.py - fix _capsule_received_lock
import os
import ast
import shutil
import sys

APP = r"E:\InevioNet\web\app.py"

shutil.copy2(APP, APP + ".bak_p17f1")
print(f"Backup: {APP}.bak_p17f1")

with open(APP, "r", encoding="utf-8") as f:
    app = f.read()

# Replace buggy globals with proper module-level vars
buggy = '''        # P17: compute hash
        code_hash = hashlib.sha256(data).hexdigest()

        # P17: check if we already received this hash recently
        global _capsule_received
        try:
            _capsule_received
        except NameError:
            _capsule_received = {}
            _capsule_received_lock = __import__('threading').Lock()

        with _capsule_received_lock:'''

fixed = '''        # P17: compute hash
        code_hash = hashlib.sha256(data).hexdigest()

        # P17: check if we already received this hash recently
        with _capsule_received_lock:'''

if buggy in app:
    app = app.replace(buggy, fixed)
    print("[OK] removed buggy global block")
else:
    print("[!!] buggy block not found")

# Add module-level variables (before the first @app.route)
marker = "# P17: capsule receive registry\n"
if marker in app:
    print("[--] module globals already exist")
else:
    # Find first @app.route
    first_route = app.index("@app.route(")
    # Insert BEFORE it (module level)
    module_globals = '''# P17: capsule receive registry
import threading as _threading_mod
_capsule_received: dict = {}
_capsule_received_lock = _threading_mod.Lock()


'''
    app = app[:first_route] + module_globals + app[first_route:]
    print("[OK] module globals added")

# Also fix the registry endpoint to use module-level vars (remove local try)
old_reg = '''@app.route('/api/capsule/registry')
def api_capsule_registry():
    """P17: list received capsules."""
    try:
        try:
            _capsule_received
        except NameError:
            return jsonify({'success': True, 'capsules': []})
        with _capsule_received_lock:
            caps = list(_capsule_received.values())
        return jsonify({'success': True, 'capsules': caps})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500'''

new_reg = '''@app.route('/api/capsule/registry')
def api_capsule_registry():
    """P17: list received capsules."""
    try:
        with _capsule_received_lock:
            caps = list(_capsule_received.values())
        return jsonify({'success': True, 'capsules': caps})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500'''

if old_reg in app:
    app = app.replace(old_reg, new_reg)
    print("[OK] registry endpoint fixed")
else:
    print("[--] registry endpoint already fixed")

# Save
with open(APP, "w", encoding="utf-8") as f:
    f.write(app)

try:
    ast.parse(app)
    print("[OK] syntax valid")
except SyntaxError as e:
    print(f"[!!] syntax error: {e}")
    shutil.copy2(APP + ".bak_p17f1", APP)
    sys.exit(1)

print()
print("=" * 70)
print("  PATCH 17-FIX1 DONE")
print("=" * 70)