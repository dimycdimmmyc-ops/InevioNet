# patch37b.py - InevioNet: ethernet endpoints JSON-safe + filter by description
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
APP = os.path.join(ROOT, "web", "app.py")
ETH = os.path.join(ROOT, "inevionet", "network", "ethernet_scanner.py")


def backup(path):
    if os.path.exists(path):
        b = path + ".bak_p37b"
        shutil.copy2(path, b)
        print(f"  [BK] {os.path.basename(b)}")


def save_py(path, code):
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    try:
        ast.parse(code)
        print(f"  [OK] syntax: {os.path.basename(path)}")
    except SyntaxError as e:
        print(f"  [!!] syntax error: {e}")
        if os.path.exists(path + ".bak_p37b"):
            shutil.copy2(path + ".bak_p37b", path)


# ============================================================
# P37b-1. web/app.py: request.get_json(silent=True)
# ============================================================
print()
print("=" * 70)
print("  P37b-1: web/app.py JSON-safe")
print("=" * 70)
backup(APP)
with open(APP, "r", encoding="utf-8") as f:
    content = f.read()

old1 = '''@app.route('/api/ethernet/scan', methods=['POST'])
def api_ethernet_scan():
    """P36: scan Ethernet subnet for industrial protocols."""
    d = request.json or {}'''
new1 = '''@app.route('/api/ethernet/scan', methods=['POST'])
def api_ethernet_scan():
    """P36: scan Ethernet subnet for industrial protocols."""
    d = request.get_json(silent=True) or {}'''

if old1 in content:
    content = content.replace(old1, new1, 1)
    print("  [OK] ethernet/scan JSON-safe")
elif 'get_json(silent=True) or {}' in content:
    print("  [--] already applied")
else:
    print("  [!!] NOT FOUND")

save_py(APP, content)


# ============================================================
# P37b-2. ethernet_scanner.py: filter by description
# ============================================================
print()
print("=" * 70)
print("  P37b-2: ethernet_scanner filter by description")
print("=" * 70)
backup(ETH)
with open(ETH, "r", encoding="utf-8") as f:
    content = f.read()

old2 = '''        for iface in data:
            name = iface.get("Name", "")
            desc = iface.get("InterfaceDescription", "")
            if "wi-fi" in name.lower() or "wireless" in desc.lower():
                continue
            ifaces.append({
                "name": name,
                "description": desc,
                "mac": iface.get("MacAddress", ""),
                "speed": iface.get("LinkSpeed", ""),
            })'''

new2 = '''        for iface in data:
            name = iface.get("Name", "")
            desc = iface.get("InterfaceDescription", "")
            # P37b: filter by description (WiFi)
            desc_low = desc.lower()
            name_low = name.lower()
            if any(x in desc_low for x in ("wi-fi", "wireless", "802.11")):
                continue
            if any(x in name_low for x in ("wi-fi", "wireless", "wlan")):
                continue
            ifaces.append({
                "name": name,
                "description": desc,
                "mac": iface.get("MacAddress", ""),
                "speed": iface.get("LinkSpeed", ""),
            })'''

if old2 in content:
    content = content.replace(old2, new2, 1)
    print("  [OK] filter by description")
elif 'P37b: filter by description' in content:
    print("  [--] already applied")
else:
    print("  [!!] NOT FOUND")

save_py(ETH, content)


# ============================================================
# DONE
# ============================================================
print()
print("=" * 70)
print("  PATCH 37b DONE")
print("=" * 70)
print()
print("  [OK] /api/ethernet/scan: request.get_json(silent=True)")
print("  [OK] ethernet_scanner: filter by description")
print()
print("Перезапусти: python -m web.app")
print()
print("Проверка:")
print("  curl.exe -k https://localhost:8080/api/ethernet/interfaces")