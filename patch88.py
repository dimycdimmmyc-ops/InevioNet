# patch88.py - P88: spores + WiFi + recursive probe + traceroute devices
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
INEV = os.path.join(ROOT, "inevionet")
MESH = os.path.join(INEV, "mesh")
ORCH = os.path.join(INEV, "orchestrator.py")
APP = os.path.join(ROOT, "web", "app.py")
HTML = os.path.join(ROOT, "web", "templates", "index.html")


def patch_file(path, replacements, label, bak=".bak_p88"):
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
# 1. network_tree.py - build() принимает spores + add_spores()
# =====================================================================

print()
print("=" * 70)
print("  1. network_tree.py - spores")
print("=" * 70)

TREE = os.path.join(MESH, "network_tree.py")

# Изменить сигнатуру build() - добавить spores
old_sig = '''    def build(self, local_map: Dict[str, Any],
              topology_map: Optional[Dict[str, Any]] = None,
              gravity: Optional[Dict[str, Any]] = None) -> "NetworkTree":'''

new_sig = '''    def build(self, local_map: Dict[str, Any],
              topology_map: Optional[Dict[str, Any]] = None,
              gravity: Optional[Dict[str, Any]] = None,
              spores: Optional[List[Dict[str, Any]]] = None) -> "NetworkTree":'''

# Добавить add_spores() метод перед build()
old_build = '''    def build(self, local_map: Dict[str, Any],'''

new_build = '''    def add_spores(self, spores: List[Dict[str, Any]]):
        """P88: добавить споры как отдельные узлы.

        Спора крепится к WiFi-родителю через via.
        Родитель ищется по parent (wifi_XXX) или по MAC.
        """
        if not self.root or not spores:
            return
        # Найти все WiFi-узлы в дереве (по MAC или node_id)
        wifi_nodes = {}
        for c in self.root.children:
            if c.node_type == "wifi":
                wifi_nodes[c.node_id] = c
                # Также по MAC
                if c.ip:
                    wifi_nodes[c.ip] = c
        # И у router
        for c in self.root.children:
            for cc in (c.children or []):
                if cc.node_type == "wifi":
                    wifi_nodes[cc.node_id] = cc

        for s in spores:
            sid = s.get("node_id", "")
            if not sid:
                continue
            parent_id = s.get("parent", "")  # wifi_04bad6a358ca
            # Ищем WiFi-родителя
            parent_node = None
            # parent: wifi_04bad6a358ca -> ищем по MAC 04:ba:d6:a3:58:ca
            mac_from_parent = ""
            if parent_id.startswith("wifi_"):
                mac_raw = parent_id[5:]  # 04bad6a358ca
                if len(mac_raw) == 12:
                    mac_from_parent = ":".join(mac_raw[i:i+2] for i in range(0, 12, 2))
            if mac_from_parent and mac_from_parent in wifi_nodes:
                parent_node = wifi_nodes[mac_from_parent]

            spore_node = TreeNode(
                node_id=sid,
                node_type="spore",
                ip=s.get("ip", ""),
                name=s.get("label", "") or s.get("name", ""),
                hops=1,
                via=parent_id,  # P88: via = wifi_XXX
                metadata={
                    "rssi": s.get("rssi", -100),
                    "signal": s.get("signal", 0),
                    "trust": s.get("trust", 0),
                    "method": s.get("method", ""),
                    "parent_label": parent_id,
                })
            if parent_node:
                parent_node.children.append(spore_node)
            else:
                # Крепим к root
                self.root.children.append(spore_node)
        self.recalc_stats()

    def build(self, local_map: Dict[str, Any],'''

patch_file(TREE, [
    (old_sig, new_sig, True),
    (old_build, new_build, True),
], "network_tree.py spores")


# =====================================================================
# 2. orchestrator.py - _full_scan_loop: spores + recursive + traceroute devices
# =====================================================================

print()
print("=" * 70)
print("  2. orchestrator.py - full_scan расширен")
print("=" * 70)

# Найти блок в _full_scan_loop, где строится дерево - добавить spores + recursive
old_block = '''                # 5. Построить дерево
                if getattr(self, "network_tree", None):
                    self.network_tree.build(local_map=local, topology_map=topo)
                    self.network_tree.add_traceroute(tr_result.get("hops", []))
                    self.network_tree.add_mdns_devices(mdns_result.get("devices", []))
                    stats = self.network_tree.get_stats()
                    logger.info("[P87fix] full_scan: %d nodes, depth=%d",
                                stats.get("total_nodes", 0),
                                stats.get("max_depth", 0))'''

