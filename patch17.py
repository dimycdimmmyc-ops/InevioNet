# patch17.py - Autostart + Hash cache + Registry
import os
import ast
import shutil
import sys

ROOT = r"E:\InevioNet"
CAPSULE = os.path.join(ROOT, "inevionet", "mycelium", "capsule.py")
ORCH = os.path.join(ROOT, "inevionet", "orchestrator.py")
APP = os.path.join(ROOT, "web", "app.py")


def backup(path):
    bak = path + ".bak_p17"
    shutil.copy2(path, bak)
    print(f"  Backup: {os.path.basename(bak)}")


def save_py(path, code):
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    try:
        ast.parse(code)
        print(f"  [OK] syntax: {os.path.basename(path)}")
    except SyntaxError as e:
        print(f"  [!!] syntax error: {e}")
        shutil.copy2(path + ".bak_p17", path)
        sys.exit(1)


# ============================================================
# 1. Patch capsule.py: hash + cache + auto_start
# ============================================================
print("=" * 70)
print("  PATCH 17a: capsule.py — hash + cache + autostart")
print("=" * 70)

backup(CAPSULE)
with open(CAPSULE, "r", encoding="utf-8") as f:
    cap = f.read()

# 1.1. Add build_hash method to CapsuleBuilder
if "def build_hash" in cap:
    print("  [--] build_hash exists")
else:
    marker = "    def estimate_size(self, include: Optional[List[str]] = None) -> int:"
    new_method = '''    def build_hash(self, include: Optional[List[str]] = None) -> str:
        """SHA256 хэш кода — для кэша."""
        code = self.build_minimal(include)
        return hashlib.sha256(code).hexdigest()

    def estimate_size(self, include: Optional[List[str]] = None) -> int:'''
    if marker in cap:
        cap = cap.replace(marker, new_method, 1)
        print("  [OK] build_hash added")
    else:
        print("  [!!] estimate_size marker not found")

# 1.2. Add auto_start param + method to CapsuleDeployer
if "def _auto_start_remote" in cap:
    print("  [--] _auto_start_remote exists")
