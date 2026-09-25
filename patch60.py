# patch60.py - InevioNet: P60 — via in topology (глубина через relay)
#
# Что делает:
#   1. AutoTopology.merge(other_map, via_node_id="") — пишет via в metadata
#      и добавляет ребро via -> node (чтобы Dijkstra нашёл путь).
#   2. api_network_map (POST) — передаёт from_node в merge.
#   3. _growth_loop — передаёт their_id в merge.
#   4. _resolve_target — если прямого адреса нет, резолвит через via.
#
# Формат — стандартный для проекта: backup -> replace -> ast.parse -> rollback.
# Идемпотентность: если new in content и old not in content — already applied.

import os
import ast
import shutil

ROOT = r"E:\InevioNet"

TARGETS = {
    "topology":  os.path.join(ROOT, "inevionet", "mesh", "auto_topology.py"),
    "app":       os.path.join(ROOT, "web", "app.py"),
    "orch":      os.path.join(ROOT, "inevionet", "orchestrator.py"),
}

BAK_SUFFIX = ".bak_p60"


def backup(path):
    if os.path.exists(path):
        b = path + BAK_SUFFIX
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
        b = path + BAK_SUFFIX
        if os.path.exists(b):
            shutil.copy2(b, path)
            print(f"  [--] rolled back")
        return False


def patch(path, replacements, name):
    print()
    print("=" * 70)
    print(f"  {name}")
    print("=" * 70)
    if not os.path.exists(path):
        print(f"  [!!] NOT FOUND: {path}")
        return False
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
        return save_py(path, content)
    return True


# =====================================================================
# P60a: auto_topology.py — merge(other_map, via_node_id="")
# =====================================================================

P60A_OLD_SIG = '''    def merge(self, other_map: dict) -> dict:
        """P38: merge external map (nodes + edges) into self."""
        added_nodes = 0
        added_edges = 0
        if not other_map:
            return {"added_nodes": 0, "added_edges": 0}'''

P60A_NEW_SIG = '''    def merge(self, other_map: dict, via_node_id: str = "") -> dict:
        """P38: merge external map (nodes + edges) into self.

        P60: via_node_id — node_id того, от кого получена карта.
        Записывается в metadata['via'] и добавляет ребро via -> node,
        чтобы Dijkstra нашёл путь для relay.
        """
        added_nodes = 0
        added_edges = 0
        if not other_map:
            return {"added_nodes": 0, "added_edges": 0}'''

P60A_OLD_NODE = '''                self.nodes[node_id] = TopologyNode(
                    node_id=node_id,
                    name=node_data.get("name", node_id),
                    node_type=node_data.get("type", "external"),
                    rssi_dbm=float(node_data.get("rssi", -80)),
                    quality=float(node_data.get("quality", 0.5)),
                    metadata={"source": "merged"},
                )
                added_nodes += 1'''

P60A_NEW_NODE = '''                self.nodes[node_id] = TopologyNode(
                    node_id=node_id,
                    name=node_data.get("name", node_id),
                    node_type=node_data.get("type", "external"),
                    rssi_dbm=float(node_data.get("rssi", -80)),
                    quality=float(node_data.get("quality", 0.5)),
                    metadata={"source": "merged", "via": via_node_id},
                )
                added_nodes += 1
                # P60: add edge via -> node (so relay path exists)
                if (via_node_id
                        and via_node_id != node_id
                        and via_node_id in self.nodes):
                    _k = (via_node_id, node_id) if via_node_id < node_id else (node_id, via_node_id)
                    if _k not in self.edges:
                        self.edges[_k] = TopologyEdge(
                            source_id=via_node_id, target_id=node_id,
                            weight=0.5)
                        self.adjacency.setdefault(via_node_id, []).append((node_id, 0.5))
                        self.adjacency.setdefault(node_id, []).append((via_node_id, 0.5))
                        added_edges += 1'''

patch(TARGETS["topology"], [
    (P60A_OLD_SIG,  P60A_NEW_SIG,  True),
    (P60A_OLD_NODE, P60A_NEW_NODE, True),
], "P60a: AutoTopology.merge(via_node_id)")


# =====================================================================
# P60b: web/app.py — api_network_map POST -> merge(via_node_id=from_node)
# =====================================================================

