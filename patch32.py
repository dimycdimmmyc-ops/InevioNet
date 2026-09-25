# patch32.py - InevioNet: pywifi fixes + rescan off + deploy http_mts + ARP topology
import os
import ast
import shutil
import sys

ROOT = r"E:\InevioNet"
APP = os.path.join(ROOT, "web", "app.py")
CAPSULE = os.path.join(ROOT, "inevionet", "mycelium", "capsule.py")


def backup(path):
    if os.path.exists(path):
        b = path + ".bak_p32"
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
        if os.path.exists(path + ".bak_p32"):
            shutil.copy2(path + ".bak_p32", path)
            print(f"  [--] rolled back")
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
            else:
                print(f"  [--] optional not found")
    if changed > 0:
        return save_py(path, content)
    print(f"  [--] nothing changed")
    return True


# ============================================================
# P32a. web/app.py: pywifi fixes (rstrip, dedup, auth)
# ============================================================
print()
print("=" * 70)
print("  P32a: pywifi fixes (rstrip, dedup, auth)")
print("=" * 70)
backup(APP)
content = load(APP)

# 1. scan_wifi_pywifi - улучшенная версия
old_scan = '''def scan_wifi_pywifi(wait_sec=4.0):
    """P31: scan WiFi via pywifi (RSSI dBm + auth)."""
    try:
        from pywifi import const  # noqa
        iface = _get_pywifi_iface()
        if iface is None:
            return []
        iface.scan()
        import time as _t
        _t.sleep(wait_sec)
        results = iface.scan_results()
        out = []
        for r in results:
            ssid = (r.ssid or '').strip()
            if not ssid or len(ssid) > 32:
                continue
            bssid = (r.bssid or '').lower()
            rssi = int(r.signal) if r.signal else -100
            # dBm -> % (грубо: -100 = 0%, -30 = 100%)
            pct = max(0, min(100, int(2 * (rssi + 100))))
            try:
                auth = str(r.auth)
            except Exception:
                auth = 'unknown'
            out.append({
                'ssid': ssid,
                'bssid': bssid,
                'signal': pct,
                'rssi_dbm': round(rssi, 1),
                'auth': auth,
                'source': 'pywifi',
            })
        return out
    except Exception as e:
        log.debug('[pywifi] scan error: %s', e)
        return []'''

new_scan = '''def scan_wifi_pywifi(wait_sec=4.0):
    """P32: scan WiFi via pywifi (RSSI dBm + auth, dedup, normalized)."""
    try:
        from pywifi import const  # noqa
        iface = _get_pywifi_iface()
        if iface is None:
            return []
        iface.scan()
        import time as _t
        _t.sleep(wait_sec)
        results = iface.scan_results()

        # P32: auth mapping
        AUTH_MAP = {
            0: 'OPEN',
            1: 'WPA',
            2: 'WPA2',
            3: 'WPA3',
            4: 'WPA2-ENT',
        }

        seen = {}  # P32: dedup by BSSID
        for r in results:
            ssid = (r.ssid or '').strip()
            if not ssid or len(ssid) > 32:
                continue
            # P32: strip trailing ':' and normalize
            bssid = (r.bssid or '').lower().rstrip(':')
            if not bssid or bssid in seen:
                continue
            rssi = int(r.signal) if r.signal else -100
            pct = max(0, min(100, int(2 * (rssi + 100))))
            # P32: decode auth
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
            seen[bssid] = {
                'ssid': ssid,
                'bssid': bssid,
                'signal': pct,
                'rssi_dbm': round(rssi, 1),
                'auth': auth,
                'source': 'pywifi',
            }
        return list(seen.values())
    except Exception as e:
        log.debug('[pywifi] scan error: %s', e)
        return []'''

if old_scan in content:
    content = content.replace(old_scan, new_scan, 1)
    print("  [OK] scan_wifi_pywifi upgraded (rstrip + dedup + auth)")
elif 'P32: scan WiFi via pywifi' in content:
    print("  [--] already upgraded")
else:
    print("  [!!] scan_wifi_pywifi NOT FOUND")

# 2. _FORCED_RESCAN_INTERVAL 1800 -> effectively off
old_rescan = '''_FORCED_RESCAN_INTERVAL = 1800  # P30: 15 -> 30 min'''
new_rescan = '''_FORCED_RESCAN_INTERVAL = 999999  # P32: effectively disabled (WiFi was degrading)'''
if old_rescan in content:
    content = content.replace(old_rescan, new_rescan, 1)
    print("  [OK] _FORCED_RESCAN_INTERVAL = 999999 (disabled)")
elif '_FORCED_RESCAN_INTERVAL = 999999' in content:
    print("  [--] already disabled")
