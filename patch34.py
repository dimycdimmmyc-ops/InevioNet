# patch34.py - InevioNet: auto-deploy http_mts + BLE filter + auth fallback
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
ORCH = os.path.join(ROOT, "inevionet", "orchestrator.py")
APP = os.path.join(ROOT, "web", "app.py")


def backup(path):
    if os.path.exists(path):
        b = path + ".bak_p34"
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
        if os.path.exists(path + ".bak_p34"):
            shutil.copy2(path + ".bak_p34", path)
            print("  [--] rolled back")
        return False


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def patch_py(path, replacements, name):
    print()
    print("=" * 70)
    print(f"  {name}")
    print("=" * 70)
    backup(path)
    content = load(path)
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
            if required:
                print(f"  [!!] NOT FOUND: {old[:60].strip()}...")
    if changed > 0:
        return save_py(path, content)
    print("  [--] nothing changed")
    return True


# ============================================================
# P34a. orchestrator.py: _auto_deploy_callback -> recon method
# ============================================================
patch_py(ORCH, [
    (
        '''        # Limit deploy count
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
        '''        # P34: use recon to pick deploy method
        deployed = 0
        for h in trusted[:5]:  # max 5
            host = h.get("host")
            if not host:
                continue
            ip = host.split(':')[0]
            method = "auto"
            try:
                from .network.router_recon import identify_firmware
                recon = identify_firmware(ip, "")
                if recon.get('can_deploy'):
                    method = recon.get('deploy_method', 'auto')
                    logger.info("[AutoDeploy] %s -> method=%s (vendor=%s)",
                                host, method, recon.get('vendor'))
            except Exception as _re:
                logger.debug("[AutoDeploy] recon error: %s", _re)
            try:
                ok = self.capsule_deployer.deploy(host, code, method=method)
                if ok:
                    deployed += 1
                    logger.info("[AutoDeploy] OK %s", host)
                else:
                    logger.info("[AutoDeploy] FAIL %s", host)
            except Exception as e:
                logger.debug("[AutoDeploy] %s: %s", host, e)

        logger.warning("[AutoDeploy] done: %d deployed", deployed)''',
        True,
    ),
], "P34a: orchestrator auto-deploy uses recon method")


# ============================================================
# P34b. web/app.py: BLE filter (skip Windows service records)
# ============================================================
patch_py(APP, [
    (
        '''            for x in d:
                iid = x.get('InstanceId', '')
                # P29: only real BLE devices (skip BTHENUM/BTHENUM_USB)
                if not iid.startswith('BTHLE'):
                    continue
                out.append({
                    'name': x.get('Name', 'BT'),
                    'id': iid.replace('\\\\', '_'),
                })''',
        '''            for x in d:
                iid = x.get('InstanceId', '')
                name = x.get('Name', '')
                # P34: skip Windows service records ({GUID}, DEV_, empty)
                if not iid.startswith('BTHLE'):
                    continue
                if not name or len(name) < 3:
                    continue
                if name.startswith('BTHLE') or '{' in name:
                    continue
                if 'DEV_' in iid:
                    continue
                out.append({
                    'name': name,
                    'id': iid.replace('\\\\', '_'),
                })''',
        True,
    ),
], "P34b: BLE filter (skip service records)")


# ============================================================
# P34c. web/app.py: auth fallback via akm
# ============================================================
patch_py(APP, [
    (
        '''            # P32: decode auth
            try:
                if r.auth and isinstance(r.auth, (list, tuple)) and len(r.auth) > 0:
                    auth_code = int(r.auth[0])
                elif r.auth:
                    auth_code = int(r.auth)
                else:
                    auth_code = -1
                auth = AUTH_MAP.get(auth_code, 'unknown')
            except Exception:
                auth = 'unknown'
''',
        '''            # P34: decode auth + fallback by akm
            try:
                if r.auth and isinstance(r.auth, (list, tuple)) and len(r.auth) > 0:
                    auth_code = int(r.auth[0])
                elif r.auth:
                    auth_code = int(r.auth)
                else:
                    auth_code = -1
                auth = AUTH_MAP.get(auth_code)
                if not auth:
                    # P34: try akm
                    akm_list = [str(a) for a in (r.akm or [])]
                    akm_str = ' '.join(akm_list).upper()
                    if 'WPA3' in akm_str:
                        auth = 'WPA3'
                    elif 'WPA2' in akm_str:
                        auth = 'WPA2'
                    elif 'WPA' in akm_str:
                        auth = 'WPA'
                    else:
                        auth = 'unknown'
            except Exception:
                auth = 'unknown'
''',
        True,
    ),
], "P34c: auth fallback via akm")


# ============================================================
# DONE
# ============================================================
print()
print("=" * 70)
print("  PATCH 34 DONE")
print("=" * 70)
print()
print("  [OK] orchestrator: _auto_deploy_callback -> recon method (http_mts)")
print("  [OK] web/app.py: BLE filter (skip Windows service records)")
print("  [OK] web/app.py: auth fallback via akm")
print()
print("Перезапусти: python -m web.app")
print("Проверка:")
print("  Get-Content logs\\inevionet.log -Tail 50 | Select-String 'http_mts|AutoDeploy'")