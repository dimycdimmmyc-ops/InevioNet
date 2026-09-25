# patch40b_fix.py - InevioNet: _growth_loop multi-port + ARP
import os
import ast
import shutil

ORCH = r"E:\InevioNet\inevionet\orchestrator.py"


def backup(path):
    if os.path.exists(path):
        b = path + ".bak_p40b"
        shutil.copy2(path, b)
        print(f"  [BK] {os.path.basename(b)}")


print()
print("=" * 70)
print("  P40b-fix: _growth_loop multi-port + ARP")
print("=" * 70)
backup(ORCH)

with open(ORCH, "r", encoding="utf-8") as f:
    content = f.read()

old = '''                else:
                    try:
                        import urllib.request as _url
                        import ssl as _ssl
                        import json as _json
                        ctx = _ssl._create_unverified_context()
                        topo = getattr(self, '_auto_topology', None)
                        if topo is None:
                            topo = self.enable_auto_topology()
                        our_map = topo.export_map()
                        targets = self.trusted_hosts.list_all()
                        sent = 0
                        total_added_n = 0
                        total_added_e = 0
                        for h in targets:
                            host = h.get('host')
                            if not host:
                                continue
                            port = 8080
                            host_only = host.split(':')[0]
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
                            except Exception:
                                pass

                        if sent:
                            stats = topo.get_stats()
                            logger.info('[Growth] probed=%d +%d nodes, +%d edges; total nodes=%d edges=%d',
                                        sent, total_added_n, total_added_e,
                                        stats.get('nodes', 0), stats.get('edges', 0))
                    except Exception as _e:
                        logger.debug('[Growth] probe error: %s', _e)'''

new = '''                else:
                    try:
                        topo = getattr(self, '_auto_topology', None)
                        if topo is None:
                            topo = self.enable_auto_topology()
                        our_map = topo.export_map()

                        # P40b-fix: collect targets — trusted_hosts + ARP
                        target_hosts = []
                        for h in self.trusted_hosts.list_all():
                            host = h.get('host')
                            if host:
                                target_hosts.append(host.split(':')[0])
                        try:
                            from .network.arp_scanner import scan_arp
                            for dev in scan_arp():
                                ip = dev.get('ip')
                                if ip:
                                    target_hosts.append(ip)
                        except Exception:
                            pass
                        # dedup + exclude self
                        my_ips = set()
                        try:
                            import socket as _s
                            for info in _s.getaddrinfo(_s.gethostname(), None):
                                my_ips.add(info[4][0])
                        except Exception:
                            pass
                        target_hosts = [h for h in set(target_hosts) if h not in my_ips]

                        # P40b-fix: use multi-port _probe_one_host
                        _probe = None
                        try:
                            from web.app import _probe_one_host as _probe
                        except Exception as _pe:
                            logger.debug('[Growth] probe import: %s', _pe)

                        sent = 0
                        total_added_n = 0
                        total_added_e = 0

                        if _probe and target_hosts:
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
                                            r['ip'], r['scheme'], r['port'])

                        if sent or target_hosts:
                            stats = topo.get_stats()
                            logger.info(
                                '[Growth] targets=%d found=%d +%d nodes, +%d edges; total nodes=%d edges=%d',
                                len(target_hosts), sent, total_added_n, total_added_e,
                                stats.get('nodes', 0), stats.get('edges', 0))
                    except Exception as _e:
                        logger.debug('[Growth] probe error: %s', _e)'''

if old in content:
    content = content.replace(old, new, 1)
    print("  [OK] _growth_loop replaced (multi-port + ARP)")
elif 'P40b-fix' in content:
    print("  [--] already applied")
else:
    print("  [!!] NOT FOUND — проверь вручную")

try:
    ast.parse(content)
    with open(ORCH, "w", encoding="utf-8") as f:
        f.write(content)
    print("  [OK] syntax OK")
except SyntaxError as e:
    print(f"  [!!] syntax error: {e}")
    shutil.copy2(ORCH + ".bak_p40b", ORCH)
    print("  [--] rolled back")

print()
print("Перезапусти: python -m web.app")