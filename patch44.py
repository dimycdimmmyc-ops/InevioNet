# patch44.py - InevioNet: DEPTH GROWTH — recursive multi-port propagation
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
APP = os.path.join(ROOT, "web", "app.py")
ORCH = os.path.join(ROOT, "inevionet", "orchestrator.py")


def backup(path):
    if os.path.exists(path):
        b = path + ".bak_p44"
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
        if os.path.exists(path + ".bak_p44"):
            shutil.copy2(path + ".bak_p44", path)


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
# P44a. web/app.py: _probe_one_host(hops) + propagate multi-port
# ============================================================
patch(APP, [
    # 1. Add hops param to _probe_one_host
    (
        '''def _probe_one_host(ip, our_map, from_node, max_hops=5, timeout=2):
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
    }).encode()''',
        '''def _probe_one_host(ip, our_map, from_node, max_hops=5, timeout=2, hops=0, visited=None):
    """P44: try multiple ports/schemes. Recursive with visited."""
    import urllib.request as _url
    import ssl as _ssl
    import json as _json
    ctx = _ssl._create_unverified_context()
    payload = _json.dumps({
        'from_node': from_node,
        'hops': hops,
        'max_hops': max_hops,
        'map': our_map,
        'visited': list(visited or []),
    }).encode()''',
        True,
    ),
    # 2. Rewrite propagate in api_network_map
    (
        '''    # P38: propagate further if hops < max_hops
    propagated = 0
    if hops < max_hops:
        import threading as _th
        def _propagate():
            nonlocal propagated
            try:
                import urllib.request as _url
                import ssl as _ssl
                import json as _json
                ctx = _ssl._create_unverified_context()
                our_map = topo.export_map()
                nodes = snapshot()
                for nid, node in nodes.items():
                    if node.get('type') not in ('router', 'device'):
                        continue
                    ip = node.get('ip')
                    if not ip or ip == from_node:
                        continue
                    port = node.get('port', 8080) or 8080
                    if port not in (8080, 8443):
                        port = 8080
                    try:
                        payload = _json.dumps({
                            'from_node': n.node_id,
                            'hops': hops + 1,
                            'max_hops': max_hops,
                            'map': our_map,
                        }).encode()
                        url = ('https://' if port == 8443 else 'http://') + f"{ip}:{port}/api/network/map"
                        req = _url.Request(
                            url, data=payload,
                            headers={'Content-Type': 'application/json'},
                            method='POST')
                        _url.urlopen(req, timeout=4, context=ctx)
                        propagated += 1
                    except Exception:
                        pass
            except Exception:
                pass
        _th.Thread(target=_propagate, daemon=True).start()''',
        '''    # P44: propagate further with multi-port + visited
    propagated = 0
    visited = list(d.get('visited', []))
    if n.node_id not in visited:
        visited.append(n.node_id)
    if hops < max_hops:
        import threading as _th
        def _propagate():
            nonlocal propagated
            try:
                our_map = topo.export_map()
                nodes = snapshot()
                # collect targets (ARP devices, exclude self/from)
                my_ips = set()
                try:
                    import socket as _s
                    for info in _s.getaddrinfo(_s.gethostname(), None):
                        my_ips.add(info[4][0])
                except Exception:
                    pass
                target_ips = []
                for nid, node in nodes.items():
                    if node.get('type') not in ('router', 'device'):
                        continue
                    ip = node.get('ip')
                    if not ip or ip == from_node or ip in my_ips:
                        continue
                    target_ips.append(ip)
                if not target_ips:
                    return
                # use multi-port probe
                try:
                    _probe = _probe_one_host
                except Exception:
                    _probe = None
                if not _probe:
                    return
                import concurrent.futures as _cf
                def _try(ip):
                    return _probe(ip, our_map, n.node_id, max_hops,
                                  timeout=1, hops=hops + 1,
                                  visited=visited)
                with _cf.ThreadPoolExecutor(max_workers=8) as _ex:
                    for r in _ex.map(_try, target_ips):
                        if r.get('success'):
                            propagated += 1
                            other_map = (r.get('data') or {}).get('our_map') or {}
                            if other_map:
                                topo.merge(other_map)
                            log.info('[Map] propagated to %s (%s:%d)',
                                     r['ip'], r['scheme'], r['port'])
            except Exception as _pe:
                log.debug('[Map] propagate error: %s', _pe)
        _th.Thread(target=_propagate, daemon=True).start()''',
        True,
    ),
    # 3. Add /api/network/depth endpoint (manual depth probe)
    (
        '''@app.route('/api/network/probe', methods=['POST'])''',
        '''@app.route('/api/network/depth', methods=['POST'])
def api_network_depth():
    """P44: depth probe — recursive map exchange with TTL."""
    d = request.get_json(silent=True) or {}
    max_hops = int(d.get('max_hops', 5))
    target = d.get('target')
    n = get_net()
    topo = getattr(n, '_auto_topology', None) or n.enable_auto_topology()
    our_map = topo.export_map()

    # collect targets
    targets = []
    if target:
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
        except Exception:
            pass
        my_ips = set()
        try:
            import socket as _s
            for info in _s.getaddrinfo(_s.gethostname(), None):
                my_ips.add(info[4][0])
        except Exception:
            pass
        targets = list(ips - my_ips)

    import concurrent.futures
    found = []
    merged_total = {'added_nodes': 0, 'added_edges': 0}
    def _try(ip):
        return _probe_one_host(ip, our_map, n.node_id, max_hops,
                               timeout=2, hops=0,
                               visited=[n.node_id])
    with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:
        for r in ex.map(_try, targets):
            if r.get('success'):
                found.append({
                    'ip': r['ip'], 'url': r['url'],
                    'port': r['port'], 'scheme': r['scheme'],
                })
                other_map = (r.get('data') or {}).get('our_map') or {}
                if other_map:
                    m = topo.merge(other_map)
                    merged_total['added_nodes'] += m.get('added_nodes', 0)
                    merged_total['added_edges'] += m.get('added_edges', 0)

    stats = topo.get_stats()
    log.info('[Depth] scanned=%d found=%d +%d nodes, +%d edges',
             len(targets), len(found),
             merged_total['added_nodes'], merged_total['added_edges'])

    return jsonify({
        'success': True,
        'scanned': len(targets),
        'found': found,
        'found_count': len(found),
        'merged': merged_total,
        'stats': stats,
        'max_hops': max_hops,
    })


@app.route('/api/network/probe', methods=['POST'])''',
        True,
    ),
], "P44a: recursive multi-port depth probe")


