# patch71_75.py - InevioNet: P71-P75
#
# P71: Hole punching (/api/network/punch, auto-punch при sprout)
# P72: Gravity в _try_relay_chain
# P73: Pheromone через Gravity
# P74: Auto-refresh Seed (каждые 50 мин)
# P75: Multi-service Sprout (несколько fetcher-ов)

import os
import ast
import shutil

ROOT = r"E:\InevioNet"
INEV = os.path.join(ROOT, "inevionet")
ORCH = os.path.join(INEV, "orchestrator.py")
APP = os.path.join(ROOT, "web", "app.py")
SPROUT = os.path.join(INEV, "bootstrap", "sprout.py")
SEED = os.path.join(INEV, "bootstrap", "seed.py")


def patch_file(path, replacements, label):
    if not os.path.exists(path):
        print("  [!!] NOT FOUND: " + path)
        return False
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    b = path + ".bak_p71_75"
    shutil.copy2(path, b)
    print("  [BK] " + os.path.basename(b))
    changed = 0
    for old, new, required in replacements:
        if new in content and old not in content:
            print("  [--] already applied: " + old[:40].strip())
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
# P71: Hole punching endpoint + auto-punch
# =====================================================================

print()
print("=" * 70)
print("  P71: Hole punching")
print("=" * 70)

# P71a: app.py - endpoint /api/network/punch
anchor_app_p71 = "@app.route('/api/bootstrap/status')"

repl_app_p71 = '''@app.route('/api/network/punch', methods=['POST'])
def api_network_punch():
    """P71: запустить UDP hole punching к peer."""
    try:
        n = get_net()
        d = request.get_json(silent=True) or {}
        peer_node = d.get('peer', '')
        peer_host = d.get('host', '')
        peer_port = int(d.get('port', 0))

        if not peer_host or not peer_port:
            # Попробовать найти в trusted_hosts по node_id
            if peer_node:
                for h in n.trusted_hosts.list_all():
                    if h.get('label') == peer_node:
                        host_str = h.get('host', '')
                        if ':' in host_str:
                            peer_host, port_s = host_str.rsplit(':', 1)
                            peer_port = int(port_s)
                        else:
                            peer_host = host_str
                            peer_port = 0
                        break

        if not peer_host or not peer_port:
            return jsonify({'success': False, 'error': 'no_peer_addr'})

        from inevionet.network.udp import UDPHolePuncher
        p = UDPHolePuncher()
        addr = p.discover_public()
        result = p.punch_bidirectional(
            (peer_host, peer_port), attempts=20, interval=0.25)
        p.close()

        if result:
            try:
                n.gravity.add_mass(peer_node or peer_host, 1.0)
            except Exception:
                pass
            return jsonify({'success': True, 'punched': True,
                            'peer': peer_node or peer_host,
                            'public_addr': list(addr or [])})
        return jsonify({'success': True, 'punched': False,
                        'peer': peer_node or peer_host,
                        'public_addr': list(addr or [])})
    except Exception as e:
        log.error('[Punch] error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/bootstrap/status')'''

patch_file(APP, [(anchor_app_p71, repl_app_p71, True)], "app.py P71a")


# P71b: sprout.py - auto-punch после sprout
anchor_sprout_p71 = '''        logger.info("[Sprout] sprouted %s at %s (nat=%s)",
                    seed.node_id, host, seed.nat_type)
        return True'''

repl_sprout_p71 = '''        logger.info("[Sprout] sprouted %s at %s (nat=%s)",
                    seed.node_id, host, seed.nat_type)

        # P71b: auto-punch в фоне
        try:
            import threading as _th
            def _auto_punch():
                try:
                    from ..network.udp import UDPHolePuncher
                    p = UDPHolePuncher()
                    p.discover_public()
                    result = p.punch_bidirectional(
                        (seed.public_ip, seed.public_port),
                        attempts=20, interval=0.25)
                    p.close()
                    if result:
                        logger.info("[Sprout] auto-punched %s", seed.node_id)
                        try:
                            self.orch.gravity.add_mass(seed.node_id, 1.0)
                        except Exception:
                            pass
                except Exception as _pe:
                    logger.debug("[Sprout] auto-punch: %s", _pe)
            _th.Thread(target=_auto_punch, daemon=True,
                       name="sprout_punch").start()
        except Exception as _e:
            logger.debug("[Sprout] auto-punch thread: %s", _e)

        return True'''

patch_file(SPROUT, [(anchor_sprout_p71, repl_sprout_p71, True)], "sprout.py P71b")


# =====================================================================
# P72: Gravity в _try_relay_chain
# =====================================================================

print()
print("=" * 70)
print("  P72: Gravity в _try_relay_chain")
print("=" * 70)

