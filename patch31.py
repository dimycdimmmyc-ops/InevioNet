# patch31.py - InevioNet: add pywifi (scan + connect + status) ALONGSIDE netsh
import os
import ast
import shutil
import time

ROOT = r"E:\InevioNet"
APP = os.path.join(ROOT, "web", "app.py")
HTML = os.path.join(ROOT, "web", "templates", "index.html")


def backup(path):
    if os.path.exists(path):
        b = path + ".bak_p31"
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
        if os.path.exists(path + ".bak_p31"):
            shutil.copy2(path + ".bak_p31", path)
            print(f"  [--] rolled back")
        return False


def save_raw(path, code):
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    print(f"  [OK] saved: {os.path.basename(path)}")


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


# ============================================================
# P31a. web/app.py: pywifi helpers + endpoints
# ============================================================
print()
print("=" * 70)
print("  P31a: pywifi helpers + 4 endpoints")
print("=" * 70)
backup(APP)
content = load(APP)

# --- 1. Add pywifi helpers after scan_bt ---
marker1 = '''def scan_bt():'''
pywifi_helpers = '''# ================================================================
# P31: pywifi — дополнительные WiFi-возможности (scan/connect/status)
# ================================================================
_pywifi_iface = None
_pywifi_lock = None

def _get_pywifi_iface():
    """P31: lazy-init pywifi interface (first adapter)."""
    global _pywifi_iface, _pywifi_lock
    import threading as _th
    if _pywifi_lock is None:
        _pywifi_lock = _th.Lock()
    with _pywifi_lock:
        if _pywifi_iface is None:
            try:
                import pywifi
                w = pywifi.PyWiFi()
                ifaces = w.interfaces()
                if not ifaces:
                    log.warning('[pywifi] no interfaces')
                    return None
                _pywifi_iface = ifaces[0]
                log.info('[pywifi] iface=%s', _pywifi_iface.name())
            except Exception as e:
                log.warning('[pywifi] init error: %s', e)
                return None
        return _pywifi_iface


def scan_wifi_pywifi(wait_sec=4.0):
    """P31: scan WiFi via pywifi (RSSI dBm + auth)."""
    try:
        from pywifi import const  # noqa
        iface = _get_pywifi_iface()
        if iface is None:
            return []
        iface.scan()
        import time as _t
        _t.sleep(wait_sec)
        results = iface.scan_results()
        out = []
        for r in results:
            ssid = (r.ssid or '').strip()
            if not ssid or len(ssid) > 32:
                continue
            bssid = (r.bssid or '').lower()
            rssi = int(r.signal) if r.signal else -100
            # dBm -> % (грубо: -100 = 0%, -30 = 100%)
            pct = max(0, min(100, int(2 * (rssi + 100))))
            try:
                auth = str(r.auth)
            except Exception:
                auth = 'unknown'
            out.append({
                'ssid': ssid,
                'bssid': bssid,
                'signal': pct,
                'rssi_dbm': round(rssi, 1),
                'auth': auth,
                'source': 'pywifi',
            })
        return out
    except Exception as e:
        log.debug('[pywifi] scan error: %s', e)
        return []


def scan_wifi_combined():
    """P31: pywifi first, netsh fallback. Dedup by BSSID."""
    seen = {}
    # 1. pywifi
    for s in scan_wifi_pywifi():
        key = s['bssid'].replace(':', '').replace('-', '').lower()
        seen[key] = s
    # 2. netsh (only if not seen)
    try:
        for s in scan_wifi():
            key = s['bssid'].replace(':', '').replace('-', '').lower()
            if key not in seen:
                s['source'] = 'netsh'
                seen[key] = s
    except Exception:
        pass
    return list(seen.values())


def scan_bt():'''
if marker1 in content and 'scan_wifi_pywifi' not in content:
    content = content.replace(marker1, pywifi_helpers, 1)
    print("  [OK] pywifi helpers added")
elif 'scan_wifi_pywifi' in content:
    print("  [--] pywifi helpers already exist")
else:
    print("  [!!] marker 'def scan_bt():' NOT FOUND")

# --- 2. Add endpoints after /api/rf/signals ---
marker2 = '''@app.route('/api/rf/signals')
def api_rf_signals():
    nodes = snapshot()
    wifi = [v for v in nodes.values() if v.get('type') == 'wifi']
    bt = [v for v in nodes.values() if v.get('type') == 'bluetooth']
    return jsonify({'success': True, 'wifi': wifi, 'bt': bt})'''
