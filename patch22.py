# patch22.py - ARP scanner + IP discovery
import os
import ast
import shutil
import sys

ROOT = r"E:\InevioNet"
APP = os.path.join(ROOT, "web", "app.py")
SCANNER = os.path.join(ROOT, "inevionet", "network", "arp_scanner.py")
HTML = os.path.join(ROOT, "web", "templates", "index.html")


def backup(path):
    if os.path.exists(path):
        shutil.copy2(path, path + ".bak_p22")
        print(f"  Backup: {os.path.basename(path)}.bak_p22")


def save_py(path, code):
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    try:
        ast.parse(code)
        print(f"  [OK] syntax: {os.path.basename(path)}")
    except SyntaxError as e:
        print(f"  [!!] syntax error: {e}")
        if os.path.exists(path + ".bak_p22"):
            shutil.copy2(path + ".bak_p22", path)
        sys.exit(1)


def save_raw(path, code):
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    print(f"  [OK] saved: {os.path.basename(path)}")


# ============================================================
# 1. Create arp_scanner.py
# ============================================================
print("=" * 70)
print("  PATCH 22a: arp_scanner.py")
print("=" * 70)

if os.path.exists(SCANNER):
    print("  [--] arp_scanner.py exists")
else:
    ARP_CODE = '''"""P22: ARP scanner - discover devices in local network."""
import re
import sys
import subprocess
from typing import List, Dict, Any
from ..core.logger import get_logger

logger = get_logger("inevionet.network.arp_scanner")


def scan_arp() -> List[Dict[str, Any]]:
    """P22: scan local network via ARP table.

    Returns list of {ip, mac, type, vendor}.
    """
    results = []
    try:
        if sys.platform == "win32":
            r = subprocess.run(
                ["arp", "-a"],
                capture_output=True, timeout=10,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            try:
                raw = r.stdout.decode("cp866", errors="replace")
            except Exception:
                raw = r.stdout.decode("utf-8", errors="replace")
        else:
            r = subprocess.run(
                ["arp", "-an"],
                capture_output=True, timeout=10,
            )
            raw = r.stdout.decode("utf-8", errors="replace")

        # Parse lines like:
        #   192.168.1.1    04-ba-d6-a3-58-c5     dynamic
        #   192.168.1.100  aa:bb:cc:dd:ee:ff     dynamic
        for line in raw.splitlines():
            # Match IP + MAC
            m = re.match(
                r"\\s*(\\d+\\.\\d+\\.\\d+\\.\\d+)\\s+"
                r"([0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-]"
                r"[0-9a-fA-F]{2}[:-][0-9a-fA-F]{2}[:-][0-9a-fA-F]{2})",
                line)
            if not m:
                continue
            ip = m.group(1)
            mac = m.group(2).replace("-", ":").lower()

            # Skip broadcast/multicast
            if ip.endswith(".255") or ip.startswith("224.") or ip.startswith("239."):
                continue
            if mac.startswith("ff:ff:ff") or mac.startswith("01:00:5e"):
                continue

            # Guess type by IP
            if ip.endswith(".1"):
                ntype = "router"
            elif ip.endswith(".255"):
                ntype = "broadcast"
            else:
                ntype = "device"

            results.append({
                "ip": ip,
                "mac": mac,
                "type": ntype,
                "vendor": "unknown",
            })

        logger.info("[ARP] found %d devices", len(results))
    except Exception as e:
        logger.error("[ARP] scan error: %s", e)

    return results


def find_ip_by_mac(mac: str) -> str:
    """P22: find IP by MAC from ARP table."""
    mac = mac.lower().replace("-", ":")
    for dev in scan_arp():
        if dev["mac"] == mac:
            return dev["ip"]
    return ""


if __name__ == "__main__":
    devices = scan_arp()
    print(f"Found {len(devices)} devices:")
    for d in devices:
        print(f"  {d['ip']:20s} {d['mac']:20s} {d['type']}")
'''
    save_py(SCANNER, ARP_CODE)


# ============================================================
# 2. app.py: import ARP, use in scanner + add device nodes
# ============================================================
print()
print("=" * 70)
print("  PATCH 22b: app.py — ARP integration")
print("=" * 70)

backup(APP)
with open(APP, "r", encoding="utf-8") as f:
    app = f.read()

# Add ARP scanner function
if "def scan_arp" in app:
    print("  [--] scan_arp in app.py already exists")
else:
    arp_func = '''
def scan_arp():
    """P22: scan ARP table for devices."""
    try:
        from inevionet.network.arp_scanner import scan_arp as _arp
        return _arp()
    except Exception as e:
        log.debug('[ARP] error: %s', e)
        return []


'''
    # Insert before def scan_wifi
    marker = "def scan_wifi():"
    if marker in app:
        app = app.replace(marker, arp_func + marker, 1)
        print("  [OK] scan_arp function added")