else:
    # Add param to __init__
    old_init = '''    def __init__(self, trusted: TrustedHosts, ssh_user: Optional[str] = None):
        self.trusted = trusted
        self.ssh_user = ssh_user
        self.stats = {
            "attempts": 0,
            "success": 0,
            "failed": 0,
            "skipped": 0,
        }'''
    new_init = '''    def __init__(self, trusted: TrustedHosts, ssh_user: Optional[str] = None,
                 auto_start: bool = True):
        self.trusted = trusted
        self.ssh_user = ssh_user
        self.auto_start = auto_start
        self.stats = {
            "attempts": 0,
            "success": 0,
            "failed": 0,
            "skipped": 0,
            "auto_started": 0,
        }
        self._last_deploy_hash: Dict[str, str] = {}
        self._last_deploy_time: Dict[str, float] = {}'''
    if old_init in cap:
        cap = cap.replace(old_init, new_init)
        print("  [OK] CapsuleDeployer __init__ extended")

    # Add hash cache check in deploy()
    old_deploy = '''    def deploy(self, target: str, code: bytes,
               method: str = "auto") -> bool:
        """Развернуть capsule на target."""
        if not self.trusted.is_trusted(target):
            logger.warning("[Deploy] refused: %s not trusted", target)
            self.stats["skipped"] += 1
            return False

        self.stats["attempts"] += 1'''
    new_deploy = '''    def deploy(self, target: str, code: bytes,
               method: str = "auto") -> bool:
        """Развернуть capsule на target."""
        if not self.trusted.is_trusted(target):
            logger.warning("[Deploy] refused: %s not trusted", target)
            self.stats["skipped"] += 1
            return False

        # P17: hash cache — skip if not changed and < 30 min ago
        import hashlib
        import time as _t
        code_hash = hashlib.sha256(code).hexdigest()
        last_hash = self._last_deploy_hash.get(target)
        last_time = self._last_deploy_time.get(target, 0)
        now = _t.time()
        if last_hash == code_hash and (now - last_time) < 1800:
            logger.debug("[Deploy] skip %s — same hash, %ds ago",
                         target, int(now - last_time))
            self.stats["skipped"] += 1
            return True

        self.stats["attempts"] += 1'''
    if old_deploy in cap:
        cap = cap.replace(old_deploy, new_deploy)
        print("  [OK] hash cache in deploy()")

    # Add _auto_start_remote method
    marker = "    def get_stats(self) -> Dict[str, Any]:"
    auto_start_method = '''    def _auto_start_remote(self, host: str, user: Optional[str] = None) -> bool:
        """P17: launch capsule on remote host after deploy."""
        if not self.auto_start:
            return False
        try:
            user_prefix = f"{user}@" if user else ""
            remote_dir = f"/tmp/inevionet_capsule"

            # Command to run: use nohup + setsid + exit
            cmd = (
                f"cd {remote_dir} && "
                f"nohup python3 run_capsule.py "
                f"> /tmp/inevionet_capsule.log 2>&1 < /dev/null & "
                f"disown; echo STARTED"
            )
            r = subprocess.run(
                ["ssh", "-o", "StrictHostKeyChecking=no",
                 "-o", "ConnectTimeout=5",
                 f"{user_prefix}{host}", cmd],
                capture_output=True, timeout=15)
            if r.returncode == 0 and b"STARTED" in r.stdout:
                logger.info("[AutoStart] started on %s", host)
                self.stats["auto_started"] += 1
                return True
            logger.debug("[AutoStart] failed: %s",
                         r.stderr.decode(errors="replace")[:200])
            return False
        except Exception as e:
            logger.error("[AutoStart] error: %s", e)
            return False

    def _mark_deployed(self, target: str, code: bytes):
        """P17: remember deploy hash + time."""
        import hashlib
        import time as _t
        self._last_deploy_hash[target] = hashlib.sha256(code).hexdigest()
        self._last_deploy_time[target] = _t.time()

    def get_stats(self) -> Dict[str, Any]:'''
    if marker in cap:
        cap = cap.replace(marker, auto_start_method, 1)
        print("  [OK] _auto_start_remote + _mark_deployed added")

    # Update deploy() to call _auto_start_remote + _mark_deployed
    old_ssh_deploy = '''            if r.returncode == 0:
                logger.info("[Deploy] ssh OK: %s", target)
                return True
            logger.debug("[Deploy] ssh run failed: %s",
                         r.stderr.decode(errors="replace")[:200])
            return False'''
    new_ssh_deploy = '''            if r.returncode == 0:
                logger.info("[Deploy] ssh OK: %s", target)
                self._auto_start_remote(host, user)
                return True
            logger.debug("[Deploy] ssh run failed: %s",
                         r.stderr.decode(errors="replace")[:200])
            return False'''
    if old_ssh_deploy in cap:
        cap = cap.replace(old_ssh_deploy, new_ssh_deploy)
        print("  [OK] ssh deploy → auto_start")

    # Update _deploy_http to trigger remote self-start via second request
    old_http = '''            with urllib.request.urlopen(req, timeout=10, context=ctx) as r:
                ok = r.status == 200
                if ok:
                    logger.info("[Deploy] http OK: %s", target)
                return ok'''
    new_http = '''            with urllib.request.urlopen(req, timeout=10, context=ctx) as r:
                ok = r.status == 200
                if ok:
                    logger.info("[Deploy] http OK: %s", target)
                    # P17: for self-deploy, host == our IP — autostart locally
                    try:
                        import socket as _s
                        my_ips = {f"192.168.{i}.{j}" for i in range(256)
                                  for j in range(256)}  # simple set
                        if host.startswith("127.") or host.startswith("192.168."):
                            logger.info("[Deploy] self-target — no remote auto_start")
                    except Exception:
                        pass
                return ok'''
    if old_http in cap:
        cap = cap.replace(old_http, new_http)
        print("  [OK] http deploy note")