new_endpoints = marker2 + '''


# ================================================================
# P31: pywifi endpoints (add to netsh, not replace)
# ================================================================
@app.route('/api/wifi/pywifi/scan', methods=['POST'])
def api_wifi_pywifi_scan():
    """P31: scan via pywifi (RSSI dBm + auth)."""
    try:
        sigs = scan_wifi_pywifi(wait_sec=4.0)
        for sig in sigs:
            nid = 'wifi_' + sig['bssid'].replace(':', '').replace('-', '').lower()
            upsert({
                'node_id': nid,
                'name': sig['ssid'],
                'label': sig['ssid'],
                'type': 'wifi',
                'ip': 'unknown', 'port': 0,
                'trust': max(10, min(100, 50 + sig['signal'] / 2.0)),
                'packets': 0, 'online': True,
                'rssi': sig['rssi_dbm'],
                'signal': sig['signal'],
                'method': 'pywifi_scan',
                'evolving': False,
                'parent': get_net().node_id,
                'auth': sig.get('auth', ''),
            })
        return jsonify({'success': True, 'count': len(sigs), 'signals': sigs, 'source': 'pywifi'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/wifi/combined/scan', methods=['POST'])
def api_wifi_combined_scan():
    """P31: pywifi + netsh combined scan."""
    try:
        sigs = scan_wifi_combined()
        return jsonify({
            'success': True,
            'count': len(sigs),
            'signals': sigs,
            'by_source': {
                'pywifi': len([s for s in sigs if s.get('source') == 'pywifi']),
                'netsh': len([s for s in sigs if s.get('source') == 'netsh']),
            }
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/wifi/pywifi/status')
def api_wifi_pywifi_status():
    """P31: pywifi interface status."""
    try:
        from pywifi import const
        iface = _get_pywifi_iface()
        if iface is None:
            return jsonify({'success': False, 'error': 'no_interface'})
        status_map = {
            const.IFACE_DISCONNECTED: 'disconnected',
            const.IFACE_SCANNING: 'scanning',
            const.IFACE_INACTIVE: 'inactive',
            const.IFACE_CONNECTING: 'connecting',
            const.IFACE_CONNECTED: 'connected',
        }
        st = iface.status()
        return jsonify({
            'success': True,
            'name': iface.name(),
            'status': status_map.get(st, str(st)),
            'available': True,
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/wifi/pywifi/connect', methods=['POST'])
def api_wifi_pywifi_connect():
    """P31: connect to WiFi via pywifi."""
    d = request.json or {}
    ssid = (d.get('ssid') or '').strip()
    password = d.get('password', '')
    if not ssid:
        return jsonify({'success': False, 'error': 'no_ssid'}), 400
    try:
        import pywifi
        from pywifi import const
        import time as _t

        iface = _get_pywifi_iface()
        if iface is None:
            return jsonify({'success': False, 'error': 'no_interface'}), 500

        # Disconnect first
        iface.disconnect()
        _t.sleep(1)

        # Build profile
        profile = pywifi.Profile()
        profile.ssid = ssid
        profile.auth = const.AUTH_ALG_OPEN

        if password:
            # Try WPA2-PSK first
            profile.akm.append(const.AKM_TYPE_WPA2PSK)
            profile.cipher = const.CIPHER_TYPE_CCMP
            profile.key = password

        iface.remove_all_network_profiles()
        tmp = iface.add_network_profile(profile)
        iface.connect(tmp)
        _t.sleep(5)

        connected = (iface.status() == const.IFACE_CONNECTED)
        log.info('[pywifi] connect %s: %s', ssid, 'OK' if connected else 'FAIL')
        return jsonify({
            'success': connected,
            'ssid': ssid,
            'status': 'connected' if connected else 'failed',
        })
    except Exception as e:
        log.error('[pywifi] connect error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/wifi/pywifi/disconnect', methods=['POST'])
def api_wifi_pywifi_disconnect():
    """P31: disconnect WiFi via pywifi."""
    try:
        from pywifi import const
        iface = _get_pywifi_iface()
        if iface is None:
            return jsonify({'success': False, 'error': 'no_interface'}), 500
        iface.disconnect()
        return jsonify({'success': True, 'status': 'disconnected'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500'''

if marker2 in content and '/api/wifi/pywifi/scan' not in content:
    content = content.replace(marker2, new_endpoints, 1)
    print("  [OK] 5 pywifi endpoints added")
elif '/api/wifi/pywifi/scan' in content:
    print("  [--] pywifi endpoints already exist")
else:
    print("  [!!] marker 'api_rf_signals' NOT FOUND")

if not save_py(APP, content):
    print("  [!!] app.py save failed — rolled back")
    sys.exit(1)


# ============================================================
# P31b. index.html: UI buttons
# ============================================================
print()
print("=" * 70)
print("  P31b: index.html UI buttons")
print("=" * 70)
backup(HTML)
html = load(HTML)

# Add buttons to "Сканирование сетей" card
marker3 = '''<button class="btn btn-glass" onclick="scanWiFi()">📶 Wi-Fi сети</button>'''
new_buttons = '''<button class="btn btn-glass" onclick="scanWiFi()">📶 Wi-Fi сети</button>
<button class="btn btn-glass" onclick="scanWiFiPywifi()">📡 Wi-Fi (pywifi, dBm)</button>
<button class="btn btn-glass" onclick="scanWiFiCombined()">🔀 Wi-Fi (pywifi + netsh)</button>'''

