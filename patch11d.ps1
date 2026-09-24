# Patch 11d: P2P Bridge API + UI
$ErrorActionPreference = "Stop"
$ProjectRoot = "E:\InevioNet"

# === 1. API endpoints in web/app.py ===
$appPath = Join-Path $ProjectRoot "web\app.py"
$app = [System.IO.File]::ReadAllText($appPath, [System.Text.Encoding]::UTF8)
$app = $app -replace "`r`n", "`n"

if ($app.Contains("/api/bridge/volunteer")) {
    Write-Host "[--] Bridge endpoints already added" -ForegroundColor Yellow
} else {
    $newEndpoints = @'
# P13: P2P Bridge state
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
    """P13: Bridge status."""
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
    """P13: Become a relay node."""
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
            _bridge_relay = RelayNode(
                node_id=n.node_id,
                broker=broker,
                capacity=capacity,
                region=region,
            )
            _bridge_relay.start()
        return jsonify({
            'success': True,
            'relay': _bridge_relay.get_stats(),
            'broker': broker.get_stats(),
        })
    except Exception as e:
        log.error('[Bridge] volunteer error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bridge/stop', methods=['POST'])
def api_bridge_stop():
    """P13: Stop being a relay."""
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
    """P13: Request a relay for client (simulated)."""
    d = request.json or {}
    region = d.get('region')
    try:
        broker = _get_bridge_broker()
        relay = broker.pick_relay(region=region)
        if relay:
            return jsonify({
                'success': True,
                'relay': relay.to_dict(),
            })
        return jsonify({
            'success': False,
            'error': 'no_relay_available',
        }), 503
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


'@

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
        Write-Host "[OK] app.py: Bridge endpoints added" -ForegroundColor Green
        python -c "import ast; ast.parse(open(r'$appPath', encoding='utf-8').read()); print('OK')"
    } else {
        Write-Host "[!!] SOCKETIO marker not found" -ForegroundColor Red
    }
}

# === 2. UI card in index.html ===
$htmlPath = Join-Path $ProjectRoot "web\templates\index.html"
$html = [System.IO.File]::ReadAllText($htmlPath, [System.Text.Encoding]::UTF8)
$html = $html -replace "`r`n", "`n"

if ($html.Contains("btnBridgeStatus")) {
    Write-Host "[--] UI already patched" -ForegroundColor Yellow
} else {
    $newCard = @'
<div class="card">
<h3>P2P Bridge</h3>
<div class="form-group"><label>Region (optional)</label>
<input id="bridgeRegion" value="RU"></div>
<div class="form-group"><label>Capacity</label>
<input id="bridgeCapacity" value="10" type="number"></div>
<button class="btn secondary" onclick="checkBridge()">Status</button>
<button class="btn secondary" onclick="becomeVolunteer()">Become Relay</button>
<button class="btn secondary" onclick="stopVolunteer()">Stop Relay</button>
<button class="btn small" onclick="requestRelay()">Request Relay</button>
<div id="bridgeResult"></div>
</div>

'@

    $logMarker = 'id="logContainer"'
    $logPos = $html.IndexOf($logMarker)
    if ($logPos -gt 0) {
        $backPos = $html.LastIndexOf('<div class="card">', $logPos)
        if ($backPos -gt 0) {
            $html = $html.Substring(0, $backPos) + $newCard + $html.Substring($backPos)
            Write-Host "[OK] UI card added" -ForegroundColor Green
        }
    }

    $newJS = @'
// P13: P2P Bridge functions
async function checkBridge() {
    addLog('Bridge status...', 'info');
    try {
        const r = await fetch('/api/bridge/status');
        const d = await r.json();
        const el = document.getElementById('bridgeResult');
        if (d.success) {
            const b = d.broker || {};
            el.textContent = 'Relays: ' + (b.total_relays || 0) +
                ' | Available: ' + (b.available_relays || 0) +
                ' | You are volunteer: ' + (d.is_volunteer ? 'YES' : 'no');
            addLog('Bridge: ' + (b.total_relays || 0) + ' relays', 'success');
        } else {
            el.textContent = 'Error: ' + d.error;
        }
    } catch (e) {
        addLog('Bridge: ' + e, 'error');
    }
}

async function becomeVolunteer() {
    const region = document.getElementById('bridgeRegion').value || 'unknown';
    const capacity = parseInt(document.getElementById('bridgeCapacity').value) || 10;
    addLog('Becoming relay (region=' + region + ', cap=' + capacity + ')...', 'info');
    try {
        const r = await fetch('/api/bridge/volunteer', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ region, capacity })
        });
        const d = await r.json();
        const el = document.getElementById('bridgeResult');
        if (d.success) {
            el.textContent = 'You are now a relay! capacity=' + (d.relay.capacity || 0);
            addLog('Relay started', 'success');
        } else {
            el.textContent = 'Error: ' + d.error;
        }
    } catch (e) {
        addLog('Volunteer: ' + e, 'error');
    }
}

async function stopVolunteer() {
    addLog('Stopping relay...', 'info');
    try {
        const r = await fetch('/api/bridge/stop', { method: 'POST' });
        const d = await r.json();
        if (d.success) {
            addLog('Relay stopped', 'success');
            document.getElementById('bridgeResult').textContent = 'Stopped';
        }
    } catch (e) {
        addLog('Stop: ' + e, 'error');
    }
}

async function requestRelay() {
    addLog('Requesting relay...', 'info');
    try {
        const r = await fetch('/api/bridge/request', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ region: 'RU' })
        });
        const d = await r.json();
        const el = document.getElementById('bridgeResult');
        if (d.success) {
            el.textContent = 'Got relay: ' + d.relay.node_id + ' @ ' + d.relay.endpoint;
            addLog('Relay assigned: ' + d.relay.node_id, 'success');
        } else {
            el.textContent = 'No relay: ' + d.error;
            addLog('No relay available', 'warn');
        }
    } catch (e) {
        addLog('Request: ' + e, 'error');
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
}

Write-Host ""
Write-Host "Done!" -ForegroundColor Green