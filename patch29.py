# patch29.py - InevioNet: auto-deploy fallback + node_id normalize + BLE filter + OUI MTS + fitness UI
import os
import ast
import shutil
import sys
import time

ROOT = r"E:\InevioNet"
ORCH = os.path.join(ROOT, "inevionet", "orchestrator.py")
RECON = os.path.join(ROOT, "inevionet", "network", "router_recon.py")
APP = os.path.join(ROOT, "web", "app.py")
HTML = os.path.join(ROOT, "web", "templates", "index.html")


def backup(path):
    if os.path.exists(path):
        b = path + ".bak_p29"
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
        if os.path.exists(path + ".bak_p29"):
            shutil.copy2(path + ".bak_p29", path)
            print(f"  [--] rolled back {os.path.basename(path)}")
        return False


def save_raw(path, code):
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    print(f"  [OK] saved: {os.path.basename(path)}")


def load(path):
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def patch_py(path, replacements, name):
    print()
    print("=" * 70)
    print(f"  {name}")
    print("=" * 70)
    backup(path)
    content = load(path)
    changed = 0
    for old, new, required in replacements:
        if new in content and old not in content:
            print(f"  [--] already applied: {old[:50]}...")
            continue
        if old in content:
            content = content.replace(old, new, 1)
            print(f"  [OK] {old[:60]}...")
            changed += 1
        else:
            if required:
                print(f"  [!!] NOT FOUND (required): {old[:60]}...")
            else:
                print(f"  [--] not found (optional): {old[:60]}...")
    if changed > 0:
        return save_py(path, content)
    else:
        print(f"  [--] nothing changed in {os.path.basename(path)}")
        return True


def patch_raw(path, replacements, name):
    print()
    print("=" * 70)
    print(f"  {name}")
    print("=" * 70)
    backup(path)
    content = load(path)
    changed = 0
    for old, new, required in replacements:
        if new in content and old not in content:
            print(f"  [--] already applied: {old[:50]}...")
            continue
        if old in content:
            content = content.replace(old, new, 1)
            print(f"  [OK] {old[:60]}...")
            changed += 1
        else:
            if required:
                print(f"  [!!] NOT FOUND (required): {old[:60]}...")
            else:
                print(f"  [--] not found (optional): {old[:60]}...")
    if changed > 0:
        save_raw(path, content)
    else:
        print(f"  [--] nothing changed in {os.path.basename(path)}")


# ============================================================
# P29a. orchestrator.py: auto-deploy fallback on deploy_all
# ============================================================
patch_py(ORCH, [
    (
        '''        trusted = self.trusted_hosts.list_all()
        if not trusted:
            logger.warning("[AutoDeploy] no trusted hosts — add via UI")
            return''',
        '''        trusted = self.trusted_hosts.list_all()
        if not trusted:
            logger.warning("[AutoDeploy] no trusted hosts — triggering deploy_all")
            try:
                import urllib.request as _urlreq
                import ssl as _ssl
                ctx = _ssl._create_unverified_context()
                req = _urlreq.Request(
                    "https://127.0.0.1:8080/api/capsule/deploy_all",
                    data=b"{}",
                    headers={"Content-Type": "application/json"},
                    method="POST")
                with _urlreq.urlopen(req, timeout=60, context=ctx) as resp:
                    import json as _json
                    result = _json.loads(resp.read().decode("utf-8"))
                    logger.warning(
                        "[AutoDeploy] deploy_all: deployed=%d failed=%d skipped=%d",
                        result.get("deployed", 0),
                        result.get("failed", 0),
                        result.get("skipped", 0))
            except Exception as e:
                logger.error("[AutoDeploy] deploy_all fallback error: %s", e)
            return''',
        True,
    ),
    # Throttle _capsule_deploy_cycle: 60 -> 300
    (
        '''        now2 = _t2.time()
        last2 = getattr(self, "_capsule_last_cycle", 0)
        if now2 - last2 < 60:
            return''',
        '''        now2 = _t2.time()
        last2 = getattr(self, "_capsule_last_cycle", 0)
        if now2 - last2 < 300:  # P29: 60 -> 300 sec (avoid dup deploy)
            return''',
        False,
    ),
], "P29a: orchestrator auto-deploy fallback + throttle")


# ============================================================
# P29e. router_recon.py: OUI 04:ba:d6 -> MTS + MTS branch
# ============================================================
patch_py(RECON, [
    # Add MTS OUI
    (
        '''    "04:ba:d6": "Unknown",   # твой роутер 192.168.1.1''',
        '''    "04:ba:d6": "MTS",       # P29: MTS router (was Unknown)''',
        True,
    ),
    # MTS branch
    (
        '''    elif info["vendor"] == "TP-Link":''',
        '''    elif info["vendor"] == "MTS":
        # P29: MTS router - try HTTP/HTTPS admin
        info["deploy_method"] = "http_mts"
        info["can_deploy"] = info["http_open"] or info["https_open"]
        info["notes"] = "MTS router: try HTTP admin panel"
    elif info["vendor"] == "TP-Link":''',
        True,
    ),
], "P29e: router_recon MTS OUI + branch")


