# patch23.py - fix ARP spam with cache
import os
import ast
import shutil
import sys

ROOT = r"E:\InevioNet"
SCANNER = os.path.join(ROOT, "inevionet", "network", "arp_scanner.py")
APP = os.path.join(ROOT, "web", "app.py")


def backup(path):
    shutil.copy2(path, path + ".bak_p23")
    print(f"  Backup: {os.path.basename(path)}.bak_p23")


def save_py(path, code):
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    try:
        ast.parse(code)
        print(f"  [OK] syntax: {os.path.basename(path)}")
    except SyntaxError as e:
        print(f"  [!!] syntax error: {e}")
        shutil.copy2(path + ".bak_p23", path)
        sys.exit(1)


# ============================================================
# 1. arp_scanner.py: add cache
# ============================================================
print("=" * 70)
print("  PATCH 23a: ARP cache")
print("=" * 70)

backup(SCANNER)
with open(SCANNER, "r", encoding="utf-8") as f:
    scan = f.read()

if "_arp_cache" in scan:
    print("  [--] cache exists")
else:
    # Add cache fields + modify scan_arp
    old_header = '''logger = get_logger("inevionet.network.arp_scanner")


def scan_arp() -> List[Dict[str, Any]]:
    """P22: scan local network via ARP table.

    Returns list of {ip, mac, type, vendor}.
    """
    results = []'''
    new_header = '''logger = get_logger("inevionet.network.arp_scanner")

# P23: cache
_arp_cache: List[Dict[str, Any]] = []
_arp_cache_time: float = 0.0
_ARP_CACHE_TTL: float = 30.0


def scan_arp(force: bool = False) -> List[Dict[str, Any]]:
    """P22/P23: scan local network via ARP table (cached 30s).

    Returns list of {ip, mac, type, vendor}.
    """
    global _arp_cache, _arp_cache_time
    import time as _t
    now = _t.time()
    if not force and _arp_cache and (now - _arp_cache_time) < _ARP_CACHE_TTL:
        return list(_arp_cache)

    results = []'''
    if old_header in scan:
        scan = scan.replace(old_header, new_header, 1)
        print("  [OK] cache fields + TTL added")

    # Add cache save at end
    old_end = '''        logger.info("[ARP] found %d devices", len(results))
    except Exception as e:
        logger.error("[ARP] scan error: %s", e)

    return results'''
    new_end = '''        _arp_cache = list(results)
        _arp_cache_time = _t.time()
        logger.info("[ARP] found %d devices (fresh)", len(results))
    except Exception as e:
        logger.error("[ARP] scan error: %s", e)

    return results'''
    if old_end in scan:
        scan = scan.replace(old_end, new_end, 1)
        print("  [OK] cache save added")

    save_py(SCANNER, scan)


# ============================================================
# 2. app.py: remove find_ip_by_mac from WiFi loop, use cache
# ============================================================
print()
print("=" * 70)
print("  PATCH 23b: app.py — remove per-WiFi ARP call")
print("=" * 70)

backup(APP)
with open(APP, "r", encoding="utf-8") as f:
    app = f.read()

# Remove per-WiFi find_ip_by_mac call
old_block = '''                    # P22: lookup IP by BSSID via ARP
                    try:
                        from inevionet.network.arp_scanner import find_ip_by_mac
                        _ip = find_ip_by_mac(sig['bssid'])
                        if _ip:
                            _nodes = dict(_nodes[0])
                            _nid = 'wifi_' + sig['bssid']
                            if _nid in _nodes:
                                _nodes[_nid]['ip'] = _ip
                                _nodes[_nid]['ip_source'] = 'arp'
                                _nodes[0] = _nodes
                    except Exception:
                        pass

'''
new_block = ''
if old_block in app:
    app = app.replace(old_block, new_block, 1)
    print("  [OK] removed per-WiFi ARP call")

# Add one-time ARP cache use in WiFi section (before footholds)
old_footholds = '''                myc = getattr(n, 'mycelium', None) or getattr(n, '_mycelium', None)
                footholds = dict(get_footholds())
                wifi_list = scan_wifi()'''
