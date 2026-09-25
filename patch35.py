# patch35.py - InevioNet: _capsule_deploy_cycle recon + _deploy_http universal + logs
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
ORCH = os.path.join(ROOT, "inevionet", "orchestrator.py")
CAPSULE = os.path.join(ROOT, "inevionet", "mycelium", "capsule.py")


def backup(path):
    if os.path.exists(path):
        b = path + ".bak_p35"
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
        if os.path.exists(path + ".bak_p35"):
            shutil.copy2(path + ".bak_p35", path)
        return False


def patch(path, replacements, name):
    print()
    print("=" * 70)
    print(f"  {name}")
    print("=" * 70)
    backup(path)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    changed = 0
    for old, new, required in replacements:
        if new in content and old not in content:
            print(f"  [--] already applied")
            continue
        if old in content:
            content = content.replace(old, new, 1)
            print(f"  [OK] {old[:60].strip()}...")
            changed += 1
        else:
            print(f"  [!!] NOT FOUND: {old[:60].strip()}...")
    if changed > 0:
        save_py(path, content)


# ============================================================
# P35a. orchestrator.py: _capsule_deploy_cycle -> recon method
# ============================================================
patch(ORCH, [
    (
        '''        # Deploy to each trusted
        for h in trusted:
            host = h["host"]
            ok = self.capsule_deployer.deploy(host, code, method=method)
            if ok:
                self.capsule_deployer._mark_deployed(host, code)
                logger.info("[Capsule] deployed to %s", host)
                self._capsule_total_deploys = getattr(
                    self, "_capsule_total_deploys", 0) + 1''',
        '''        # P35: Deploy to each trusted (recon method)
        for h in trusted:
            host = h["host"]
            ip = host.split(':')[0]
            _method = method
            try:
                from .network.router_recon import identify_firmware
                _recon = identify_firmware(ip, "")
                if _recon.get('can_deploy'):
                    _method = _recon.get('deploy_method', method)
                    logger.info("[Capsule] %s -> method=%s", host, _method)
            except Exception as _re:
                logger.debug("[Capsule] recon error: %s", _re)
            ok = self.capsule_deployer.deploy(host, code, method=_method)
            if ok:
                self.capsule_deployer._mark_deployed(host, code)
                logger.info("[Capsule] deployed to %s", host)
                self._capsule_total_deploys = getattr(
                    self, "_capsule_total_deploys", 0) + 1''',
        True,
    ),
], "P35a: _capsule_deploy_cycle recon method")


# ============================================================
# P35b. capsule.py: _deploy_http_mts logging
# ============================================================
patch(CAPSULE, [
    (
        '''        for port in (80, 443, 8080, 8443):
            scheme = "https" if port in (443, 8443) else "http"
            url = f"{scheme}://{host}:{port}/api/capsule/receive"
            try:
                req = urllib.request.Request(
                    url, data=code,
                    headers={"Content-Type": "application/octet-stream"},
                    method="POST")
                with urllib.request.urlopen(req, timeout=5, context=ctx) as r:
                    if r.status == 200:
                        logger.info("[Deploy] http_mts OK: %s (port %d)", target, port)
                        return True
            except Exception as e:
                logger.debug("[Deploy] http_mts %s:%d: %s", host, port, e)
                continue''',
        '''        for port in (80, 443, 8080, 8443):
            scheme = "https" if port in (443, 8443) else "http"
            url = f"{scheme}://{host}:{port}/api/capsule/receive"
            logger.info("[Deploy] http_mts trying %s:%d", host, port)
            try:
                req = urllib.request.Request(
                    url, data=code,
                    headers={"Content-Type": "application/octet-stream"},
                    method="POST")
                with urllib.request.urlopen(req, timeout=5, context=ctx) as r:
                    if r.status == 200:
                        logger.info("[Deploy] http_mts OK: %s (port %d)", target, port)
                        return True
            except Exception as e:
                logger.debug("[Deploy] http_mts %s:%d: %s", host, port, e)
                continue''',
        True,
    ),
    # P35c: _deploy_http universal (80/8080/443/8443)
    (
        '''    def _deploy_http(self, target: str, code: bytes) -> bool:
        try:
            import urllib.request
            host = target.split(":")[0]
            # P16-http: use https on 8080 (matches web.app)
            import ssl as _ssl
            ctx = _ssl._create_unverified_context()
            url = f"https://{host}:8080/api/capsule/receive"
            req = urllib.request.Request(
                url, data=code,
                headers={"Content-Type": "application/octet-stream"},
                method="POST")
            with urllib.request.urlopen(req, timeout=10, context=ctx) as r:
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
                return ok
        except Exception as e:
            logger.debug("[Deploy] http error: %s", e)
            return False''',
        '''    def _deploy_http(self, target: str, code: bytes) -> bool:
        """P35: try HTTP/HTTPS on 80/8080/443/8443."""
        import urllib.request
        import ssl as _ssl
        host = target.split(":")[0]
        ctx = _ssl._create_unverified_context()
        for port in (80, 8080, 443, 8443):
            scheme = "https" if port in (443, 8443) else "http"
            url = f"{scheme}://{host}:{port}/api/capsule/receive"
            logger.info("[Deploy] http trying %s:%d", host, port)
            try:
                req = urllib.request.Request(
                    url, data=code,
                    headers={"Content-Type": "application/octet-stream"},
                    method="POST")
                with urllib.request.urlopen(req, timeout=5, context=ctx) as r:
                    if r.status == 200:
                        logger.info("[Deploy] http OK: %s (port %d)", target, port)
                        return True
            except Exception as e:
                logger.debug("[Deploy] http %s:%d: %s", host, port, e)
                continue
        return False''',
        True,
    ),
], "P35b/c: capsule http_mts logs + http universal")


print()
print("=" * 70)
print("  PATCH 35 DONE")
print("=" * 70)
print()
print("  [OK] _capsule_deploy_cycle -> recon method")
print("  [OK] _deploy_http_mts -> logger.info")
print("  [OK] _deploy_http -> 80/8080/443/8443")
print()
print("Перезапусти: python -m web.app")