anchor_orch_p72 = '''            path = None
            if hasattr(topo, 'shortest_path'):
                path = topo.shortest_path(self.node_id, receiver)
            if not path or len(path) < 2:
                return False, None'''

repl_orch_p72 = '''            path = None

            # P72: сначала Gravity, потом Dijkstra
            if getattr(self, "gravity", None) is not None:
                try:
                    from .mesh.gravity import GravityRouter
                    router = GravityRouter(self.gravity, topo)
                    gpath = router.route(self.node_id, receiver)
                    if gpath and len(gpath) >= 2:
                        path = gpath
                        logger.debug('[Gravity] route: %s', gpath)
                except Exception as _ge:
                    logger.debug('[Gravity] route error: %s', _ge)

            if not path and hasattr(topo, 'shortest_path'):
                path = topo.shortest_path(self.node_id, receiver)

            if not path or len(path) < 2:
                return False, None'''

patch_file(ORCH, [(anchor_orch_p72, repl_orch_p72, True)], "orchestrator.py P72")


# =====================================================================
# P73: Pheromone через Gravity (mark_transit + add_mass)
# =====================================================================

print()
print("=" * 70)
print("  P73: Pheromone через Gravity")
print("=" * 70)

anchor_app_p73 = '''    merged = topo.merge(other_map, via_node_id=from_node)
    log.info('[Growth] merged map from %s via=%s (+%d nodes, +%d edges)',
             from_node, from_node, merged.get('added_nodes', 0),
             merged.get('added_edges', 0))'''

repl_app_p73 = '''    merged = topo.merge(other_map, via_node_id=from_node)
    log.info('[Growth] merged map from %s via=%s (+%d nodes, +%d edges)',
             from_node, from_node, merged.get('added_nodes', 0),
             merged.get('added_edges', 0))

    # P73: обновить gravity - from_node имеет массу
    try:
        if getattr(n, "gravity", None):
            n.gravity.add_mass(from_node, 1.0)
            # рёбра от from_node ко всем новым узлам
            for nid in other_map.get("nodes", {}).keys():
                if nid != from_node:
                    n.gravity.set_edge(from_node, nid, 0.7)
    except Exception as _ge:
        log.debug('[P73] gravity update: %s', _ge)'''

patch_file(APP, [(anchor_app_p73, repl_app_p73, True)], "app.py P73")


# =====================================================================
# P74: Auto-refresh Seed (каждые 50 мин)
# =====================================================================

print()
print("=" * 70)
print("  P74: Auto-refresh Seed")
print("=" * 70)

# P74a: orchestrator - новый loop
anchor_orch_p74 = '''    def _topology_loop(self):'''

repl_orch_p74 = '''    def _seed_refresh_loop(self):
        """P74: обновлять Seed каждые 50 минут."""
        import time as _t
        _t.sleep(300)  # подождать старт и первый STUN
        while getattr(self, '_running', False):
            try:
                if getattr(self, "public_addr", None):
                    from .bootstrap import Seed, SeedPublisher
                    seed = Seed(
                        node_id=self.node_id,
                        public_ip=self.public_addr[0],
                        public_port=self.public_addr[1],
                        nat_type=getattr(self, "nat_type", "unknown"),
                        ttl_sec=3600,
                    )
                    seed.sign()
                    pub = SeedPublisher()
                    url = pub.publish(seed)
                    if url:
                        self.seed = seed
                        self.seed_url = url
                        logger.info("[P74] seed refreshed: %s", url)
                    else:
                        logger.debug("[P74] seed publish failed")
            except Exception as _e:
                logger.debug("[P74] refresh error: %s", _e)
            _t.sleep(3000)  # 50 минут

    def _topology_loop(self):'''

# P74b: start() - запустить loop
anchor_start_p74 = '''        # P70f: запуск SproutEngine'''

repl_start_p74 = '''        # P74: seed refresh loop
        try:
            import threading as _th_seed
            _th_seed.Thread(target=self._seed_refresh_loop,
                            daemon=True, name="seed_refresh").start()
            logger.info("[P74] seed refresh loop started")
        except Exception as _se:
            logger.debug("[P74] seed refresh start: %s", _se)

        # P70f: запуск SproutEngine'''

# P74c: __init__ - self.seed_url
anchor_init_p74 = '''        self.seed = None
        self.sprout = None
        self.gravity = None'''

repl_init_p74 = '''        self.seed = None
        self.seed_url = None
        self.sprout = None
        self.gravity = None'''

patch_file(ORCH, [
    (anchor_init_p74, repl_init_p74, True),
    (anchor_orch_p74, repl_orch_p74, True),
    (anchor_start_p74, repl_start_p74, True),
], "orchestrator.py P74")


# =====================================================================
# P75: Multi-service Sprout
# =====================================================================

print()
print("=" * 70)
print("  P75: Multi-service Sprout")
print("=" * 70)

