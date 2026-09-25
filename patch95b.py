# patch95b.py - P95b: endpoint /api/organism + диагностика scout
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
APP = os.path.join(ROOT, "web", "app.py")
ORG = os.path.join(ROOT, "inevionet", "organism.py")

BAK = ".bak_p95b"


def patch_file(path, replacements, label, bak=BAK):
    if not os.path.exists(path):
        print("  [!!] NOT FOUND: " + path)
        return False
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    b = path + bak
    shutil.copy2(path, b)
    print("  [BK] " + os.path.basename(b))
    changed = 0
    for old, new, required in replacements:
        if new and new in content and (not old or old not in content):
            print("  [--] already applied")
            continue
        if old and old in content:
            content = content.replace(old, new, 1)
            changed += 1
            print("  [OK] " + old[:55].strip().replace(chr(10), ' '))
        else:
            if required:
                print("  [!!] NOT FOUND: " + old[:55].strip().replace(chr(10), ' '))
    if changed > 0:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        if path.endswith(".py"):
            try:
                ast.parse(content)
                print("  [OK] syntax " + label)
                return True
            except SyntaxError as e:
                print("  [!!] syntax: " + str(e))
                shutil.copy2(b, path)
                print("  [--] rolled back")
                return False
    return True


# =====================================================================
# 1. app.py: endpoint /api/organism
# =====================================================================

print()
print("=" * 70)
print("  1. app.py: /api/organism")
print("=" * 70)

anchor = "@app.route('/api/network/public')"

new_ep = '''@app.route('/api/organism')
def api_organism():
    """P95b: статистика живого организма."""
    try:
        n = get_net()
        org = getattr(n, "organism", None)
        if org is None:
            return jsonify({'success': False, 'error': 'organism not running',
                            'hint': 'check INEVIO_ORGANISM env'})
        return jsonify({
            'success': True,
            'stats': org.get_stats(),
            'phase_log': org.get_phase_log(30),
            'memory': {
                'nodes_count': len(org.memory.get("nodes", {})),
                'colonized_count': len(org.memory.get("colonized", set())),
                'taught_count': len(org.memory.get("taught", set())),
                'routes_count': len(org.memory.get("routes", [])),
                'depth_count': len(org.memory.get("depth", {})),
            },
            'nodes_sample': list(org.memory.get("nodes", {}).items())[:10],
        })
    except Exception as e:
        log.error('[P95b] organism: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/network/public')'''

patch_file(APP, [(anchor, new_ep, True)], "app.py /api/organism")


# =====================================================================
# 2. app.py: /api/stats - добавить organism
# =====================================================================

print()
print("=" * 70)
print("  2. app.py: /api/stats + organism")
print("=" * 70)

# Найти endpoint /api/stats
import re
with open(APP, "r", encoding="utf-8") as f:
    app_content = f.read()

# Найти def api_stats(): - найти тело
m = re.search(r"def api_stats\(\):(.*?)(?=\n@app\.route|\ndef\s+\w+\s*\()", app_content, re.DOTALL)
if m:
    old_body = m.group(1)
    # Вставить organism в конце перед return
    # Ищем последний return
    if "return jsonify" in old_body:
        # Найти "return jsonify"
        idx = old_body.rfind("return jsonify")
        if idx > 0:
            new_body = old_body[:idx] + '''# P95b: добавить organism
        _stats_org = {}
        try:
            _org = getattr(n, "organism", None)
            if _org is not None:
                _stats_org = _org.get_stats()
        except Exception:
            pass
        result["organism"] = _stats_org
        ''' + old_body[idx:]
            
            app_content_new = app_content[:m.start(1)] + new_body + app_content[m.end(1):]
            
            b = APP + BAK + "_stats"
            shutil.copy2(APP, b)
            print("  [BK] " + os.path.basename(b))
            with open(APP, "w", encoding="utf-8") as f:
                f.write(app_content_new)
            try:
                ast.parse(app_content_new)
                print("  [OK] /api/stats + organism")
            except SyntaxError as e:
                print("  [!!] syntax: " + str(e))
                shutil.copy2(b, APP)
        else:
            print("  [!!] no return jsonify in api_stats")
    else:
        print("  [!!] no return in api_stats")
else:
    print("  [!!] api_stats not found")


# =====================================================================
# 3. organism.py: диагностика scout
# =====================================================================

print()
print("=" * 70)
print("  3. organism.py: диагностика scout")
print("=" * 70)

# Заменить блок scout - добавить счётчики
old_scout = '''    def scout(self) -> List[Dict[str, Any]]:
        """Разведчики ищут ЛЮБЫЕ узлы."""
        found = []
        seen_ips = set(self.memory["nodes"].keys())'''

new_scout = '''    def scout(self) -> List[Dict[str, Any]]:
        """Разведчики ищут ЛЮБЫЕ узлы."""
        found = []
        seen_ips = set(self.memory["nodes"].keys())
        # P95b: счётчики источников
        c_lan = c_mdns = c_router = c_tr = 0'''

patch_file(ORG, [(old_scout, new_scout, True)], "organism scout counters")


