# patch25.py - Ping sweep for ARP population
import os
import ast
import shutil
import sys

ROOT = r"E:\InevioNet"
SCANNER = os.path.join(ROOT, "inevionet", "network", "arp_scanner.py")
APP = os.path.join(ROOT, "web", "app.py")
HTML = os.path.join(ROOT, "web", "templates", "index.html")


def backup(path):
    if os.path.exists(path):
        shutil.copy2(path, path + ".bak_p25")
        print(f"  Backup: {os.path.basename(path)}.bak_p25")


def save_py(path, code):
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    try:
        ast.parse(code)
        print(f"  [OK] syntax: {os.path.basename(path)}")
    except SyntaxError as e:
        print(f"  [!!] syntax error: {e}")
        if os.path.exists(path + ".bak_p25"):
            shutil.copy2(path + ".bak_p25", path)
        sys.exit(1)


def save_raw(path, code):
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    print(f"  [OK] saved: {os.path.basename(path)}")


# ============================================================
# 1. arp_scanner.py: add ping sweep
# ============================================================
print("=" * 70)
print("  PATCH 25a: ping sweep in arp_scanner.py")
print("=" * 70)

backup(SCANNER)
with open(SCANNER, "r", encoding="utf-8") as f:
    scan = f.read()

if "def ping_sweep" in scan:
    print("  [--] ping_sweep exists")
else:
    # Add ping_sweep function before scan_arp
    marker = "# P23: cache"
    ping_code = '''# P25: ping sweep
def ping_sweep(subnet: str = None, timeout: float = 0.3,
               max_workers: int = 64) -> int:
    """P25: ping all hosts in subnet to populate ARP table.

    Returns number of responding hosts.
    """
    import subprocess
    import socket
    import concurrent.futures

    # Auto-detect subnet
    if subnet is None:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            local_ip = s.getsockname()[0]
            s.close()
            subnet = ".".join(local_ip.split(".")[:3])
        except Exception:
            subnet = "192.168.1"

    logger.info("[Sweep] pinging %s.1-254 ...", subnet)

    def ping_one(i):
        ip = f"{subnet}.{i}"
        try:
            if sys.platform == "win32":
                # Windows ping
                r = subprocess.run(
                    ["ping", "-n", "1", "-w", str(int(timeout * 1000)), ip],
                    capture_output=True, timeout=2,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                return r.returncode == 0
            else:
                r = subprocess.run(
                    ["ping", "-c", "1", "-W", str(int(timeout)), ip],
                    capture_output=True, timeout=2,
                )
                return r.returncode == 0
        except Exception:
            return False

    alive = 0
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
            results = list(ex.map(ping_one, range(1, 255)))
        alive = sum(1 for r in results if r)
        logger.info("[Sweep] alive: %d/254", alive)
    except Exception as e:
        logger.error("[Sweep] error: %s", e)

    # Small delay to let ARP table settle
    import time as _t
    _t.sleep(0.5)

    return alive


# P23: cache'''
    if marker in scan:
        scan = scan.replace(marker, ping_code, 1)
        print("  [OK] ping_sweep added")
    else:
        print("  [!!] cache marker not found")

    # Add auto-sweep in scan_arp (every 4th call)
    old_scan_header = '''    results = []
    try:
        if sys.platform == "win32":'''
    new_scan_header = '''    # P25: auto ping sweep every 4 calls (with cache miss)
    global _arp_sweep_counter
    try:
        _arp_sweep_counter
    except NameError:
        _arp_sweep_counter = 0

    _arp_sweep_counter += 1
    if _arp_sweep_counter % 4 == 1:
        try:
            ping_sweep()
        except Exception:
            pass

    results = []
    try:
        if sys.platform == "win32":'''
    if old_scan_header in scan:
        scan = scan.replace(old_scan_header, new_scan_header, 1)
        print("  [OK] auto-sweep in scan_arp")

    save_py(SCANNER, scan)


# ============================================================
# 2. app.py: endpoint /api/network/sweep
# ============================================================
print()
print("=" * 70)
print("  PATCH 25b: app.py — /api/network/sweep")
print("=" * 70)

