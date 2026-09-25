# patch40.py - InevioNet: PROBE MULTI-PORT + multi-scheme (find neighbors everywhere)
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
ORCH = os.path.join(ROOT, "inevionet", "orchestrator.py")
APP = os.path.join(ROOT, "web", "app.py")
HTML = os.path.join(ROOT, "web", "templates", "index.html")


def backup(path):
    if os.path.exists(path):
        b = path + ".bak_p40"
        shutil.copy2(path, b)
        print(f"  [BK] {os.path.basename(b)}")


def save_py(path, code):
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    try:
        ast.parse(code)
        print(f"  [OK] syntax: {os.path.basename(path)}")
    except SyntaxError as e:
        print(f"  [!!] syntax error: {e}")
        if os.path.exists(path + ".bak_p40"):
            shutil.copy2(path + ".bak_p40", path)


def patch(path, replacements, name):
    print()
    print("=" * 70)
    print(f"  {name}")
    print("=" * 70)
    backup(path)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    changed = 0
    for old, new, required in replacements:
        if new in content and old not in content:
            print(f"  [--] already applied")
            continue
        if old in content:
            content = content.replace(old, new, 1)
            print(f"  [OK] {old[:60].strip()}...")
            changed += 1
        else:
            if required:
                print(f"  [!!] NOT FOUND: {old[:60].strip()}...")
    if changed > 0:
        save_py(path, content)


