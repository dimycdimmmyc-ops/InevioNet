# Patch 12a: Polish - logs, icons, export
$ErrorActionPreference = "Stop"
$ProjectRoot = "E:\InevioNet"

# ============================================================
# 1. Fix duplicate logs in web/app.py
# ============================================================
$appPath = Join-Path $ProjectRoot "web\app.py"
$app = [System.IO.File]::ReadAllText($appPath, [System.Text.Encoding]::UTF8)
$app = $app -replace "`r`n", "`n"

if ($app.Contains("P13: dedup logs")) {
    Write-Host "[--] logs already dedup'd" -ForegroundColor Yellow
} else {
    $oldBridge = @'
def install_log_bridge():
    fmt = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] %(name)s: %(message)s',
        datefmt='%H:%M:%S',
    )
    root = logging.getLogger('inevionet')
    # Убираем дубли
    streams = [h for h in root.handlers
               if isinstance(h, logging.StreamHandler)
               and not isinstance(h, SocketLogHandler)]
    for h in streams[1:]:
        root.removeHandler(h)
    # Добавляем мост, если нет
    if not any(isinstance(h, SocketLogHandler) for h in root.handlers):
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt)
        bh = SocketLogHandler()
        bh.setFormatter(fmt)
        root.addHandler(sh)
        root.addHandler(bh)
    root.setLevel(logging.INFO)
'@

    $newBridge = @'
def install_log_bridge():
    # P13: dedup logs - remove ALL handlers first
    fmt = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] %(name)s: %(message)s',
        datefmt='%H:%M:%S',
    )
    root = logging.getLogger('inevionet')
    # Remove ALL existing handlers
    for h in list(root.handlers):
        root.removeHandler(h)
    # Add console + socket
    sh = logging.StreamHandler(sys.stdout)
    try:
        sh.stream.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    sh.setFormatter(fmt)
    bh = SocketLogHandler()
    bh.setFormatter(fmt)
    root.addHandler(sh)
    root.addHandler(bh)
    root.setLevel(logging.INFO)
    root.propagate = False
'@

    if ($app.Contains($oldBridge)) {
        $app = $app.Replace($oldBridge, $newBridge)
        Write-Host "[OK] Log dedup applied" -ForegroundColor Green
    } else {
        Write-Host "[--] Log bridge pattern not found" -ForegroundColor Yellow
    }
}

# ============================================================
# 2. Add export endpoint
# ============================================================
if ($app.Contains("/api/export/full")) {
    Write-Host "[--] Export endpoint already added" -ForegroundColor Yellow
} else {
    $newExport = @'
@app.route('/api/export/full')
def api_export_full():
    """P13: Full state export as JSON."""
    try:
        n = get_net()
        nodes = snapshot()
        state = {
            'node_id': n.node_id,
            'timestamp': time.time(),
            'nodes': nodes,
            'infected': len(get_footholds()),
            'inbox': list(get_inbox())[-50:],
            'stats': n.get_stats(),
            'evolution': n.evolution.get_stats() if n.evolution else {},
            'best_strategies': {
                'penetration': n.evolution.best_strategy('penetration') if n.evolution else None,
                'masking': n.evolution.best_strategy('masking') if n.evolution else None,
                'stego': n.evolution.best_strategy('stego') if n.evolution else None,
                'industrial': n.evolution.best_strategy('industrial') if n.evolution else None,
            },
        }
        return jsonify(state)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/export/state.json')
def api_export_state_json():
    """P13: Download state as .json file."""
    try:
        n = get_net()
        state = {
            'node_id': n.node_id,
            'timestamp': time.time(),
            'nodes': snapshot(),
            'infected': len(get_footholds()),
            'stats': n.get_stats(),
        }
        from flask import Response
        import json as _json
        return Response(
            _json.dumps(state, ensure_ascii=False, indent=2),
            mimetype='application/json',
            headers={'Content-Disposition': 'attachment; filename=inevionet_state.json'},
        )
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
        $app = $app.Substring(0, $pos) + $newExport + $app.Substring($pos)
        Write-Host "[OK] Export endpoints added" -ForegroundColor Green
    }
}

$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($appPath, $app, $utf8)

# Syntax check
python -c "import ast; ast.parse(open(r'$appPath', encoding='utf-8').read()); print('OK')"

# ============================================================
# 3. Add icons for new node types + export button in index.html
# ============================================================
$htmlPath = Join-Path $ProjectRoot "web\templates\index.html"
$html = [System.IO.File]::ReadAllText($htmlPath, [System.Text.Encoding]::UTF8)
$html = $html -replace "`r`n", "`n"

# 3.1. Update COLORS and RANK
$oldColors = "const COLORS = { self:'#00ff9c', wifi:'#2ed573', bluetooth:'#4a9eff', peer:'#00ffff', spore:'#ff6b9d' };"
$newColors = "const COLORS = { self:'#00ff9c', wifi:'#2ed573', bluetooth:'#4a9eff', peer:'#00ffff', spore:'#ff6b9d', ble:'#00cec9', cellular:'#fdcb6e', industrial:'#e17055', super:'#ffeaa7' };"

if ($html.Contains($oldColors)) {
    $html = $html.Replace($oldColors, $newColors)
    Write-Host "[OK] COLORS updated" -ForegroundColor Green
}

$oldRank = "const RANK = { self:0, wifi:1, spore:2, bluetooth:3, peer:4 };"
$newRank = "const RANK = { self:0, wifi:1, super:2, spore:3, ble:4, bluetooth:5, cellular:6, industrial:7, peer:8 };"

if ($html.Contains($oldRank)) {
    $html = $html.Replace($oldRank, $newRank)
    Write-Host "[OK] RANK updated" -ForegroundColor Green
}

# 3.2. Add export button in Export card
$oldExportCard = @'
<div class="card">
<h3>Экспорт</h3>
'@

$newExportCard = @'
<div class="card">
<h3>Экспорт</h3>
<button class="btn small" onclick="exportState()">Download state.json</button>
'@

if ($html.Contains($oldExportCard) -and -not $html.Contains("exportState()")) {
    $html = $html.Replace($oldExportCard, $newExportCard)
    Write-Host "[OK] Export button added" -ForegroundColor Green
}

# 3.3. Add exportState JS function
if (-not $html.Contains("function exportState()")) {
    $exportJS = @'
async function exportState() {
    addLog('Exporting state...', 'info');
    try {
        const r = await fetch('/api/export/state.json');
        const blob = await r.blob();
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = 'inevionet_state_' + Date.now() + '.json';
        a.click();
        URL.revokeObjectURL(url);
        addLog('State exported', 'success');
    } catch (e) {
        addLog('Export: ' + e, 'error');
    }
}

'@

    $jsMarker = "checkAuth();"
    $jsPos = $html.IndexOf($jsMarker)
    if ($jsPos -gt 0) {
        $html = $html.Substring(0, $jsPos) + $exportJS + $html.Substring($jsPos)
        Write-Host "[OK] exportState JS added" -ForegroundColor Green
    }
}

$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($htmlPath, $html, $utf8)
Write-Host "[OK] index.html saved" -ForegroundColor Green

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  PATCH 12a DONE" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Fixed:" -ForegroundColor Cyan
Write-Host "  - Log duplication (root.propagate = False)" -ForegroundColor White
Write-Host "  - UTF-8 in stdout" -ForegroundColor White
Write-Host "  - New node colors (BLE, cellular, industrial, super)" -ForegroundColor White
Write-Host "  - Export endpoint: /api/export/state.json" -ForegroundColor White
Write-Host "  - Export button in UI" -ForegroundColor White