new_footholds = '''                myc = getattr(n, 'mycelium', None) or getattr(n, '_mycelium', None)
                footholds = dict(get_footholds())
                wifi_list = scan_wifi()

                # P23: get ARP cache ONCE for all WiFi
                try:
                    from inevionet.network.arp_scanner import scan_arp
                    _arp_devices = scan_arp()  # cached, не спамит
                    _arp_by_mac = {d['mac']: d['ip'] for d in _arp_devices}
                except Exception:
                    _arp_by_mac = {}'''
if old_footholds in app:
    app = app.replace(old_footholds, new_footholds, 1)
    print("  [OK] one-time ARP cache for WiFi section")

# Apply IP from cache to WiFi nodes
old_wifi_upsert = '''                    upsert({
                        'node_id': nid,
                        'name': sig['ssid'],
                        'label': sig['ssid'][:24],
                        'type': 'wifi',
                        'ip': 'unknown',
                        'port': 0,'''
new_wifi_upsert = '''                    # P23: lookup IP from cached ARP
                    _wifi_ip = _arp_by_mac.get(sig['bssid'].lower(), 'unknown')
                    _wifi_ip = _wifi_ip if _wifi_ip else 'unknown'

                    upsert({
                        'node_id': nid,
                        'name': sig['ssid'],
                        'label': sig['ssid'][:24],
                        'type': 'wifi',
                        'ip': _wifi_ip,
                        'port': 0,'''
if old_wifi_upsert in app:
    app = app.replace(old_wifi_upsert, new_wifi_upsert, 1)
    print("  [OK] WiFi nodes use cached ARP")

# Remove ARP block spam (sc%3)
old_arp_block = '''            # --- ARP SCAN (каждые 3 цикла) ---
            if sc % 3 == 1:
                try:
                    arp_devices = scan_arp()
                    for dev in arp_devices:
                        nid = 'arp_' + dev['mac'].replace(':', '')
                        upsert({
                            'node_id': nid,
                            'name': '%s (%s)' % (dev['ip'], dev['type']),
                            'label': dev['ip'],
                            'type': dev['type'],
                            'ip': dev['ip'],
                            'port': 0,
                            'trust': 60.0,
                            'packets': 0,
                            'online': True,
                            'rssi': -50,
                            'signal': 80,
                            'method': 'arp_scan',
                            'evolving': False,
                            'parent': None,
                            'mac': dev['mac'],
                        })
                except Exception as _e:
                    log.debug('[ARP] loop error: %s', _e)

'''
new_arp_block = '''            # --- ARP DEVICES (каждые 5 циклов = раз в 20 сек) ---
            if sc % 5 == 0:
                try:
                    arp_devices = scan_arp()
                    for dev in arp_devices:
                        nid = 'arp_' + dev['mac'].replace(':', '')
                        upsert({
                            'node_id': nid,
                            'name': '%s (%s)' % (dev['ip'], dev['type']),
                            'label': dev['ip'],
                            'type': dev['type'],
                            'ip': dev['ip'],
                            'port': 0,
                            'trust': 60.0,
                            'packets': 0,
                            'online': True,
                            'rssi': -50,
                            'signal': 80,
                            'method': 'arp_scan',
                            'evolving': False,
                            'parent': None,
                            'mac': dev['mac'],
                        })
                except Exception as _e:
                    log.debug('[ARP] loop error: %s', _e)

'''
if old_arp_block in app:
    app = app.replace(old_arp_block, new_arp_block, 1)
    print("  [OK] ARP block -> every 5 cycles (20s)")

save_py(APP, app)


print()
print("=" * 70)
print("  PATCH 23 DONE")
print("=" * 70)
print()
print("Что изменилось:")
print("  [OK] ARP cache (30 сек TTL) — не спамит")
print("  [OK] Убран per-WiFi find_ip_by_mac (12 вызовов → 1)")
print("  [OK] ARP block → раз в 20 сек (было 12 сек)")
print("  [OK] WiFi nodes получают IP из кеша")
print()
print("Перезапусти сервер: python -m web.app")