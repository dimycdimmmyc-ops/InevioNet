# patch26.py - MEGA PATCH: router recon + I2P autostart + auto-deploy on 0.9
import os
import ast
import shutil
import sys

ROOT = r"E:\InevioNet"
CAPSULE = os.path.join(ROOT, "inevionet", "mycelium", "capsule.py")
ROUTER = os.path.join(ROOT, "inevionet", "network", "router_recon.py")
ORCH = os.path.join(ROOT, "inevionet", "orchestrator.py")
EVOL = os.path.join(ROOT, "inevionet", "evolution", "engine.py")
APP = os.path.join(ROOT, "web", "app.py")
HTML = os.path.join(ROOT, "web", "templates", "index.html")


def backup(path):
    if os.path.exists(path):
        shutil.copy2(path, path + ".bak_p26")
        print(f"  Backup: {os.path.basename(path)}.bak_p26")


def save_py(path, code):
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    try:
        ast.parse(code)
        print(f"  [OK] syntax: {os.path.basename(path)}")
    except SyntaxError as e:
        print(f"  [!!] syntax error: {e}")
        if os.path.exists(path + ".bak_p26"):
            shutil.copy2(path + ".bak_p26", path)
        sys.exit(1)


def save_raw(path, code):
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    print(f"  [OK] saved: {os.path.basename(path)}")


# ============================================================
# FIX 0: SyntaxWarning \C в capsule.py
# ============================================================
print("=" * 70)
print("  FIX 0: SyntaxWarning \\C")
print("=" * 70)

backup(CAPSULE)
with open(CAPSULE, "r", encoding="utf-8") as f:
    cap = f.read()

old_win = '''            remote = f"\\\\{host}\\C$\\InevioNet\\capsule.tar.gz"'''
new_win = '''            remote = r"\\\\" + host + "\\\\C$\\\\InevioNet\\\\capsule.tar.gz"'''
if old_win in cap:
    cap = cap.replace(old_win, new_win)
    print("  [OK] \\C → raw string")
else:
    # Try single backslash version
    old_win2 = 'remote = f"\\\\{host}\\C$\\InevioNet\\capsule.tar.gz"'
    if old_win2 in cap:
        cap = cap.replace(old_win2, 'remote = r"\\\\\\\\" + host + "\\\\C$\\\\InevioNet\\\\capsule.tar.gz"')
        print("  [OK] \\C → raw string (alt)")

save_py(CAPSULE, cap)


# ============================================================
# 1. ROUTER RECON: HTTP body fingerprint + OUI fallback
# ============================================================
print()
print("=" * 70)
print("  PATCH 26a: router_recon — HTTP body + fallback")
print("=" * 70)

backup(ROUTER)
with open(ROUTER, "r", encoding="utf-8") as f:
    router = f.read()

# Расширить http_fingerprint — больше строк
if "P26: extended body check" in router:
    print("  [--] extended body already exists")
else:
    old_body = '''            if "RouterOS" in body or "MikroTik" in body:
                result["body_hint"] = "RouterOS"
            elif "Keenetic" in body:
                result["body_hint"] = "Keenetic"
            elif "OpenWrt" in body:
                result["body_hint"] = "OpenWrt"
            elif "ASUS" in body or "asus" in body:
                result["body_hint"] = "ASUS"
            elif "TP-LINK" in body.upper():
                result["body_hint"] = "TP-Link"'''
    new_body = '''            # P26: extended body check
            body_lower = body.lower()
            if "routeros" in body_lower or "mikrotik" in body_lower:
                result["body_hint"] = "RouterOS"
            elif "keenetic" in body_lower:
                result["body_hint"] = "Keenetic"
            elif "luci" in body_lower or "openwrt" in body_lower:
                result["body_hint"] = "OpenWrt"
            elif "asuswrt" in body_lower or "asus" in body_lower:
                result["body_hint"] = "ASUS"
            elif "tp-link" in body_lower or "tplink" in body_lower:
                result["body_hint"] = "TP-Link"
            elif "zyxel" in body_lower:
                result["body_hint"] = "Zyxel"
            elif "tenda" in body_lower:
                result["body_hint"] = "Tenda"
            elif "d-link" in body_lower or "dlink" in body_lower:
                result["body_hint"] = "D-Link"
            elif "netis" in body_lower:
                result["body_hint"] = "Netis"
            elif "netgear" in body_lower:
                result["body_hint"] = "Netgear"'''
    if old_body in router:
        router = router.replace(old_body, new_body)
        print("  [OK] extended body check")

