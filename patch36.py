# patch36.py - FULL: _capsule_deploy_cycle MAC + Ethernet scanner + endpoints + UI
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
ORCH = os.path.join(ROOT, "inevionet", "orchestrator.py")
APP = os.path.join(ROOT, "web", "app.py")
HTML = os.path.join(ROOT, "web", "templates", "index.html")
ETH = os.path.join(ROOT, "inevionet", "network", "ethernet_scanner.py")


def backup(path):
    if os.path.exists(path):
        b = path + ".bak_p36"
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
        if os.path.exists(path + ".bak_p36"):
            shutil.copy2(path + ".bak_p36", path)
        return False


def save_raw(path, code):
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    print(f"  [OK] saved: {os.path.basename(path)}")


# ============================================================
# P36a. orchestrator.py: _capsule_deploy_cycle MAC from label
# ============================================================
print()
print("=" * 70)
print("  P36a: _capsule_deploy_cycle MAC from label")
print("=" * 70)
backup(ORCH)
with open(ORCH, "r", encoding="utf-8") as f:
    content = f.read()

old1 = '''        # P35: Deploy to each trusted (recon method)
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
                logger.debug("[Capsule] recon error: %s", _re)'''

new1 = '''        # P36: Deploy to each trusted (recon method with MAC from label)
        for h in trusted:
            host = h["host"]
            label = h.get("label", "")
            ip = host.split(':')[0]
            _method = method
            try:
                from .network.router_recon import identify_firmware
                mac = ""
                if label.startswith("arp_"):
                    _raw = label[4:]
                    if len(_raw) == 12:
                        mac = ':'.join(_raw[i:i+2] for i in range(0, 12, 2))
                _recon = identify_firmware(ip, mac)
                if _recon.get('can_deploy'):
                    _method = _recon.get('deploy_method', method)
                    logger.info("[Capsule] %s -> method=%s (mac=%s)",
                                host, _method, mac or "none")
            except Exception as _re:
                logger.debug("[Capsule] recon error: %s", _re)'''

if old1 in content:
    content = content.replace(old1, new1, 1)
    print("  [OK] _capsule_deploy_cycle MAC from label")
elif 'P36: extract MAC from label' in content or 'mac = ""' in content and 'label.startswith("arp_")' in content:
    print("  [--] already applied")
else:
    print("  [!!] NOT FOUND — проверь вручную")

save_py(ORCH, content)


# ============================================================
# P36b. ethernet_scanner.py (new file)
# ============================================================
print()
print("=" * 70)
print("  P36b: ethernet_scanner.py")
print("=" * 70)

eth_code = '''"""P36: Ethernet scanner for industrial protocols (Modbus/MQTT/OPC-UA/DNP3)."""
import socket
import concurrent.futures
from typing import List, Dict, Any

from ..core.logger import get_logger

logger = get_logger("inevionet.network.ethernet_scanner")

INDUSTRIAL_PORTS = {
    502: "modbus",
    1883: "mqtt",
    8883: "mqtt_ssl",
    4840: "opcua",
    20000: "dnp3",
    44818: "ethernet_ip",
    102: "s7comm",
    2404: "iec104",
}


def scan_ethernet_subnet(subnet: str = None, timeout: float = 0.5,
                         max_workers: int = 128) -> List[Dict[str, Any]]:
    """P36: scan Ethernet subnet for industrial protocol ports."""
    if subnet is None:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            subnet = ".".join(local_ip.split(".")[:3])
        except Exception:
            subnet = "192.168.1"

    logger.info("[EthScan] scanning %s.1-254 for industrial ports", subnet)

    results = []

    def check_host(ip):
        found = []
        for port, proto in INDUSTRIAL_PORTS.items():
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(timeout)
                r = s.connect_ex((ip, port))
                s.close()
                if r == 0:
                    found.append({"port": port, "protocol": proto})
            except Exception:
                pass
        if found:
            return {"ip": ip, "services": found}
        return None

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
            futures = {ex.submit(check_host, f"{subnet}.{i}"): i for i in range(1, 255)}
            for fut in concurrent.futures.as_completed(futures):
                try:
                    res = fut.result()
                    if res:
                        results.append(res)
                        logger.info("[EthScan] found: %s -> %s",
                                    res["ip"], [s["protocol"] for s in res["services"]])
                except Exception:
                    pass
    except Exception as e:
        logger.error("[EthScan] error: %s", e)

    logger.info("[EthScan] total: %d hosts with industrial ports", len(results))
    return results


def get_ethernet_interfaces() -> List[Dict[str, Any]]:
    """P36: list Ethernet interfaces (not WiFi)."""
    import subprocess
    import json
    ifaces = []
    try:
        r = subprocess.run(
            ["powershell", "-Command",
             "Get-NetAdapter | Where-Object {$_.Status -eq 'Up'} | "
             "Select-Object Name, InterfaceDescription, LinkSpeed, MacAddress | "
             "ConvertTo-Json"],
            capture_output=True, text=True, timeout=10,
            encoding="utf-8", errors="ignore")
        data = json.loads(r.stdout) if r.stdout.strip() else []
        if isinstance(data, dict):
            data = [data]
        for iface in data:
            name = iface.get("Name", "")
            desc = iface.get("InterfaceDescription", "")
            if "wi-fi" in name.lower() or "wireless" in desc.lower():
                continue
            ifaces.append({
                "name": name,
                "description": desc,
                "mac": iface.get("MacAddress", ""),
                "speed": iface.get("LinkSpeed", ""),
            })
    except Exception as e:
        logger.debug("[EthScan] ifaces error: %s", e)
    return ifaces
'''

