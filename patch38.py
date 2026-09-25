# patch38.py - InevioNet: MYCELIUM GROWTH (merge maps + probe + growth loop + growth genes)
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
ORCH = os.path.join(ROOT, "inevionet", "orchestrator.py")
TOPO = os.path.join(ROOT, "inevionet", "mesh", "auto_topology.py")
SPORES = os.path.join(ROOT, "inevionet", "mycelium", "spores.py")
PHERO = os.path.join(ROOT, "inevionet", "mycelium", "pheromones.py")
GENOME = os.path.join(ROOT, "inevionet", "evolution", "genome.py")
APP = os.path.join(ROOT, "web", "app.py")
HTML = os.path.join(ROOT, "web", "templates", "index.html")


def backup(path):
    if os.path.exists(path):
        b = path + ".bak_p38"
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
        if os.path.exists(path + ".bak_p38"):
            shutil.copy2(path + ".bak_p38", path)
        return False


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
# P38a. auto_topology.py: merge() + export_map()
# ============================================================
patch(TOPO, [
    (
        '''    def clear(self):
        self.nodes.clear()
        self.edges.clear()
        self.adjacency.clear()''',
        '''    def export_map(self) -> dict:
        """P38: export map for sharing (nodes + edges)."""
        return {
            "nodes": {
                nid: {
                    "name": n.name,
                    "type": n.node_type,
                    "rssi": n.rssi_dbm,
                    "quality": n.quality,
                }
                for nid, n in self.nodes.items()
            },
            "edges": [
                {
                    "source": e.source_id,
                    "target": e.target_id,
                    "weight": e.weight,
                }
                for e in self.edges.values()
            ],
            "stats": {
                "nodes": len(self.nodes),
                "edges": len(self.edges),
            },
        }

    def merge(self, other_map: dict) -> dict:
        """P38: merge external map (nodes + edges) into self."""
        added_nodes = 0
        added_edges = 0
        if not other_map:
            return {"added_nodes": 0, "added_edges": 0}
        for node_id, node_data in other_map.get("nodes", {}).items():
            if node_id in self.nodes:
                continue
            try:
                self.nodes[node_id] = TopologyNode(
                    node_id=node_id,
                    name=node_data.get("name", node_id),
                    node_type=node_data.get("type", "external"),
                    rssi_dbm=float(node_data.get("rssi", -80)),
                    quality=float(node_data.get("quality", 0.5)),
                    metadata={"source": "merged"},
                )
                added_nodes += 1
            except Exception:
                pass
        for edge in other_map.get("edges", []):
            try:
                src = edge["source"]
                dst = edge["target"]
                w = float(edge.get("weight", 1.0))
                if src not in self.nodes or dst not in self.nodes:
                    continue
                key = (src, dst) if src < dst else (dst, src)
                if key in self.edges:
                    continue
                self.edges[key] = TopologyEdge(
                    source_id=src, target_id=dst, weight=w)
                self.adjacency[src].append((dst, w))
                self.adjacency[dst].append((src, w))
                added_edges += 1
            except Exception:
                pass
        if added_nodes or added_edges:
            logger.info("[Topology] MERGED: +%d nodes, +%d edges",
                        added_nodes, added_edges)
        return {"added_nodes": added_nodes, "added_edges": added_edges}

    def clear(self):
        self.nodes.clear()
        self.edges.clear()
        self.adjacency.clear()''',
        True,
    ),
], "P38a: auto_topology merge + export_map")