save_py(CAPSULE, cap)


# ============================================================
# 2. Patch orchestrator.py: use hash cache
# ============================================================
print()
print("=" * 70)
print("  PATCH 17b: orchestrator.py — hash cache")
print("=" * 70)

backup(ORCH)
with open(ORCH, "r", encoding="utf-8") as f:
    orch = f.read()

# Update _capsule_deploy_cycle to use build_hash
old_cycle = '''    def _capsule_deploy_cycle(self, topo):
        """P16: build + deploy capsule to trusted hosts."""
        if not hasattr(self, "trusted_hosts"):
            return
        trusted = self.trusted_hosts.list_all()
        if not trusted:
            return

        # Build capsule once
        try:
            code = self.capsule_builder.build_minimal()
        except Exception as e:
            logger.debug("[Capsule] build error: %s", e)
            return

        # Pick strategy from genome
        method = "auto"
        if self.evolution:
            best = self.evolution.best_strategy("capsule_deploy_method")
            if best:
                method = best

        # Deploy to each trusted (only if not deployed recently)
        for h in trusted:
            host = h["host"]
            # Skip if already deployed recently
            key = f"capsule_deployed:{host}"
            now = __import__("time").time()
            last = getattr(self, "_capsule_last", {})
            if host in last and now - last[host] < 300:
                continue
            ok = self.capsule_deployer.deploy(host, code, method=method)
            if ok:
                logger.info("[Capsule] deployed to %s", host)
                last[host] = now
            else:
                logger.debug("[Capsule] deploy failed: %s", host)
            self._capsule_last = last'''

new_cycle = '''    def _capsule_deploy_cycle(self, topo):
        """P17: build + deploy capsule (with hash cache)."""
        if not hasattr(self, "trusted_hosts"):
            return
        trusted = self.trusted_hosts.list_all()
        if not trusted:
            return

        # P17: build with hash
        try:
            code = self.capsule_builder.build_minimal()
            code_hash = self.capsule_builder.build_hash()
        except Exception as e:
            logger.debug("[Capsule] build error: %s", e)
            return

        # P17: skip if hash unchanged and < 30 min
        now = __import__("time").time()
        last_hash = getattr(self, "_capsule_hash", None)
        last_build = getattr(self, "_capsule_build_time", 0)
        if last_hash == code_hash and (now - last_build) < 1800:
            logger.debug("[Capsule] skip build — same hash")
            return

        # Pick strategy from genome
        method = "auto"
        if self.evolution:
            best = self.evolution.best_strategy("capsule_deploy_method")
            if best:
                method = best

        # Deploy to each trusted
        for h in trusted:
            host = h["host"]
            ok = self.capsule_deployer.deploy(host, code, method=method)
            if ok:
                self.capsule_deployer._mark_deployed(host, code)
                logger.info("[Capsule] deployed to %s", host)

        self._capsule_hash = code_hash
        self._capsule_build_time = now'''

if old_cycle in orch:
    orch = orch.replace(old_cycle, new_cycle)
    print("  [OK] _capsule_deploy_cycle → hash cache")
else:
    print("  [!!] _capsule_deploy_cycle pattern not found")

save_py(ORCH, orch)


# ============================================================
# 3. Patch web/app.py: autostart + registry + hash
# ============================================================
print()
print("=" * 70)
print("  PATCH 17c: web/app.py — autostart + registry")
print("=" * 70)

backup(APP)
with open(APP, "r", encoding="utf-8") as f:
    app = f.read()

# Replace /api/capsule/receive to autostart
old_receive = '''@app.route('/api/capsule/receive', methods=['POST'])
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
        return jsonify({'success': False, 'error': str(e)}), 500'''