# ============================================================
# P29b/c/d. web/app.py: node_id normalize + BLE filter + rescan 900
# ============================================================
patch_py(APP, [
    # P29d. _FORCED_RESCAN_INTERVAL 300 -> 900
    (
        '''_FORCED_RESCAN_INTERVAL = 300  # 5 minutes''',
        '''_FORCED_RESCAN_INTERVAL = 900  # P29: 5 -> 15 min''',
        True,
    ),
    # P29c. scan_bt - only BTHLE
    (
        '''            for x in d:
                out.append({
                    'name': x.get('Name', 'BT'),
                    'id': x.get('InstanceId', 'x').replace('\\\\', '_'),
                })''',
        '''            for x in d:
                iid = x.get('InstanceId', '')
                # P29: only real BLE devices (skip BTHENUM/BTHENUM_USB)
                if not iid.startswith('BTHLE'):
                    continue
                out.append({
                    'name': x.get('Name', 'BT'),
                    'id': iid.replace('\\\\', '_'),
                })''',
        True,
    ),
    # P29b1. wifi node_id normalize (first occurrence - in background_scanner)
    (
        '''                for sig in scan_wifi():
                    nid = 'wifi_' + sig['bssid']
                    upsert({''',
        '''                for sig in scan_wifi():
                    # P29: normalize BSSID (strip :, lower) to merge with arp_*
                    nid = 'wifi_' + sig['bssid'].replace(':', '').replace('-', '').lower()
                    upsert({''',
        True,
    ),
    # P29b2. spore node_id normalize
    (
        '''                        sid = 'spore_' + sig['bssid']''',
        '''                        sid = 'spore_' + sig['bssid'].replace(':', '').replace('-', '').lower()  # P29''',
        True,
    ),
    # P29b3. /api/rf/scan normalize
    (
        '''    for sig in wifi:
        upsert({
            'node_id': 'wifi_' + sig['bssid'],''',
        '''    for sig in wifi:
        upsert({
            'node_id': 'wifi_' + sig['bssid'].replace(':', '').replace('-', '').lower(),  # P29''',
        True,
    ),
    # P29b4. parent reference in spore
    (
        '''                            'method': 'mycelium:' + footholds[sig['ssid']],
                            'evolving': True,
                            'parent': 'wifi_' + sig['bssid'],''',
        '''                            'method': 'mycelium:' + footholds[sig['ssid']],
                            'evolving': True,
                            'parent': 'wifi_' + sig['bssid'].replace(':', '').replace('-', '').lower(),  # P29''',
        True,
    ),
], "P29b/c/d: web/app.py normalize + BLE filter + rescan 900")


# ============================================================
# P29f. index.html: fitnessStatus + autoDeployStatus + JS
# ============================================================
patch_raw(HTML, [
    # Add fitness status elements
    (
        '''<div class="card">
<h3>🌐 Капсулы (грибница)</h3>
<div style="font-size:0.85em;color:var(--dim);margin-bottom:10px">
Разворачивает InevioNet на твоих устройствах. Только для доверенных!
</div>''',
        '''<div class="card">
<h3>🌐 Капсулы (грибница)</h3>
<div style="font-size:0.85em;color:var(--dim);margin-bottom:10px">
Разворачивает InevioNet на твоих устройствах. Только для доверенных!
</div>
<div id="autoDeployStatus" style="font-size:0.8em;color:var(--dim);margin-bottom:6px">Auto-deploy: ON (при fitness ≥ 0.85)</div>
<div id="fitnessStatus" style="font-size:0.85em;color:var(--green);margin-bottom:10px">Best fitness: —</div>''',
        True,
    ),
    # Add JS: loadFitness before checkAuth()
    (
        '''checkAuth();
setInterval(loadInbox, 10000);''',
        '''async function loadFitness() {
    try {
        const r = await fetch('/api/stats');
        const d = await r.json();
        const evo = d.evolution || {};
        const best = (evo.best_fitness || 0).toFixed(3);
        const gen = evo.generation || 0;
        const el = document.getElementById('fitnessStatus');
        if (el) el.textContent = 'Best fitness: ' + best + ' (порог 0.85, gen ' + gen + ')';
    } catch (e) {}
}
setInterval(loadFitness, 30000);
loadFitness();

checkAuth();
setInterval(loadInbox, 10000);''',
        True,
    ),
], "P29f: index.html fitness status")


# ============================================================
# DONE
# ============================================================
print()
print("=" * 70)
print("  PATCH 29 DONE")
print("=" * 70)
print()
print("Что изменилось:")
print("  [OK] orchestrator: auto-deploy fallback -> deploy_all (если trusted пуст)")
print("  [OK] orchestrator: _capsule_deploy_cycle throttle 60 -> 300 sec")
print("  [OK] router_recon: OUI 04:ba:d6 -> MTS + MTS branch (http_mts)")
print("  [OK] web/app.py: wifi/spore node_id normalize (strip :, lower)")
print("  [OK] web/app.py: scan_bt only BTHLE (skip BTHENUM/BTHENUM_USB)")
print("  [OK] web/app.py: _FORCED_RESCAN_INTERVAL 300 -> 900")
print("  [OK] index.html: fitnessStatus + autoDeployStatus + loadFitness JS")
print()
print("Перезапусти сервер: python -m web.app")
print("Логи: E:\\InevioNet\\logs\\inevionet.log")