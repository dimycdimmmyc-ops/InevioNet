# patch24.py - Router reconnaissance + adaptive deploy
import os
import ast
import shutil
import sys

ROOT = r"E:\InevioNet"
ROUTER = os.path.join(ROOT, "inevionet", "network", "router_recon.py")
APP = os.path.join(ROOT, "web", "app.py")
HTML = os.path.join(ROOT, "web", "templates", "index.html")


def backup(path):
    if os.path.exists(path):
        shutil.copy2(path, path + ".bak_p24")
        print(f"  Backup: {os.path.basename(path)}.bak_p24")


def save_py(path, code):
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    try:
        ast.parse(code)
        print(f"  [OK] syntax: {os.path.basename(path)}")
    except SyntaxError as e:
        print(f"  [!!] syntax error: {e}")
        if os.path.exists(path + ".bak_p24"):
            shutil.copy2(path + ".bak_p24", path)
        sys.exit(1)


def save_raw(path, code):
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    print(f"  [OK] saved: {os.path.basename(path)}")


# ============================================================
# 1. Create router_recon.py
# ============================================================
print("=" * 70)
print("  PATCH 24a: router_recon.py")
print("=" * 70)

if os.path.exists(ROUTER):
    print("  [--] router_recon.py exists")
else:
    ROUTER_CODE = '''"""P24: Router reconnaissance - fingerprint and identify firmware."""
import re
import socket
import urllib.request
import ssl
from typing import Dict, Any, Optional
from ..core.logger import get_logger

logger = get_logger("inevionet.network.router_recon")


# MAC OUI → vendor
OUI_MAP = {
    # MikroTik
    "4c:5e:0c": "MikroTik", "6c:3b:6b": "MikroTik", "74:4d:28": "MikroTik",
    "78:9a:18": "MikroTik", "dc:2c:6e": "MikroTik", "e4:8d:8c": "MikroTik",
    # Keenetic (Zyxel)
    "50:ff:20": "Keenetic", "54:6c:0e": "Keenetic", "70:6b:b9": "Keenetic",
    # ASUS
    "04:d4:c4": "ASUS", "2c:56:dc": "ASUS", "38:d5:47": "ASUS",
    "50:46:5d": "ASUS", "ac:9e:17": "ASUS", "b0:6e:bf": "ASUS",
    # TP-Link
    "14:cc:20": "TP-Link", "50:c7:bf": "TP-Link", "a4:2b:b0": "TP-Link",
    "b0:4e:26": "TP-Link", "ec:08:6b": "TP-Link",
    # Xiaomi
    "28:d1:27": "Xiaomi", "34:ce:00": "Xiaomi", "50:64:2b": "Xiaomi",
    "64:09:80": "Xiaomi", "78:11:dc": "Xiaomi",
    # Tenda
    "c8:3a:35": "Tenda", "d8:32:14": "Tenda",
    # Netis
    "10:13:31": "Netis", "28:76:cd": "Netis",
    # Huawei
    "00:e0:fc": "Huawei", "28:6e:d4": "Huawei", "8c:34:fd": "Huawei",
    # Zyxel
    "00:13:49": "Zyxel", "5c:f4:ab": "Zyxel",
    # Netgear
    "20:e5:2a": "Netgear", "a0:40:a0": "Netgear", "c4:04:15": "Netgear",
    # D-Link
    "14:d6:4d": "D-Link", "1c:7e:e5": "D-Link", "3c:1e:04": "D-Link",
}


def get_vendor_by_mac(mac: str) -> str:
    """P24: vendor by MAC OUI."""
    mac = mac.lower().replace("-", ":")
    prefix = ":".join(mac.split(":")[:3])
    return OUI_MAP.get(prefix, "unknown")


def http_fingerprint(ip: str, port: int = 80, timeout: float = 3.0) -> Dict[str, Any]:
    """P24: get HTTP headers."""
    result = {"reachable": False, "server": "", "www_auth": "", "body_hint": ""}
    try:
        url = f"http://{ip}:{port}/"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as r:
            result["reachable"] = True
            result["server"] = r.headers.get("Server", "")
            result["www_auth"] = r.headers.get("WWW-Authenticate", "")
            body = r.read(2000).decode("utf-8", errors="replace")
            # Look for firmware hints
            if "RouterOS" in body or "MikroTik" in body:
                result["body_hint"] = "RouterOS"
            elif "Keenetic" in body:
                result["body_hint"] = "Keenetic"
            elif "OpenWrt" in body:
                result["body_hint"] = "OpenWrt"
            elif "ASUS" in body or "asus" in body:
                result["body_hint"] = "ASUS"
            elif "TP-LINK" in body.upper():
                result["body_hint"] = "TP-Link"
    except Exception as e:
        logger.debug("[Recon] http %s:%d: %s", ip, port, e)
    return result


def port_scan(ip: str, ports: list, timeout: float = 1.5) -> Dict[int, bool]:
    """P24: check open ports."""
    result = {}
    for port in ports:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(timeout)
            r = s.connect_ex((ip, port))
            s.close()
            result[port] = (r == 0)
        except Exception:
            result[port] = False
    return result


def identify_firmware(ip: str, mac: str = "") -> Dict[str, Any]:
    """P24: identify router firmware/model."""
    info = {
        "ip": ip,
        "mac": mac,
        "vendor": get_vendor_by_mac(mac) if mac else "unknown",
        "firmware": "unknown",
        "ssh_open": False,
        "http_open": False,
        "https_open": False,
        "open_ports": [],
        "server_header": "",
        "deploy_method": "unknown",
        "can_deploy": False,
        "notes": "",
    }

    # Port scan
    ports = [22, 23, 80, 443, 8080, 8443]
    port_results = port_scan(ip, ports)

    info["ssh_open"] = port_results.get(22, False)
    info["http_open"] = port_results.get(80, False)
    info["https_open"] = port_results.get(443, False)
    info["open_ports"] = [p for p, ok in port_results.items() if ok]

    # HTTP fingerprint
    if info["http_open"]:
        fp = http_fingerprint(ip, 80)
        info["server_header"] = fp.get("server", "")
        hint = fp.get("body_hint", "")
        if hint:
            info["firmware"] = hint
        elif "RouterOS" in fp.get("server", ""):
            info["firmware"] = "RouterOS"
        elif "nginx" in fp.get("server", "").lower():
            info["firmware"] = "Linux (nginx)"
        elif "Keenetic" in fp.get("www_auth", ""):
            info["firmware"] = "Keenetic"

    # Determine strategy
    if info["firmware"] == "RouterOS" or info["vendor"] == "MikroTik":
        info["deploy_method"] = "ssh_mikrotik"
        info["can_deploy"] = info["ssh_open"]
        info["notes"] = "MikroTik: container package required"
    elif info["firmware"] == "Keenetic" or info["vendor"] == "Keenetic":
        info["deploy_method"] = "ssh_keenetic"
        info["can_deploy"] = info["ssh_open"]
        info["notes"] = "Keenetic: install Entware (opkg)"
    elif info["firmware"] == "OpenWrt":
        info["deploy_method"] = "ssh_openwrt"
        info["can_deploy"] = info["ssh_open"]
        info["notes"] = "OpenWrt: opkg install python3"
    elif info["firmware"] == "ASUS" or info["vendor"] == "ASUS":
        info["deploy_method"] = "ssh_asus_merlin"
        info["can_deploy"] = info["ssh_open"]
        info["notes"] = "ASUS: Merlin firmware + Entware"
    elif info["vendor"] == "TP-Link":
        info["deploy_method"] = "skip"
        info["can_deploy"] = False
        info["notes"] = "TP-Link: closed firmware, no deploy"
    elif info["vendor"] == "Tenda":
        info["deploy_method"] = "skip"
        info["can_deploy"] = False
        info["notes"] = "Tenda: closed firmware"
    else:
        info["deploy_method"] = "unknown"
        info["can_deploy"] = False
        info["notes"] = "Unknown router, manual check needed"

    logger.info("[Recon] %s: vendor=%s firmware=%s deploy=%s can=%s",
                ip, info["vendor"], info["firmware"],
                info["deploy_method"], info["can_deploy"])
    return info


if __name__ == "__main__":
    import sys
    ip = sys.argv[1] if len(sys.argv) > 1 else "192.168.1.1"
    mac = sys.argv[2] if len(sys.argv) > 2 else ""
    info = identify_firmware(ip, mac)
    import json
    print(json.dumps(info, indent=2))
'''
    save_py(ROUTER, ROUTER_CODE)


