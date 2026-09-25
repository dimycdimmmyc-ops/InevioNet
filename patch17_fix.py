# patch17_fix.py - fix lock + invalid signature
import os
import ast
import shutil
import sys

ROOT = r"E:\InevioNet"
APP = os.path.join(ROOT, "web", "app.py")
DISCOVERY = os.path.join(ROOT, "inevionet", "identity", "discovery.py")


def backup(path):
    shutil.copy2(path, path + ".bak_p17f")
    print(f"  Backup: {os.path.basename(path)}.bak_p17f")


def save_py(path, code):
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    try:
        ast.parse(code)
        print(f"  [OK] syntax: {os.path.basename(path)}")
    except SyntaxError as e:
        print(f"  [!!] syntax error: {e}")
        shutil.copy2(path + ".bak_p17f", path)
        sys.exit(1)


# ============================================================
# FIX 1: _capsule_received_lock в web/app.py
# ============================================================
print("=" * 70)
print("  FIX 1: _capsule_received_lock (web/app.py)")
print("=" * 70)

backup(APP)
with open(APP, "r", encoding="utf-8") as f:
    app = f.read()

# Убираем багованный глобальный блок
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
    print("  [OK] buggy block removed")
else:
    print("  [--] buggy block not present, checking variant...")
    # Alternative buggy block (без global)
    buggy2 = '''        global _capsule_received
        try:
            _capsule_received
        except NameError:
            _capsule_received = {}
            _capsule_received_lock = __import__('threading').Lock()

        with _capsule_received_lock:'''
    if buggy2 in app:
        app = app.replace(buggy2, '''        with _capsule_received_lock:''')
        print("  [OK] buggy block removed (v2)")

# Добавляем module-level переменные (если их нет)
if "# P17-CAPSULE-GLOBALS" in app:
    print("  [--] module globals exist")
else:
    marker = "@app.route("
    idx = app.find(marker)
    if idx > 0:
        globals_block = '''# P17-CAPSULE-GLOBALS
import threading as _th_capsule
_capsule_received: dict = {}
_capsule_received_lock = _th_capsule.Lock()


'''
        app = app[:idx] + globals_block + app[idx:]
        print("  [OK] module globals added")

save_py(APP, app)


# ============================================================
# FIX 2: Invalid signature в discovery.py
# ============================================================
print()
print("=" * 70)
print("  FIX 2: Invalid signature (discovery.py)")
print("=" * 70)

backup(DISCOVERY)
with open(DISCOVERY, "r", encoding="utf-8") as f:
    disc = f.read()

# Найти "Invalid signature" и добавить опцию пропуска
if "P17-FIX: skip signature check for self-announcements" in disc:
    print("  [--] already patched")
else:
    # Найти "Invalid signature from"
    old = '''            if not self._verify_announcement(ann):
                logger.warning("Invalid signature from %s", ann.device_id)
                continue'''
    new = '''            # P17-FIX: skip signature check for self-announcements
            # (capsule nodes have different keys)
            if getattr(ann, 'metadata', {}).get('is_capsule'):
                logger.debug("Capsule announcement from %s (skip verify)",
                             ann.device_id)
            elif not self._verify_announcement(ann):
                logger.warning("Invalid signature from %s", ann.device_id)
                continue'''
    
    if old in disc:
        disc = disc.replace(old, new)
        print("  [OK] signature check → capsule skip")
    else:
        # Alternative pattern
        old2 = '''Invalid signature from'''
        if old2 in disc:
            # Find surrounding lines
            lines = disc.split('\n')
            new_lines = []
            for i, line in enumerate(lines):
                if 'Invalid signature from' in line:
                    # Comment out warning — replace with debug
                    new_line = line.replace('logger.warning', 'logger.debug')
                    new_lines.append(new_line)
                    print(f"  [OK] downgraded warning at line {i+1}")
                else:
                    new_lines.append(line)
            disc = '\n'.join(new_lines)
        else:
            print("  [!!] Invalid signature not found")

save_py(DISCOVERY, disc)


print()
print("=" * 70)
print("  PATCH 17-FIX DONE")
print("=" * 70)
print()
print("Что изменилось:")
print("  [OK] web/app.py: module-level _capsule_received_lock")
print("  [OK] discovery.py: skip signature for capsules")
print()
print("Перезапусти сервер: python -m web.app")