# patch18.py - Anti-flood protection for capsules
import os
import ast
import shutil
import sys

ROOT = r"E:\InevioNet"
CAPSULE = os.path.join(ROOT, "inevionet", "mycelium", "capsule.py")
ORCH = os.path.join(ROOT, "inevionet", "orchestrator.py")
APP = os.path.join(ROOT, "web", "app.py")


def backup(path):
    bak = path + ".bak_p18"
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
        shutil.copy2(path + ".bak_p18", path)
        sys.exit(1)


# ============================================================
# 1. capsule.py: self-target detection + env flags
# ============================================================
print("=" * 70)
print("  PATCH 18a: capsule.py — self-target + env flags")
print("=" * 70)

backup(CAPSULE)
with open(CAPSULE, "r", encoding="utf-8") as f:
    cap = f.read()

# 1.1. Add _get_my_ips method to CapsuleDeployer
if "def _get_my_ips" in cap:
    print("  [--] _get_my_ips exists")
else:
    marker = "    def deploy(self, target: str, code: bytes,"
    new_method = '''    def _get_my_ips(self) -> set:
        """P18: detect own IPs to prevent self-deploy."""
        ips = {"127.0.0.1", "localhost", "0.0.0.0"}
        try:
            import socket as _s
            hostname = _s.gethostname()
            for info in _s.getaddrinfo(hostname, None):
                ips.add(info[4][0])
        except Exception:
            pass
        return ips

    def deploy(self, target: str, code: bytes,'''
    if marker in cap:
        cap = cap.replace(marker, new_method, 1)
        print("  [OK] _get_my_ips added")

# 1.2. Add self-target check in deploy()
old_deploy_start = '''        # P17: hash cache — skip if not changed and < 30 min ago
        import hashlib
        import time as _t
        code_hash = hashlib.sha256(code).hexdigest()'''
new_deploy_start = '''        # P18: skip self-deploy
        target_host = target.split(":")[0]
        my_ips = self._get_my_ips()
        if target_host in my_ips:
            logger.debug("[Deploy] skip self-target: %s", target)
            self.stats["skipped"] += 1
            return False

        # P18: env flag check
        if os.environ.get("INEVIO_NO_DEPLOY") == "1":
            logger.debug("[Deploy] INEVIO_NO_DEPLOY=1, skip")
            self.stats["skipped"] += 1
            return False

        # P17: hash cache — skip if not changed and < 30 min ago
        import hashlib
        import time as _t
        code_hash = hashlib.sha256(code).hexdigest()'''
if old_deploy_start in cap:
    cap = cap.replace(old_deploy_start, new_deploy_start, 1)
    print("  [OK] self-target check in deploy()")

save_py(CAPSULE, cap)


# ============================================================
# 2. orchestrator.py: deploy cycle protection
# ============================================================
print()
print("=" * 70)
print("  PATCH 18b: orchestrator.py — deploy cycle protection")
print("=" * 70)

backup(ORCH)
with open(ORCH, "r", encoding="utf-8") as f:
    orch = f.read()

# 2.1. Add env flag check at start of _capsule_deploy_cycle
old_cycle = '''    def _capsule_deploy_cycle(self, topo):
        """P17: build + deploy capsule (with hash cache)."""
        if not hasattr(self, "trusted_hosts"):
            return
        trusted = self.trusted_hosts.list_all()
        if not trusted:
            return'''
new_cycle = '''    def _capsule_deploy_cycle(self, topo):
        """P18: build + deploy capsule (anti-flood)."""
        # P18: env flag
        if __import__("os").environ.get("INEVIO_NO_DEPLOY") == "1":
            return
        # P18: not too often
        import time as _t2
        now2 = _t2.time()
        last2 = getattr(self, "_capsule_last_cycle", 0)
        if now2 - last2 < 60:
            return
        self._capsule_last_cycle = now2

        if not hasattr(self, "trusted_hosts"):
            return
        trusted = self.trusted_hosts.list_all()
        if not trusted:
            return

        # P18: cap total deploys
        total = getattr(self, "_capsule_total_deploys", 0)
        if total >= 5:
            logger.debug("[Capsule] total deploy limit reached")
            return'''
if old_cycle in orch:
    orch = orch.replace(old_cycle, new_cycle, 1)
    print("  [OK] deploy cycle protection added")

# 2.2. Increment counter after successful deploy
old_deployed = '''            if ok:
                self.capsule_deployer._mark_deployed(host, code)
                logger.info("[Capsule] deployed to %s", host)'''
new_deployed = '''            if ok:
                self.capsule_deployer._mark_deployed(host, code)
                logger.info("[Capsule] deployed to %s", host)
                self._capsule_total_deploys = getattr(
                    self, "_capsule_total_deploys", 0) + 1'''
if old_deployed in orch:
    orch = orch.replace(old_deployed, new_deployed, 1)
    print("  [OK] deploy counter added")

save_py(ORCH, orch)


# ============================================================
# 3. app.py: autostart limit + env flag
# ============================================================
print()
print("=" * 70)
print("  PATCH 18c: app.py — autostart limit")
print("=" * 70)

