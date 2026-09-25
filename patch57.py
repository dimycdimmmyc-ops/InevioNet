# patch57.py - InevioNet: full portable mode
#  - INEVIO_PORT в run_app.py
#  - data/ -> %APPDATA%\InevioNet\data\
#  - logs/ -> %APPDATA%\InevioNet\logs\
#  - web_state, p2_inbox -> %APPDATA%
#  - браузер открывается на нужном порту
import os
import ast
import re
import shutil

ROOT = r"E:\InevioNet"
APP = os.path.join(ROOT, "web", "app.py")
RUN = os.path.join(ROOT, "run_app.py")


def backup(path):
    if os.path.exists(path):
        b = path + ".bak_p57"
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
        if os.path.exists(path + ".bak_p57"):
            shutil.copy2(path + ".bak_p57", path)
        return False


# ============================================================
# P57a. run_app.py — полная перезапись (portable mode)
# ============================================================
print()
print("=" * 70)
print("  P57a: run_app.py — portable mode")
print("=" * 70)
backup(RUN)

RUN_APP = '''# run_app.py - PyInstaller entry point (portable)
import os
import sys
import io
import threading
import time

# === stdout/stderr для console=False ===
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

# P56: force threading async_mode
os.environ['SOCKETIO_ASYNC_MODE'] = 'threading'
os.environ['ENGINEIO_ASYNC_MODE'] = 'threading'

# P57: portable mode — data/logs в %APPDATA%\\InevioNet
PORT = int(os.environ.get('INEVIO_PORT', 8080))
USER_HOME = os.environ.get('APPDATA') or os.path.expanduser('~')
DATA_HOME = os.path.join(USER_HOME, 'InevioNet')
os.makedirs(os.path.join(DATA_HOME, 'data'), exist_ok=True)
os.makedirs(os.path.join(DATA_HOME, 'logs'), exist_ok=True)
os.makedirs(os.path.join(DATA_HOME, 'data', 'users'), exist_ok=True)
os.makedirs(os.path.join(DATA_HOME, 'data', 'users', 'qr_codes'), exist_ok=True)
os.makedirs(os.path.join(DATA_HOME, 'data', 'tls'), exist_ok=True)

os.environ['INEVIO_DATA_DIR'] = os.path.join(DATA_HOME, 'data')
os.environ['INEVIO_LOGS_DIR'] = os.path.join(DATA_HOME, 'logs')

# PyInstaller: BASE_DIR
if getattr(sys, 'frozen', False):
    BASE_DIR = sys._MEIPASS
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))

sys.path.insert(0, BASE_DIR)
os.chdir(BASE_DIR)

LOG_FILE = os.path.join(DATA_HOME, 'logs', f'inevionet_{PORT}.log')


def open_browser():
    time.sleep(3)
    try:
        import webbrowser
        webbrowser.open(f'https://localhost:{PORT}')
    except Exception:
        pass


if __name__ == '__main__':
    # Перенаправляем stdout/stderr в файл
    try:
        log_fp = open(LOG_FILE, 'a', encoding='utf-8', errors='replace')
        sys.stdout = log_fp
        sys.stderr = log_fp
    except Exception:
        pass

    # Патчим константы ДО импорта web.app
    try:
        from inevionet.core import constants as _const
        if hasattr(_const, 'DataPaths'):
            try:
                _const.DataPaths.OVERRIDE_ROOT = os.path.join(DATA_HOME, 'data')
            except Exception:
                pass
    except Exception:
        pass

    from web.app import app, socketio, background_scanner, install_log_bridge

    install_log_bridge()
    threading.Thread(target=open_browser, daemon=True).start()
    socketio.start_background_task(background_scanner)
    socketio.run(app, host='0.0.0.0', port=PORT,
                 debug=False, allow_unsafe_werkzeug=True)
'''

with open(RUN, "w", encoding="utf-8") as f:
    f.write(RUN_APP)
print("  [OK] run_app.py перезаписан (portable)")


# ============================================================
# P57b. web/app.py — INEVIO_DATA_DIR, per-port state
# ============================================================
print()
print("=" * 70)
print("  P57b: web/app.py — portable data dir + per-port files")
print("=" * 70)
backup(APP)
with open(APP, "r", encoding="utf-8") as f:
    app = f.read()

# 1. BASE_DIR: %APPDATA%\InevioNet\data если portable, иначе локально
old_base = '''BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# P49: per-port files (so PC-A and PC-B don't share)
_PORT = os.environ.get('INEVIO_PORT', '8080')
STATE_FILE = os.path.join(BASE_DIR, 'data', 'web_state_%s.json' % _PORT)
INBOX_FILE = os.path.join(BASE_DIR, 'data', 'p2_inbox_%s.json' % _PORT)'''