# P75a: seed.py - fetch_all_known_services
anchor_seed_p75 = '''    def fetch_from_transfer(self, url: str) -> Optional[Seed]:
        # transfer.sh отдаёт файл по прямому URL
        return self.fetch(url)'''

repl_seed_p75 = '''    def fetch_from_transfer(self, url: str) -> Optional[Seed]:
        # transfer.sh отдаёт файл по прямому URL
        return self.fetch(url)

    def fetch_multi(self, urls: List[str]) -> Optional[Seed]:
        """P75: попробовать несколько URL, вернуть первый валидный."""
        for url in urls:
            seed = self.fetch(url)
            if seed:
                return seed
        return None

    def guess_urls_from_text(self, text: str) -> List[str]:
        """P75: вытащить все URL из текста (для Telegram)."""
        import re
        urls = re.findall(r'https?://[^\\s]+', text)
        return urls'''

patch_file(SEED, [(anchor_seed_p75, repl_seed_p75, True)], "seed.py P75a")


# P75b: sprout.py - add_urls_multi
anchor_sprout_p75 = '''    def add_url(self, url: str):
        if url and url not in self._pending_urls:
            self._pending_urls.append(url)
            logger.info("[Sprout] queued url: %s", url)'''

repl_sprout_p75 = '''    def add_url(self, url: str):
        if url and url not in self._pending_urls:
            self._pending_urls.append(url)
            logger.info("[Sprout] queued url: %s", url)

    def add_urls_multi(self, text_or_urls):
        """P75: добавить несколько URL (из текста или списка)."""
        from .seed import SeedFetcher
        if isinstance(text_or_urls, str):
            urls = SeedFetcher().guess_urls_from_text(text_or_urls)
            if not urls and text_or_urls.startswith("http"):
                urls = [text_or_urls]
        else:
            urls = list(text_or_urls)
        for u in urls:
            self.add_url(u)
        return len(urls)'''

patch_file(SPROUT, [(anchor_sprout_p75, repl_sprout_p75, True)], "sprout.py P75b")


# P75c: app.py - /api/bootstrap/sprout принимает "texts" (список)
anchor_app_p75 = '''        url = d.get('url', '')
        text = d.get('text', '')
        if url:
            n.sprout.add_url(url)
            return jsonify({'success': True, 'action': 'queued_url'})'''

repl_app_p75 = '''        url = d.get('url', '')
        text = d.get('text', '')
        texts = d.get('texts', [])  # P75: список
        if texts:
            cnt = n.sprout.add_urls_multi(texts)
            return jsonify({'success': True, 'action': 'queued_urls',
                            'count': cnt})
        if url:
            if url.startswith("http") and ("\\n" in url or " " in url):
                cnt = n.sprout.add_urls_multi(url)
                return jsonify({'success': True, 'action': 'queued_urls',
                                'count': cnt})
            n.sprout.add_url(url)
            return jsonify({'success': True, 'action': 'queued_url'})'''

patch_file(APP, [(anchor_app_p75, repl_app_p75, True)], "app.py P75c")


# =====================================================================
# Дополнительный endpoint: /api/network/punch/status
# =====================================================================

print()
print("=" * 70)
print("  Доп: /api/network/punch/status")
print("=" * 70)

anchor_app_punch_status = "@app.route('/api/network/public')"

repl_app_punch_status = '''@app.route('/api/network/punch/status')
def api_network_punch_status():
    """P71: статистика punch."""
    try:
        n = get_net()
        gravity_stats = {}
        if getattr(n, "gravity", None):
            gravity_stats = n.gravity.get_stats()
        return jsonify({
            'success': True,
            'gravity': gravity_stats,
            'public_addr': list(getattr(n, "public_addr", None) or []),
            'nat_type': getattr(n, "nat_type", "unknown"),
            'relay_port': int(os.environ.get('INEVIO_RELAY_PORT', 0)),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/network/public')'''

patch_file(APP, [(anchor_app_punch_status, repl_app_punch_status, True)],
           "app.py punch status")


# =====================================================================
# Итог
# =====================================================================

print()
print("=" * 70)
print("  PATCH 71-75 DONE")
print("=" * 70)
print("  [OK] P71: /api/network/punch + auto-punch в sprout")
print("  [OK] P72: Gravity в _try_relay_chain")
print("  [OK] P73: Pheromone через Gravity (add_mass на merge)")
print("  [OK] P74: Auto-refresh Seed каждые 50 мин")
print("  [OK] P75: Multi-service Sprout (texts/urls)")
print()
print("  Доп: /api/network/punch/status")
print()
print("Проверка после перезапуска:")
print("  curl -k https://localhost:8080/api/network/punch/status")
print("  curl -k -X POST https://localhost:8080/api/network/punch -d '{\"peer\":\"web_node_XXXX\"}'")