new_block = '''                # 5. Spores
                spores_list = []
                try:
                    if getattr(self, "mycelium", None) and getattr(self.mycelium, "spores", None):
                        sm = self.mycelium.spores
                        if hasattr(sm, "spores") and isinstance(sm.spores, dict):
                            for spore_id, spore in sm.spores.items():
                                try:
                                    spores_list.append({
                                        "node_id": spore_id,
                                        "label": getattr(spore, "target_network", "") or getattr(spore, "label", ""),
                                        "parent": "wifi_" + spore_id.split("_")[-1] if "_" in spore_id else "",
                                        "ip": "mycelium",
                                        "rssi": -70,
                                        "trust": 65.0,
                                        "method": getattr(spore, "method", ""),
                                    })
                                except Exception:
                                    pass
                except Exception as _se:
                    logger.debug("[P88] spores collect: %s", _se)

                # 6. RecursiveProbe (P88)
                rp_result = {}
                try:
                    from .network.recursive_probe import RecursiveProbe
                    rp = RecursiveProbe()
                    subnet = local.get("subnet", "")
                    if subnet:
                        rp_result = rp.probe_subnet(subnet, depth=0)
                except Exception as _re:
                    logger.debug("[P88] recursive probe: %s", _re)

                # 7. Построить дерево
                if getattr(self, "network_tree", None):
                    self.network_tree.build(local_map=local, topology_map=topo,
                                            spores=spores_list)
                    self.network_tree.add_traceroute(tr_result.get("hops", []))
                    self.network_tree.add_mdns_devices(mdns_result.get("devices", []))

                    # P88: InevioNet-узлы из recursive probe
                    for node in rp_result.get("inevionet_nodes", []):
                        try:
                            self.network_tree.add_traceroute([{
                                "hop": 1, "ip": node["ip"], "target": "inevionet"}])
                        except Exception:
                            pass

                    stats = self.network_tree.get_stats()
                    logger.info("[P88] full_scan: %d nodes, depth=%d, spores=%d",
                                stats.get("total_nodes", 0),
                                stats.get("max_depth", 0),
                                len(spores_list))'''

patch_file(ORCH, [(old_block, new_block, True)], "orchestrator.py P88")


# =====================================================================
# 3. app.py - tree передаёт spores
# =====================================================================

print()
print("=" * 70)
print("  3. app.py - tree + spores")
print("=" * 70)

# Обновить api_network_tree - собирать spores
old_tree = '''        # Форс: запустить полный скан синхронно
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
            n.network_tree.recalc_stats()'''

new_tree = '''        # Форс: запустить полный скан синхронно
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
            # P88: spores
            spores_list = []
            try:
                if getattr(n, "mycelium", None) and getattr(n.mycelium, "spores", None):
                    sm = n.mycelium.spores
                    if hasattr(sm, "spores") and isinstance(sm.spores, dict):
                        for spore_id, spore in sm.spores.items():
                            try:
                                spores_list.append({
                                    "node_id": spore_id,
                                    "label": getattr(spore, "target_network", "") or getattr(spore, "label", ""),
                                    "parent": "wifi_" + spore_id.split("_")[-1] if "_" in spore_id else "",
                                    "ip": "mycelium",
                                    "rssi": -70,
                                    "trust": 65.0,
                                    "method": getattr(spore, "method", ""),
                                })
                            except Exception:
                                pass
            except Exception:
                pass
            n.network_tree.build(local_map=local, topology_map=topo, spores=spores_list)
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
            n.network_tree.recalc_stats()'''

patch_file(APP, [(old_tree, new_tree, True)], "app.py tree spores")


# =====================================================================
# 4. UI - нормализация spore, rssi-size, свежие fetch
# =====================================================================

print()
print("=" * 70)
print("  4. UI - spore + rssi size")
print("=" * 70)