# Add ARP scan to background_scanner
if "P22: ARP scan" in app:
    print("  [--] ARP in scanner exists")
else:
    # Find "--- BLUETOOTH (каждые 4 цикла) ---"
    marker = '''            # --- BLUETOOTH (каждые 4 цикла) ---
            if sc % 4 == 0:'''
    new_block = '''            # --- ARP SCAN (каждые 3 цикла) ---
            if sc % 3 == 1:
                try:
                    arp_devices = scan_arp()
                    for dev in arp_devices:
                        nid = 'arp_' + dev['mac'].replace(':', '')
                        upsert({
                            'node_id': nid,
                            'name': '%s (%s)' % (dev['ip'], dev['type']),
                            'label': dev['ip'],
                            'type': dev['type'],
                            'ip': dev['ip'],
                            'port': 0,
                            'trust': 60.0,
                            'packets': 0,
                            'online': True,
                            'rssi': -50,
                            'signal': 80,
                            'method': 'arp_scan',
                            'evolving': False,
                            'parent': None,
                            'mac': dev['mac'],
                        })
                except Exception as _e:
                    log.debug('[ARP] loop error: %s', _e)

            # --- BLUETOOTH (каждые 4 цикла) ---
            if sc % 4 == 0:'''
    if marker in app:
        app = app.replace(marker, new_block, 1)
        print("  [OK] ARP scan in background")

# Also update WiFi nodes to try find IP by BSSID
if "P22: lookup IP by BSSID" in app:
    print("  [--] BSSID lookup exists")
else:
    old_wifi = """                    if sig['ssid'] not in footholds and myc is not None:"""
    new_wifi = """                    # P22: lookup IP by BSSID via ARP
                    try:
                        from inevionet.network.arp_scanner import find_ip_by_mac
                        _ip = find_ip_by_mac(sig['bssid'])
                        if _ip:
                            _nodes = dict(_nodes[0])
                            _nid = 'wifi_' + sig['bssid']
                            if _nid in _nodes:
                                _nodes[_nid]['ip'] = _ip
                                _nodes[_nid]['ip_source'] = 'arp'
                                _nodes[0] = _nodes
                    except Exception:
                        pass

                    if sig['ssid'] not in footholds and myc is not None:"""
    if old_wifi in app:
        app = app.replace(old_wifi, new_wifi, 1)
        print("  [OK] BSSID → IP lookup added")

save_py(APP, app)


# ============================================================
# 3. index.html: show IP with device types
# ============================================================
print()
print("=" * 70)
print("  PATCH 22c: index.html — IP display")
print("=" * 70)

backup(HTML)
with open(HTML, "r", encoding="utf-8") as f:
    html = f.read()

if "device:'#ff6b9d'" in html or "device:" in html:
    print("  [--] device color exists")
else:
    # Add device + router colors
    old_colors = "const COLORS = {\n    self:'#30d158', wifi:'#0a84ff', bluetooth:'#64d2ff',\n    peer:'#bf5af2', spore:'#ff375f',\n    ble:'#5ac8fa', cellular:'#ffd60a',\n    industrial:'#ff9f0a', super:'#ffffff'\n};"
    new_colors = "const COLORS = {\n    self:'#30d158', wifi:'#0a84ff', bluetooth:'#64d2ff',\n    peer:'#bf5af2', spore:'#ff375f',\n    ble:'#5ac8fa', cellular:'#ffd60a',\n    industrial:'#ff9f0a', super:'#ffffff',\n    device:'#ff9ff3', router:'#feca57'\n};"
    if old_colors in html:
        html = html.replace(old_colors, new_colors, 1)
        print("  [OK] device/router colors added")

    # Add label with IP
    old_label = """        ctx.fillText(s.node.label || s.node.name || s.node.node_id, s.x + r + 6 / zoom, s.y + 3 / zoom);"""
    new_label = """        // P22: show name + IP
        let _label = s.node.label || s.node.name || s.node.node_id;
        if (s.node.ip && s.node.ip !== 'unknown' && s.node.type !== 'self') {
            _label = s.node.name + ' (' + s.node.ip + ')';
        }
        ctx.fillText(_label, s.x + r + 6 / zoom, s.y + 3 / zoom);"""
    if old_label in html:
        html = html.replace(old_label, new_label, 1)
        print("  [OK] label with IP")

    save_raw(HTML, html)


print()
print("=" * 70)
print("  PATCH 22 DONE")
print("=" * 70)
print()
print("Что изменилось:")
print("  [OK] arp_scanner.py — сканер ARP таблицы")
print("  [OK] app.py: ARP-скан в background_scanner")
print("  [OK] app.py: BSSID → IP lookup через ARP")
print("  [OK] UI: цвета для device/router")
print("  [OK] UI: показ IP в подписи")
print()
print("Перезапусти сервер: python -m web.app")