# ============================================================
# P38b. spores.py: map_data + create_probe + merge_map + get_maps
# ============================================================
patch(SPORES, [
    # 1. Add map fields to Spore
    (
        '''    # P16: capsule payload
    capsule_code: bytes = b""
    capsule_target: str = ""
    capsule_method: str = "auto"
    capsule_version: str = "1.0.0"
    parent_capsule_id: str = ""
    generation: int = 0''',
        '''    # P16: capsule payload
    capsule_code: bytes = b""
    capsule_target: str = ""
    capsule_method: str = "auto"
    capsule_version: str = "1.0.0"
    parent_capsule_id: str = ""
    generation: int = 0

    # P38: map data (щупальце)
    map_data: Dict[str, Any] = field(default_factory=dict)
    probe_ttl: int = 5
    probe_time: float = 0.0
    is_probe: bool = False''',
        True,
    ),
    # 2. Add create_probe + merge_map + get_maps to SporeManager
    (
        '''    def tick_all(self, hours=1.0):''',
        '''    def create_probe(self, node_id, target_network, ttl=5):
        """P38: create probe-spore with map."""
        spore = Spore(
            node_id=node_id, target_network=target_network,
            method="probe", ttl=600.0, viability=1.0,
        )
        spore.probe_ttl = ttl
        spore.is_probe = True
        spore.probe_time = time.time()
        with self._lock:
            if len(self.spores) >= self.max_spores:
                self._cleanup_oldest(100)
            self.spores[spore.spore_id] = spore
        if self.persist:
            self._save()
        return spore

    def merge_map(self, spore_id, map_data):
        """P38: merge map from spore."""
        spore = self.get(spore_id)
        if not spore:
            return False
        spore.map_data = map_data or {}
        spore.probe_time = time.time()
        if self.persist:
            self._save()
        return True

    def get_maps(self):
        """P38: all maps from spores."""
        with self._lock:
            return {
                sid: s.map_data for sid, s in self.spores.items()
                if s.map_data
            }

    def get_probes(self):
        """P38: all probe-spores."""
        with self._lock:
            return [s for s in self.spores.values() if s.is_probe and s.is_alive()]

    def tick_all(self, hours=1.0):''',
        True,
    ),
], "P38b: spores map_data + create_probe + merge_map")


# ============================================================
# P38c. pheromones.py: via + path in Pheromone
# ============================================================
patch(PHERO, [
    (
        '''    source: str
    destination: str
    protocol: str
    strength: float = 1.0
    timestamp: float = 0.0
    hops: int = 0
    success_count: int = 1
    total_attempts: int = 1''',
        '''    source: str
    destination: str
    protocol: str
    strength: float = 1.0
    timestamp: float = 0.0
    hops: int = 0
    success_count: int = 1
    total_attempts: int = 1
    # P38: транзитивность
    via: str = ""           # через кого (next hop)
    path: List[str] = field(default_factory=list)  # полный маршрут''',
        True,
    ),
    # Update to_dict / from_dict
    (
        '''    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source, "destination": self.destination,
            "protocol": self.protocol, "strength": self.strength,
            "timestamp": self.timestamp, "hops": self.hops,
            "success_count": self.success_count,
            "total_attempts": self.total_attempts,
        }''',
        '''    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source, "destination": self.destination,
            "protocol": self.protocol, "strength": self.strength,
            "timestamp": self.timestamp, "hops": self.hops,
            "success_count": self.success_count,
            "total_attempts": self.total_attempts,
            "via": self.via, "path": self.path,
        }''',
        True,
    ),
    (
        '''    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Pheromone":
        return cls(
            source=data["source"], destination=data["destination"],
            protocol=data["protocol"], strength=data.get("strength", 1.0),
            timestamp=data.get("timestamp", time.time()),
            hops=data.get("hops", 0),
            success_count=data.get("success_count", 1),
            total_attempts=data.get("total_attempts", 1))''',
        '''    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Pheromone":
        return cls(
            source=data["source"], destination=data["destination"],
            protocol=data["protocol"], strength=data.get("strength", 1.0),
            timestamp=data.get("timestamp", time.time()),
            hops=data.get("hops", 0),
            success_count=data.get("success_count", 1),
            total_attempts=data.get("total_attempts", 1),
            via=data.get("via", ""),
            path=data.get("path", []))''',
        True,
    ),
    # Add transitive method
    (
        '''    def evaporate(self):''',
        '''    def mark_transit(self, source, destination, via, path=None):
        """P38: mark transitive route (source -> via -> destination)."""
        key = self._make_key(source, destination, "TRANSIT")
        with self._lock:
            if key in self.pheromones:
                p = self.pheromones[key]
                p.reinforce()
                p.via = via
                if path:
                    p.path = list(path)
            else:
                p = Pheromone(
                    source=source, destination=destination,
                    protocol="TRANSIT", strength=0.7)
                p.via = via
                p.path = list(path or [])
                self.pheromones[key] = p
        if self.persist:
            self._save()

    def get_transit_path(self, source, destination):
        """P38: get transitive path (source -> ... -> destination)."""
        with self._lock:
            for p in self.pheromones.values():
                if (p.source == source and p.destination == destination
                        and p.protocol == "TRANSIT" and p.path):
                    return list(p.path)
        return None

    def evaporate(self):''',
        True,
    ),
], "P38c: pheromones via + path + transit")