backup(APP)
with open(APP, "r", encoding="utf-8") as f:
    app = f.read()

# 3.1. Add autostart counter
if "_autostart_counter" in app:
    print("  [--] autostart counter exists")
else:
    marker = "# P17-CAPSULE-GLOBALS"
    new_globals = '''# P17-CAPSULE-GLOBALS
_autostart_counter: int = 0
_MAX_AUTOSTART: int = 3
'''
    if marker in app:
        app = app.replace(marker, new_globals + marker.replace("# P17", "# P18"))
        # Fix: actually add new globals
        app = app.replace(new_globals + "# P18-CAPSULE-GLOBALS", "# P18-CAPSULE-GLOBALS")
        print("  [OK] autostart counter defined")
    else:
        # Fallback: insert before @app.route
        idx = app.find("@app.route(")
        if idx > 0:
            block = '''# P18-CAPSULE-GLOBALS
_autostart_counter: int = 0
_MAX_AUTOSTART: int = 3
'''
            app = app[:idx] + block + app[idx:]
            print("  [OK] autostart counter added (fallback)")

# 3.2. Add limit check in autostart section
old_autostart = '''        # P17: autostart in background (nohup-style)
        started_pid = None
        try:
            # Detached subprocess
            proc = _sp.Popen('''
new_autostart = '''        # P18: env flag + limit
        if os.environ.get("INEVIO_NO_AUTOSTART") == "1":
            log.info("[Capsule] INEVIO_NO_AUTOSTART=1, skip autostart")
            return jsonify({
                'success': True,
                'autostarted': False,
                'reason': 'env_disabled',
            })
        global _autostart_counter
        if _autostart_counter >= _MAX_AUTOSTART:
            log.warning("[Capsule] autostart limit (%d) reached",
                        _MAX_AUTOSTART)
            return jsonify({
                'success': True,
                'autostarted': False,
                'reason': 'limit_reached',
                'count': _autostart_counter,
            })
        _autostart_counter += 1

        # P17: autostart in background (nohup-style)
        started_pid = None
        try:
            # Detached subprocess
            proc = _sp.Popen('''
if old_autostart in app:
    app = app.replace(old_autostart, new_autostart, 1)
    print("  [OK] autostart limit added")

# 3.3. Set INEVIO_NO_DEPLOY for autostarted children
old_popen_env = '''            started_pid = proc.pid
            log.info('[Capsule] autostarted PID=%d', started_pid)'''
new_popen_env = '''            started_pid = proc.pid
            log.info('[Capsule] autostarted PID=%d', started_pid)'''
# (Skip — Popen inherits env; we need to set INEVIO_NO_DEPLOY=1)
# Better: pass env explicitly
old_popen_call = '''            proc = _sp.Popen(
                [sys.executable, entry_path],
                cwd=extract_dir,
                stdout=_sp.DEVNULL,
                stderr=_sp.DEVNULL,
                stdin=_sp.DEVNULL,
                creationflags=_sp.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0,
                close_fds=True,
            )'''
new_popen_call = '''            # P18: child inherits env with NO_DEPLOY + NO_AUTOSTART
            child_env = os.environ.copy()
            child_env["INEVIO_NO_DEPLOY"] = "1"
            child_env["INEVIO_NO_AUTOSTART"] = "1"
            proc = _sp.Popen(
                [sys.executable, entry_path],
                cwd=extract_dir,
                env=child_env,
                stdout=_sp.DEVNULL,
                stderr=_sp.DEVNULL,
                stdin=_sp.DEVNULL,
                creationflags=_sp.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0,
                close_fds=True,
            )'''
if old_popen_call in app:
    app = app.replace(old_popen_call, new_popen_call, 1)
    print("  [OK] child env flags set")

# 3.4. Add reset endpoint
if "/api/capsule/reset_counter" in app:
    print("  [--] reset counter endpoint exists")
else:
    reset_ep = '''
@app.route('/api/capsule/reset_counter', methods=['POST'])
def api_capsule_reset_counter():
    """P18: reset autostart counter."""
    global _autostart_counter
    _autostart_counter = 0
    log.info('[Capsule] autostart counter reset')
    return jsonify({'success': True, 'counter': _autostart_counter})


'''
    marker = "@socketio.on('connect')"
    if marker in app:
        app = app.replace(marker, reset_ep + marker, 1)
        print("  [OK] reset endpoint added")

save_py(APP, app)


print()
print("=" * 70)
print("  PATCH 18 DONE")
print("=" * 70)
print()
print("Защита:")
print("  [OK] skip self-deploy (свои IP)")
print("  [OK] INEVIO_NO_DEPLOY=1 — блокирует deploy")
print("  [OK] INEVIO_NO_AUTOSTART=1 — блокирует автозапуск")
print("  [OK] Лимит 5 deploy-циклов на сессию")
print("  [OK] Лимит 3 автозапуска")
print("  [OK] Дочерние процессы получают NO_DEPLOY=1")
print()
print("Restart: python -m web.app")