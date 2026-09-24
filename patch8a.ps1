# Patch 8a: Restore scanner to 130+ nodes
$ErrorActionPreference = "Stop"
$ProjectRoot = "E:\InevioNet"

$appPath = Join-Path $ProjectRoot "web\app.py"
$backupDir = Join-Path $ProjectRoot "_backup_scanner"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
Copy-Item $appPath (Join-Path $backupDir "app.py") -Force
Write-Host "Backup: $backupDir\app.py"

$app = [System.IO.File]::ReadAllText($appPath, [System.Text.Encoding]::UTF8)
$app = $app -replace "`r`n", "`n"

if ($app.Contains("P13: FULL SCANNER RESTORED")) {
    Write-Host "[!!] Scanner already restored" -ForegroundColor Yellow
    return
}

# Найдём функцию background_scanner
$startMarker = "def background_scanner():"
$endMarker = "# ================================================================`n# ROUTES"

$startPos = $app.IndexOf($startMarker)
$endPos = $app.IndexOf($endMarker)

if ($startPos -lt 0 -or $endPos -lt 0) {
    Write-Host "[!!] background_scanner not found" -ForegroundColor Red
    return
}

Write-Host "Scanner at: $startPos, ROUTES at: $endPos" -ForegroundColor Cyan

$newScanner = @'
def background_scanner():
    """P13: FULL SCANNER RESTORED - 130+ nodes."""
    install_log_bridge()
    load_state()
    init_discovery_socket()
    log.info('[Scanner] режим ЖИВОЙ сети: RF + multicast + мицелий + эволюция')
    sc = 0
    while True:
        try:
            socketio.sleep(4)
            sc += 1
            n = get_net()
            now = time.time()

            # --- SELF ---
            upsert({
                'node_id': n.node_id,
                'name': 'My Node',
                'label': 'ME: ' + n.node_id,
                'type': 'self',
                'ip': '127.0.0.1',
                'port': 8080,
                'trust': 100.0,
                'packets': n.stats.get('packets_sent', 0),
                'online': True,
                'rssi': -30, 'signal': 100,
                'method': 'local',
                'evolving': False,
                'parent': None,
            })

            # --- DISCOVERY (каждые 3 цикла) ---
            if sc % 3 == 0:
                send_beacon()
                for p in recv_beacons():
                    upsert(p)

            # --- WIFI + MYCELIUM (каждые 2 цикла) ---
            if sc % 2 == 0:
                myc = getattr(n, 'mycelium', None) or getattr(n, '_mycelium', None)
                footholds = dict(get_footholds())
                wifi_list = scan_wifi()

                for sig in wifi_list:
                    nid = 'wifi_' + sig['bssid']
                    # WiFi ВСЕГДА обновляем
                    upsert({
                        'node_id': nid,
                        'name': sig['ssid'],
                        'label': sig['ssid'][:24],
                        'type': 'wifi',
                        'ip': 'unknown', 'port': 0,
                        'trust': max(10, min(100, 50 + sig['signal'] / 2.0)),
                        'packets': 0, 'online': True,
                        'rssi': sig['rssi_dbm'],
                        'signal': sig['signal'],
                        'method': 'rf_scan',
                        'evolving': False,
                        'parent': n.node_id,
                    })
                    # Пытаемся infiltrate ТОЛЬКО если ещё нет
                    if sig['ssid'] not in footholds and myc is not None:
                        try:
                            ok, method = myc.infiltrate(sig['ssid'], max_attempts=1)
                            if ok:
                                footholds[sig['ssid']] = method or 'unknown'
                                log.info('[Mycelium] закрепление "%s" (%s)',
                                         sig['ssid'], method)
                        except Exception:
                            pass

                set_footholds(footholds)

                # СПОРЫ - пересоздаём для ВСЕХ footholds КАЖДЫЙ цикл
                wifi_map = {s['ssid']: s for s in wifi_list}
                for ssid, method in footholds.items():
                    sig = wifi_map.get(ssid)
                    if not sig:
                        continue
                    sid = 'spore_' + sig['bssid']
                    upsert({
                        'node_id': sid,
                        'name': 'spore ' + ssid[:20],
                        'label': 'spore: ' + ssid[:18],
                        'type': 'spore',
                        'ip': 'mycelium', 'port': 0,
                        'trust': 65.0, 'packets': 0, 'online': True,
                        'rssi': sig['rssi_dbm'] - 10,
                        'signal': sig['signal'],
                        'method': 'mycelium:' + method,
                        'evolving': True,
                        'parent': 'wifi_' + sig['bssid'],
                    })

                # SUPER-NODES: WiFi с >=1 спорами = super
                for ssid, method in footholds.items():
                    sig = wifi_map.get(ssid)
                    if not sig:
                        continue
                    snid = 'super_' + sig['bssid']
                    upsert({
                        'node_id': snid,
                        'name': 'super ' + ssid[:18],
                        'label': 'super: ' + ssid[:16],
                        'type': 'super',
                        'ip': 'unknown', 'port': 0,
                        'trust': 85.0, 'packets': 0, 'online': True,
                        'rssi': sig['rssi_dbm'],
                        'signal': sig['signal'],
                        'method': 'mycelium_super',
                        'evolving': True,
                        'parent': 'wifi_' + sig['bssid'],
                    })

            # --- BLUETOOTH (каждые 4 цикла) ---
            if sc % 4 == 0:
                for d in scan_bt():
                    nid = 'bt_' + d['id']
                    upsert({
                        'node_id': nid,
                        'name': d['name'][:24],
                        'label': d['name'][:20],
                        'type': 'bluetooth',
                        'ip': 'unknown', 'port': 0,
                        'trust': 40.0, 'packets': 0, 'online': True,
                        'rssi': -70, 'signal': 50,
                        'method': 'rf_scan',
                        'evolving': False,
                        'parent': n.node_id,
                    })

            # --- EVOLUTION (каждые 10 циклов) ---
            evo_log = []
            if sc % 10 == 0:
                evo = getattr(n, 'evolution', None) or getattr(n, 'evolution_engine', None)
                if evo is not None and hasattr(evo, 'evolve'):
                    try:
                        evo.evolve()
                        st = evo.get_stats()
                        msg = '[Evolution] gen %s: best=%.3f avg=%.3f diversity=%.3f' % (
                            st.get('generation', '?'),
                            st.get('best_fitness', 0.0),
                            st.get('avg_fitness', 0.0),
                            st.get('diversity', 0.0),
                        )
                        log.info(msg)
                        evo_log.append({'time': now, 'msg': msg})
                        with state_lock:
                            _evo_log[0] = (evo_log + _evo_log[0])[:10]
                    except Exception as e:
                        log.debug('[Evolution] %s', e)

            # --- EMIT ---
            nodes = snapshot()
            socketio.emit('nodes_update', {
                'nodes': nodes,
                'count': len(nodes),
                'timestamp': now,
                'evo_log': evo_log,
                'infected': len(get_footholds()),
            })

            if sc % 5 == 0:
                log.info('[Scanner] узлов=%d, закреплений=%d',
                         len(nodes), len(get_footholds()))
                save_state()

        except Exception as e:
            log.error('[Scanner] ошибка цикла: %s', e)

# P13: FULL SCANNER RESTORED

'@

$app = $app.Substring(0, $startPos) + $newScanner + $app.Substring($endPos)

$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($appPath, $app, $utf8)
Write-Host "[OK] Scanner restored" -ForegroundColor Green

python -c "import ast; ast.parse(open(r'$appPath', encoding='utf-8').read()); print('OK')"