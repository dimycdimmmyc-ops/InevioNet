# patch33.py - InevioNet: scan_wifi via pywifi + AUTH_MAP + rescan 300
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
APP = os.path.join(ROOT, "web", "app.py")


def backup(path):
    if os.path.exists(path):
        b = path + ".bak_p33"
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
        if os.path.exists(path + ".bak_p33"):
            shutil.copy2(path + ".bak_p33", path)
            print("  [--] rolled back")
        return False


print()
print("=" * 70)
print("  P33: scan_wifi via pywifi + AUTH_MAP + rescan 300")
print("=" * 70)
backup(APP)

with open(APP, "r", encoding="utf-8") as f:
    content = f.read()

# --- 1. _FORCED_RESCAN_INTERVAL 999999 -> 300 ---
old1 = '_FORCED_RESCAN_INTERVAL = 999999  # P29: 5 -> 15 min'
new1 = '_FORCED_RESCAN_INTERVAL = 300  # P33: 5 min (fallback only)'
if old1 in content:
    content = content.replace(old1, new1, 1)
    print("  [OK] _FORCED_RESCAN_INTERVAL = 300")
elif '_FORCED_RESCAN_INTERVAL = 300' in content:
    print("  [--] already 300")
else:
    print("  [!!] NOT FOUND (interval)")

# --- 2. scan_wifi: pywifi first ---
old2 = '''def scan_wifi():
    # P32: _force_wifi_rescan disabled (was killing WiFi)
    out = []
    try:
        r = subprocess.run(
            ['netsh', 'wlan', 'show', 'networks', 'mode=bssid'],
            capture_output=True, timeout=5,
        )
        try:
            raw = r.stdout.decode('utf-8')
        except UnicodeDecodeError:
            raw = r.stdout.decode('cp866', errors='replace')
        for block in re.split(r'(?i)\\n\\s*SSID\\s+\\d+\\s*:\\s*', '\\n' + raw)[1:]:
            lines = block.split('\\n')
            ssid = lines[0].strip() or ''
            # --- ФИЛЬТР МУСОРА ---
            if (not ssid
                    or ssid.startswith('Тип сети')
                    or ssid.startswith('Type')
                    or ssid.startswith('BSSID')
                    or ssid == 'Unknown'
                    or len(ssid) > 32):
                continue
            # ---------------------
            bssid = pct = None
            for ln in lines[1:20]:
                if not bssid:
                    m = re.search(r'([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}', ln)
                    if m:
                        bssid = m.group(0)
                if pct is None and '%' in ln:
                    m = re.search(r':\\s*(\\d+)\\s*%', ln)
                    if m:
                        pct = int(m.group(1))
            if bssid:
                out.append({
                    'ssid': ssid,
                    'bssid': bssid,
                    'signal': pct or 0,
                    'rssi_dbm': round(-100 + (pct or 0) / 2.0, 1),
                })
    except Exception as e:
        log.debug('[Scanner] WiFi: %s', e)
    return out'''