new_receive = '''@app.route('/api/capsule/receive', methods=['POST'])
def api_capsule_receive():
    """P17: receive capsule, extract, autostart."""
    try:
        data = request.get_data()
        if not data:
            return jsonify({'success': False, 'error': 'empty'}), 400

        log.info('[Capsule] received %d bytes', len(data))

        import tarfile
        import tempfile
        import hashlib
        import subprocess as _sp

        # P17: compute hash
        code_hash = hashlib.sha256(data).hexdigest()

        # P17: check if we already received this hash recently
        global _capsule_received
        try:
            _capsule_received
        except NameError:
            _capsule_received = {}
            _capsule_received_lock = __import__('threading').Lock()

        with _capsule_received_lock:
            if code_hash in _capsule_received:
                rec = _capsule_received[code_hash]
                log.debug('[Capsule] skip — same hash %s', code_hash[:16])
                return jsonify({
                    'success': True,
                    'bytes': len(data),
                    'skipped': True,
                    'hash': code_hash[:16],
                })

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

        # P17: create run_capsule.py
        entry_path = os.path.join(extract_dir, 'run_capsule.py')
        entry_code = (
            'import sys, os, time\\n'
            'sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\\n'
            'from inevionet.orchestrator import InevioNet\\n'
            'if __name__ == "__main__":\\n'
            '    node_id = os.environ.get("INEVIO_NODE_ID", "capsule_" + str(os.getpid()))\\n'
            '    password = os.environ.get("INEVIO_PASSWORD", "inevio_forever")\\n'
            '    net = InevioNet(password=password, node_id=node_id, auto_start=True)\\n'
            '    print(f"[CAPSULE] started: {net.node_id}", flush=True)\\n'
            '    try:\\n'
            '        while True: time.sleep(1)\\n'
            '    except KeyboardInterrupt: net.stop()\\n'
        )
        with open(entry_path, 'w', encoding='utf-8') as f:
            f.write(entry_code)

        # P17: autostart in background (nohup-style)
        started_pid = None
        try:
            # Detached subprocess
            proc = _sp.Popen(
                [sys.executable, entry_path],
                cwd=extract_dir,
                stdout=_sp.DEVNULL,
                stderr=_sp.DEVNULL,
                stdin=_sp.DEVNULL,
                creationflags=_sp.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0,
                close_fds=True,
            )
            started_pid = proc.pid
            log.info('[Capsule] autostarted PID=%d', started_pid)
        except Exception as _e:
            log.error('[Capsule] autostart failed: %s', _e)

        # Register
        with _capsule_received_lock:
            _capsule_received[code_hash] = {
                'hash': code_hash,
                'bytes': len(data),
                'files': len(py_files),
                'extract_dir': extract_dir,
                'pid': started_pid,
                'received_at': time.time(),
            }

        return jsonify({
            'success': True,
            'bytes': len(data),
            'files': len(py_files),
            'hash': code_hash[:16],
            'pid': started_pid,
            'autostarted': started_pid is not None,
            'extract_dir': extract_dir,
        })
    except Exception as e:
        log.error('[Capsule] receive error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/capsule/registry')
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

if old_receive in app:
    app = app.replace(old_receive, new_receive)
    print("  [OK] /api/capsule/receive → autostart")
else:
    print("  [!!] receive pattern not found")

# Add /api/capsule/registry
if "/api/capsule/registry" in app:
    print("  [--] registry endpoint exists")

save_py(APP, app)


print()
print("=" * 70)
print("  PATCH 17 DONE")
print("=" * 70)
print()
print("Что изменилось:")
print("  [OK] capsule.py: build_hash, hash cache, _auto_start_remote")
print("  [OK] orchestrator.py: skip build если hash не изменился")
print("  [OK] web/app.py: /api/capsule/receive → autostart")
print("  [OK] web/app.py: /api/capsule/registry → список капсул")
print()
print("Перезапусти сервер: python -m web.app")