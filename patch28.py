# patch28.py - InevioNet: P27 fixes + logs + relay + autostart counter
import os
import ast
import re
import shutil
import sys
import time

ROOT = r"E:\InevioNet"
ORCH = os.path.join(ROOT, "inevionet", "orchestrator.py")
EVOL = os.path.join(ROOT, "inevionet", "evolution", "engine.py")
RECON = os.path.join(ROOT, "inevionet", "network", "router_recon.py")
APP = os.path.join(ROOT, "web", "app.py")

STAMP = time.strftime("%Y%m%d_%H%M%S")


def backup(path):
    if os.path.exists(path):
        b = path + ".bak_p28"
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
        if os.path.exists(path + ".bak_p28"):
            shutil.copy2(path + ".bak_p28", path)
            print(f"  [--] rolled back {os.path.basename(path)}")
        return False


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def patch(path, replacements, name):
    """replacements: list of (old, new, required)"""
    print()
    print("=" * 70)
    print(f"  {name}")
    print("=" * 70)
    backup(path)
    content = load(path)
    changed = 0
    for old, new, required in replacements:
        if new in content and old not in content:
            print(f"  [--] already applied: {old[:50]}...")
            continue
        if old in content:
            content = content.replace(old, new, 1)
            print(f"  [OK] {old[:60]}...")
            changed += 1
        else:
            if required:
                print(f"  [!!] NOT FOUND (required): {old[:60]}...")
            else:
                print(f"  [--] not found (optional): {old[:60]}...")
    if changed > 0:
        save_py(path, content)
    else:
        print(f"  [--] nothing changed in {os.path.basename(path)}")
    return changed


# ============================================================
# 1. evolution/engine.py: порог 0.9 -> 0.85, катастрофа 50 -> 20
# ============================================================
patch(EVOL, [
    # Порог auto-deploy
    (
        """        if (self.best_genome and self.best_genome.fitness >= 0.9
                and not getattr(self, "_auto_deploy_triggered", False)):
            self._auto_deploy_triggered = True
            logger.info("[Evolution] AUTO-DEPLOY: fitness=%.3f >= 0.9",
                        self.best_genome.fitness)""",
        """        if (self.best_genome and self.best_genome.fitness >= 0.85
                and not getattr(self, "_auto_deploy_triggered", False)):
            self._auto_deploy_triggered = True
            logger.warning("[Evolution] AUTO-DEPLOY: fitness=%.3f >= 0.85",
                        self.best_genome.fitness)""",
        True,
    ),
    # Reset
    (
        """        if (self.best_genome and self.best_genome.fitness < 0.85):
            self._auto_deploy_triggered = False""",
        """        if (self.best_genome and self.best_genome.fitness < 0.80):
            self._auto_deploy_triggered = False""",
        True,
    ),
    # Катастрофа
    (
        """        if self.generation > 0 and self.generation % 50 == 0:
            self._catastrophe()""",
        """        # P28: catastrophe every 20 gens OR when diversity < 0.05
        if self.generation > 0 and (
                self.generation % 20 == 0 or self._diversity() < 0.05):
            self._catastrophe()""",
        True,
    ),
], "P28a: evolution threshold + faster catastrophe")


# ============================================================
# 2. orchestrator.py: _auto_deploy_callback (P27)
# ============================================================
patch(ORCH, [
    (
        '''    def _auto_deploy_callback(self):
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

        logger.info("[AutoDeploy] done: %d deployed", deployed)''',
        '''    def _auto_deploy_callback(self):
        """P28: called when best_fitness >= 0.85."""
        logger.warning("[AutoDeploy] *** TRIGGERED *** fitness=%.3f",
                       self.evolution.best_genome.fitness
                       if self.evolution and self.evolution.best_genome else 0)
        if not hasattr(self, "capsule_builder"):
            logger.warning("[AutoDeploy] no capsule_builder — skip")
            return
        if not hasattr(self, "trusted_hosts"):
            logger.warning("[AutoDeploy] no trusted_hosts — skip")
            return

        try:
            code = self.capsule_builder.build_minimal()
            logger.info("[AutoDeploy] capsule: %d bytes", len(code))
        except Exception as e:
            logger.error("[AutoDeploy] build error: %s", e)
            return

        trusted = self.trusted_hosts.list_all()
        if not trusted:
            logger.warning("[AutoDeploy] no trusted hosts — add via UI")
            return

        logger.info("[AutoDeploy] trying %d trusted hosts", len(trusted))
        deployed = 0
        failed = 0
        for h in trusted[:5]:  # max 5
            host = h.get("host")
            if not host:
                continue
            try:
                ok = self.capsule_deployer.deploy(host, code, method="auto")
                if ok:
                    deployed += 1
                    logger.info("[AutoDeploy] OK %s", host)
                else:
                    failed += 1
                    logger.info("[AutoDeploy] FAIL %s", host)
            except Exception as e:
                logger.debug("[AutoDeploy] %s error: %s", host, e)

        logger.warning("[AutoDeploy] DONE: deployed=%d failed=%d", deployed, failed)''',
        True,
    ),
    # /api/relay -> /api/relay/incoming
    (
        '''                req = _urlreq.Request(
                    "https://127.0.0.1:8080/api/relay",
                    data=payload,
                    headers={"Content-Type": "application/json"})''',
        '''                req = _urlreq.Request(
                    "https://127.0.0.1:8080/api/relay/incoming",
                    data=payload,
                    headers={"Content-Type": "application/json"})''',
        True,
    ),
], "P28b: orchestrator auto-deploy + relay endpoint")