# ============================================================
# P44b. orchestrator.py: _growth_loop uses depth
# ============================================================
patch(ORCH, [
    (
        '''                        if _probe and target_hosts:
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
                                        logger.info(
                                            '[Growth] FOUND %s (%s:%d)',
                                            r['ip'], r['scheme'], r['port'])''',
        '''                        if _probe and target_hosts:
                            import concurrent.futures as _cf
                            _visited = [self.node_id]
                            def _try(ip):
                                return _probe(ip, our_map, self.node_id,
                                              max_hops, timeout=2,
                                              hops=0, visited=_visited)
                            with _cf.ThreadPoolExecutor(max_workers=8) as _ex:
                                for r in _ex.map(_try, target_hosts):
                                    if r.get('success'):
                                        sent += 1
                                        other_map = (r.get('data') or {}).get('our_map') or {}
                                        if other_map:
                                            m = topo.merge(other_map)
                                            total_added_n += m.get('added_nodes', 0)
                                            total_added_e += m.get('added_edges', 0)
                                        logger.info(
                                            '[Growth] FOUND %s (%s:%d)',
                                            r['ip'], r['scheme'], r['port'])''',
        True,
    ),
], "P44b: growth uses visited")


print()
print("=" * 70)
print("  PATCH 44 DONE — DEPTH GROWTH")
print("=" * 70)
print()
print("  [OK] _probe_one_host(hops, visited)")
print("  [OK] api_network_map propagate: multi-port + visited")
print("  [OK] /api/network/depth: recursive depth probe")
print("  [OK] _growth_loop: visited list")
print()
print("Перезапусти: python -m web.app")
print()
print("Проверка:")
print("  curl.exe -k -X POST https://localhost:8080/api/network/depth -H \"Content-Type: application/json\" -d \"{\\\"max_hops\\\": 5}\"")