# ============================================================
# 2. app.py: use router_recon in deploy_all
# ============================================================
print()
print("=" * 70)
print("  PATCH 24b: app.py — use router_recon")
print("=" * 70)

backup(APP)
with open(APP, "r", encoding="utf-8") as f:
    app = f.read()

if "router_recon" in app:
    print("  [--] router_recon already used")
else:
    # Replace deploy_all body to add recon
    old_block = '''            # Try deploy
            target = ip
            port = node.get('port', 0)
            if port:
                target = f"{ip}:{port}"

            # Add as trusted temporarily? No — use direct deploy
            # Add to trusted for this call
            try:
                n.trusted_hosts.add(target, label=nid, method='auto')
            except Exception:
                pass'''
    new_block = '''            # Try deploy
            target = ip
            port = node.get('port', 0)
            if port:
                target = f"{ip}:{port}"

            # P24: router reconnaissance
            recon = None
            if ntype in ('router', 'device'):
                try:
                    from inevionet.network.router_recon import identify_firmware
                    mac = node.get('mac', '')
                    recon = identify_firmware(ip, mac)
                except Exception as _re:
                    log.debug('[Recon] error: %s', _re)

            if recon and not recon.get('can_deploy', False):
                skipped_count += 1
                results.append({
                    'node_id': nid, 'target': target, 'type': ntype,
                    'status': 'skip',
                    'skip_reason': 'no_deploy_method',
                    'vendor': recon.get('vendor', '?'),
                    'firmware': recon.get('firmware', '?'),
                    'notes': recon.get('notes', ''),
                })
                continue

            # Add as trusted
            try:
                n.trusted_hosts.add(target, label=nid, method='auto')
            except Exception:
                pass'''
    if old_block in app:
        app = app.replace(old_block, new_block, 1)
        print("  [OK] router_recon in deploy_all")

    # Add recon results to output
    old_resp = '''                results.append({
                        'node_id': nid,
                        'target': target,
                        'type': ntype,
                        'status': 'deployed',
                    })'''
    new_resp = '''                results.append({
                        'node_id': nid,
                        'target': target,
                        'type': ntype,
                        'status': 'deployed',
                        'vendor': (recon or {}).get('vendor', '?'),
                        'firmware': (recon or {}).get('firmware', '?'),
                    })'''
    if old_resp in app:
        app = app.replace(old_resp, new_resp, 1)
        print("  [OK] deployed results include vendor")

    save_py(APP, app)


