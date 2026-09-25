# patch87fix.py - P87-fix
#
# 1. network_tree.py: recalc_stats() - пересчёт после add_*
# 2. orchestrator.py: _full_scan_loop - каждые 2 мин
# 3. network_tree.py: spiral-раскладка для traceroute
# 4. app.py: /api/network/tree читает кэш

import os
import ast
import shutil

ROOT = r"E:\InevioNet"
INEV = os.path.join(ROOT, "inevionet")
MESH = os.path.join(INEV, "mesh")
ORCH = os.path.join(INEV, "orchestrator.py")
APP = os.path.join(ROOT, "web", "app.py")
HTML = os.path.join(ROOT, "web", "templates", "index.html")


def patch_file(path, replacements, label, bak=".bak_p87fix"):
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
        if new in content and old not in content:
            print("  [--] already applied")
            continue
        if old in content:
            content = content.replace(old, new, 1)
            changed += 1
            print("  [OK] " + old[:50].strip())
        else:
            if required:
                print("  [!!] NOT FOUND: " + old[:50].strip())
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
        else:
            print("  [OK] saved " + label)
            return True
    return True


# =====================================================================
# 1. network_tree.py - recalc_stats()
# =====================================================================

print()
print("=" * 70)
print("  1. network_tree.py - recalc_stats")
print("=" * 70)

TREE = os.path.join(MESH, "network_tree.py")

# Добавить метод recalc_stats после _compute_depth
old_method = '''    def _compute_depth(self, node: TreeNode, depth: int = 0) -> int:
        if not node.children:
            return depth
        return max(self._compute_depth(c, depth + 1) for c in node.children)'''

new_method = '''    def _compute_depth(self, node: TreeNode, depth: int = 0) -> int:
        if not node.children:
            return depth
        return max(self._compute_depth(c, depth + 1) for c in node.children)

    def recalc_stats(self):
        """P87fix: пересчитать stats после add_*."""
        if self.root:
            self._stats["total_nodes"] = self.root.count_nodes()
            self._stats["max_depth"] = self._compute_depth(self.root)'''

patch_file(TREE, [(old_method, new_method, True)], "network_tree.py recalc")


# 2. В add_traceroute - вызвать recalc_stats
old_tr = '''            parent.children.append(node)
            parent = node

    def add_mdns_devices(self, devices: List[Dict[str, Any]]):'''

new_tr = '''            parent.children.append(node)
            parent = node
        # P87fix: пересчёт stats
        self.recalc_stats()

    def add_mdns_devices(self, devices: List[Dict[str, Any]]):'''

patch_file(TREE, [(old_tr, new_tr, True)], "network_tree.py add_traceroute")


# 3. add_mdns_devices - recalc_stats
old_mdns = '''            self.root.children.append(node)

    def add_router_admin(self, admin_result: Dict[str, Any]):'''

new_mdns = '''            self.root.children.append(node)
        # P87fix: пересчёт stats
        self.recalc_stats()

    def add_router_admin(self, admin_result: Dict[str, Any]):'''

patch_file(TREE, [(old_mdns, new_mdns, True)], "network_tree.py add_mdns")


# 4. add_router_admin - recalc_stats
old_ra = '''            else:
                self.root.children.append(node)

    def build(self, local_map: Dict[str, Any],'''

new_ra = '''            else:
                self.root.children.append(node)
        # P87fix: пересчёт stats
        self.recalc_stats()

    def build(self, local_map: Dict[str, Any],'''

patch_file(TREE, [(old_ra, new_ra, True)], "network_tree.py add_router_admin")


# =====================================================================
# 5. orchestrator.py - _full_scan_loop
# =====================================================================

print()
print("=" * 70)
print("  5. orchestrator.py - _full_scan_loop")
print("=" * 70)

# Новый loop перед _seed_refresh_loop
old_loop_anchor = '''    def _seed_refresh_loop(self):'''

new_loop = '''    def _full_scan_loop(self):
        """P87fix: полный скан каждые 2 минуты (traceroute + mdns + tree)."""
        import time as _t
        _t.sleep(30)  # подождать старт
        while getattr(self, '_running', False):
            try:
                # 1. LocalMap
                local = {}
                if getattr(self, "local_map", None):
                    local = self.local_map.build()

                # 2. Traceroute multi
                tr_result = {}
                if getattr(self, "traceroute_scan", None):
                    tr_result = self.traceroute_scan.scan_multi()

                # 3. mDNS/SSDP/LLMNR
                mdns_result = {}
                if getattr(self, "local_discovery", None):
                    mdns_result = self.local_discovery.scan_all(timeout=2.0)

                # 4. Topology
                topo = {}
                if getattr(self, "_auto_topology", None):
                    try:
                        topo = self._auto_topology.export_map()
                    except Exception:
                        pass

                # 5. Построить дерево
                if getattr(self, "network_tree", None):
                    self.network_tree.build(local_map=local, topology_map=topo)
                    self.network_tree.add_traceroute(tr_result.get("hops", []))
                    self.network_tree.add_mdns_devices(mdns_result.get("devices", []))
                    stats = self.network_tree.get_stats()
                    logger.info("[P87fix] full_scan: %d nodes, depth=%d",
                                stats.get("total_nodes", 0),
                                stats.get("max_depth", 0))
            except Exception as _e:
                logger.debug("[P87fix] full_scan error: %s", _e)
            _t.sleep(120)  # 2 минуты

    def _seed_refresh_loop(self):'''

