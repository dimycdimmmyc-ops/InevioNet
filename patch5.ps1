# Patch 5: web/app.py - add 6 new endpoints
$ErrorActionPreference = "Stop"
$ProjectRoot = "E:\InevioNet"

$path = Join-Path $ProjectRoot "web\app.py"
$content = [System.IO.File]::ReadAllText($path, [System.Text.Encoding]::UTF8)
$content = $content -replace "`r`n", "`n"
$content = $content -replace "`r", "`n"

# Проверка
if ($content.Contains("/api/industrial/scan")) {
    Write-Host "[!!] endpoints already added" -ForegroundColor Yellow
    return
}

# Точка вставки - перед "# SOCKETIO"
$marker = "# ================================================================`n# SOCKETIO"
$pos = $content.IndexOf($marker)

if ($pos -lt 0) {
    Write-Host "[!!] SOCKETIO marker not found" -ForegroundColor Red
    # Альтернатива
    $marker = "@socketio.on('connect')"
    $pos = $content.IndexOf($marker)
    if ($pos -lt 0) {
        Write-Host "[!!] @socketio.on('connect') not found either" -ForegroundColor Red
        return
    }
}

Write-Host "Insert position: $pos" -ForegroundColor Cyan

$newEndpoints = @'
# ================================================================
# P13: INDUSTRIAL / STEGO / EVOLUTION endpoints
# ================================================================
@app.route('/api/industrial/scan', methods=['POST'])
def api_industrial_scan():
    """P13: СЃРєР°РЅРёСЂРѕРІР°РЅРёРµ РїСЂРѕРјС‹С€Р»РµРЅРЅС‹С… РїСЂРѕС‚РѕРєРѕР»РѕРІ."""
    d = request.json or {}
    target = (d.get('target') or '').strip()
    if not target:
        return jsonify({'success': False, 'error': 'no_target'}), 400
    try:
        n = get_net()
        results = n.scan_industrial(target)
        for proto, res in results.items():
            if res.get('found'):
                nid = 'ind_%s_%s' % (proto, target.replace(':', '_'))
                upsert({
                    'node_id': nid,
                    'name': '%s @ %s' % (proto.upper(), target),
                    'label': '%s:%s' % (proto, target),
                    'type': 'industrial',
                    'ip': target.split(':')[0],
                    'port': {'modbus': 502, 'mqtt': 1883,
                             'opcua': 4840, 'dnp3': 20000}.get(proto, 0),
                    'trust': 70.0, 'packets': 0, 'online': True,
                    'rssi': -50, 'signal': 80,
                    'method': 'industrial_scan',
                    'evolving': False, 'parent': n.node_id,
                })
        return jsonify({'success': True, 'target': target, 'results': results})
    except Exception as e:
        log.error('[Industrial] scan error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/industrial/mqtt/publish', methods=['POST'])
def api_industrial_mqtt_publish():
    d = request.json or {}
    host = (d.get('host') or '').strip()
    topic = d.get('topic', 'inevionet/test')
    message = d.get('message', '')
    if not host or not message:
        return jsonify({'success': False, 'error': 'empty'}), 400
    try:
        n = get_net()
        result = n.transport.send_via_mqtt(
            data=message.encode('utf-8'), host=host,
            port=int(d.get('port', 1883)), topic=topic,
            qos=int(d.get('qos', 0)))
        return jsonify({
            'success': result.success,
            'bytes_sent': result.bytes_sent,
            'error': result.error,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/stego/send', methods=['POST'])
def api_stego_send():
    """P13: РѕС‚РїСЂР°РІРєР° С‡РµСЂРµР· СЃС‚РµРіР°РЅРѕРіСЂР°С„РёСЋ."""
    d = request.json or {}
    target = d.get('target', 'httpbin.org')
    method = d.get('method', 'HTTP_HEADERS')
    data_str = d.get('data', 'test message')
    try:
        n = get_net()
        data = data_str.encode('utf-8')
        result = n.stealth.send(data, method=method, target=target)
        if hasattr(n, 'evolution') and n.evolution:
            n.evolution.reward('stego', method, result.success)
        return jsonify({
            'success': result.success,
            'method': result.method,
            'bytes_sent': result.bytes_sent,
            'overhead': result.overhead,
            'duration_ms': result.duration_ms,
            'error': result.error,
        })
    except Exception as e:
        log.error('[Stego] send error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/evolution/catastrophe', methods=['POST'])
def api_evolution_catastrophe():
    """P13: С„РѕСЂСЃРёСЂРѕРІР°С‚СЊ РєР°С‚Р°СЃС‚СЂРѕС„Сѓ."""
    try:
        n = get_net()
        if not n.evolution:
            return jsonify({'success': False, 'error': 'no_evolution'}), 400
        before = n.evolution.get_stats()
        n.evolution._catastrophe()
        after = n.evolution.get_stats()
        return jsonify({
            'success': True,
            'generation': n.evolution.generation,
            'before': before, 'after': after,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/evolution/best_strategies')
def api_evolution_best_strategies():
    """P13: Р»СѓС‡С€РёРµ СЃС‚СЂР°С‚РµРіРёРё РїРѕ С‚РёРїР°Рј."""
    try:
        n = get_net()
        if not n.evolution:
            return jsonify({'success': False, 'error': 'no_evolution'})
        return jsonify({
            'success': True,
            'generation': n.evolution.generation,
            'best': {
                'penetration': n.evolution.best_strategy('penetration'),
                'masking': n.evolution.best_strategy('masking'),
                'stego': n.evolution.best_strategy('stego'),
                'industrial': n.evolution.best_strategy('industrial'),
                'protocol': n.evolution.best_strategy('protocol'),
            },
            'stats': n.evolution.get_stats(),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/masking/stats')
def api_masking_stats_full():
    """P13: СЃС‚Р°С‚РёСЃС‚РёРєР° РјР°СЃРєРёСЂРѕРІРєРё."""
    try:
        n = get_net()
        return jsonify({'success': True, 'stats': n.get_masking_stats()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


'@

$newContent = $content.Substring(0, $pos) + $newEndpoints + $content.Substring($pos)

$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($path, $newContent, $utf8)
Write-Host "[OK] web/app.py patched" -ForegroundColor Green

# Проверка синтаксиса
$check = python -c "import ast; ast.parse(open(r'$path', encoding='utf-8').read()); print('OK')" 2>&1
Write-Host "Syntax: $check"