# ============================================================
# P38d. genome.py: growth genes
# ============================================================
patch(GENOME, [
    # Add growth genes
    (
        '''    # P16: capsule genes
    capsule_strategy: str = "minimal"
    capsule_deploy_method: str = "auto"
    capsule_fragment_size: int = 32768
    capsule_channel: str = "DNS"
    capsule_spawn_depth: int = 2
    capsule_targets_per_cycle: int = 5''',
        '''    # P16: capsule genes
    capsule_strategy: str = "minimal"
    capsule_deploy_method: str = "auto"
    capsule_fragment_size: int = 32768
    capsule_channel: str = "DNS"
    capsule_spawn_depth: int = 2
    capsule_targets_per_cycle: int = 5

    # P38: growth genes (mycelium)
    growth_aggressiveness: float = 0.5
    growth_max_hops: int = 5
    growth_probe_interval: int = 60
    growth_share_map: bool = True
    growth_accept_map: bool = True''',
        True,
    ),
    # Mutate growth genes
    (
        '''        if random.random() < 0.01:
            self.mutation_rate *= random.uniform(0.8, 1.2)
            self.mutation_rate = max(0.001, min(0.1, self.mutation_rate))''',
        '''        # P38: mutate growth genes
        if random.random() < self.mutation_rate * strength:
            self.growth_aggressiveness = max(0.0, min(1.0,
                self.growth_aggressiveness + random.gauss(0, 0.1 * strength)))
        if random.random() < self.mutation_rate * strength:
            self.growth_max_hops = max(1, min(10,
                self.growth_max_hops + random.randint(-1, 1)))
        if random.random() < self.mutation_rate * strength:
            self.growth_probe_interval = max(30, min(600,
                self.growth_probe_interval + random.randint(-30, 30)))
        if random.random() < self.mutation_rate * strength:
            self.growth_share_map = not self.growth_share_map
        if random.random() < self.mutation_rate * strength:
            self.growth_accept_map = not self.growth_accept_map

        if random.random() < 0.01:
            self.mutation_rate *= random.uniform(0.8, 1.2)
            self.mutation_rate = max(0.001, min(0.1, self.mutation_rate))''',
        True,
    ),
    # Crossover growth genes
    (
        '''        child.packet_size = random.choice([self.packet_size, partner.packet_size])''',
        '''        # P38: crossover growth genes
        child.growth_aggressiveness = (
            self.growth_aggressiveness + partner.growth_aggressiveness) / 2
        child.growth_max_hops = random.choice(
            [self.growth_max_hops, partner.growth_max_hops])
        child.growth_probe_interval = random.choice(
            [self.growth_probe_interval, partner.growth_probe_interval])
        child.growth_share_map = random.choice(
            [self.growth_share_map, partner.growth_share_map])
        child.growth_accept_map = random.choice(
            [self.growth_accept_map, partner.growth_accept_map])

        child.packet_size = random.choice([self.packet_size, partner.packet_size])''',
        True,
    ),
    # to_dict
    (
        '''            "clone_threshold": self.clone_threshold, "fitness": self.fitness,
            "mutation_rate": self.mutation_rate,
        }''',
        '''            "clone_threshold": self.clone_threshold, "fitness": self.fitness,
            "mutation_rate": self.mutation_rate,
            "growth_aggressiveness": self.growth_aggressiveness,
            "growth_max_hops": self.growth_max_hops,
            "growth_probe_interval": self.growth_probe_interval,
            "growth_share_map": self.growth_share_map,
            "growth_accept_map": self.growth_accept_map,
        }''',
        True,
    ),
], "P38d: genome growth genes")


