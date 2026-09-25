# patch19.py - Optimize + Kill-switch
import os
import ast
import shutil
import sys

ROOT = r"E:\InevioNet"
CAPSULE = os.path.join(ROOT, "inevionet", "mycelium", "capsule.py")
ORCH = os.path.join(ROOT, "inevionet", "orchestrator.py")
APP = os.path.join(ROOT, "web", "app.py")
HTML = os.path.join(ROOT, "web", "templates", "index.html")


def backup(path):
    shutil.copy2(path, path + ".bak_p19")
    print(f"  Backup: {os.path.basename(path)}.bak_p19")


def save_py(path, code):
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    try:
        ast.parse(code)
        print(f"  [OK] syntax: {os.path.basename(path)}")
    except SyntaxError as e:
        print(f"  [!!] syntax error: {e}")
        shutil.copy2(path + ".bak_p19", path)
        sys.exit(1)


def save_raw(path, code):
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    print(f"  [OK] saved: {os.path.basename(path)}")


# ============================================================
# A1 + A2 + A3: capsule.py — mtime cache, skip self, debug
# ============================================================
print("=" * 70)
print("  A1-A3: capsule.py optimization")
print("=" * 70)

backup(CAPSULE)
with open(CAPSULE, "r", encoding="utf-8") as f:
    cap = f.read()

# A3: заменить print на logger.debug в build_minimal
old_print = '                        tar.add(full, arcname=rel.replace("\\\\", "/"))\n' \
            '                        print(f"[CapsuleBuilder] added: {rel}")'
new_print = '                        tar.add(full, arcname=rel.replace("\\\\", "/"))\n' \
            '                        logger.debug("[CapsuleBuilder] added: %s", rel)'
if old_print in cap:
    cap = cap.replace(old_print, new_print)
    print("  [OK] A3: print → logger.debug")
else:
    # Try with single backslash
    old_print2 = '                        print(f"[CapsuleBuilder] added: {rel}")'
    new_print2 = '                        logger.debug("[CapsuleBuilder] added: %s", rel)'
    if old_print2 in cap:
        cap = cap.replace(old_print2, new_print2)
        print("  [OK] A3: print → logger.debug (alt)")

# A2: skip self в TrustedHosts.add
old_add = '''    def add(self, host: str, label: str = "", user: str = None,
            method: str = "auto") -> bool:
        with self._lock:'''
new_add = '''    def add(self, host: str, label: str = "", user: str = None,
            method: str = "auto") -> bool:
        # P19: skip self
        host_ip = host.split(":")[0]
        my_ips = {"127.0.0.1", "localhost", "0.0.0.0"}
        try:
            import socket as _s
            for info in _s.getaddrinfo(_s.gethostname(), None):
                my_ips.add(info[4][0])
        except Exception:
            pass
        if host_ip in my_ips:
            logger.warning("[Trusted] skip self: %s", host)
            return False

        with self._lock:'''
if old_add in cap:
    cap = cap.replace(old_add, new_add, 1)
    print("  [OK] A2: skip self in TrustedHosts.add")
else:
    print("  [!!] A2: TrustedHosts.add pattern not found")

# A1: mtime cache в CapsuleBuilder
if "_last_cache_key" in cap:
    print("  [--] A1: mtime cache exists")