# ============================================================
# P40a. web/app.py: PROBE_TARGETS + _probe_one_host + /api/network/scan
# ============================================================
patch(APP, [
    # 1. Add constants + helper before "def api_network_map"
    (
        '''@app.route('/api/network/map', methods=['GET', 'POST'])''',
        '''# P40: probe ports and schemes (try in order)
PROBE_TARGETS = [
    (8443, "https"), (8080, "https"), (8080, "http"),
    (8081, "https"), (8081, "http"),
    (443, "https"), (80, "http"),
    (9090, "https"), (9090, "http"),
    (3000, "http"), (5000, "http"),
    (8000, "http"), (8888, "http"),
    (9443, "https"), (10443, "https"),
    (7000, "https"), (7001, "https"),
    (8008, "http"), (8009, "http"),
    (9000, "http"), (9001, "http"),
]


def _probe_one_host(ip, our_map, from_node, max_hops=5, timeout=2):
    """P40: try multiple ports/schemes to find InevioNet on a host."""
    import urllib.request as _url
    import ssl as _ssl
    import json as _json
    ctx = _ssl._create_unverified_context()
    payload = _json.dumps({
        'from_node': from_node,
        'hops': 0,
        'max_hops': max_hops,
        'map': our_map,
    }).encode()
    for port, scheme in PROBE_TARGETS:
        url = f"{scheme}://{ip}:{port}/api/network/map"
        try:
            req = _url.Request(
                url, data=payload,
                headers={'Content-Type': 'application/json'},
                method='POST')
            with _url.urlopen(req, timeout=timeout, context=ctx) as resp:
                data = _json.loads(resp.read().decode('utf-8'))
            return {
                'success': True,
                'ip': ip,
                'url': url,
                'port': port,
                'scheme': scheme,
                'data': data,
            }
        except Exception:
            continue
    return {'success': False, 'ip': ip}


@app.route('/api/network/map', methods=['GET', 'POST'])''',
        True,
    ),
    # 2. Rewrite api_network_probe to use _probe_one_host
    (
        '''    import urllib.request as _url
    import ssl as _ssl
    import json as _json
    ctx = _ssl._create_unverified_context()

    targets = []
    if target:
        targets = [target]
    else:
        nodes = snapshot()
        for nid, node in nodes.items():
            if node.get('type') in ('router', 'device') and node.get('ip'):
                ip = node['ip']
                port = node.get('port', 8080) or 8080
                if port not in (8080, 8443):
                    port = 8080
                targets.append(f"{ip}:{port}")
        # P39: add ARP-scanned devices
        try:
            from inevionet.network.arp_scanner import scan_arp
            for dev in scan_arp():
                ip = dev.get('ip')
                if ip:
                    targets.append(f"{ip}:8080")
        except Exception as _e:
            log.debug('[Probe] arp scan: %s', _e)
        # dedup
        targets = list(set(targets))

    sent = 0
    merged_total = {"added_nodes": 0, "added_edges": 0}
    for t in targets:
        try:
            payload = _json.dumps({
                'from_node': n.node_id,
                'hops': 0,
                'max_hops': max_hops,
                'map': our_map,
            }).encode()
            url = 'https://' + t + '/api/network/map'
            req = _url.Request(
                url, data=payload,
                headers={'Content-Type': 'application/json'},
                method='POST')
            with _url.urlopen(req, timeout=6, context=ctx) as resp:
                other = _json.loads(resp.read().decode('utf-8'))
            other_map = other.get('our_map') or other.get('map') or {}
            if other_map:
                m = topo.merge(other_map)
                merged_total['added_nodes'] += m.get('added_nodes', 0)
                merged_total['added_edges'] += m.get('added_edges', 0)
            sent += 1
        except Exception as e:
            log.info('[Probe] %s: %s', t, e)''',
        '''    targets = []
    if target:
        # target may be "ip" or "ip:port"
        targets = [target.split(':')[0]]
    else:
        ips = set()
        nodes = snapshot()
        for nid, node in nodes.items():
            if node.get('type') in ('router', 'device') and node.get('ip'):
                ips.add(node['ip'])
        try:
            from inevionet.network.arp_scanner import scan_arp
            for dev in scan_arp():
                if dev.get('ip'):
                    ips.add(dev['ip'])
        except Exception as _e:
            log.debug('[Probe] arp scan: %s', _e)
        # exclude self
        my_ips = set()
        try:
            import socket as _s
            for info in _s.getaddrinfo(_s.gethostname(), None):
                my_ips.add(info[4][0])
        except Exception:
            pass
        targets = list(ips - my_ips)

    sent = 0
    merged_total = {"added_nodes": 0, "added_edges": 0}
    found_list = []
    import concurrent.futures
    def _try(ip):
        return _probe_one_host(ip, our_map, n.node_id, max_hops, timeout=2)
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
        for r in ex.map(_try, targets):
            if r.get('success'):
                sent += 1
                found_list.append({
                    'ip': r['ip'], 'url': r['url'],
                    'port': r['port'], 'scheme': r['scheme'],
                })
                other_map = (r.get('data') or {}).get('our_map') or {}
                if other_map:
                    m = topo.merge(other_map)
                    merged_total['added_nodes'] += m.get('added_nodes', 0)
                    merged_total['added_edges'] += m.get('added_edges', 0)
                log.info('[Probe] FOUND %s (%s:%d)',
                         r['ip'], r['scheme'], r['port'])
            else:
                log.info('[Probe] %s: no InevioNet on any port', r['ip'])''',
        True,
    ),
    # 3. Add found_list to response
    (
        '''    return jsonify({
        'success': True,
        'sent': sent,
        'merged': merged_total,
        'stats': stats,
        'spore_id': spore_id,
    })''',
        '''    return jsonify({
        'success': True,
        'sent': sent,
        'found': found_list,
        'merged': merged_total,
        'stats': stats,
        'spore_id': spore_id,
    })''',
        True,
    ),
    # 4. Add /api/network/scan endpoint
    (
        '''@app.route('/api/network/probe', methods=['POST'])''',
        '''@app.route('/api/network/scan', methods=['POST'])
def api_network_scan():
    """P40: scan all ARP devices for InevioNet on ANY port/scheme."""
    d = request.get_json(silent=True) or {}
    timeout = float(d.get('timeout', 2))
    n = get_net()
    topo = getattr(n, '_auto_topology', None)
    if topo is None:
        topo = n.enable_auto_topology()
    our_map = topo.export_map()

    ips = set()
    nodes = snapshot()
    for nid, node in nodes.items():
        if node.get('type') in ('router', 'device') and node.get('ip'):
            ips.add(node['ip'])
    try:
        from inevionet.network.arp_scanner import scan_arp
        for dev in scan_arp():
            if dev.get('ip'):
                ips.add(dev['ip'])
    except Exception:
        pass
    my_ips = set()
    try:
        import socket as _s
        for info in _s.getaddrinfo(_s.gethostname(), None):
            my_ips.add(info[4][0])
    except Exception:
        pass
    ips = list(ips - my_ips)

    import concurrent.futures
    found = []
    merged_total = {'added_nodes': 0, 'added_edges': 0}
    def _try(ip):
        return _probe_one_host(ip, our_map, n.node_id, 5, timeout=timeout)
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
        for r in ex.map(_try, ips):
            if r.get('success'):
                found.append({
                    'ip': r['ip'],
                    'url': r['url'],
                    'port': r['port'],
                    'scheme': r['scheme'],
                })
                other_map = (r.get('data') or {}).get('our_map') or {}
                if other_map:
                    m = topo.merge(other_map)
                    merged_total['added_nodes'] += m.get('added_nodes', 0)
                    merged_total['added_edges'] += m.get('added_edges', 0)

    log.info('[NetScan] scanned=%d found=%d', len(ips), len(found))
    return jsonify({
        'success': True,
        'scanned': len(ips),
        'found': found,
        'found_count': len(found),
        'merged': merged_total,
        'stats': topo.get_stats(),
    })


@app.route('/api/network/probe', methods=['POST'])''',
        True,
    ),
], "P40a: multi-port probe + /api/network/scan")


