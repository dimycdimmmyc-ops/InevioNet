# run_app.py - PyInstaller entry point (portable)
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

# P57: portable mode — data/logs в %APPDATA%\InevioNet
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
        # P58: EXE — HTTP (TLS self-signed браузер не принимает)
        scheme = 'http'
        if os.environ.get('INEVIO_TLS', '').lower() in ('1', 'true', 'yes'):
            scheme = 'https'
        url = f'{scheme}://localhost:{PORT}'
        webbrowser.open(url)
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
