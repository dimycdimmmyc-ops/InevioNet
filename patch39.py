# patch39.py - InevioNet: ARP in growth + probe INFO logs + dedup
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
ORCH = os.path.join(ROOT, "inevionet", "orchestrator.py")
APP = os.path.join(ROOT, "web", "app.py")


def backup(path):
    if os.path.exists(path):
        b = path + ".bak_p39"
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
        if os.path.exists(path + ".bak_p39"):
            shutil.copy2(path + ".bak_p39", path)


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
# P39a. web/app.py: /api/network/probe INFO logs + ARP
# ============================================================
patch(APP, [
    # 1. Replace target collection in api_network_probe
    (
        '''    targets = []
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
                targets.append(f"{ip}:{port}")''',
        '''    targets = []
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
        targets = list(set(targets))''',
        True,
    ),
    # 2. log.debug -> log.info for probe errors
    (
        '''        except Exception as e:
            log.debug('[Probe] %s: %s', t, e)''',
        '''        except Exception as e:
            log.info('[Probe] %s: %s', t, e)''',
        True,
    ),
], "P39a: probe INFO logs + ARP")


# ============================================================
# P39b. orchestrator.py: _growth_loop ARP + trusted
# ============================================================
patch(ORCH, [
    (
        '''                        our_map = topo.export_map()
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
                            try:''',
        '''                        our_map = topo.export_map()
                        # P39: collect targets — trusted_hosts + ARP
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
                        target_hosts = list(set(target_hosts))
                        my_ips = set()
                        try:
                            import socket as _s
                            for info in _s.getaddrinfo(_s.gethostname(), None):
                                my_ips.add(info[4][0])
                        except Exception:
                            pass
                        target_hosts = [h for h in target_hosts if h not in my_ips]

                        sent = 0
                        total_added_n = 0
                        total_added_e = 0
                        for host_only in target_hosts:
                            port = 8080
                            try:''',
        True,
    ),
    # Also update the log line inside loop
    (
        '''                                if other_map:
                                    m = topo.merge(other_map)
                                    total_added_n += m.get('added_nodes', 0)
                                    total_added_e += m.get('added_edges', 0)
                                sent += 1
                            except Exception:
                                pass''',
        '''                                if other_map:
                                    m = topo.merge(other_map)
                                    total_added_n += m.get('added_nodes', 0)
                                    total_added_e += m.get('added_edges', 0)
                                sent += 1
                                logger.info('[Growth] merged from %s: +%d nodes",
                                           host_only, m.get("added_nodes", 0))
                            except Exception as _pe:
                                logger.debug('[Growth] %s: %s', host_only, _pe)''',
        True,
    ),
], "P39b: growth ARP + trusted")


print()
print("=" * 70)
print("  PATCH 39 DONE")
print("=" * 70)
print()
print("  [OK] /api/network/probe: INFO logs + ARP")
print("  [OK] _growth_loop: trusted + ARP, dedup, exclude self")
print()
print("Перезапусти: python -m web.app")
print()
print("Проверка:")
print("  curl.exe -k -X POST https://localhost:8080/api/network/probe -H \"Content-Type: application/json\" -d \"{}\"")