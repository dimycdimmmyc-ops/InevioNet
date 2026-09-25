# patch88fix3.py - P88-fix3: spores из footholds
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
MESH = os.path.join(ROOT, "inevionet", "mesh")
ORCH = os.path.join(ROOT, "inevionet", "orchestrator.py")
APP = os.path.join(ROOT, "web", "app.py")


def patch_file(path, replacements, label, bak=".bak_p88fix3"):
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
            print("  [OK] " + old[:55].strip())
        else:
            if required:
                print("  [!!] NOT FOUND: " + old[:55].strip())
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
# 1. network_tree.py - add_footholds() (из web_state.footholds)
# =====================================================================

print()
print("=" * 70)
print("  1. network_tree.py - add_footholds")
print("=" * 70)

TREE = os.path.join(MESH, "network_tree.py")

# Добавить метод add_footholds перед add_spores
old_anchor = '''    def add_spores(self, spores: List[Dict[str, Any]]):'''

new_anchor = '''    def add_footholds(self, footholds: Dict[str, str]):
        """P88-fix3: добавить footholds (из web_state) как spore-узлы.

        footholds: {"MTSRouter_58C5": "DNS_Tunneling", ...}
        parent ищем по имени WiFi-узла в дереве.
        """
        if not self.root or not footholds:
            return
        # Все WiFi-узлы по имени
        wifi_by_name = {}
        all_wifi = []
        for c in self.root.children:
            if c.node_type == "wifi":
                wifi_by_name[c.name] = c
                all_wifi.append(c)
            for cc in (c.children or []):
                if cc.node_type == "wifi":
                    wifi_by_name[cc.name] = cc
                    all_wifi.append(cc)

        added = 0
        for net_name, method in footholds.items():
            sid = "spore_" + net_name.replace(" ", "_")
            # Найти WiFi-родителя
            parent = wifi_by_name.get(net_name)
            spore_node = TreeNode(
                node_id=sid,
                node_type="spore",
                ip="mycelium",
                name="spore: " + net_name,
                hops=1,
                via=(parent.node_id if parent else ""),
                metadata={"method": method, "network": net_name, "source": "footholds"})
            if parent:
                parent.children.append(spore_node)
            else:
                self.root.children.append(spore_node)
            added += 1
        self.recalc_stats()
        return added

    def add_spores(self, spores: List[Dict[str, Any]]):'''

patch_file(TREE, [(old_anchor, new_anchor, True)], "network_tree.py add_footholds")


# =====================================================================
# 2. app.py - tree читает footholds из web_state
# =====================================================================

print()
print("=" * 70)
print("  2. app.py - tree + footholds")
print("=" * 70)

old_tree = '''            n.network_tree.build(local_map=local, topology_map=topo, spores=spores_list)'''

new_tree = '''            n.network_tree.build(local_map=local, topology_map=topo, spores=spores_list)
            # P88-fix3: footholds из web_state
            try:
                import json as _json
                from pathlib import Path as _Path
                state_paths = [
                    _Path(_data_home) / "web_state_%s.json" % _PORT,
                    _Path(_data_home) / "web_state.json",
                    _Path("E:/InevioNet/data/web_state.json"),
                ]
                for sp in state_paths:
                    if sp.exists():
                        with open(str(sp), "r", encoding="utf-8") as _f:
                            _st = _json.load(_f)
                        _footholds = _st.get("footholds", {})
                        if _footholds:
                            n.network_tree.add_footholds(_footholds)
                            log.info('[P88fix3] footholds: %d spores', len(_footholds))
                        break
            except Exception as _fe:
                log.debug('[P88fix3] footholds: %s', _fe)'''

patch_file(APP, [(old_tree, new_tree, True)], "app.py footholds")


# =====================================================================
# 3. orchestrator.py - full_scan_loop тоже читает footholds
# =====================================================================

print()
print("=" * 70)
print("  3. orchestrator.py - footholds в loop")
print("=" * 70)

old_loop = '''                    stats = self.network_tree.get_stats()
                    logger.info("[P88] full_scan: %d nodes, depth=%d, spores=%d",
                                stats.get("total_nodes", 0),
                                stats.get("max_depth", 0),
                                len(spores_list))'''

new_loop = '''                    # P88-fix3: footholds из web_state
                    try:
                        import json as _json
                        from pathlib import Path as _Path
                        _state_paths = [
                            _Path(os.environ.get("APPDATA", "")) / "InevioNet" / "data" / "web_state_8080.json",
                            _Path("E:/InevioNet/data/web_state.json"),
                        ]
                        for _sp in _state_paths:
                            if _sp.exists():
                                with open(str(_sp), "r", encoding="utf-8") as _f:
                                    _st = _json.load(_f)
                                _footholds = _st.get("footholds", {})
                                if _footholds:
                                    self.network_tree.add_footholds(_footholds)
                                    logger.info("[P88fix3] footholds: %d", len(_footholds))
                                break
                    except Exception as _fe:
                        logger.debug("[P88fix3] footholds: %s", _fe)

                    stats = self.network_tree.get_stats()
                    logger.info("[P88] full_scan: %d nodes, depth=%d, spores=%d",
                                stats.get("total_nodes", 0),
                                stats.get("max_depth", 0),
                                len(spores_list))'''

patch_file(ORCH, [(old_loop, new_loop, True)], "orchestrator.py footholds")


print()
print("=" * 70)
print("  PATCH 88-FIX3 DONE")
print("=" * 70)
print("  [OK] network_tree.add_footholds()")
print("  [OK] app.py tree: footholds из web_state")
print("  [OK] orchestrator loop: footholds")
print()
print("Перезапуск InevioNet, потом Ctrl+F5.")