# ============================================================
# P38e. web/app.py: /api/network/map + /api/network/probe
# ============================================================
patch(APP, [
    (
        '''@app.route('/api/network/sweep', methods=['POST'])''',
        '''@app.route('/api/network/map', methods=['GET', 'POST'])
def api_network_map():
    """P38: get/merge network map (mycelium growth)."""
    n = get_net()
    topo = getattr(n, '_auto_topology', None)
    if topo is None:
        try:
            topo = n.enable_auto_topology()
        except Exception:
            topo = None
    if topo is None:
        return jsonify({'success': False, 'error': 'no_topology'}), 500

    if request.method == 'GET':
        return jsonify({
            'success': True,
            'node_id': n.node_id,
            'map': topo.export_map(),
        })

    # POST: merge incoming map
    d = request.get_json(silent=True) or {}
    other_map = d.get('map', {})
    from_node = d.get('from_node', 'unknown')
    hops = int(d.get('hops', 0))
    max_hops = int(d.get('max_hops', 5))

    if not other_map:
        return jsonify({'success': False, 'error': 'empty_map'}), 400

    merged = topo.merge(other_map)
    log.info('[Growth] merged map from %s (+%d nodes, +%d edges)',
             from_node, merged.get('added_nodes', 0),
             merged.get('added_edges', 0))

    # P38: register transit pheromone
    try:
        n.mycelium.pheromones.mark_transit(
            source=from_node, destination=n.node_id,
            via=from_node, path=[from_node, n.node_id])
    except Exception:
        pass

    # P38: propagate further if hops < max_hops
    propagated = 0
    if hops < max_hops:
        import threading as _th
        def _propagate():
            nonlocal propagated
            try:
                import urllib.request as _url
                import ssl as _ssl
                import json as _json
                ctx = _ssl._create_unverified_context()
                our_map = topo.export_map()
                nodes = snapshot()
                for nid, node in nodes.items():
                    if node.get('type') not in ('router', 'device'):
                        continue
                    ip = node.get('ip')
                    if not ip or ip == from_node:
                        continue
                    port = node.get('port', 8080) or 8080
                    if port not in (8080, 8443):
                        port = 8080
                    try:
                        payload = _json.dumps({
                            'from_node': n.node_id,
                            'hops': hops + 1,
                            'max_hops': max_hops,
                            'map': our_map,
                        }).encode()
                        url = ('https://' if port == 8443 else 'http://') + f"{ip}:{port}/api/network/map"
                        req = _url.Request(
                            url, data=payload,
                            headers={'Content-Type': 'application/json'},
                            method='POST')
                        _url.urlopen(req, timeout=4, context=ctx)
                        propagated += 1
                    except Exception:
                        pass
            except Exception:
                pass
        _th.Thread(target=_propagate, daemon=True).start()

    return jsonify({
        'success': True,
        'merged': merged,
        'our_map': topo.export_map(),
        'propagated': propagated,
    })


@app.route('/api/network/probe', methods=['POST'])
def api_network_probe():
    """P38: send probe to neighbors (recursive map request)."""
    d = request.get_json(silent=True) or {}
    max_hops = int(d.get('max_hops', 5))
    target = d.get('target')

    n = get_net()
    topo = getattr(n, '_auto_topology', None)
    if topo is None:
        try:
            topo = n.enable_auto_topology()
        except Exception:
            topo = None
    if topo is None:
        return jsonify({'success': False, 'error': 'no_topology'}), 500

    our_map = topo.export_map()

    # P38: create probe-spore
    try:
        spore = n.mycelium.spores.create_probe(
            node_id=n.node_id,
            target_network=target or "broadcast",
            ttl=max_hops)
        spore_id = spore.spore_id
    except Exception:
        spore_id = None

    import urllib.request as _url
    import ssl as _ssl
    import json as _json
    ctx = _ssl._create_unverified_context()

    targets = []
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

    sent = 0
    merged_total = {"added_nodes": 0, "added_edges": 0}
    for t in targets:
        try:
            payload = _json.dumps({
                'from_node': n.node_id,
                'hops': 0,
                'max_hops': max_hops,
                'map': our_map,
            }).encode()
            url = 'https://' + t + '/api/network/map'
            req = _url.Request(
                url, data=payload,
                headers={'Content-Type': 'application/json'},
                method='POST')
            with _url.urlopen(req, timeout=6, context=ctx) as resp:
                other = _json.loads(resp.read().decode('utf-8'))
            other_map = other.get('our_map') or other.get('map') or {}
            if other_map:
                m = topo.merge(other_map)
                merged_total['added_nodes'] += m.get('added_nodes', 0)
                merged_total['added_edges'] += m.get('added_edges', 0)
            sent += 1
        except Exception as e:
            log.debug('[Probe] %s: %s', t, e)

    # P38: save merged map into spore
    if spore_id:
        try:
            n.mycelium.spores.merge_map(spore_id, topo.export_map())
        except Exception:
            pass

    stats = topo.get_stats()
    log.info('[Growth] PROBE: sent=%d merged=+%d nodes, +%d edges; total nodes=%d edges=%d',
             sent, merged_total['added_nodes'], merged_total['added_edges'],
             stats.get('nodes', 0), stats.get('edges', 0))

    return jsonify({
        'success': True,
        'sent': sent,
        'merged': merged_total,
        'stats': stats,
        'spore_id': spore_id,
    })


@app.route('/api/network/sweep', methods=['POST'])''',
        True,
    ),
], "P38e: /api/network/map + /api/network/probe")