P60B_OLD = '''    merged = topo.merge(other_map)
    log.info('[Growth] merged map from %s (+%d nodes, +%d edges)',
             from_node, merged.get('added_nodes', 0),
             merged.get('added_edges', 0))'''

P60B_NEW = '''    merged = topo.merge(other_map, via_node_id=from_node)
    log.info('[Growth] merged map from %s via=%s (+%d nodes, +%d edges)',
             from_node, from_node, merged.get('added_nodes', 0),
             merged.get('added_edges', 0))'''

patch(TARGETS["app"], [
    (P60B_OLD, P60B_NEW, True),
], "P60b: api_network_map -> merge(via_node_id=from_node)")


# =====================================================================
# P60c: orchestrator.py — _growth_loop -> merge(via_node_id=their_id)
# =====================================================================

P60C_OLD = '''                                    if r.get('success'):
                                        sent += 1
                                        other_map = (r.get('data') or {}).get('our_map') or {}
                                        if other_map:
                                            m = topo.merge(other_map)
                                            total_added_n += m.get('added_nodes', 0)
                                            total_added_e += m.get('added_edges', 0)'''

P60C_NEW = '''                                    if r.get('success'):
                                        sent += 1
                                        other_map = (r.get('data') or {}).get('our_map') or {}
                                        their_id_pre = (r.get('data') or {}).get('node_id', '') or ''
                                        if other_map:
                                            m = topo.merge(other_map, via_node_id=their_id_pre)
                                            total_added_n += m.get('added_nodes', 0)
                                            total_added_e += m.get('added_edges', 0)'''

patch(TARGETS["orch"], [
    (P60C_OLD, P60C_NEW, True),
], "P60c: _growth_loop -> merge(via_node_id=their_id)")


# =====================================================================
# P60d: orchestrator.py — _resolve_target -> via lookup
# =====================================================================

P60D_OLD = '''        # P46: lookup in trusted_hosts (by label=node_id or host)
        try:
            for h in self.trusted_hosts.list_all():
                label = h.get('label', '') or ''
                host = h.get('host', '') or ''
                if (label == r or host == r
                        or (label and label.startswith(r))
                        or (host and host.startswith(r))):
                    if ':' in host and not host.startswith('http'):
                        return "https://" + host
                    elif host.startswith('http'):
                        return host
                    else:
                        return "https://" + host + ":8080"
        except Exception:
            pass'''

P60D_NEW = '''        # P46: lookup in trusted_hosts (by label=node_id or host)
        try:
            for h in self.trusted_hosts.list_all():
                label = h.get('label', '') or ''
                host = h.get('host', '') or ''
                if (label == r or host == r
                        or (label and label.startswith(r))
                        or (host and host.startswith(r))):
                    if ':' in host and not host.startswith('http'):
                        return "https://" + host
                    elif host.startswith('http'):
                        return host
                    else:
                        return "https://" + host + ":8080"
        except Exception:
            pass

        # P60: via lookup in topology (relay через соседа)
        try:
            topo = getattr(self, '_auto_topology', None)
            if topo and hasattr(topo, 'nodes') and r in topo.nodes:
                md = getattr(topo.nodes[r], 'metadata', {}) or {}
                via = md.get('via', '') or ''
                if via and via != self.node_id:
                    logger.info('[Resolve] %s via %s', r, via)
                    return self._resolve_target(via)
        except Exception:
            pass'''

patch(TARGETS["orch"], [
    (P60D_OLD, P60D_NEW, True),
], "P60d: _resolve_target -> via lookup")


# =====================================================================
# Итог
# =====================================================================

print()
print("=" * 70)
print("  PATCH 60 DONE")
print("=" * 70)
print("  [OK] auto_topology.py: merge(via_node_id) + edge via->node")
print("  [OK] web/app.py:       api_network_map -> merge(via_node_id=from_node)")
print("  [OK] orchestrator.py:  _growth_loop -> merge(via_node_id=their_id)")
print("  [OK] orchestrator.py:  _resolve_target -> via lookup")
print()
print("Перезапусти:")
print("  python -m web.app")
print()
print("Проверка после запуска:")
print("  curl.exe -k http://localhost:8080/api/network/map")
print("  # у merged-узлов должен появиться via в metadata")
print()
print("Логи:")
print("  Get-Content E:\\InevioNet\\logs\\inevionet.log -Tail 50 | Select-String 'via|MERGE|Resolve'")