# Patch 13: restore I2P/Bridge endpoints safely
$ErrorActionPreference = "Stop"
$ProjectRoot = "E:\InevioNet"

$appPath = Join-Path $ProjectRoot "web\app.py"
$backupDir = Join-Path $ProjectRoot "_backup_endpoints"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
Copy-Item $appPath (Join-Path $backupDir "app.py") -Force
Write-Host "Backup: $backupDir\app.py"

$app = [System.IO.File]::ReadAllText($appPath, [System.Text.Encoding]::UTF8)
$app = $app -replace "`r`n", "`n"

# === 1. I2P endpoints ===
if ($app.Contains("/api/i2p/status")) {
    Write-Host "[--] I2P endpoints already present" -ForegroundColor Yellow
} else {
    $i2pEndpoints = @'
@app.route('/api/i2p/status')
def api_i2p_status():
    try:
        from inevionet.network.i2p_transport import I2PTransport
        t = I2PTransport()
        return jsonify({'success': True, 'available': t.is_available()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@app.route('/api/i2p/send', methods=['POST'])
def api_i2p_send():
    d = request.json or {}
    host = d.get('host', 'i2p-projekt.i2p')
    port = int(d.get('port', 80))
    data = d.get('data', 'GET / HTTP/1.0\r\n\r\n')
    try:
        from inevionet.network.i2p_transport import I2PTransport
        t = I2PTransport()
        if not t.is_available():
            return jsonify({'success': False, 'error': 'i2p_unavailable'}), 503
        ok, resp = t.send(data.encode('utf-8'), host, port)
        return jsonify({'success': ok, 'response_len': len(resp) if resp else 0, 'via': 'i2p'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


'@
    # Insert before SOCKETIO
    $marker = "@socketio.on('connect')"
    $pos = $app.IndexOf($marker)
    if ($pos -gt 0) {
        $app = $app.Substring(0, $pos) + $i2pEndpoints + $app.Substring($pos)
        Write-Host "[OK] I2P endpoints added" -ForegroundColor Green
    }
}

# === 2. Bridge endpoints ===
if ($app.Contains("/api/bridge/status")) {
    Write-Host "[--] Bridge endpoints already present" -ForegroundColor Yellow
} else {
    $bridgeEndpoints = @'
_bridge_broker = None
_bridge_relay = None
_bridge_lock = __import__('threading').Lock()


def _get_bridge_broker():
    global _bridge_broker
    with _bridge_lock:
        if _bridge_broker is None:
            from inevionet.network.bridge_broker import BridgeBroker
            _bridge_broker = BridgeBroker()
        return _bridge_broker


@app.route('/api/bridge/status')
def api_bridge_status():
    try:
        broker = _get_bridge_broker()
        return jsonify({
            'success': True,
            'broker': broker.get_stats(),
            'relays': broker.get_relays(),
            'is_volunteer': _bridge_relay is not None,
            'relay': _bridge_relay.get_stats() if _bridge_relay else None,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bridge/volunteer', methods=['POST'])
def api_bridge_volunteer():
    global _bridge_relay
    d = request.json or {}
    capacity = int(d.get('capacity', 10))
    region = d.get('region', 'unknown')
    try:
        from inevionet.network.relay_node import RelayNode
        broker = _get_bridge_broker()
        n = get_net()
        with _bridge_lock:
            if _bridge_relay is not None:
                _bridge_relay.stop()
            _bridge_relay = RelayNode(node_id=n.node_id, broker=broker,
                                       capacity=capacity, region=region)
            _bridge_relay.start()
        return jsonify({'success': True, 'relay': _bridge_relay.get_stats(),
                        'broker': broker.get_stats()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bridge/stop', methods=['POST'])
def api_bridge_stop():
    global _bridge_relay
    try:
        with _bridge_lock:
            if _bridge_relay is not None:
                _bridge_relay.stop()
                _bridge_relay = None
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bridge/request', methods=['POST'])
def api_bridge_request():
    d = request.json or {}
    try:
        broker = _get_bridge_broker()
        relay = broker.pick_relay(region=d.get('region'))
        if relay:
            return jsonify({'success': True, 'relay': relay.to_dict()})
        return jsonify({'success': False, 'error': 'no_relay_available'}), 503
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


'@
    $marker = "@socketio.on('connect')"
    $pos = $app.IndexOf($marker)
    if ($pos -gt 0) {
        $app = $app.Substring(0, $pos) + $bridgeEndpoints + $app.Substring($pos)
        Write-Host "[OK] Bridge endpoints added" -ForegroundColor Green
    }
}

# === 3. Export endpoints ===
if ($app.Contains("/api/export/state.json")) {
    Write-Host "[--] Export endpoints already present" -ForegroundColor Yellow
} else {
    $exportEndpoints = @'
@app.route('/api/export/state.json')
def api_export_state_json():
    try:
        from flask import Response
        import json as _json
        n = get_net()
        state = {
            'node_id': n.node_id,
            'timestamp': time.time(),
            'nodes': snapshot(),
            'infected': len(get_footholds()),
            'stats': n.get_stats(),
        }
        return Response(
            _json.dumps(state, ensure_ascii=False, indent=2),
            mimetype='application/json',
            headers={'Content-Disposition': 'attachment; filename=inevionet_state.json'},
        )
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


'@
    $marker = "@socketio.on('connect')"
    $pos = $app.IndexOf($marker)
    if ($pos -gt 0) {
        $app = $app.Substring(0, $pos) + $exportEndpoints + $app.Substring($pos)
        Write-Host "[OK] Export endpoint added" -ForegroundColor Green
    }
}

# === 4. Restore wifi_provider ===
if ($app.Contains("wifi_provider=scan_wifi")) {
    Write-Host "[--] wifi_provider already set" -ForegroundColor Yellow
} else {
    $oldCall = "net.enable_rf_scanning(interface='Wi-Fi')"
    $newCall = "net.enable_rf_scanning(interface='Wi-Fi', wifi_provider=scan_wifi)"
    if ($app.Contains($oldCall)) {
        $app = $app.Replace($oldCall, $newCall)
        Write-Host "[OK] wifi_provider restored" -ForegroundColor Green
    }
}

$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($appPath, $app, $utf8)
Write-Host "[OK] app.py saved" -ForegroundColor Green

python -c "import ast; ast.parse(open(r'$appPath', encoding='utf-8').read()); print('OK')"

Write-Host ""
Write-Host "Restart: python -m web.app" -ForegroundColor Cyan