# ============================================================
# 3. New endpoint: /api/router/scan
# ============================================================
print()
print("=" * 70)
print("  PATCH 24c: /api/router/scan endpoint")
print("=" * 70)

backup(APP)
with open(APP, "r", encoding="utf-8") as f:
    app = f.read()

if "/api/router/scan" in app:
    print("  [--] router scan endpoint exists")
else:
    endpoint = '''
@app.route('/api/router/scan', methods=['POST'])
def api_router_scan():
    """P24: scan router and identify firmware."""
    d = request.json or {}
    ip = (d.get('ip') or '').strip()
    mac = d.get('mac', '')
    if not ip:
        return jsonify({'success': False, 'error': 'no_ip'}), 400
    try:
        from inevionet.network.router_recon import identify_firmware
        info = identify_firmware(ip, mac)
        # Update node
        nodes = snapshot()
        for nid, node in nodes.items():
            if node.get('ip') == ip:
                node['vendor'] = info.get('vendor')
                node['firmware'] = info.get('firmware')
                node['can_deploy'] = info.get('can_deploy')
                node['deploy_method'] = info.get('deploy_method')
                node['recon_notes'] = info.get('notes')
                upsert(node)
        return jsonify({'success': True, 'info': info})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


'''
    marker = "@socketio.on('connect')"
    if marker in app:
        app = app.replace(marker, endpoint + marker, 1)
        save_py(APP, app)
        print("  [OK] /api/router/scan added")
    else:
        print("  [!!] socketio marker not found")