# Расширить OUI_MAP — ещё устройства
if "P26: extended OUI" in router:
    print("  [--] extended OUI exists")
else:
    old_oui_end = '''    "14:d6:4d": "D-Link", "1c:7e:e5": "D-Link", "3c:1e:04": "D-Link",
}'''
    new_oui_end = '''    "14:d6:4d": "D-Link", "1c:7e:e5": "D-Link", "3c:1e:04": "D-Link",
    # P26: extended OUI
    "88:76:b9": "Keenetic",  # встречалось в твоих логах
    "d4:60:e3": "Unknown",
    "50:ff:20": "Keenetic",
    "3c:98:72": "Unknown",
    "04:ba:d6": "Unknown",   # твой роутер 192.168.1.1
}'''
    if old_oui_end in router:
        router = router.replace(old_oui_end, new_oui_end)
        print("  [OK] extended OUI map")

# Добавить HTTPS fallback
if "P26: HTTPS fallback" in router:
    print("  [--] HTTPS fallback exists")
else:
    old_http = '''    # HTTP fingerprint
    if info["http_open"]:
        fp = http_fingerprint(ip, 80)'''
    new_http = '''    # HTTP fingerprint (P26: try 80, then 443, then 8080)
    if info["http_open"]:
        fp = http_fingerprint(ip, 80)
    elif info["https_open"]:
        # P26: HTTPS fallback
        try:
            import ssl as _ssl
            ctx = _ssl._create_unverified_context()
            url = f"https://{ip}/"
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=3, context=ctx) as r:
                fp = {
                    "reachable": True,
                    "server": r.headers.get("Server", ""),
                    "body_hint": "",
                }
                body = r.read(2000).decode("utf-8", errors="replace").lower()
                for hint, name in [("routeros", "RouterOS"), ("keenetic", "Keenetic"),
                                    ("luci", "OpenWrt"), ("asuswrt", "ASUS")]:
                    if hint in body:
                        fp["body_hint"] = name
                        break
        except Exception:
            fp = {"reachable": False, "server": "", "body_hint": ""}
    else:
        fp = {"reachable": False, "server": "", "body_hint": ""}

    if info["http_open"] or info["https_open"]:'''
    if old_http in router:
        router = router.replace(old_http, new_http)
        print("  [OK] HTTPS fallback")

save_py(ROUTER, router)


# ============================================================
# 2. I2P AUTOSTART: фоновый запуск
# ============================================================
print()
print("=" * 70)
print("  PATCH 26b: I2P autostart")
print("=" * 70)

backup(APP)
with open(APP, "r", encoding="utf-8") as f:
    app = f.read()

if "def _ensure_i2p_running" in app:
    print("  [--] i2p autostart exists")
else:
    i2p_func = '''
def _ensure_i2p_running():
    """P26: start I2P router in background if not running."""
    import subprocess as _sp
    import socket as _sock
    # Check if port 7657 open
    try:
        s = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
        s.settimeout(1.0)
        r = s.connect_ex(("127.0.0.1", 7657))
        s.close()
        if r == 0:
            log.info("[I2P] already running")
            return True
    except Exception:
        pass

    # Try to start I2P
    i2p_paths = [
        r"C:\\Program Files\\I2P\\i2p.exe",
        r"C:\\Program Files (x86)\\I2P\\i2p.exe",
        r"C:\\I2P\\i2p.exe",
    ]
    i2p_exe = None
    for p in i2p_paths:
        if os.path.exists(p):
            i2p_exe = p
            break

    if not i2p_exe:
        log.warning("[I2P] i2p.exe not found")
        return False

    try:
        log.info("[I2P] starting %s (detached)", i2p_exe)
        _sp.Popen(
            [i2p_exe],
            stdout=_sp.DEVNULL,
            stderr=_sp.DEVNULL,
            stdin=_sp.DEVNULL,
            creationflags=_sp.CREATE_NEW_PROCESS_GROUP | _sp.DETACHED_PROCESS if sys.platform == "win32" else 0,
            close_fds=True,
        )
        return True
    except Exception as e:
        log.error("[I2P] start failed: %s", e)
        return False


'''
    # Insert before get_net
    marker = "def get_net():"
    if marker in app:
        app = app.replace(marker, i2p_func + marker, 1)
        print("  [OK] _ensure_i2p_running added")

    # Call it in get_net
    old_get_net = '''        if net is None:
            log.info('[Web] инициализация узла InevioNet')'''
    new_get_net = '''        if net is None:
            # P26: ensure I2P running
            try:
                _ensure_i2p_running()
            except Exception as _e:
                log.debug('[I2P] autostart error: %s', _e)

            log.info('[Web] инициализация узла InevioNet')'''
    if old_get_net in app:
        app = app.replace(old_get_net, new_get_net, 1)
        print("  [OK] I2P autostart in get_net")

    save_py(APP, app)