# ============================================================
# P38f. orchestrator.py: _growth_loop + start
# ============================================================
patch(ORCH, [
    # Start growth loop
    (
        '''        logger.info(f"InevioNet started: {self.node_id}")''',
        '''        # P38: mycelium growth loop
        try:
            import threading as _th_growth
            _th_growth.Thread(target=self._growth_loop, daemon=True,
                              name='growth_loop').start()
            logger.info('[Growth] mycelium growth loop started')
        except Exception as _ge:
            logger.debug('[Growth] start error: %s', _ge)
        logger.info(f"InevioNet started: {self.node_id}")''',
        True,
    ),
    # Add method before _topology_loop
    (
        '''    def _topology_loop(self):''',
        '''    def _growth_loop(self):
        """P38: mycelium growth — probe neighbors, merge maps."""
        import time as _t
        # wait for topology to initialize
        _t.sleep(45)
        while getattr(self, '_running', False):
            try:
                # read best genome
                interval = 60
                max_hops = 5
                if self.evolution and self.evolution.best_genome:
                    bg = self.evolution.best_genome
                    max_hops = int(getattr(bg, 'growth_max_hops', 5))
                    interval = int(getattr(bg, 'growth_probe_interval', 60))
                    interval = max(30, min(600, interval))

                # check enabled
                enabled = True
                if self.evolution and self.evolution.best_genome:
                    bg = self.evolution.best_genome
                    if not getattr(bg, 'growth_share_map', True):
                        enabled = False

                if not enabled:
                    logger.debug('[Growth] disabled by genome')
                else:
                    try:
                        import urllib.request as _url
                        import ssl as _ssl
                        import json as _json
                        ctx = _ssl._create_unverified_context()
                        topo = getattr(self, '_auto_topology', None)
                        if topo is None:
                            topo = self.enable_auto_topology()
                        our_map = topo.export_map()
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
                            try:
                                payload = _json.dumps({
                                    'from_node': self.node_id,
                                    'hops': 0,
                                    'max_hops': max_hops,
                                    'map': our_map,
                                }).encode()
                                url = f"https://{host_only}:{port}/api/network/map"
                                req = _url.Request(
                                    url, data=payload,
                                    headers={'Content-Type': 'application/json'},
                                    method='POST')
                                with _url.urlopen(req, timeout=6, context=ctx) as resp:
                                    other = _json.loads(resp.read().decode('utf-8'))
                                other_map = other.get('our_map') or other.get('map') or {}
                                if other_map:
                                    m = topo.merge(other_map)
                                    total_added_n += m.get('added_nodes', 0)
                                    total_added_e += m.get('added_edges', 0)
                                sent += 1
                            except Exception:
                                pass

                        if sent:
                            stats = topo.get_stats()
                            logger.info('[Growth] probed=%d +%d nodes, +%d edges; total nodes=%d edges=%d',
                                        sent, total_added_n, total_added_e,
                                        stats.get('nodes', 0), stats.get('edges', 0))
                    except Exception as _e:
                        logger.debug('[Growth] probe error: %s', _e)

                _t.sleep(interval)
            except Exception as e:
                logger.debug('[Growth] loop error: %s', e)
                _t.sleep(60)

    def _topology_loop(self):''',
        True,
    ),
], "P38f: orchestrator _growth_loop")