# ============================================================
# 4. UI: "Scan router" button
# ============================================================
print()
print("=" * 70)
print("  PATCH 24d: UI — router scan")
print("=" * 70)

backup(HTML)
with open(HTML, "r", encoding="utf-8") as f:
    html = f.read()

if "btnRouterScan" in html:
    print("  [--] router scan button exists")
else:
    # Add to capsule card
    old = '''<button class="btn btn-danger" onclick="killCapsules()">⛔ СТОП (убить все капсулы)</button>'''
    new = '''<button class="btn btn-danger" onclick="killCapsules()">⛔ СТОП (убить все капсулы)</button>
<div class="form-group" style="margin-top:12px">
  <label>Проверить роутер (fingerprint)</label>
  <input id="routerScanIp" placeholder="192.168.1.1">
</div>
<button class="btn btn-glass" onclick="scanRouter()">🔍 Сканировать роутер</button>
<div id="routerScanResult" style="margin-top:10px;font-size:0.8em;font-family:monospace"></div>'''
    if old in html:
        html = html.replace(old, new, 1)
        print("  [OK] router scan UI added")

    # Add JS
    js = '''
async function scanRouter() {
    const ip = document.getElementById('routerScanIp').value.trim();
    if (!ip) { addLog('Введите IP роутера', 'error'); return; }
    addLog('Scan router: ' + ip, 'info');
    const el = document.getElementById('routerScanResult');
    el.textContent = 'Сканирую...';
    try {
        const r = await fetch('/api/router/scan', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ ip })
        });
        const d = await r.json();
        if (d.success) {
            const i = d.info;
            el.innerHTML =
                'Vendor: ' + i.vendor + '<br>' +
                'Firmware: ' + i.firmware + '<br>' +
                'SSH: ' + (i.ssh_open ? '✅' : '❌') +
                ' HTTP: ' + (i.http_open ? '✅' : '❌') +
                ' HTTPS: ' + (i.https_open ? '✅' : '❌') + '<br>' +
                'Method: ' + i.deploy_method + '<br>' +
                'Can deploy: ' + (i.can_deploy ? '✅ YES' : '❌ NO') + '<br>' +
                'Notes: ' + i.notes;
            addLog('Router: ' + i.vendor + ' / ' + i.firmware, 'success');
        } else {
            el.textContent = 'Error: ' + d.error;
        }
    } catch (e) {
        addLog('Router scan: ' + e, 'error');
    }
}

'''
    js_marker = "checkAuth();"
    if js_marker in html:
        html = html.replace(js_marker, js + '\n' + js_marker, 1)
        print("  [OK] router scan JS added")

    save_raw(HTML, html)


print()
print("=" * 70)
print("  PATCH 24 DONE")
print("=" * 70)
print()
print("Что изменилось:")
print("  [OK] router_recon.py — fingerprint роутеров")
print("  [OK] MAC OUI → vendor (Keenetic/MikroTik/ASUS/TP-Link/...)")
print("  [OK] HTTP fingerprint (RouterOS/Keenetic/OpenWrt)")
print("  [OK] Port scan (22/23/80/443/8080/8443)")
print("  [OK] /api/router/scan — endpoint")
print("  [OK] UI: кнопка 🔍 Сканировать роутер")
print()
print("Перезапусти сервер: python -m web.app")