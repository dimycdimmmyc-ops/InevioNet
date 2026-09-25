# patch34b_fix.py - BLE filter by iid + auth fallback extended
import os
import ast
import shutil

APP = r"E:\InevioNet\web\app.py"


def backup(path):
    if os.path.exists(path):
        b = path + ".bak_p34b"
        shutil.copy2(path, b)
        print(f"  [BK] {os.path.basename(b)}")


print()
print("=" * 70)
print("  P34b-fix: BLE by iid + auth extended")
print("=" * 70)
backup(APP)

with open(APP, "r", encoding="utf-8") as f:
    content = f.read()

# --- Fix 1: scan_bt by iid ---
old1 = '''            for x in d:
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
                })'''

new1 = '''            for x in d:
                iid = x.get('InstanceId', '')
                name = x.get('Name', '')
                # P34b-fix: only BTHLEDEVICE (not BTHENUM/BTHLE_DEV)
                if not iid.startswith('BTHLEDEVICE'):
                    continue
                # Skip Windows service records (have GUID in iid)
                if '{' in iid or 'DEV_' in iid:
                    continue
                if not name or len(name) < 3:
                    continue
                # Skip garbled names (mostly non-latin chars)
                latin = sum(1 for c in name if c.isascii() and c.isprintable())
                if latin < 2:
                    continue
                out.append({
                    'name': name,
                    'id': iid.replace('\\\\', '_'),
                })'''

if old1 in content:
    content = content.replace(old1, new1, 1)
    print("  [OK] scan_bt by iid")
elif 'P34b-fix: only BTHLEDEVICE' in content:
    print("  [--] already applied")
else:
    print("  [!!] scan_bt NOT FOUND")

# --- Fix 2: auth fallback extended ---
old2 = '''            # P34: decode auth + fallback by akm
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
'''

new2 = '''            # P34b-fix: decode auth + fallback
            try:
                if r.auth and isinstance(r.auth, (list, tuple)) and len(r.auth) > 0:
                    auth_code = int(r.auth[0])
                elif r.auth:
                    auth_code = int(r.auth)
                else:
                    auth_code = -1
                auth = AUTH_MAP.get(auth_code)
                if not auth:
                    akm_list = [str(a) for a in (r.akm or [])]
                    akm_str = ' '.join(akm_list).upper()
                    if 'WPA3' in akm_str:
                        auth = 'WPA3'
                    elif 'WPA2' in akm_str:
                        auth = 'WPA2'
                    elif 'WPA' in akm_str:
                        auth = 'WPA'
                    elif 'NONE' in akm_str or 'OPEN' in akm_str:
                        auth = 'OPEN'
                    else:
                        auth = 'unknown'
            except Exception:
                auth = 'unknown'
'''

if old2 in content:
    content = content.replace(old2, new2, 1)
    print("  [OK] auth fallback extended")
elif 'P34b-fix: decode auth' in content:
    print("  [--] already applied")
else:
    print("  [!!] auth NOT FOUND")

try:
    ast.parse(content)
    with open(APP, "w", encoding="utf-8") as f:
        f.write(content)
    print("  [OK] syntax OK")
except SyntaxError as e:
    print(f"  [!!] syntax error: {e}")
    shutil.copy2(APP + ".bak_p34b", APP)
    print("  [--] rolled back")

print()
print("Перезапусти: python -m web.app")