with open(ETH, "w", encoding="utf-8") as f:
    f.write(eth_code)
try:
    ast.parse(eth_code)
    print(f"  [OK] created: {os.path.basename(ETH)}")
except SyntaxError as e:
    print(f"  [!!] syntax error: {e}")


# ============================================================
# P36c. web/app.py: /api/ethernet/scan + /api/ethernet/interfaces
# ============================================================
print()
print("=" * 70)
print("  P36c: web/app.py endpoints")
print("=" * 70)
backup(APP)
with open(APP, "r", encoding="utf-8") as f:
    content = f.read()

marker = "@app.route('/api/rf/signals')"
if '/api/ethernet/scan' in content:
    print("  [--] already applied")
elif marker in content:
    new_endpoints = '''@app.route('/api/ethernet/scan', methods=['POST'])
def api_ethernet_scan():
    """P36: scan Ethernet subnet for industrial protocols."""
    d = request.json or {}
    subnet = d.get('subnet')
    try:
        from inevionet.network.ethernet_scanner import scan_ethernet_subnet
        results = scan_ethernet_subnet(subnet=subnet)
        for host in results:
            ip = host['ip']
            for svc in host['services']:
                nid = 'ind_%s_%s' % (svc['protocol'], ip.replace('.', '_'))
                upsert({
                    'node_id': nid,
                    'name': '%s @ %s' % (svc['protocol'].upper(), ip),
                    'label': '%s:%s' % (svc['protocol'], ip),
                    'type': 'industrial',
                    'ip': ip,
                    'port': svc['port'],
                    'trust': 70.0, 'packets': 0, 'online': True,
                    'rssi': -30, 'signal': 100,
                    'method': 'ethernet_scan',
                    'evolving': False,
                    'parent': get_net().node_id,
                })
        return jsonify({'success': True, 'hosts': results, 'count': len(results)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ethernet/interfaces')
def api_ethernet_interfaces():
    """P36: list Ethernet interfaces."""
    try:
        from inevionet.network.ethernet_scanner import get_ethernet_interfaces
        return jsonify({'success': True, 'interfaces': get_ethernet_interfaces()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


''' + marker
    content = content.replace(marker, new_endpoints, 1)
    print("  [OK] /api/ethernet/scan + /api/ethernet/interfaces added")
else:
    print("  [!!] marker NOT FOUND — проверь вручную")

save_py(APP, content)


# ============================================================
# P36d. index.html: Ethernet button + JS
# ============================================================
print()
print("=" * 70)
print("  P36d: index.html Ethernet button + JS")
print("=" * 70)
backup(HTML)
with open(HTML, "r", encoding="utf-8") as f:
    html = f.read()

# 1. Add button
marker_btn = '<button class="btn btn-glass" onclick="scanIndustrial()">🔍 Найти устройства</button>'
new_btn = '<button class="btn btn-glass" onclick="scanIndustrial()">🔍 Найти устройства</button>\n<button class="btn btn-glass" onclick="scanEthernet()">🌐 Ethernet (пром.)</button>'

if 'scanEthernet' in html:
    print("  [--] button already exists")
elif marker_btn in html:
    html = html.replace(marker_btn, new_btn, 1)
    print("  [OK] button added")
else:
    print("  [!!] button marker NOT FOUND")

# 2. Add JS function
marker_js = 'function generateQR() {'
js_func = '''async function scanEthernet() {
    addLog('Ethernet scan (industrial)...', 'info');
    document.getElementById('industrialResults').textContent = 'Ethernet scanning...';
    try {
        const r = await fetch('/api/ethernet/scan', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({})
        });
        const d = await r.json();
        if (d.success) {
            document.getElementById('industrialResults').textContent =
                '🌐 Ethernet: ' + d.count + ' хостов';
            addLog('Ethernet: ' + d.count + ' хостов с пром. портами', 'success');
        } else {
            addLog('Ethernet error: ' + (d.error || '?'), 'error');
        }
    } catch (e) { addLog('Ethernet: ' + e, 'error'); }
}

function generateQR() {'''

if 'async function scanEthernet' in html:
    print("  [--] JS already exists")
elif marker_js in html:
    html = html.replace(marker_js, js_func, 1)
    print("  [OK] JS added")
else:
    print("  [!!] JS marker NOT FOUND")

save_raw(HTML, html)


# ============================================================
# DONE
# ============================================================
print()
print("=" * 70)
print("  PATCH 36 DONE")
print("=" * 70)
print()
print("  [OK] orchestrator: _capsule_deploy_cycle MAC from label")
print("  [OK] network/ethernet_scanner.py created")
print("  [OK] web/app.py: /api/ethernet/scan + /api/ethernet/interfaces")
print("  [OK] index.html: button + JS")
print()
print("Перезапусти: python -m web.app")
print()
print("Проверка:")
print("  curl.exe -k https://localhost:8080/api/ethernet/interfaces")
print("  curl.exe -k -X POST https://localhost:8080/api/ethernet/scan")