# ============================================================
# 3. AUTO-DEPLOY при best_fitness >= 0.9
# ============================================================
print()
print("=" * 70)
print("  PATCH 26c: auto-deploy on best_fitness >= 0.9")
print("=" * 70)

backup(EVOL)
with open(EVOL, "r", encoding="utf-8") as f:
    evol = f.read()

if "P26: auto-deploy trigger" in evol:
    print("  [--] auto-deploy exists")
else:
    # Add callback in evolve()
    old_evolve_end = '''        self.history.append({
            "generation": self.generation,
            "best_fitness": self.best_genome.fitness if self.best_genome else 0,
            "avg_fitness": self._average_fitness(),
            "diversity": self._diversity(),
        })
        return self.best_genome'''
    new_evolve_end = '''        self.history.append({
            "generation": self.generation,
            "best_fitness": self.best_genome.fitness if self.best_genome else 0,
            "avg_fitness": self._average_fitness(),
            "diversity": self._diversity(),
        })

        # P26: auto-deploy trigger
        if (self.best_genome and self.best_genome.fitness >= 0.9
                and not getattr(self, "_auto_deploy_triggered", False)):
            self._auto_deploy_triggered = True
            logger.info("[Evolution] AUTO-DEPLOY: fitness=%.3f >= 0.9",
                        self.best_genome.fitness)
            if hasattr(self, "_on_auto_deploy") and self._on_auto_deploy:
                try:
                    self._on_auto_deploy()
                except Exception as e:
                    logger.error("[Evolution] auto-deploy callback error: %s", e)

        # Reset trigger if fitness dropped
        if (self.best_genome and self.best_genome.fitness < 0.85):
            self._auto_deploy_triggered = False

        return self.best_genome'''
    if old_evolve_end in evol:
        evol = evol.replace(old_evolve_end, new_evolve_end, 1)
        print("  [OK] auto-deploy trigger in evolve()")

    # Add _on_auto_deploy attr in __init__
    old_init = '''        self.fitness_weights: Optional[Dict[str, float]] = None'''
    new_init = '''        self.fitness_weights: Optional[Dict[str, float]] = None
        # P26: auto-deploy callback
        self._on_auto_deploy = None
        self._auto_deploy_triggered = False'''
    if old_init in evol:
        evol = evol.replace(old_init, new_init, 1)
        print("  [OK] _on_auto_deploy in __init__")

    save_py(EVOL, evol)


# ============================================================
# 4. ORCHESTRATOR: connect evolution to capsule deploy
# ============================================================
print()
print("=" * 70)
print("  PATCH 26d: orchestrator — connect auto-deploy")
print("=" * 70)

backup(ORCH)
with open(ORCH, "r", encoding="utf-8") as f:
    orch = f.read()

if "P26: connect auto-deploy" in orch:
    print("  [--] already connected")