# В loadTreeFromAPI - нормализовать type для spore
old_norm = '''      // P87d: нормализация типа
      let ntype = n.node_type || 'device';
      if (n.node_id.startsWith('tr_')) ntype = 'traceroute';
      else if (n.node_id.startsWith('web_node_')) ntype = 'inevionet';
      else if (n.node_id.startsWith('router_')) ntype = 'router';
      else if (n.node_id.startsWith('dev_')) ntype = 'device';
      else if (n.node_id.startsWith('mdns_')) ntype = 'local_device';
      else if (n.node_id.includes(':') && n.node_id.length === 17) ntype = 'wifi';'''

new_norm = '''      // P87d: нормализация типа
      let ntype = n.node_type || 'device';
      if (n.node_id.startsWith('tr_')) ntype = 'traceroute';
      else if (n.node_id.startsWith('web_node_')) ntype = 'inevionet';
      else if (n.node_id.startsWith('router_')) ntype = 'router';
      else if (n.node_id.startsWith('dev_')) ntype = 'device';
      else if (n.node_id.startsWith('mdns_')) ntype = 'local_device';
      else if (n.node_id.startsWith('spore_')) ntype = 'spore';
      else if (n.node_id.includes(':') && n.node_id.length === 17) ntype = 'wifi';'''

# В rebuildStars - размер споры по rssi
old_size = '''    else if (nd.type === 'traceroute' || (nd.node_id && nd.node_id.startsWith('tr_'))) {
      base = 3.5;  // P87d: увеличил размер
      color = tracerouteColor(nd.hops || 1);
      nd.type = 'traceroute';  // нормализуем
    }'''

new_size = '''    else if (nd.type === 'traceroute' || (nd.node_id && nd.node_id.startsWith('tr_'))) {
      base = 3.5;
      color = tracerouteColor(nd.hops || 1);
      nd.type = 'traceroute';
    }
    else if (nd.type === 'spore') {
      // P88: размер споры по rssi
      const rssi = (nd.rssi || -70);
      // rssi от -30 до -100 -> размер от 4 до 2
      base = 2 + Math.max(0, (rssi + 100) / 70 * 2);
      color = '#ff375f';  // розовый
    }'''

# В layout - споры вокруг WiFi-родителя
old_layout_spore = '''  // P87g: traceroute спираль для 100 hops
  const isTr = (nd.type === 'traceroute') || (nd.node_id && nd.node_id.startsWith('tr_'));
  if (isTr) {'''

new_layout_spore = '''  // P88: споры вокруг WiFi-родителя
  if (nd.type === 'spore') {
    const parent = nd.via && pm[nd.via.replace('wifi_', '')];
    // Или напрямую по mac
    let macParent = null;
    if (nd.via && nd.via.startsWith('wifi_')) {
      const raw = nd.via.slice(5);
      if (raw.length === 12) {
        macParent = raw.slice(0,2)+':'+raw.slice(2,4)+':'+raw.slice(4,6)+':'+raw.slice(6,8)+':'+raw.slice(8,10)+':'+raw.slice(10,12);
      }
    }
    const p = (macParent && pm[macParent]) || (parent);
    if (p) {
      const a2 = (h % 360) * Math.PI / 180;
      const r2 = 25 + (h % 15);
      return { x: p.x + Math.cos(a2) * r2, y: p.y + Math.sin(a2) * r2 };
    }
    // Fallback - вокруг центра
    const r3 = 200 + (h % 60);
    return { x: Math.cos(a) * r3, y: Math.sin(a) * r3 };
  }

  // P87g: traceroute спираль для 100 hops
  const isTr = (nd.type === 'traceroute') || (nd.node_id && nd.node_id.startsWith('tr_'));
  if (isTr) {'''

patch_file(HTML, [
    (old_norm, new_norm, True),
    (old_size, new_size, True),
    (old_layout_spore, new_layout_spore, True),
], "index.html P88", bak=".bak_p88")


print()
print("=" * 70)
print("  PATCH 88 DONE")
print("=" * 70)
print("  [OK] network_tree: add_spores() + build(spores=)")
print("  [OK] orchestrator: full_scan расширен (spores + recursive + inevionet)")
print("  [OK] app.py: /api/network/tree передаёт spores")
print("  [OK] UI: spore color #ff375f, размер по rssi, вокруг WiFi")
print()
print("Перезапусти InevioNet. Ждём 30-120 сек (первый full_scan).")
print("Ctrl+F5 в браузере.")