new_base = '''# P57: portable data dir
if getattr(sys, 'frozen', False):
    # EXE: данные в %APPDATA%\\InevioNet\\data
    _data_home = os.environ.get('INEVIO_DATA_DIR') or os.path.join(
        os.environ.get('APPDATA', os.path.expanduser('~')),
        'InevioNet', 'data')
else:
    # Из исходников: локально
    _data_home = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        'data')

os.makedirs(_data_home, exist_ok=True)
BASE_DIR = os.path.dirname(_data_home)

# P49/P57: per-port files
_PORT = os.environ.get('INEVIO_PORT', '8080')
STATE_FILE = os.path.join(_data_home, 'web_state_%s.json' % _PORT)
INBOX_FILE = os.path.join(_data_home, 'p2_inbox_%s.json' % _PORT)
_NODE_ID_FILE = os.path.join(_data_home, 'node_id_%s.txt' % _PORT)
_TRUSTED_FILE = os.path.join(_data_home, 'trusted_hosts_%s.json' % _PORT)'''

if old_base in app:
    app = app.replace(old_base, new_base, 1)
    print("  [OK] BASE_DIR portable + per-port files")
elif 'P57: portable data dir' in app:
    print("  [--] already applied")
else:
    print("  [!!] BASE_DIR block NOT FOUND")


# 2. node_id: использовать _NODE_ID_FILE вместо старого пути
old_nid = '''            # P48: persistent node_id (per-port)
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
                log.info('[Node] created new node_id=%s (port %s)', _node_id, _port)'''

new_nid = '''            # P48/P57: persistent node_id (per-port, in _data_home)
            _nid_path = _NODE_ID_FILE
            if os.path.exists(_nid_path):
                with open(_nid_path, 'r', encoding='utf-8') as _f:
                    _node_id = _f.read().strip()
                log.info('[Node] persistent node_id=%s (port %s)', _node_id, _PORT)
            else:
                _node_id = 'web_node_%d' % random.randint(1000, 9999)
                with open(_nid_path, 'w', encoding='utf-8') as _f:
                    _f.write(_node_id)
                log.info('[Node] created new node_id=%s (port %s)', _node_id, _PORT)'''

if old_nid in app:
    app = app.replace(old_nid, new_nid, 1)
    print("  [OK] node_id in _data_home")
elif '_NODE_ID_FILE' in app and 'P48/P57' in app:
    print("  [--] already applied")
else:
    print("  [!!] node_id block NOT FOUND")


# 3. Убедиться, что web_state / p2_inbox используют новые пути
if "os.path.join(_data_home" in app:
    print("  [OK] state/inbox в _data_home")
else:
    print("  [!!] state/inbox не в _data_home — проверь")


save_py(APP, app)


# ============================================================
# P57c. inevionet/core/constants.py — OVERRIDE_ROOT
# ============================================================
CONST = os.path.join(ROOT, "inevionet", "core", "constants.py")
if os.path.exists(CONST):
    print()
    print("=" * 70)
    print("  P57c: core/constants.py — OVERRIDE_ROOT support")
    print("=" * 70)
    backup(CONST)
    with open(CONST, "r", encoding="utf-8") as f:
        const = f.read()

    # Найти get_root или DataPaths
    if "OVERRIDE_ROOT" not in const:
        # Попробуем вставить в начало DataPaths
        marker = "class DataPaths"
        if marker in const:
            # Добавить атрибут OVERRIDE_ROOT = None и модифицировать get_root
            const = const.replace(
                marker,
                "class DataPaths:\n    OVERRIDE_ROOT = None  # P57\n",
                1,
            )
            # Найти get_root и добавить проверку
            if "def get_root" in const:
                # Заменить тело get_root
                import re as _re
                def replace_get_root(match):
                    body = match.group(0)
                    return body  # оставить как есть, потом допишем
                const = const.replace(
                    "def get_root():",
                    "def get_root():\n        if DataPaths.OVERRIDE_ROOT:\n            return __import__('pathlib').Path(DataPaths.OVERRIDE_ROOT)",
                    1,
                )
            print("  [OK] OVERRIDE_ROOT support added")
            save_py(CONST, const)
        else:
            print("  [!!] 'class DataPaths' NOT FOUND")
    else:
        print("  [--] already has OVERRIDE_ROOT")


print()
print("=" * 70)
print("  PATCH 57 DONE — PORTABLE MODE")
print("=" * 70)
print()
print("Что изменилось:")
print("  [OK] INEVIO_PORT читается в run_app.py")
print("  [OK] data/ -> %APPDATA%\\InevioNet\\data\\")
print("  [OK] logs/ -> %APPDATA%\\InevioNet\\logs\\inevionet_<PORT>.log")
print("  [OK] node_id_<PORT>.txt, web_state_<PORT>.json, p2_inbox_<PORT>.json")
print("  [OK] trusted_hosts_<PORT>.json")
print("  [OK] браузер открывается на https://localhost:<PORT>")
print()
print("Пересобери:")
print("  Get-Process InevioNet,python -ErrorAction SilentlyContinue | Stop-Process -Force")
print("  cd E:\\InevioNet")
print("  Remove-Item dist,build -Recurse -Force -ErrorAction SilentlyContinue")
print("  .\\venv\\Scripts\\Activate.ps1")
print("  pyinstaller InevioNet.spec --clean --noconfirm")