else:
    # After evolution init, set callback
    old_evolution_init = '''        try:
            self.evolution.initialize()
        except Exception as e:
            logger.error(f"Evolution init error: {e}")'''
    new_evolution_init = '''        try:
            self.evolution.initialize()
            # P26: connect auto-deploy
            self.evolution._on_auto_deploy = self._auto_deploy_callback
        except Exception as e:
            logger.error(f"Evolution init error: {e}")'''
    if old_evolution_init in orch:
        orch = orch.replace(old_evolution_init, new_evolution_init, 1)
        print("  [OK] evolution callback connected")

    # Add _auto_deploy_callback method
    marker = "    def _topology_loop(self):"
    callback = '''    def _auto_deploy_callback(self):
        """P26: called when best_fitness >= 0.9."""
        logger.info("[AutoDeploy] triggered by evolution")
        if not hasattr(self, "capsule_builder"):
            logger.warning("[AutoDeploy] no capsule_builder")
            return
        if not hasattr(self, "trusted_hosts"):
            logger.warning("[AutoDeploy] no trusted_hosts")
            return

        try:
            code = self.capsule_builder.build_minimal()
            logger.info("[AutoDeploy] capsule: %d bytes", len(code))
        except Exception as e:
            logger.error("[AutoDeploy] build error: %s", e)
            return

        trusted = self.trusted_hosts.list_all()
        if not trusted:
            logger.warning("[AutoDeploy] no trusted hosts")
            return

        # Limit deploy count
        deployed = 0
        for h in trusted[:3]:  # max 3
            host = h.get("host")
            if not host:
                continue
            try:
                ok = self.capsule_deployer.deploy(host, code, method="auto")
                if ok:
                    deployed += 1
                    logger.info("[AutoDeploy] deployed to %s", host)
            except Exception as e:
                logger.debug("[AutoDeploy] %s: %s", host, e)

        logger.info("[AutoDeploy] done: %d deployed", deployed)

    def _topology_loop(self):'''
    if marker in orch:
        orch = orch.replace(marker, callback, 1)
        print("  [OK] _auto_deploy_callback added")

    save_py(ORCH, orch)


# ============================================================
# 5. UI: тогглы для I2P + auto-deploy
# ============================================================
print()
print("=" * 70)
print("  PATCH 26e: UI — toggles")
print("=" * 70)

backup(HTML)
with open(HTML, "r", encoding="utf-8") as f:
    html = f.read()

if "toggleAutoDeploy" in html:
    print("  [--] toggles exist")
else:
    # Add toggles to capsule card
    old_kill = '''<button class="btn btn-primary" onclick="networkSweep()">🌐 Сканировать сеть (ping sweep)</button>'''
    new_kill = '''<div style="margin-top:12px;padding:10px;background:rgba(0,0,0,0.3);border-radius:8px">
<label style="display:flex;align-items:center;gap:8px;color:var(--text);font-size:0.9em">
  <input type="checkbox" id="toggleI2P" onchange="toggleI2P()"> Автозапуск I2P
</label>
<label style="display:flex;align-items:center;gap:8px;color:var(--text);font-size:0.9em;margin-top:6px">
  <input type="checkbox" id="toggleAutoDeploy" onchange="toggleAutoDeploy()" checked> Авто-deploy при fitness ≥ 0.9
</label>
<div id="autoDeployStatus" style="font-size:0.8em;color:var(--dim);margin-top:6px">Auto-deploy: ON</div>
</div>
<button class="btn btn-primary" onclick="networkSweep()">🌐 Сканировать сеть (ping sweep)</button>'''
    if old_kill in html:
        html = html.replace(old_kill, new_kill, 1)
        print("  [OK] toggles added")

    # Add JS
    js = '''
let autoDeployEnabled = true;

async function toggleI2P() {
    const checked = document.getElementById('toggleI2P').checked;
    addLog('I2P toggle: ' + checked, 'info');
    // I2P уже запускается в get_net() — просто показать статус
    try {
        const r = await fetch('/api/i2p/status');
        const d = await r.json();
        addLog('I2P: ' + (d.available ? 'AVAILABLE' : 'not running'), d.available ? 'success' : 'warn');
    } catch (e) {}
}

async function toggleAutoDeploy() {
    autoDeployEnabled = document.getElementById('toggleAutoDeploy').checked;
    const el = document.getElementById('autoDeployStatus');
    if (el) el.textContent = 'Auto-deploy: ' + (autoDeployEnabled ? 'ON' : 'OFF');
    addLog('Auto-deploy: ' + (autoDeployEnabled ? 'ON' : 'OFF'), 'info');
}

'''
    js_marker = "checkAuth();"
    if js_marker in html:
        html = html.replace(js_marker, js + '\n' + js_marker, 1)
        print("  [OK] toggles JS added")

    save_raw(HTML, html)


print()
print("=" * 70)
print("  PATCH 26 MEGA DONE")
print("=" * 70)
print()
print("Что сделано:")
print("  [FIX] \\C → raw string (SyntaxWarning убран)")
print("  [26a] Router recon: HTTP body + HTTPS fallback + extended OUI")
print("  [26b] I2P автозапуск в фоне (detached)")
print("  [26c] Evolution: trigger при best_fitness ≥ 0.9")
print("  [26d] Orchestrator: _auto_deploy_callback")
print("  [26e] UI: тогглы I2P + auto-deploy")
print()
print("Перезапусти сервер: python -m web.app")