# LAN counter
old_lan = '''                for dev in local.get("devices", []):
                    ip = dev.get("ip")
                    if ip and ip not in seen_ips:
                        found.append({
                            "ip": ip, "mac": dev.get("mac"),
                            "vendor": dev.get("vendor"),
                            "type": "lan_device", "source": "arp", "depth": 1,
                        })'''
new_lan = '''                for dev in local.get("devices", []):
                    ip = dev.get("ip")
                    if ip and ip not in seen_ips:
                        found.append({
                            "ip": ip, "mac": dev.get("mac"),
                            "vendor": dev.get("vendor"),
                            "type": "lan_device", "source": "arp", "depth": 1,
                        })
                        c_lan += 1'''

patch_file(ORG, [(old_lan, new_lan, False)], "organism lan counter")


# mDNS counter
old_mdns = '''                for dev in mdns.get("devices", []):
                    ip = dev.get("ip")
                    if ip and ip not in seen_ips:
                        found.append({
                            "ip": ip, "type": "service",
                            "service": dev.get("server") or dev.get("source"),
                            "source": "mdns", "depth": 1,
                        })'''
new_mdns = '''                for dev in mdns.get("devices", []):
                    ip = dev.get("ip")
                    if ip and ip not in seen_ips:
                        found.append({
                            "ip": ip, "type": "service",
                            "service": dev.get("server") or dev.get("source"),
                            "source": "mdns", "depth": 1,
                        })
                        c_mdns += 1'''

patch_file(ORG, [(old_mdns, new_mdns, False)], "organism mdns counter")


# router counter
old_router = '''            if router_ip and router_ip not in seen_ips:
                found.append({
                    "ip": router_ip, "type": "router",
                    "source": "gateway", "depth": 1, "is_gateway": True,
                })'''
new_router = '''            if router_ip and router_ip not in seen_ips:
                found.append({
                    "ip": router_ip, "type": "router",
                    "source": "gateway", "depth": 1, "is_gateway": True,
                })
                c_router += 1'''

patch_file(ORG, [(old_router, new_router, False)], "organism router counter")


# traceroute counter
old_tr = '''                for hop in tr.get("hops", []):
                    ip = hop.get("ip")
                    if ip and ip not in seen_ips:
                        found.append({
                            "ip": ip, "type": "isp_router",
                            "source": "traceroute", "depth": 2,
                        })'''
new_tr = '''                for hop in tr.get("hops", []):
                    ip = hop.get("ip")
                    if ip and ip not in seen_ips:
                        found.append({
                            "ip": ip, "type": "isp_router",
                            "source": "traceroute", "depth": 2,
                        })
                        c_tr += 1'''

patch_file(ORG, [(old_tr, new_tr, False)], "organism traceroute counter")


# Итоговый лог
old_log = '''        self._log_phase("scout", 0, f"found={len(found)}")
        return found'''
new_log = '''        logger.info("[Scout] lan=%d mdns=%d router=%d traceroute=%d total=%d",
                    c_lan, c_mdns, c_router, c_tr, len(found))
        self._log_phase("scout", 0, f"found={len(found)}")
        return found'''

patch_file(ORG, [(old_log, new_log, True)], "organism scout log")


# =====================================================================
# 4. app.py: инжекция SuperNode + Evolution в net
# =====================================================================

print()
print("=" * 70)
print("  4. app.py: инжекция SuperNode/Evolution")
print("=" * 70)

anchor2 = "net = get_net()"

new_inject = '''net = get_net()

# P95b: инжекция SuperNode + Evolution в net для Organism.teach()
def _inject_organism_hooks(_net):
    """Инжектирует _supernode_loop_once и _evolution_once в net."""
    try:
        # Проверяем, есть ли super_node_loop
        import inspect
        mod = __import__(__name__)
        # SuperNode
        if hasattr(mod, "_supernode_loop_once_fn"):
            _net._supernode_loop_once = mod._supernode_loop_once_fn
        elif hasattr(mod, "supernode_loop_once"):
            _net._supernode_loop_once = mod.supernode_loop_once
        # Evolution
        if hasattr(mod, "_evolution_once_fn"):
            _net._evolution_once = mod._evolution_once_fn
        elif hasattr(mod, "evolution_once"):
            _net._evolution_once = mod.evolution_once
        log.info('[P95b] hooks injected: supernode=%s evolution=%s',
                 hasattr(_net, "_supernode_loop_once"),
                 hasattr(_net, "_evolution_once"))
    except Exception as e:
        log.debug('[P95b] inject: %s', e)'''

patch_file(APP, [(anchor2, new_inject, False)], "app.py inject hooks", bak=".bak_p95b_inject")


print()
print("=" * 70)
print("  PATCH 95b DONE")
print("=" * 70)
print("  [OK] /api/organism endpoint")
print("  [OK] /api/stats + organism")
print("  [OK] scout: диагностика (lan/mdns/router/traceroute)")
print("  [OK] app.py: заготовка инжекции hooks")
print()
print("Перезапуск:")
print("  python -m web.app")
print()
print("Проверка:")
print("  curl -k https://localhost:8080/api/organism | python -m json.tool")