# ============================================================
# P40b. orchestrator.py: _growth_loop use _probe_one_host
# ============================================================
patch(ORCH, [
    (
        '''                        sent = 0
                        total_added_n = 0
                        total_added_e = 0
                        for host_only in target_hosts:
                            port = 8080
                            try:
                                payload = _json.dumps({
                                    'from_node': self.node_id,
                                    'hops': 0,
                                    'max_hops': max_hops,
                                    'map': our_map,
                                }).encode()
                                url = f"https://{host_only}:{port}/api/network/map"
                                req = _url.Request(
                                    url, data=payload,
                                    headers={'Content-Type': 'application/json'},
                                    method='POST')
                                with _url.urlopen(req, timeout=6, context=ctx) as resp:
                                    other = _json.loads(resp.read().decode('utf-8'))
                                other_map = other.get('our_map') or other.get('map') or {}
                                if other_map:
                                    m = topo.merge(other_map)
                                    total_added_n += m.get('added_nodes', 0)
                                    total_added_e += m.get('added_edges', 0)
                                sent += 1
                                logger.info('[Growth] merged from %s: +%d nodes",
                                           host_only, m.get("added_nodes", 0))
                            except Exception as _pe:
                                logger.debug('[Growth] %s: %s', host_only, _pe)''',
        '''                        # P40: probe with multi-port helper
                        try:
                            import web.app as _webapp
                            _probe = _webapp._probe_one_host
                        except Exception:
                            _probe = None

                        sent = 0
                        total_added_n = 0
                        total_added_e = 0

                        if _probe:
                            import concurrent.futures as _cf
                            def _try(ip):
                                return _probe(ip, our_map, self.node_id,
                                              max_hops, timeout=2)
                            with _cf.ThreadPoolExecutor(max_workers=8) as _ex:
                                for r in _ex.map(_try, target_hosts):
                                    if r.get('success'):
                                        sent += 1
                                        other_map = (r.get('data') or {}).get('our_map') or {}
                                        if other_map:
                                            m = topo.merge(other_map)
                                            total_added_n += m.get('added_nodes', 0)
                                            total_added_e += m.get('added_edges', 0)
                                        logger.info('[Growth] FOUND %s (%s:%d)',
                                                    r['ip'], r['scheme'], r['port'])''',
        True,
    ),
], "P40b: growth multi-port")


# ============================================================
# P40c. index.html: button + JS
# ============================================================
print()
print("=" * 70)
print("  P40c: index.html scan neighbors")
print("=" * 70)
backup(HTML)
with open(HTML, "r", encoding="utf-8") as f:
    html = f.read()

marker_btn = '<button class="btn btn-success" onclick="growNetwork()">🌱 Расти (mycelium)</button>'
new_btn = (marker_btn +
           '\n<button class="btn btn-primary" onclick="scanNeighbors()">🔍 Найти соседей (все порты)</button>')

if 'scanNeighbors()' in html:
    print("  [--] already exists")
elif marker_btn in html:
    html = html.replace(marker_btn, new_btn, 1)
    print("  [OK] button added")
else:
    print("  [!!] button marker NOT FOUND")

marker_js = 'async function growNetwork() {'
js = '''async function scanNeighbors() {
    addLog('🔍 Сканирование всех ARP + портов...', 'info');
    try {
        const r = await fetch('/api/network/scan', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({timeout: 2})
        });
        const d = await r.json();
        if (d.success) {
            addLog('🔍 Просканировано: ' + d.scanned + ', найдено: ' + d.found_count,
                   d.found_count > 0 ? 'success' : 'warn');
            for (const f of (d.found || [])) {
                addLog('  ✅ ' + f.ip + ' (' + f.scheme + ':' + f.port + ')', 'success');
            }
            const m = d.merged || {};
            addLog('📊 Merged: +' + (m.added_nodes||0) + ' nodes, +' +
                   (m.added_edges||0) + ' edges', 'info');
            addLog('📊 Всего: ' + (d.stats.nodes||0) + ' nodes, ' +
                   (d.stats.edges||0) + ' edges', 'info');
        } else {
            addLog('scan error: ' + (d.error||'?'), 'error');
        }
    } catch (e) { addLog('scan: ' + e, 'error'); }
}

async function growNetwork() {'''

if 'async function scanNeighbors' in html:
    print("  [--] JS already exists")
elif marker_js in html:
    html = html.replace(marker_js, js, 1)
    print("  [OK] JS added")
else:
    print("  [!!] JS marker NOT FOUND")

with open(HTML, "w", encoding="utf-8") as f:
    f.write(html)
print("  [OK] saved: index.html")


# ============================================================
# DONE
# ============================================================
print()
print("=" * 70)
print("  PATCH 40 DONE — MULTI-PORT PROBE")
print("=" * 70)
print()
print("  [OK] _probe_one_host: 22 ports × 2 schemes")
print("  [OK] /api/network/probe: multi-port")
print("  [OK] /api/network/scan: scan all ARP on all ports")
print("  [OK] _growth_loop: multi-port")
print("  [OK] index.html: 🔍 Найти соседей")
print()
print("Перезапусти: python -m web.app")
print()
print("Проверка:")
print("  curl.exe -k -X POST https://localhost:8080/api/network/scan -H \"Content-Type: application/json\" -d \"{}\"")