# patch54.py - InevioNet: fix PyInstaller console=False (sys.stdout is None)
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
INIT = os.path.join(ROOT, "inevionet", "__init__.py")
APP = os.path.join(ROOT, "web", "app.py")
RUN_APP = os.path.join(ROOT, "run_app.py")


def backup(path):
    if os.path.exists(path):
        b = path + ".bak_p54"
        shutil.copy2(path, b)
        print(f"  [BK] {os.path.basename(b)}")


def save_py(path, code):
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    try:
        ast.parse(code)
        print(f"  [OK] syntax: {os.path.basename(path)}")
        return True
    except SyntaxError as e:
        print(f"  [!!] syntax error: {e}")
        if os.path.exists(path + ".bak_p54"):
            shutil.copy2(path + ".bak_p54", path)
        return False


print()
print("=" * 70)
print("  P54: fix sys.stdout=None in PyInstaller")
print("=" * 70)

# === P54a: run_app.py ===
print("\n[P54a] run_app.py")
RUN_APP_CODE = '''# run_app.py - PyInstaller entry point
import os
import sys
import io
import threading
import time

# P54: PyInstaller console=False -> sys.stdout = None
if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

# UTF-8
if sys.platform == 'win32':
    try:
        if hasattr(sys.stdout, 'reconfigure') and sys.stdout is not None:
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if hasattr(sys.stderr, 'reconfigure') and sys.stderr is not None:
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')

# PyInstaller: _MEIPASS в sys.path
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, BASE_DIR)
os.chdir(BASE_DIR)

# P54: logs в %APPDATA%\\InevioNet\\logs
LOGS_DIR = os.path.join(os.environ.get('APPDATA', BASE_DIR), 'InevioNet', 'logs')
os.makedirs(LOGS_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOGS_DIR, 'inevionet.log')


def open_browser():
    time.sleep(3)
    try:
        import webbrowser
        webbrowser.open('https://localhost:8080')
    except Exception:
        pass


if __name__ == '__main__':
    try:
        log_fp = open(LOG_FILE, 'a', encoding='utf-8', errors='replace')
        sys.stdout = log_fp
        sys.stderr = log_fp
    except Exception:
        pass

    from web.app import app, socketio, background_scanner, install_log_bridge

    install_log_bridge()
    threading.Thread(target=open_browser, daemon=True).start()
    socketio.start_background_task(background_scanner)
    socketio.run(app, host='0.0.0.0', port=8080,
                 debug=False, allow_unsafe_werkzeug=True)
'''
with open(RUN_APP, 'w', encoding='utf-8') as f:
    f.write(RUN_APP_CODE)
print("  [OK] run_app.py перезаписан")

# === P54b: inevionet/__init__.py ===
print("\n[P54b] inevionet/__init__.py")
backup(INIT)
with open(INIT, 'r', encoding='utf-8') as f:
    content = f.read()

old_init = '''try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    try:
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
    except Exception:
        pass'''

new_init = '''# P54: guard for PyInstaller console=False (sys.stdout is None)
try:
    if sys.stdout is not None and hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    if sys.stderr is not None and hasattr(sys.stderr, 'reconfigure'):
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass'''

if old_init in content:
    content = content.replace(old_init, new_init, 1)
    print("  [OK] fixed reconfigure block")
elif 'P54: guard for PyInstaller' in content:
    print("  [--] already applied")
else:
    print("  [!!] NOT FOUND — проверь вручную")
    # Fallback: найти любую строку с reconfigure
    if 'sys.stdout.reconfigure' in content:
        # Заменить все reconfigure на guarded
        import re
        content = re.sub(
            r'sys\.stdout\.reconfigure\([^)]*\)',
            "if sys.stdout is not None and hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8', errors='replace')",
            content)
        content = re.sub(
            r'sys\.stderr\.reconfigure\([^)]*\)',
            "if sys.stderr is not None and hasattr(sys.stderr, 'reconfigure'): sys.stderr.reconfigure(encoding='utf-8', errors='replace')",
            content)
        print("  [OK] regex-replaced reconfigure")

save_py(INIT, content)

# === P54c: web/app.py ===
print("\n[P54c] web/app.py")
backup(APP)
with open(APP, 'r', encoding='utf-8') as f:
    content = f.read()

old_app = '''if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')'''

new_app = '''if sys.platform == 'win32':
    # P54: guard for PyInstaller console=False
    try:
        if sys.stdout is not None and hasattr(sys.stdout, 'reconfigure'):
            sys.stdout.reconfigure(encoding='utf-8', errors='replace')
        if sys.stderr is not None and hasattr(sys.stderr, 'reconfigure'):
            sys.stderr.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    os.environ.setdefault('PYTHONIOENCODING', 'utf-8')'''

if old_app in content:
    content = content.replace(old_app, new_app, 1)
    print("  [OK] fixed app.py stdout block")
elif 'P54: guard for PyInstaller console=False' in content:
    print("  [--] already applied")
else:
    print("  [!!] NOT FOUND — проверь вручную")

save_py(APP, content)

print()
print("=" * 70)
print("  PATCH 54 DONE")
print("=" * 70)
print()
print("Пересобери EXE:")
print("  pyinstaller InevioNet.spec --clean --noconfirm")
print()
print("Пересобери установщик:")
print("  & \"$env:LOCALAPPDATA\\Programs\\Inno Setup 6\\ISCC.exe\" InevioNet_Setup.iss")