"""InevioNet NetworkTree - дерево сетей.

Структура:
  root (свой роутер)
  ├── devices (устройства своей подсети)
  ├── subnets (соседние подсети)
  │   ├── router (роутер соседа)
  │   ├── devices
  │   └── subnets (глубже)
  └── inevionet_nodes (InevioNet-узлы)
"""
import time
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

from ..core.logger import get_logger

logger = get_logger("inevionet.mesh.network_tree")


@dataclass
class TreeNode:
    """Узел дерева сетей."""
    node_id: str = ""
    node_type: str = ""          # self / router / device / inevionet / subnet
    ip: str = ""
    mac: str = ""
    name: str = ""
    vendor: str = ""
    hops: int = 0
    via: str = ""
    children: List["TreeNode"] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["children"] = [c.to_dict() for c in self.children]
        return d

    def count_nodes(self) -> int:
        n = 1
        for c in self.children:
            n += c.count_nodes()
        return n


class NetworkTree:
    """Дерево сетей InevioNet."""

    def __init__(self, node_id: str):
        self.node_id = node_id
        self.root: Optional[TreeNode] = None
        self._stats = {
            "builds": 0,
            "total_nodes": 0,
            "max_depth": 0,
            "started_at": time.time(),
        }

    def add_traceroute(self, hops: List[Dict[str, Any]]):
        """P84: добавить traceroute hops в дерево."""
        if not self.root or not hops:
            return
        # Traceroute создаёт цепочку: self -> hop1 -> hop2 -> ...
        parent = self.root
        for h in sorted(hops, key=lambda x: x.get("hop", 0)):
            ip = h.get("ip", "")
            if not ip:
                continue
            node = TreeNode(
                node_id="tr_" + ip,
                node_type="traceroute",
                ip=ip,
                name="hop " + str(h.get("hop", "?")) + " " + ip,
                hops=int(h.get("hop", 0)),
                via=parent.node_id,
                metadata={"source": "traceroute",
                          "target": h.get("target", "")})
            parent.children.append(node)
            parent = node
        # P87fix: пересчёт stats
        self.recalc_stats()

    def add_mdns_devices(self, devices: List[Dict[str, Any]]):
        """P85: добавить mDNS/SSDP устройства в дерево."""
        if not self.root:
            return
        for d in devices:
            ip = d.get("ip", "")
            if not ip:
                continue
            node = TreeNode(
                node_id="mdns_" + ip,
                node_type="local_device",
                ip=ip,
                name=d.get("server", "") or ip,
                hops=1,
                via=self.root.node_id,
                metadata={"source": d.get("source", "mdns"),
                          "location": d.get("location", "")})
            self.root.children.append(node)
        # P87fix: пересчёт stats
        self.recalc_stats()

    def add_router_admin(self, admin_result: Dict[str, Any]):
        """P86: добавить ARP роутера в дерево."""
        if not self.root:
            return
        ip = admin_result.get("ip", "")
        for entry in admin_result.get("arp", []):
            dev_ip = entry.get("ip", "")
            if not dev_ip or dev_ip == ip:
                continue
            # Уже в дереве?
            found = False
            for c in self.root.children:
                if c.ip == dev_ip:
                    found = True
                    break
            if found:
                continue
            node = TreeNode(
                node_id="rarp_" + dev_ip,
                node_type="device",
                ip=dev_ip,
                mac=entry.get("mac", ""),
                name=dev_ip,
                hops=2,
                via=ip,
                metadata={"source": "router_arp"})
            # Крепим к роутеру, если он в дереве
            for c in self.root.children:
                if c.ip == ip:
                    c.children.append(node)
                    break
            else:
                self.root.children.append(node)
        # P87fix: пересчёт stats
        self.recalc_stats()

    def add_wifi_devices(self, local_map: Dict[str, Any]):
        """P90a: добавить устройства своего роутера под ним.

        Из local_map: devices (ARP) + router_ip.
        Каждое устройство -> ребёнок router_XXX.
        """
        if not self.root or not local_map:
            return
        router_ip = local_map.get("router_ip", "")
        devices = local_map.get("devices", [])
        my_ip = local_map.get("my_ip", "")
        if not router_ip or not devices:
            return

        # Найти router_XXX в дереве
        router_node = None
        for c in self.root.children:
            if c.node_id == "router_" + router_ip or c.ip == router_ip:
                router_node = c
                break
        if not router_node:
            return

        # Уже добавленные дети
        existing_ips = set()
        for ch in (router_node.children or []):
            if ch.ip:
                existing_ips.add(ch.ip)

        added = 0
        for d in devices:
            ip = d.get("ip", "")
            if not ip or ip == my_ip or ip == router_ip:
                continue
            if ip in existing_ips:
                continue
            # Тип из local_map
            dtype = d.get("type", "device")
            if dtype == "router":
                continue
            dev_node = TreeNode(
                node_id="dev_" + ip,
                node_type="device",
                ip=ip,
                mac=d.get("mac", ""),
                name=d.get("hostname", "") or ip,
                hops=2,
                via=router_ip,
                metadata={"source": "local_map",
                          "vendor": d.get("vendor", "")})
            router_node.children.append(dev_node)
            added += 1

        self.recalc_stats()
        return added

    def add_footholds(self, footholds: Dict[str, str]):
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

    def add_footholds(self, footholds: Dict[str, str]):
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

    def add_spores(self, spores: List[Dict[str, Any]]):
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

    def build(self, local_map: Dict[str, Any],
              topology_map: Optional[Dict[str, Any]] = None,
              gravity: Optional[Dict[str, Any]] = None,
              spores: Optional[List[Dict[str, Any]]] = None) -> "NetworkTree":
        """Построить дерево из LocalMap + Topology + Gravity."""
        # P82fix: fix for NoneType context manager
        self._stats["builds"] = self._stats.get("builds", 0) + 1

        # Root - свой роутер
        router_ip = local_map.get("router_ip", "")
        my_ip = local_map.get("my_ip", "")
        subnet = local_map.get("subnet", "")

        self.root = TreeNode(
            node_id=self.node_id,
            node_type="self",
            ip=my_ip,
            name=f"self ({self.node_id})",
            hops=0,
            metadata={"subnet": subnet, "router_ip": router_ip})

        # Свой роутер как отдельный узел
        router_node = TreeNode(
            node_id=f"router_{router_ip}",
            node_type="router",
            ip=router_ip,
            name=f"router {router_ip}",
            hops=1,
            via=self.node_id,
            metadata={"subnet": subnet})

        # Устройства своей подсети
        for d in local_map.get("devices", []):
            ip = d.get("ip", "")
            if not ip or ip == my_ip or ip == router_ip:
                continue
            ntype = d.get("type", "device")
            if ntype == "router":
                continue
            child = TreeNode(
                node_id=f"dev_{ip}",
                node_type="device",
                ip=ip,
                mac=d.get("mac", ""),
                name=d.get("hostname", "") or ip,
                vendor=d.get("vendor", ""),
                hops=1,
                via=router_ip,
                metadata={"source": d.get("source", "arp")})
            router_node.children.append(child)

        self.root.children.append(router_node)

        # Узлы из topology - различаем тип по node_id
        if topology_map:
            nodes = topology_map.get("nodes", {})
            for nid, nd in nodes.items():
                if nid == self.node_id:
                    continue
                # P84-fix: определение типа
                if nid.startswith("web_node_"):
                    ntype = "inevionet"
                elif nid.startswith("dev_"):
                    ntype = "device"
                elif nid.startswith("router_"):
                    ntype = "router"
                elif nid.startswith("tr_"):
                    ntype = "traceroute"
                elif nid.startswith("mdns_"):
                    ntype = "local_device"
                elif ":" in nid and len(nid) == 17:
                    # MAC-адрес => WiFi-роутер
                    ntype = "wifi"
                else:
                    ntype = nd.get("type", "external")
                hops = int(nd.get("hops", 1))
                via = nd.get("via", "")
                # Источник
                if ntype == "wifi":
                    src = "rf"
                elif ntype == "inevionet":
                    src = "topology"
                else:
                    src = nd.get("source", "topology")
                child = TreeNode(
                    node_id=nid,
                    node_type=ntype,
                    ip=nd.get("ip", ""),
                    name=nd.get("name", nid),
                    hops=hops,
                    via=via,
                    metadata={"source": src})
                self.root.children.append(child)

        # Обновить stats
        self._stats["total_nodes"] = self.root.count_nodes()
        self._stats["max_depth"] = self._compute_depth(self.root)

        return self

    def _compute_depth(self, node: TreeNode, depth: int = 0, max_depth: int = 100) -> int:
        # P87g: ограничение 100
        if depth >= max_depth:
            return depth
        if not node.children:
            return depth
        return max(self._compute_depth(c, depth + 1, max_depth) for c in node.children)

    def recalc_stats(self):
        """P87fix: пересчитать stats после add_*."""
        if self.root:
            self._stats["total_nodes"] = self.root.count_nodes()
            self._stats["max_depth"] = self._compute_depth(self.root)

    def get_tree(self) -> Dict[str, Any]:
        if not self.root:
            return {"root": None, "stats": self._stats}
        return {
            "root": self.root.to_dict(),
            "stats": self._stats,
        }

    def get_stats(self) -> Dict[str, Any]:
        return dict(self._stats)

    def get_by_depth(self) -> Dict[int, List[Dict[str, Any]]]:
        """Сгруппировать узлы по глубине."""
        result = {}
        if not self.root:
            return result

        def walk(node: TreeNode, depth: int):
            result.setdefault(depth, []).append({
                "node_id": node.node_id,
                "type": node.node_type,
                "ip": node.ip,
                "name": node.name,
                "hops": node.hops,
                "via": node.via,
            })
            for c in node.children:
                walk(c, depth + 1)

        walk(self.root, 0)
        return result