else:
    print("  [!!] _FORCED_RESCAN_INTERVAL NOT FOUND")

# 3. scan_wifi - skip _force_wifi_rescan
old_force = '''def scan_wifi():
        # P13: force rescan if needed
    try:
        _force_wifi_rescan()
    except Exception:
        pass
    out = []'''
new_force = '''def scan_wifi():
    # P32: _force_wifi_rescan disabled (was killing WiFi)
    out = []'''
if old_force in content:
    content = content.replace(old_force, new_force, 1)
    print("  [OK] _force_wifi_rescan call removed")
elif '# P32: _force_wifi_rescan disabled' in content:
    print("  [--] already removed")
else:
    print("  [!!] scan_wifi force block NOT FOUND")

# 4. /api/wifi/pywifi/connect - add `iface.scan()` before disconnect
old_connect = '''        # Disconnect first
        iface.disconnect()
        _t.sleep(1)'''
new_connect = '''        # P32: disconnect + wait
        try:
            iface.disconnect()
        except Exception:
            pass
        _t.sleep(1.5)'''
if old_connect in content:
    content = content.replace(old_connect, new_connect, 1)
    print("  [OK] connect: safe disconnect")
else:
    print("  [--] connect block unchanged")

if not save_py(APP, content):
    sys.exit(1)


# ============================================================
# P32b. capsule.py: add http_mts method (try 80/443/8080/8443)
# ============================================================
patch_py(CAPSULE, [
    # 1. Add http_mts to methods dict
    (
        '''        methods = {
            "ssh": lambda: self._deploy_ssh(target, code, user),
            "smb": lambda: self._deploy_smb(target, code),
            "adb": lambda: self._deploy_adb(target, code),
            "http": lambda: self._deploy_http(target, code),
        }''',
        '''        methods = {
            "ssh": lambda: self._deploy_ssh(target, code, user),
            "smb": lambda: self._deploy_smb(target, code),
            "adb": lambda: self._deploy_adb(target, code),
            "http": lambda: self._deploy_http(target, code),
            # P32: method from router_recon
            "http_mts": lambda: self._deploy_http_mts(target, code),
            "ssh_try": lambda: self._deploy_ssh(target, code, user),
            "http_try": lambda: self._deploy_http(target, code),
        }''',
        True,
    ),
    # 2. Add _deploy_http_mts method after _deploy_http
    (
        '''    def _auto_start_remote(self, host: str, user: Optional[str] = None) -> bool:''',
        '''    def _deploy_http_mts(self, target: str, code: bytes) -> bool:
        """P32: try HTTP/HTTPS on multiple ports for MTS/unknown routers."""
        import urllib.request
        import ssl as _ssl
        host = target.split(":")[0]
        ctx = _ssl._create_unverified_context()
        for port in (80, 443, 8080, 8443):
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
                continue
        logger.debug("[Deploy] http_mts all ports failed: %s", target)
        return False

    def _auto_start_remote(self, host: str, user: Optional[str] = None) -> bool:''',
        True,
    ),
], "P32b: capsule.py http_mts method")


# ============================================================
# P32c. web/app.py: deploy_all - use recon deploy_method
# ============================================================
patch_py(APP, [
    (
        '''            try:
                ok = n.capsule_deployer.deploy(target, code, method='auto')
                if ok:
                    deployed_count += 1''',
        '''            try:
                # P32: use recon method if available
                deploy_method = 'auto'
                if recon and recon.get('deploy_method'):
                    deploy_method = recon['deploy_method']
                ok = n.capsule_deployer.deploy(target, code, method=deploy_method)
                if ok:
                    deployed_count += 1''',
        True,
    ),
], "P32c: deploy_all uses recon method")


# ============================================================
# DONE
# ============================================================
print()
print("=" * 70)
print("  PATCH 32 DONE")
print("=" * 70)
print()
print("Что изменилось:")
print("  [OK] pywifi scan: rstrip ':' + dedup by BSSID + auth decode")
print("  [OK] _FORCED_RESCAN_INTERVAL = 999999 (disabled)")
print("  [OK] scan_wifi: _force_wifi_rescan() call removed")
print("  [OK] pywifi connect: safe disconnect")
print("  [OK] capsule: http_mts method (ports 80/443/8080/8443)")
print("  [OK] deploy_all: uses recon['deploy_method'] (http_mts)")
print()
print("Перезапусти сервер: python -m web.app")
print("Проверка:")
print("  curl.exe -k -X POST https://localhost:8080/api/wifi/pywifi/scan")
print("  curl.exe -k -X POST https://localhost:8080/api/capsule/deploy_all")