if marker3 in html and 'scanWiFiPywifi' not in html:
    html = html.replace(marker3, new_buttons, 1)
    print("  [OK] buttons added")
elif 'scanWiFiPywifi' in html:
    print("  [--] buttons already exist")
else:
    print("  [!!] marker 'scanWiFi()' NOT FOUND")

# Add JS functions before "function scanBLE()"
marker4 = '''function scanBLE() {'''
js_funcs = '''function scanWiFiPywifi() {
  addLog('pywifi scan (dBm)...', 'info');
  document.getElementById('scanResult').textContent = 'pywifi scanning...';
  fetch('/api/wifi/pywifi/scan', {method:'POST'})
    .then(r => r.json())
    .then(d => {
      if (d.success) {
        document.getElementById('scanResult').textContent =
          '📡 pywifi: ' + d.count + ' сетей';
        addLog('pywifi: ' + d.count + ' сетей (dBm)', 'success');
      } else {
        addLog('pywifi error: ' + (d.error || '?'), 'error');
      }
    })
    .catch(e => addLog('pywifi: ' + e, 'error'));
}

function scanWiFiCombined() {
  addLog('Combined scan (pywifi + netsh)...', 'info');
  document.getElementById('scanResult').textContent = 'Combined scanning...';
  fetch('/api/wifi/combined/scan', {method:'POST'})
    .then(r => r.json())
    .then(d => {
      if (d.success) {
        const by = d.by_source || {};
        document.getElementById('scanResult').textContent =
          '🔀 Всего: ' + d.count + ' (pywifi: ' + (by.pywifi||0) +
          ', netsh: ' + (by.netsh||0) + ')';
        addLog('Combined: ' + d.count + ' сетей', 'success');
      } else {
        addLog('Combined error: ' + (d.error || '?'), 'error');
      }
    })
    .catch(e => addLog('Combined: ' + e, 'error'));
}

async function wifiPywifiStatus() {
  try {
    const r = await fetch('/api/wifi/pywifi/status');
    const d = await r.json();
    if (d.success) {
      addLog('pywifi status: ' + d.status + ' (' + d.name + ')', 'info');
    } else {
      addLog('pywifi status error: ' + (d.error || '?'), 'warn');
    }
  } catch (e) { addLog('pywifi: ' + e, 'error'); }
}

async function wifiPywifiConnect() {
  const ssid = prompt('SSID для подключения:');
  if (!ssid) return;
  const pass = prompt('Пароль (пусто = открытая сеть):') || '';
  addLog('pywifi connect: ' + ssid, 'info');
  try {
    const r = await fetch('/api/wifi/pywifi/connect', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({ssid, password: pass})
    });
    const d = await r.json();
    if (d.success) {
      addLog('Подключено к ' + ssid, 'success');
    } else {
      addLog('Не подключено: ' + (d.error || '?'), 'error');
    }
  } catch (e) { addLog('connect: ' + e, 'error'); }
}

function scanBLE() {'''

if marker4 in html and 'scanWiFiPywifi' not in html.split('function scanBLE')[0]:
    html = html.replace(marker4, js_funcs, 1)
    print("  [OK] JS functions added")
elif 'function scanWiFiPywifi' in html:
    print("  [--] JS already exists")
else:
    print("  [!!] marker 'function scanBLE()' NOT FOUND")

# Add "Подключиться" button after scan result area
marker5 = '''<div id="scanResult" style="margin-top:10px;font-size:0.85em;color:var(--dim)"></div>'''
new_scan_area = marker5 + '''
<button class="btn btn-glass" style="margin-top:8px" onclick="wifiPywifiStatus()">📊 Статус WiFi</button>
<button class="btn btn-success" style="margin-top:8px" onclick="wifiPywifiConnect()">🔗 Подключиться</button>'''

if marker5 in html and 'wifiPywifiStatus' not in html:
    html = html.replace(marker5, new_scan_area, 1)
    print("  [OK] status + connect buttons added")
elif 'wifiPywifiStatus' in html:
    print("  [--] buttons already exist")
else:
    print("  [!!] marker 'scanResult' NOT FOUND")

save_raw(HTML, html)


# ============================================================
# DONE
# ============================================================
print()
print("=" * 70)
print("  PATCH 31 DONE")
print("=" * 70)
print()
print("Что добавлено (не заменено!):")
print("  [OK] /api/wifi/pywifi/scan       — scan через pywifi (dBm + auth)")
print("  [OK] /api/wifi/combined/scan     — pywifi + netsh (dedup)")
print("  [OK] /api/wifi/pywifi/status     — статус адаптера")
print("  [OK] /api/wifi/pywifi/connect    — подключение к сети")
print("  [OK] /api/wifi/pywifi/disconnect — отключение")
print("  [OK] UI: 3 кнопки scan + статус + подключиться")
print()
print("netsh (scan_wifi) — НЕ тронут, работает как раньше.")
print()
print("Перезапусти сервер: python -m web.app")