patch_file(ORCH, [(old_loop_anchor, new_loop, True)], "orchestrator.py loop")


# 6. Запустить loop в start()
old_start = '''        # P74: seed refresh loop'''
new_start = '''        # P87fix: full_scan loop
        try:
            import threading as _th_scan
            _th_scan.Thread(target=self._full_scan_loop,
                            daemon=True, name="full_scan").start()
            logger.info("[P87fix] full_scan loop started")
        except Exception as _se:
            logger.debug("[P87fix] full_scan start: %s", _se)

        # P74: seed refresh loop'''

patch_file(ORCH, [(old_start, new_start, True)], "orchestrator.py start")


# =====================================================================
# 7. app.py - /api/network/tree читает кэш
# =====================================================================

print()
print("=" * 70)
print("  7. app.py - /api/network/tree")
print("=" * 70)

old_tree_ep = '''@app.route('/api/network/tree')
def api_network_tree():
    """P82: дерево сетей."""
    try:
        n = get_net()
        if not getattr(n, "network_tree", None):
            return jsonify({'success': False, 'error': 'no_tree'})

        # LocalMap
        local = {}
        if getattr(n, "local_map", None):
            force = request.args.get('force', '0') == '1'
            if force or not n.local_map.devices:
                local = n.local_map.build()
            else:
                local = n.local_map.get_map()

        # Topology map
        topo = {}
        if getattr(n, "_auto_topology", None):
            try:
                topo = n._auto_topology.export_map()
            except Exception:
                pass

        # Gravity
        gravity = {}
        if getattr(n, "gravity", None):
            try:
                gravity = n.gravity.get_stats()
            except Exception:
                pass

        n.network_tree.build(local_map=local, topology_map=topo, gravity=gravity)
        return jsonify({'success': True, **n.network_tree.get_tree()})
    except Exception as e:
        log.error('[Tree] error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500'''

new_tree_ep = '''@app.route('/api/network/tree')
def api_network_tree():
    """P82/P87fix: дерево сетей (из кэша фон-скана)."""
    try:
        n = get_net()
        if not getattr(n, "network_tree", None):
            return jsonify({'success': False, 'error': 'no_tree'})

        force = request.args.get('force', '0') == '1'
        refresh = request.args.get('refresh', '0') == '1'

        # Форс: запустить полный скан синхронно
        if force or refresh or not n.network_tree.root:
            local = {}
            if getattr(n, "local_map", None):
                local = n.local_map.build()
            topo = {}
            if getattr(n, "_auto_topology", None):
                try:
                    topo = n._auto_topology.export_map()
                except Exception:
                    pass
            n.network_tree.build(local_map=local, topology_map=topo)
            # traceroute + mdns только при force
            if force:
                if getattr(n, "traceroute_scan", None):
                    try:
                        tr = n.traceroute_scan.scan_multi()
                        n.network_tree.add_traceroute(tr.get("hops", []))
                    except Exception:
                        pass
                if getattr(n, "local_discovery", None):
                    try:
                        md = n.local_discovery.scan_all(timeout=2.0)
                        n.network_tree.add_mdns_devices(md.get("devices", []))
                    except Exception:
                        pass
            n.network_tree.recalc_stats()

        return jsonify({'success': True, **n.network_tree.get_tree()})
    except Exception as e:
        log.error('[Tree] error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500'''

patch_file(APP, [(old_tree_ep, new_tree_ep, True)], "app.py tree endpoint")


print()
print("=" * 70)
print("  PATCH 87-FIX DONE")
print("=" * 70)
print("  [OK] network_tree.py: recalc_stats() + вызовы в add_*")
print("  [OK] orchestrator.py: _full_scan_loop (каждые 2 мин)")
print("  [OK] app.py: /api/network/tree читает кэш, ?force=1 - полный скан")
print()
print("Перезапусти InevioNet. Через 30 сек - первое полное дерево.")
print("UI: Ctrl+F5, потом ждать 30-60 сек.")