else:
    # Add cache fields to __init__
    old_builder_init = '''    def __init__(self, project_root: Optional[str] = None):
        # __file__ = E:\\InevioNet\\inevionet\\mycelium\\capsule.py
        # parent  = E:\\InevioNet\\inevionet\\mycelium
        # parent2 = E:\\InevioNet\\inevionet         ← это self.inev_dir
        # parent3 = E:\\InevioNet                     ← это project_root
        if project_root is None:
            capsule_file = os.path.abspath(__file__)
            inev_dir = os.path.dirname(os.path.dirname(capsule_file))
            project_root = os.path.dirname(inev_dir)
        self.project_root = project_root
        self.inev_dir = os.path.join(project_root, "inevionet")
        print(f"[CapsuleBuilder] project_root={self.project_root}")
        print(f"[CapsuleBuilder] inev_dir={self.inev_dir}")'''
    new_builder_init = '''    def __init__(self, project_root: Optional[str] = None):
        if project_root is None:
            capsule_file = os.path.abspath(__file__)
            inev_dir = os.path.dirname(os.path.dirname(capsule_file))
            project_root = os.path.dirname(inev_dir)
        self.project_root = project_root
        self.inev_dir = os.path.join(project_root, "inevionet")
        # P19: mtime cache
        self._last_cache_key = None
        self._last_code = None
        logger.debug("[CapsuleBuilder] project_root=%s", self.project_root)
        logger.debug("[CapsuleBuilder] inev_dir=%s", self.inev_dir)

    def _get_mtimes_key(self, include=None) -> str:
        """P19: SHA256 от (путь, mtime) всех .py файлов."""
        include = include or self.INCLUDE_MODULES
        import hashlib
        parts = []
        for module in include:
            mod_path = os.path.join(self.inev_dir, module)
            if not os.path.isdir(mod_path):
                continue
            for dirpath, dirnames, filenames in os.walk(mod_path):
                dirnames[:] = [d for d in dirnames if d != "__pycache__"]
                for fname in filenames:
                    if not fname.endswith(".py"):
                        continue
                    full = os.path.join(dirpath, fname)
                    try:
                        mt = os.path.getmtime(full)
                        parts.append(f"{full}:{mt}")
                    except OSError:
                        pass
        return hashlib.sha256("|".join(sorted(parts)).encode()).hexdigest()'''
    if old_builder_init in cap:
        cap = cap.replace(old_builder_init, new_builder_init, 1)
        print("  [OK] A1: __init__ with cache")
    else:
        # Fallback: insert cache fields only
        old_simple_init = '''        self.project_root = project_root
        self.inev_dir = os.path.join(project_root, "inevionet")'''
        new_simple_init = '''        self.project_root = project_root
        self.inev_dir = os.path.join(project_root, "inevionet")
        # P19: mtime cache
        self._last_cache_key = None
        self._last_code = None'''
        if old_simple_init in cap:
            cap = cap.replace(old_simple_init, new_simple_init, 1)
            print("  [OK] A1: cache fields added (simple)")

    # Add check at start of build_minimal
    old_build = '''    def build_minimal(self, include: Optional[List[str]] = None) -> bytes:
        """Собрать минимальный capsule (tar.gz в base64)."""
        import io
        import tarfile
        import base64

        include = include or self.INCLUDE_MODULES'''
    new_build = '''    def build_minimal(self, include: Optional[List[str]] = None) -> bytes:
        """P19: Собрать минимальный capsule (tar.gz) с mtime-кэшем."""
        import io
        import tarfile

        include = include or self.INCLUDE_MODULES

        # P19: check mtime cache
        cache_key = self._get_mtimes_key(include)
        if cache_key == self._last_cache_key and self._last_code is not None:
            logger.debug("[CapsuleBuilder] cache hit, skip build")
            return self._last_code'''
    if old_build in cap:
        cap = cap.replace(old_build, new_build, 1)
        print("  [OK] A1: build_minimal cache check")

    # Save cache at end of build_minimal
    old_return = '''        raw = buf.getvalue()
        logger.info("[Capsule] built: %d bytes", len(raw))
        return raw'''
    new_return = '''        raw = buf.getvalue()
        self._last_cache_key = cache_key
        self._last_code = raw
        logger.info("[Capsule] built: %d bytes (fresh)", len(raw))
        return raw'''
    if old_return in cap:
        cap = cap.replace(old_return, new_return, 1)
        print("  [OK] A1: cache save")

save_py(CAPSULE, cap)


# ============================================================
# B: Kill-switch в web/app.py
# ============================================================
print()
print("=" * 70)
print("  B: Kill-switch in app.py")
print("=" * 70)

backup(APP)
with open(APP, "r", encoding="utf-8") as f:
    app = f.read()

if "/api/capsule/kill" in app:
    print("  [--] kill endpoint exists")
