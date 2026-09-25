# patch43.py - InevioNet: FULL AUTOMATION (scans + growth + bridge + deploy in background)
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
ORCH = os.path.join(ROOT, "inevionet", "orchestrator.py")


def backup(path):
    if os.path.exists(path):
        b = path + ".bak_p43"
        shutil.copy2(path, b)
        print(f"  [BK] {os.path.basename(b)}")


print()
print("=" * 70)
print("  P43: FULL AUTOMATION")
print("=" * 70)
backup(ORCH)

with open(ORCH, "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add automation loop start in start()
old_start = '''        # P38: mycelium growth loop
        try:
            import threading as _th_growth
            _th_growth.Thread(target=self._growth_loop, daemon=True,
                              name='growth_loop').start()
            logger.info('[Growth] mycelium growth loop started')
        except Exception as _ge:
            logger.debug('[Growth] start error: %s', _ge)
        logger.info(f"InevioNet started: {self.node_id}")'''

new_start = '''        # P38: mycelium growth loop
        try:
            import threading as _th_growth
            _th_growth.Thread(target=self._growth_loop, daemon=True,
                              name='growth_loop').start()
            logger.info('[Growth] mycelium growth loop started')
        except Exception as _ge:
            logger.debug('[Growth] start error: %s', _ge)
        # P43: full automation loop
        try:
            import threading as _th_auto
            _th_auto.Thread(target=self._automation_loop, daemon=True,
                            name='automation_loop').start()
            logger.info('[Auto] automation loop started')
        except Exception as _ae:
            logger.debug('[Auto] start error: %s', _ae)
        logger.info(f"InevioNet started: {self.node_id}")'''

if old_start in content:
    content = content.replace(old_start, new_start, 1)
    print("  [OK] automation loop start added")
elif '[Auto] automation loop started' in content:
    print("  [--] already applied")
else:
    print("  [!!] start marker NOT FOUND")

# 2. Add _automation_loop + helpers before _growth_loop
old_growth = '''    def _growth_loop(self):'''

new_methods = '''    def _automation_loop(self):
        """P43: full automation — scans, anon check, deploy."""
        import time as _t
        # wait for full init
        _t.sleep(60)

        # 1. Auto-volunteer bridge at start
        try:
            self._auto_volunteer_bridge()
        except Exception as e:
            logger.debug('[Auto] bridge volunteer: %s', e)

        counters = {
            'scan_rf': 0,
            'scan_neighbors': 0,
            'check_anon': 0,
            'auto_deploy': 0,
        }

        while getattr(self, '_running', False):
            _t.sleep(30)
            if not getattr(self, '_running', False):
                break

            try:
                # 1. RF scan every 2 min
                counters['scan_rf'] += 1
                if counters['scan_rf'] >= 4:
                    counters['scan_rf'] = 0
                    try:
                        scanner = getattr(self, '_rf_scanner', None)
                        if scanner is None:
                            scanner = self.enable_rf_scanning()
                        result = scanner.scan_all()
                        logger.info('[Auto] RF scan: %d signals',
                                    getattr(result, 'total_count', 0))
                    except Exception as e:
                        logger.debug('[Auto] rf scan: %s', e)

                # 2. Neighbors scan every 5 min
                counters['scan_neighbors'] += 1
                if counters['scan_neighbors'] >= 10:
                    counters['scan_neighbors'] = 0
                    try:
                        self._auto_scan_neighbors()
                    except Exception as e:
                        logger.debug('[Auto] neighbors: %s', e)

                # 3. Tor/I2P check every 5 min
                counters['check_anon'] += 1
                if counters['check_anon'] >= 10:
                    counters['check_anon'] = 0
                    try:
                        self._auto_check_anon()
                    except Exception as e:
                        logger.debug('[Auto] anon: %s', e)

                # 4. Auto-deploy every 10 min
                counters['auto_deploy'] += 1
                if counters['auto_deploy'] >= 20:
                    counters['auto_deploy'] = 0
                    try:
                        self._auto_deploy_cycle()
                    except Exception as e:
                        logger.debug('[Auto] deploy: %s', e)

            except Exception as e:
                logger.debug('[Auto] loop error: %s', e)

    def _auto_volunteer_bridge(self):
        """P43: auto-register as relay node."""
        try:
            import urllib.request as _url
            import ssl as _ssl
            import json as _json
            ctx = _ssl._create_unverified_context()
            payload = _json.dumps({"region": "RU", "capacity": 10}).encode()
            req = _url.Request(
                "https://127.0.0.1:8080/api/bridge/volunteer",
                data=payload,
                headers={'Content-Type': 'application/json'},
                method='POST')
            with _url.urlopen(req, timeout=10, context=ctx) as resp:
                result = _json.loads(resp.read().decode('utf-8'))
            if result.get('success'):
                logger.info('[Auto] Bridge relay registered')
        except Exception as e:
            logger.debug('[Auto] bridge volunteer: %s', e)

    def _auto_scan_neighbors(self):
        """P43: auto-scan neighbors (multi-port probe)."""
        try:
            import urllib.request as _url
            import ssl as _ssl
            import json as _json
            ctx = _ssl._create_unverified_context()
            req = _url.Request(
                "https://127.0.0.1:8080/api/network/scan",
                data=b'{"timeout": 1}',
                headers={'Content-Type': 'application/json'},
                method='POST')
            with _url.urlopen(req, timeout=45, context=ctx) as resp:
                result = _json.loads(resp.read().decode('utf-8'))
            logger.info('[Auto] neighbors: scanned=%d found=%d',
                        result.get('scanned', 0),
                        result.get('found_count', 0))
        except Exception as e:
            logger.debug('[Auto] neighbors error: %s', e)

    def _auto_check_anon(self):
        """P43: auto-check Tor/I2P status."""
        try:
            from .network.tor_transport import TorTransport
            t = TorTransport()
            avail = t.is_available()
            logger.info('[Auto] Tor: %s', 'available' if avail else 'not running')
        except Exception:
            pass
        try:
            if getattr(self, 'i2p', None):
                avail = self.i2p.is_available()
                logger.info('[Auto] I2P: %s', 'available' if avail else 'not running')
        except Exception:
            pass

    def _auto_deploy_cycle(self):
        """P43: auto-deploy to all discovered nodes."""
        try:
            if hasattr(self, '_capsule_deploy_cycle'):
                topo = getattr(self, '_auto_topology', None)
                if topo:
                    self._capsule_deploy_cycle(topo)
        except Exception as e:
            logger.debug('[Auto] deploy error: %s', e)

    def _growth_loop(self):'''

if old_growth in content and '_automation_loop' not in content:
    content = content.replace(old_growth, new_methods, 1)
    print("  [OK] automation methods added")
elif '_automation_loop' in content:
    print("  [--] already applied")
else:
    print("  [!!] growth_loop marker NOT FOUND")

try:
    ast.parse(content)
    with open(ORCH, "w", encoding="utf-8") as f:
        f.write(content)
    print("  [OK] syntax OK")
except SyntaxError as e:
    print(f"  [!!] syntax error: {e}")
    shutil.copy2(ORCH + ".bak_p43", ORCH)
    print("  [--] rolled back")

print()
print("=" * 70)
print("  PATCH 43 DONE — FULL AUTOMATION")
print("=" * 70)
print()
print("  [OK] _automation_loop: RF scan every 2 min")
print("  [OK] _auto_scan_neighbors: every 5 min")
print("  [OK] _auto_check_anon: Tor/I2P every 5 min")
print("  [OK] _auto_deploy_cycle: every 10 min")
print("  [OK] _auto_volunteer_bridge: at start")
print()
print("Перезапусти: python -m web.app")
print()
print("В логах ищи:")
print("  [Auto] automation loop started")
print("  [Auto] Bridge relay registered")
print("  [Auto] RF scan: N signals")
print("  [Auto] neighbors: scanned=N found=M")
print("  [Auto] Tor: available/not running")
print("  [Auto] I2P: available/not running")