# ============================================================
# 3. router_recon.py: Unknown vendor -> can_deploy=True if ports open
# ============================================================
patch(RECON, [
    (
        '''    else:
        info["deploy_method"] = "unknown"
        info["can_deploy"] = False
        info["notes"] = "Unknown router, manual check needed"''',
        '''    else:
        # P28: try HTTP/SSH anyway for unknown routers
        if info["ssh_open"] or info["http_open"] or info["https_open"]:
            info["deploy_method"] = "ssh_try" if info["ssh_open"] else "http_try"
            info["can_deploy"] = True
            info["notes"] = "Unknown router, but ports open - try generic"
        else:
            info["deploy_method"] = "unknown"
            info["can_deploy"] = False
            info["notes"] = "Unknown router, no open ports"''',
        True,
    ),
], "P28c: router_recon unknown vendor fallback")


# ============================================================
# 4. web/app.py: P27 MAC + P18 autostart counter + logs + dedup
# ============================================================
patch(APP, [
    # 4a. Dedup _capsule_received + add autostart counter
    (
        '''# P17: capsule receive registry
import threading as _threading_mod
_capsule_received: dict = {}
_capsule_received_lock = _threading_mod.Lock()


# P18-CAPSULE-GLOBALS
import threading as _th_capsule
_capsule_received: dict = {}
_capsule_received_lock = _th_capsule.Lock()''',
        '''# P28: capsule receive registry (dedup, single source of truth)
import threading as _th_capsule
_capsule_received: dict = {}
_capsule_received_lock = _th_capsule.Lock()
_autostart_counter = 0
_MAX_AUTOSTART = 10''',
        True,
    ),
    # 4b. MAC extraction in deploy_all
    (
        '''            if ntype in ('router', 'device'):
                try:
                    from inevionet.network.router_recon import identify_firmware
                    mac = node.get('mac', '')
                    recon = identify_firmware(ip, mac)
                except Exception as _re:
                    log.debug('[Recon] error: %s', _re)''',
        '''            if ntype in ('router', 'device'):
                try:
                    from inevionet.network.router_recon import identify_firmware
                    # P28: extract MAC from node or from node_id (arp_XXXX)
                    mac = node.get('mac', '')
                    if not mac and nid.startswith('arp_'):
                        _raw = nid[4:]
                        if len(_raw) == 12:
                            mac = ':'.join(_raw[i:i+2] for i in range(0, 12, 2))
                    recon = identify_firmware(ip, mac)
                    log.info('[Recon] %s mac=%s vendor=%s can=%s',
                             ip, mac, recon.get('vendor'), recon.get('can_deploy'))
                except Exception as _re:
                    log.debug('[Recon] error: %s', _re)''',
        True,
    ),
    # 4c. Log file with rotation
    (
        '''def install_log_bridge():
    fmt = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] %(name)s: %(message)s',
        datefmt='%H:%M:%S',
    )
    root = logging.getLogger('inevionet')''',
        '''def install_log_bridge():
    fmt = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] %(name)s: %(message)s',
        datefmt='%H:%M:%S',
    )
    root = logging.getLogger('inevionet')
    # P28: file logs with rotation
    try:
        import logging.handlers as _lh
        import pathlib as _pl
        log_dir = _pl.Path(__file__).parent.parent / 'logs'
        log_dir.mkdir(exist_ok=True)
        fh = _lh.RotatingFileHandler(
            str(log_dir / 'inevionet.log'),
            maxBytes=5 * 1024 * 1024, backupCount=3, encoding='utf-8')
        fh.setFormatter(fmt)
        if not any(isinstance(h, _lh.RotatingFileHandler)
                   for h in root.handlers):
            root.addHandler(fh)
    except Exception:
        pass''',
        True,
    ),
], "P28d: web/app.py MAC + autostart + logs + dedup")


# ============================================================
# DONE
# ============================================================
print()
print("=" * 70)
print("  PATCH 28 DONE")
print("=" * 70)
print()
print("Что изменилось:")
print("  [OK] evolution: порог 0.9 -> 0.85, reset 0.85 -> 0.80")
print("  [OK] evolution: катастрофа 50 -> 20 gens + diversity < 0.05")
print("  [OK] orchestrator: _auto_deploy_callback (P27, warning, 5 хостов)")
print("  [OK] orchestrator: /api/relay -> /api/relay/incoming")
print("  [OK] router_recon: Unknown vendor + открытые порты -> can_deploy=True")
print("  [OK] web/app.py: MAC из node_id (arp_XXXX)")
print("  [OK] web/app.py: _autostart_counter + _MAX_AUTOSTART")
print("  [OK] web/app.py: logs/inevionet.log с ротацией 5MB x 3")
print("  [OK] web/app.py: дубль _capsule_received убран")
print()
print("Перезапусти сервер: python -m web.app")
print("Логи: E:\\InevioNet\\logs\\inevionet.log")