else:
    # Add STOP endpoint
    kill_ep = '''
@app.route('/api/capsule/kill', methods=['POST'])
def api_capsule_kill():
    """P19: emergency stop — kill all autostarted capsules."""
    import subprocess as _sp
    global _autostart_counter
    try:
        # Block future autostarts
        _autostart_counter = _MAX_AUTOSTART

        # Find and kill python processes (except our own)
        my_pid = os.getpid()
        killed = 0
        try:
            if sys.platform == "win32":
                r = _sp.run(
                    ["wmic", "process", "where",
                     "name='python.exe'", "get", "ProcessId,CommandLine"],
                    capture_output=True, text=True, timeout=10)
                for line in r.stdout.splitlines():
                    if "run_capsule.py" in line or "capsule_" in line:
                        try:
                            parts = line.strip().split()
                            pid = int(parts[-1])
                            if pid != my_pid:
                                _sp.run(["taskkill", "/F", "/PID", str(pid)],
                                        capture_output=True, timeout=5)
                                killed += 1
                        except (ValueError, IndexError):
                            pass
            else:
                r = _sp.run(
                    ["pgrep", "-f", "run_capsule.py"],
                    capture_output=True, text=True, timeout=5)
                for line in r.stdout.splitlines():
                    try:
                        pid = int(line.strip())
                        if pid != my_pid:
                            _sp.run(["kill", "-9", str(pid)],
                                    capture_output=True, timeout=5)
                            killed += 1
                    except ValueError:
                        pass
        except Exception as e:
            log.error('[Kill] error: %s', e)

        log.warning('[Capsule] KILL: %d processes terminated, autostart blocked',
                    killed)
        return jsonify({
            'success': True,
            'killed': killed,
            'autostart_blocked': True,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


'''
    marker = "@socketio.on('connect')"
    if marker in app:
        app = app.replace(marker, kill_ep + marker, 1)
        save_py(APP, app)
        print("  [OK] kill endpoint added")
    else:
        print("  [!!] socketio marker not found")


# ============================================================
# B: Kill-switch в index.html
# ============================================================
print()
print("=" * 70)
print("  B: Kill-switch in UI")
print("=" * 70)

backup(HTML)
with open(HTML, "r", encoding="utf-8") as f:
    html = f.read()

if "btnKillCapsules" in html:
    print("  [--] kill button exists")
else:
    # Add button to capsule card
    old_capsule_btns = '''<button class="btn btn-glass" onclick="loadCapsuleStats()">📊 Обновить</button>'''
    new_capsule_btns = '''<button class="btn btn-glass" onclick="loadCapsuleStats()">📊 Обновить</button>
<button class="btn btn-danger" onclick="killCapsules()">⛔ СТОП (убить все капсулы)</button>'''
    if old_capsule_btns in html:
        html = html.replace(old_capsule_btns, new_capsule_btns, 1)
        print("  [OK] kill button added")

    # Add JS
    js = '''
async function killCapsules() {
    if (!confirm('Убить все капсулы и заблокировать автозапуск?')) return;
    addLog('KILL: останавливаю капсулы...', 'warn');
    try {
        const r = await fetch('/api/capsule/kill', { method: 'POST' });
        const d = await r.json();
        if (d.success) {
            addLog('Убито процессов: ' + d.killed + ', автозапуск заблокирован', 'success');
        } else {
            addLog('KILL error: ' + (d.error || '?'), 'error');
        }
    } catch (e) {
        addLog('KILL: ' + e, 'error');
    }
}

'''
    js_marker = "checkAuth();"
    if js_marker in html:
        html = html.replace(js_marker, js + '\n' + js_marker, 1)
        print("  [OK] kill JS added")

    save_raw(HTML, html)


print()
print("=" * 70)
print("  PATCH 19 DONE")
print("=" * 70)
print()
print("Что изменилось:")
print("  [A1] CapsuleBuilder: mtime-кэш (не строить если не менялось)")
print("  [A2] TrustedHosts.add: skip self (свой IP не добавить)")
print("  [A3] Убран спам логов (print → debug)")
print("  [B]  /api/capsule/kill — убить все капсулы + блок")
print("  [B]  UI: кнопка ⛔ СТОП")
print()
print("Перезапусти сервер: python -m web.app")