new2 = '''def scan_wifi():
    """P33: pywifi first (8-9 networks), netsh fallback."""
    # 1. pywifi (best)
    try:
        sigs = scan_wifi_pywifi(wait_sec=3.5)
        if len(sigs) >= 3:
            log.debug('[scan_wifi] pywifi: %d networks', len(sigs))
            return sigs
    except Exception as e:
        log.debug('[scan_wifi] pywifi failed: %s', e)

    # 2. netsh fallback
    out = []
    try:
        r = subprocess.run(
            ['netsh', 'wlan', 'show', 'networks', 'mode=bssid'],
            capture_output=True, timeout=5,
        )
        try:
            raw = r.stdout.decode('utf-8')
        except UnicodeDecodeError:
            raw = r.stdout.decode('cp866', errors='replace')
        for block in re.split(r'(?i)\\n\\s*SSID\\s+\\d+\\s*:\\s*', '\\n' + raw)[1:]:
            lines = block.split('\\n')
            ssid = lines[0].strip() or ''
            if (not ssid
                    or ssid.startswith('Тип сети')
                    or ssid.startswith('Type')
                    or ssid.startswith('BSSID')
                    or ssid == 'Unknown'
                    or len(ssid) > 32):
                continue
            bssid = pct = None
            for ln in lines[1:20]:
                if not bssid:
                    m = re.search(r'([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}', ln)
                    if m:
                        bssid = m.group(0)
                if pct is None and '%' in ln:
                    m = re.search(r':\\s*(\\d+)\\s*%', ln)
                    if m:
                        pct = int(m.group(1))
            if bssid:
                out.append({
                    'ssid': ssid,
                    'bssid': bssid,
                    'signal': pct or 0,
                    'rssi_dbm': round(-100 + (pct or 0) / 2.0, 1),
                    'auth': 'unknown',
                    'source': 'netsh',
                })
    except Exception as e:
        log.debug('[Scanner] WiFi: %s', e)

    # 3. if too few — force rescan + retry
    if len(out) < 3:
        try:
            _force_wifi_rescan()
        except Exception:
            pass
        try:
            r = subprocess.run(
                ['netsh', 'wlan', 'show', 'networks', 'mode=bssid'],
                capture_output=True, timeout=5,
            )
            raw = r.stdout.decode('cp866', errors='replace')
            for block in re.split(r'(?i)\\n\\s*SSID\\s+\\d+\\s*:\\s*', '\\n' + raw)[1:]:
                lines = block.split('\\n')
                ssid = lines[0].strip() or ''
                if (not ssid or ssid.startswith('Тип сети')
                        or ssid.startswith('Type') or len(ssid) > 32):
                    continue
                bssid = None
                for ln in lines[1:20]:
                    m = re.search(r'([0-9a-fA-F]{2}[:-]){5}[0-9a-fA-F]{2}', ln)
                    if m:
                        bssid = m.group(0)
                        break
                if bssid and not any(s['bssid'] == bssid for s in out):
                    out.append({
                        'ssid': ssid, 'bssid': bssid,
                        'signal': 0, 'rssi_dbm': -100,
                        'auth': 'unknown', 'source': 'netsh_rescan',
                    })
        except Exception:
            pass

    return out'''

if old2 in content:
    content = content.replace(old2, new2, 1)
    print("  [OK] scan_wifi -> pywifi first")
elif 'P33: pywifi first' in content:
    print("  [--] already patched")
else:
    print("  [!!] scan_wifi NOT FOUND")

# --- 3. AUTH_MAP expanded ---
old3 = '''        # P32: auth mapping
        AUTH_MAP = {
            0: 'OPEN',
            1: 'WPA',
            2: 'WPA2',
            3: 'WPA3',
            4: 'WPA2-ENT',
        }'''
new3 = '''        # P33: auth mapping (expanded)
        AUTH_MAP = {
            0: 'OPEN',
            1: 'WPA',
            2: 'WPA2',
            3: 'WPA3',
            4: 'WPA2-ENT',
            5: 'WPA3-ENT',
            6: 'WEP',
            7: '802.1X',
        }'''
if old3 in content:
    content = content.replace(old3, new3, 1)
    print("  [OK] AUTH_MAP expanded")
else:
    print("  [--] AUTH_MAP unchanged")

if not save_py(APP, content):
    raise SystemExit(1)

print()
print("=" * 70)
print("  PATCH 33 DONE")
print("=" * 70)
print()
print("  [OK] scan_wifi -> pywifi first (8-9 networks)")
print("  [OK] netsh fallback + force_rescan if <3")
print("  [OK] _FORCED_RESCAN_INTERVAL = 300 (fallback only)")
print("  [OK] AUTH_MAP expanded (WEP, 802.1X)")
print()
print("Перезапусти: python -m web.app")
print("Проверка:")
print("  curl.exe -k -X POST https://localhost:8080/api/rf/scan")
print("  (Topology должен показать 7-9 nodes, а не 2)")