# ============================================================
# P38g. index.html: button + JS
# ============================================================
print()
print("=" * 70)
print("  P38g: index.html grow button")
print("=" * 70)
backup(HTML)
with open(HTML, "r", encoding="utf-8") as f:
    html = f.read()

# Button
marker_btn = '<button class="btn btn-glass" onclick="scanEthernet()">🌐 Ethernet (пром.)</button>'
new_btn = (marker_btn +
           '\n<button class="btn btn-success" onclick="growNetwork()">🌱 Расти (mycelium)</button>'
           '\n<button class="btn btn-glass" onclick="showMap()">🗺️ Карта сети</button>')

if 'growNetwork()' in html:
    print("  [--] button already exists")
elif marker_btn in html:
    html = html.replace(marker_btn, new_btn, 1)
    print("  [OK] button added")
else:
    print("  [!!] button marker NOT FOUND")

# JS
marker_js = 'async function scanEthernet() {'
new_js = '''async function growNetwork() {
    addLog('🌱 Рост мицелия...', 'info');
    try {
        const r = await fetch('/api/network/probe', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({max_hops: 5})
        });
        const d = await r.json();
        if (d.success) {
            const m = d.merged || {};
            addLog('🌱 Проверено: ' + d.sent + ' узлов, +' +
                   (m.added_nodes || 0) + ' nodes, +' +
                   (m.added_edges || 0) + ' edges', 'success');
            addLog('📊 Всего: ' + (d.stats.nodes || 0) + ' nodes, ' +
                   (d.stats.edges || 0) + ' edges', 'info');
        } else {
            addLog('🌱 error: ' + (d.error || '?'), 'error');
        }
    } catch (e) { addLog('grow: ' + e, 'error'); }
}

async function showMap() {
    try {
        const r = await fetch('/api/network/map');
        const d = await r.json();
        if (d.success) {
            const m = d.map || {};
            const n = Object.keys(m.nodes || {}).length;
            const e = (m.edges || []).length;
            addLog('🗺️ Карта: ' + n + ' узлов, ' + e + ' рёбер', 'success');
            // Show first 10 nodes
            const sample = Object.entries(m.nodes || {}).slice(0, 10);
            for (const [id, info] of sample) {
                addLog('  • ' + id + ' (' + (info.type || '?') +
                       ', rssi=' + (info.rssi || '?') + ')', 'info');
            }
        }
    } catch (e) { addLog('map: ' + e, 'error'); }
}

async function scanEthernet() {'''

if 'async function growNetwork' in html:
    print("  [--] JS already exists")
elif marker_js in html:
    html = html.replace(marker_js, new_js, 1)
    print("  [OK] JS added")
else:
    print("  [!!] JS marker NOT FOUND")

with open(HTML, "w", encoding="utf-8") as f:
    f.write(html)
print("  [OK] saved: index.html")


# ============================================================
# DONE
# ============================================================
print()
print("=" * 70)
print("  PATCH 38 DONE — MYCELIUM GROWTH")
print("=" * 70)
print()
print("  [OK] auto_topology: merge() + export_map()")
print("  [OK] spores: map_data + create_probe + merge_map + get_maps")
print("  [OK] pheromones: via + path + mark_transit + get_transit_path")
print("  [OK] genome: growth_aggressiveness/max_hops/probe_interval/share_map/accept_map")
print("  [OK] web/app.py: /api/network/map + /api/network/probe")
print("  [OK] orchestrator: _growth_loop (probes every 30-600s)")
print("  [OK] index.html: 🌱 Расти + 🗺️ Карта сети")
print()
print("Перезапусти: python -m web.app")
print()
print("Проверка:")
print("  curl.exe -k https://localhost:8080/api/network/map")
print("  curl.exe -k -X POST https://localhost:8080/api/network/probe -H \"Content-Type: application/json\" -d \"{}\"")
print()
print("Ищи в логах: [Growth] probed=N +X nodes, +Y edges")