backup(APP)
with open(APP, "r", encoding="utf-8") as f:
    app = f.read()

if "/api/network/sweep" in app:
    print("  [--] sweep endpoint exists")
else:
    endpoint = '''
@app.route('/api/network/sweep', methods=['POST'])
def api_network_sweep():
    """P25: ping sweep + ARP scan."""
    d = request.json or {}
    subnet = d.get('subnet', None)
    try:
        from inevionet.network.arp_scanner import ping_sweep, scan_arp
        alive = ping_sweep(subnet=subnet, timeout=0.3, max_workers=64)
        # Scan ARP after sweep (force — skip cache)
        devices = scan_arp(force=True)

        # Add to nodes
        for dev in devices:
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
                'method': 'ping_sweep',
                'evolving': False,
                'parent': None,
                'mac': dev['mac'],
            })

        return jsonify({
            'success': True,
            'alive': alive,
            'devices_found': len(devices),
            'devices': devices,
        })
    except Exception as e:
        log.error('[Sweep] error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


'''
    marker = "@socketio.on('connect')"
    if marker in app:
        app = app.replace(marker, endpoint + marker, 1)
        save_py(APP, app)
        print("  [OK] /api/network/sweep added")


# ============================================================
# 3. UI: button "Scan network"
# ============================================================
print()
print("=" * 70)
print("  PATCH 25c: UI — network scan button")
print("=" * 70)

backup(HTML)
with open(HTML, "r", encoding="utf-8") as f:
    html = f.read()

if "btnNetworkSweep" in html:
    print("  [--] sweep button exists")
else:
    # Add to capsule card (before kill button)
    old = '''<button class="btn btn-danger" onclick="killCapsules()">⛔ СТОП (убить все капсулы)</button>'''
    new = '''<button class="btn btn-primary" onclick="networkSweep()">🌐 Сканировать сеть (ping sweep)</button>
<button class="btn btn-danger" onclick="killCapsules()">⛔ СТОП (убить все капсулы)</button>'''
    if old in html:
        html = html.replace(old, new, 1)
        print("  [OK] sweep button added")

    # Add JS
    js = '''
async function networkSweep() {
    if (!confirm('Пропинговать всю подсеть 192.168.x.1-254?\\nЭто может занять 10-15 секунд.')) return;
    addLog('Ping sweep 192.168.x.x ...', 'warn');
    try {
        const r = await fetch('/api/network/sweep', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({})
        });
        const d = await r.json();
        if (d.success) {
            addLog('Sweep: alive=' + d.alive + ', devices=' + d.devices_found, 'success');
            const el = document.getElementById('capsuleList');
            if (el) {
                let out = '<div style="margin-top:10px">';
                out += '<b>Найдено устройств (' + d.devices_found + '):</b><br>';
                for (const dev of (d.devices || [])) {
                    out += '<div class="deploy-result deployed">✅ ' +
                           dev.ip + ' (' + dev.type + ') ' +
                           dev.mac + '</div>';
                }
                out += '</div>';
                el.innerHTML = out + el.innerHTML;
            }
        } else {
            addLog('Sweep error: ' + (d.error || '?'), 'error');
        }
    } catch (e) {
        addLog('Sweep: ' + e, 'error');
    }
}

'''
    js_marker = "checkAuth();"
    if js_marker in html:
        html = html.replace(js_marker, js + '\n' + js_marker, 1)
        print("  [OK] sweep JS added")

    save_raw(HTML, html)


print()
print("=" * 70)
print("  PATCH 25 DONE")
print("=" * 70)
print()
print("Что изменилось:")
print("  [OK] arp_scanner.py: ping_sweep() — пингует 254 адреса")
print("  [OK] arp_scanner.py: auto-sweep каждые 4 вызова")
print("  [OK] /api/network/sweep — endpoint")
print("  [OK] UI: кнопка 🌐 Сканировать сеть")
print()
print("Перезапусти сервер: python -m web.app")