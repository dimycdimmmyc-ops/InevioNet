# Patch 7e: Tor/BLE/LTE endpoints + UI
$ErrorActionPreference = "Stop"
$ProjectRoot = "E:\InevioNet"

# === 1. web/app.py endpoints ===
$appPath = Join-Path $ProjectRoot "web\app.py"
$app = [System.IO.File]::ReadAllText($appPath, [System.Text.Encoding]::UTF8)
$app = $app -replace "`r`n", "`n"

if ($app.Contains("/api/tor/status")) {
    Write-Host "[--] Tor endpoints already added" -ForegroundColor Yellow
} else {
    $newEndpoints = @'
@app.route('/api/tor/status')
def api_tor_status():
    """P13: Tor availability."""
    try:
        from inevionet.network.tor_transport import TorTransport
        t = TorTransport()
        return jsonify({'success': True, 'available': t.is_available()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/tor/send', methods=['POST'])
def api_tor_send():
    """P13: Send via Tor."""
    d = request.json or {}
    host = d.get('host', 'check.torproject.org')
    port = int(d.get('port', 80))
    data = d.get('data', 'GET / HTTP/1.0\r\n\r\n')
    try:
        from inevionet.network.tor_transport import TorTransport
        t = TorTransport()
        if not t.is_available():
            return jsonify({'success': False, 'error': 'tor_unavailable'}), 503
        ok, resp = t.send(data.encode('utf-8'), host, port)
        return jsonify({
            'success': ok,
            'response_len': len(resp) if resp else 0,
            'via': 'tor',
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ble/scan', methods=['POST'])
def api_ble_scan():
    """P13: BLE scan."""
    d = request.json or {}
    duration = float(d.get('duration', 5.0))
    try:
        from inevionet.network.ble_scanner import scan_ble
        devices = scan_ble(duration=duration)
        for dev in devices:
            nid = 'ble_' + dev.get('mac', 'unknown')
            upsert({
                'node_id': nid,
                'name': dev.get('name', 'BLE'),
                'label': dev.get('name', 'BLE')[:20],
                'type': 'ble',
                'ip': 'unknown', 'port': 0,
                'trust': 50.0, 'packets': 0, 'online': True,
                'rssi': dev.get('rssi', -70), 'signal': 50,
                'method': 'ble_scan', 'evolving': False,
                'parent': None,
            })
        return jsonify({'success': True, 'devices': devices, 'count': len(devices)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/lte/scan', methods=['POST'])
def api_lte_scan():
    """P13: LTE/5G scan."""
    try:
        from inevionet.network.lte_scanner import scan_lte
        cells = scan_lte()
        for cell in cells:
            nid = 'cell_' + (cell.get('operator', 'unknown')[:16])
            upsert({
                'node_id': nid,
                'name': cell.get('operator', 'Cell'),
                'label': cell.get('tech', 'LTE'),
                'type': 'cellular',
                'ip': 'unknown', 'port': 0,
                'trust': 60.0, 'packets': 0, 'online': True,
                'rssi': -85, 'signal': 40,
                'method': 'lte_scan', 'evolving': False,
                'parent': None,
            })
        return jsonify({'success': True, 'cells': cells, 'count': len(cells)})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


'@

    # Insert before SOCKETIO
    $marker = "# ================================================================`n# SOCKETIO"
    $pos = $app.IndexOf($marker)
    if ($pos -lt 0) {
        $marker = "@socketio.on('connect')"
        $pos = $app.IndexOf($marker)
    }
    if ($pos -gt 0) {
        $app = $app.Substring(0, $pos) + $newEndpoints + $app.Substring($pos)
        $utf8 = New-Object System.Text.UTF8Encoding($false)
        [System.IO.File]::WriteAllText($appPath, $app, $utf8)
        Write-Host "[OK] app.py: Tor/BLE/LTE endpoints added" -ForegroundColor Green
        python -c "import ast; ast.parse(open(r'$appPath', encoding='utf-8').read()); print('OK')"
    } else {
        Write-Host "[!!] SOCKETIO marker not found" -ForegroundColor Red
    }
}

# === 2. index.html UI ===
$htmlPath = Join-Path $ProjectRoot "web\templates\index.html"
$html = [System.IO.File]::ReadAllText($htmlPath, [System.Text.Encoding]::UTF8)
$html = $html -replace "`r`n", "`n"

if ($html.Contains("btnTorStatus")) {
    Write-Host "[--] UI already added" -ForegroundColor Yellow
    return
}

# Card HTML - ASCII only
$newCard = @'
<div class="card">
<h3>Network Scanners</h3>
<button class="btn secondary" onclick="checkTor()">Check Tor</button>
<button class="btn secondary" onclick="scanBLE()">Scan BLE</button>
<button class="btn secondary" onclick="scanLTE()">Scan LTE/5G</button>
<div id="netScanResult"></div>
</div>

'@

$logMarker = 'id="logContainer"'
$logPos = $html.IndexOf($logMarker)
if ($logPos -gt 0) {
    $backPos = $html.LastIndexOf('<div class="card">', $logPos)
    if ($backPos -gt 0) {
        $html = $html.Substring(0, $backPos) + $newCard + $html.Substring($backPos)
        Write-Host "[OK] HTML card inserted" -ForegroundColor Green
    }
}

# JS functions
$newJS = @'
// P13: Network scanners
async function checkTor() {
    addLog('Checking Tor...', 'info');
    try {
        const r = await fetch('/api/tor/status');
        const d = await r.json();
        const el = document.getElementById('netScanResult');
        if (d.available) {
            el.textContent = 'Tor: AVAILABLE (127.0.0.1:9050)';
            addLog('Tor OK', 'success');
        } else {
            el.textContent = 'Tor: NOT AVAILABLE';
            addLog('Tor not running', 'warn');
        }
    } catch (e) {
        addLog('Tor check: ' + e, 'error');
    }
}

async function scanBLE() {
    addLog('BLE scan (5s)...', 'info');
    const el = document.getElementById('netScanResult');
    el.textContent = 'BLE scanning...';
    try {
        const r = await fetch('/api/ble/scan', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ duration: 5.0 })
        });
        const d = await r.json();
        if (d.success) {
            el.textContent = 'BLE: ' + d.count + ' devices';
            addLog('BLE found: ' + d.count, 'success');
        } else {
            el.textContent = 'BLE error: ' + d.error;
        }
    } catch (e) {
        addLog('BLE: ' + e, 'error');
    }
}

async function scanLTE() {
    addLog('LTE/5G scan...', 'info');
    const el = document.getElementById('netScanResult');
    el.textContent = 'LTE scanning...';
    try {
        const r = await fetch('/api/lte/scan', { method: 'POST' });
        const d = await r.json();
        if (d.success) {
            el.textContent = 'LTE: ' + d.count + ' cells';
            addLog('LTE found: ' + d.count, 'success');
        } else {
            el.textContent = 'LTE error: ' + d.error;
        }
    } catch (e) {
        addLog('LTE: ' + e, 'error');
    }
}

'@

$jsMarker = "checkAuth();"
$jsPos = $html.IndexOf($jsMarker)
if ($jsPos -gt 0) {
    $html = $html.Substring(0, $jsPos) + $newJS + $html.Substring($jsPos)
    Write-Host "[OK] JS added" -ForegroundColor Green
}

$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($htmlPath, $html, $utf8)
Write-Host "[OK] index.html saved" -ForegroundColor Green