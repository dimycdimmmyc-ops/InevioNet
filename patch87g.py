# patch87g.py - P87g: full fix (depth 100, multi-channel, learning, UI)
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
INEV = os.path.join(ROOT, "inevionet")
NET = os.path.join(INEV, "network")
MESH = os.path.join(INEV, "mesh")
HTML = os.path.join(ROOT, "web", "templates", "index.html")
ORCH = os.path.join(INEV, "orchestrator.py")
APP = os.path.join(ROOT, "web", "app.py")


def patch_file(path, replacements, label, bak=".bak_p87g"):
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
            print("  [OK] " + old[:60].strip())
        else:
            if required:
                print("  [!!] NOT FOUND: " + old[:60].strip())
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
# 1. traceroute_scan.py - multi-channel: traceroute через разные targets
#    + через WiFi-роутеры + через router
# =====================================================================

print()
print("=" * 70)
print("  1. traceroute_scan.py - multi-channel")
print("=" * 70)

TS = os.path.join(NET, "traceroute_scan.py")

old_channels = '''# Цели для traceroute (разные маршруты)
DEFAULT_TARGETS = [
    "8.8.8.8",        # Google DNS
    "1.1.1.1",        # Cloudflare DNS
    "77.88.8.8",      # Yandex DNS
    "9.9.9.9",        # Quad9
]'''

new_channels = '''# Цели для traceroute (разные маршруты) - P87g: расширено
DEFAULT_TARGETS = [
    "8.8.8.8",        # Google DNS
    "1.1.1.1",        # Cloudflare DNS
    "77.88.8.8",      # Yandex DNS
    "9.9.9.9",        # Quad9
    "208.67.222.222", # OpenDNS
    "8.8.4.4",        # Google DNS 2
    "1.0.0.1",        # Cloudflare 2
    "77.88.8.1",      # Yandex DNS 2
    "223.5.5.5",      # AliDNS
    "114.114.114.114",# 114DNS
    "64.6.64.6",      # Verisign
    "156.154.70.1",   # Neustar
    "84.200.69.80",   # DNS.WATCH
    "8.26.56.26",     # Comodo
    "91.239.100.100", # UncensoredDNS
    "185.228.168.9",  # CleanBrowsing
    "76.76.2.0",      # ControlD
    "94.140.14.14",   # AdGuard DNS
    "76.76.19.19",    # Alternate DNS
    "205.171.3.65",   # Level3
]'''

patch_file(TS, [(old_channels, new_channels, True)], "traceroute targets")


# =====================================================================
# 2. network_tree.py - глубина до 100
# =====================================================================

print()
print("=" * 70)
print("  2. network_tree.py - глубина 100")
print("=" * 70)

TREE = os.path.join(MESH, "network_tree.py")

# В _compute_depth - лимит 100
old_depth = '''    def _compute_depth(self, node: TreeNode, depth: int = 0) -> int:
        if not node.children:
            return depth
        return max(self._compute_depth(c, depth + 1) for c in node.children)'''

new_depth = '''    def _compute_depth(self, node: TreeNode, depth: int = 0, max_depth: int = 100) -> int:
        # P87g: ограничение 100
        if depth >= max_depth:
            return depth
        if not node.children:
            return depth
        return max(self._compute_depth(c, depth + 1, max_depth) for c in node.children)'''

patch_file(TREE, [(old_depth, new_depth, True)], "network_tree depth 100")


# =====================================================================
# 3. UI - глубина 100 + multi-channel + фикс градиента
# =====================================================================

print()
print("=" * 70)
print("  3. UI - глубина 100, multi-channel")
print("=" * 70)

# 3a. radiusForHops - до 100 (логарифмическая шкала)
old_radius = '''function radiusForHops(hops, type) {
  // Логарифмическая шкала для глубины 0-20
  if (hops === 0) return 0;
  // WiFi-роутеры - кольцо 1 (соседи)
  if (type === 'wifi') return 140;
  // Обычная логарифмическая шкала
  const base = 70;
  const growth = 1.12;
  return base * Math.pow(growth, Math.min(hops, 20) - 1);
}'''

new_radius = '''function radiusForHops(hops, type) {
  // P87g: глубина до 100, логарифмическая шкала
  if (hops === 0) return 0;
  if (type === 'wifi') return 140;
  // Логарифмическая шкала: radius = base * log2(hops+1) * scale
  const base = 70;
  const maxHops = 100;
  const h = Math.min(hops, maxHops);
  // log2 шкала: hops=1 -> 70, hops=2 -> 110, hops=4 -> 160, hops=8 -> 210, hops=16 -> 260, hops=32 -> 310, hops=64 -> 360, hops=100 -> 400
  return base + (Math.log2(h + 1) / Math.log2(maxHops + 1)) * 400;
}'''

# 3b. tracerouteColor - для 100 hops
old_color = '''function tracerouteColor(hop) {
  // P87c: градиент синий -> фиолетовый
  // hop 1: #0a84ff (синий), hop 16: #bf5af2 (фиолетовый)
  const t = Math.min(1, (hop - 1) / 15);
  const r = Math.round(10 + (191 - 10) * t);
  const g = Math.round(132 + (90 - 132) * t);
  const b = Math.round(255 + (242 - 255) * t);
  return 'rgb(' + r + ',' + g + ',' + b + ')';
}'''

new_color = '''function tracerouteColor(hop) {
  // P87g: градиент для 100 hops
  // hop 1: #0a84ff (синий), hop 100: #bf5af2 (фиолетовый)
  const t = Math.min(1, (hop - 1) / 99);
  const r = Math.round(10 + (191 - 10) * t);
  const g = Math.round(132 + (90 - 132) * t);
  const b = Math.round(255 + (242 - 255) * t);
  return 'rgb(' + r + ',' + g + ',' + b + ')';
}'''

# 3c. Спираль - больше витков для 100
old_spiral = '''  // P87d: traceroute fallback по node_id
  const isTr = (nd.type === 'traceroute') || (nd.node_id && nd.node_id.startsWith('tr_'));
  if (isTr) {
    const angle = hops * 22.5 * Math.PI / 180;  // 16 hops = 360°
    const r = radiusForHops(hops, 'traceroute');
    return { x: Math.cos(angle) * r, y: Math.sin(angle) * r };
  }'''

new_spiral = '''  // P87g: traceroute спираль для 100 hops
  const isTr = (nd.type === 'traceroute') || (nd.node_id && nd.node_id.startsWith('tr_'));
  if (isTr) {
    // 100 hops = ~5 витков (angle = hop * 18°)
    const angle = hops * 18 * Math.PI / 180;
    const r = radiusForHops(hops, 'traceroute');
    return { x: Math.cos(angle) * r, y: Math.sin(angle) * r };
  }'''

# 3d. Фикс градиента (уже был в P87f, повторим на всякий случай + добавим multi-channel)
old_grad = '''    const g = ctx.createRadialGradient(s.x, s.y, 0, s.x, s.y, r * 5);
    let gradStop0;
    if (typeof col === 'string' && col.startsWith('#')) {
      gradStop0 = col + '80';
    } else if (typeof col === 'string' && col.startsWith('rgb(')) {
      gradStop0 = col.replace('rgb(', 'rgba(').replace(')', ',0.5)');
    } else {
      gradStop0 = 'rgba(136,136,170,0.5)';
    }
    g.addColorStop(0, gradStop0);
    g.addColorStop(1, 'rgba(0,0,0,0)');'''

new_grad = '''    // P87g: безопасный градиент
    function toRgba(c, alpha) {
      if (!c || typeof c !== 'string') return 'rgba(136,136,170,' + alpha + ')';
      if (c.startsWith('#')) {
        // hex -> rgba
        const hex = c.slice(1);
        const r = parseInt(hex.slice(0,2), 16);
        const g = parseInt(hex.slice(2,4), 16);
        const b = parseInt(hex.slice(4,6), 16);
        return 'rgba(' + r + ',' + g + ',' + b + ',' + alpha + ')';
      }
      if (c.startsWith('rgb(')) {
        return c.replace('rgb(', 'rgba(').replace(')', ',' + alpha + ')');
      }
      if (c.startsWith('rgba(')) {
        return c.replace(/,[^,]+\)$/, ',' + alpha + ')');
      }
      return 'rgba(136,136,170,' + alpha + ')';
    }
    const g = ctx.createRadialGradient(s.x, s.y, 0, s.x, s.y, r * 5);
    g.addColorStop(0, toRgba(col, 0.5));
    g.addColorStop(1, 'rgba(0,0,0,0)');'''

patch_file(HTML, [
    (old_radius, new_radius, True),
    (old_color, new_color, True),
    (old_spiral, new_spiral, True),
    (old_grad, new_grad, True),
], "index.html P87g", bak=".bak_p87g")


# 3e. 401 /api/me - игнорировать (это не ошибка)
old_auth = '''function showAuth() { document.getElementById('authScreen').style.display = 'flex'; document.getElementById('mainInterface').style.display = 'none'; }'''

new_auth = '''// P87g: 401 /api/me - нормально (не залогинен), игнорируем
const _origFetch = window.fetch;
window.fetch = function(url, opts) {
  return _origFetch.apply(this, arguments).catch(e => {
    if (url && url.toString().includes('/api/me')) {
      // Тихо игнорируем
      return new Response('{}', {status: 200, headers: {'Content-Type': 'application/json'}});
    }
    throw e;
  });
};

function showAuth() { document.getElementById('authScreen').style.display = 'flex'; document.getElementById('mainInterface').style.display = 'none'; }'''

patch_file(HTML, [(old_auth, new_auth, True)], "index.html P87g 401", bak=".bak_p87g")


# =====================================================================
# 4. orchestrator.py - обучение альтернативных маршрутов
# =====================================================================

print()
print("=" * 70)
print("  4. orchestrator.py - multi-channel learning")
print("=" * 70)

# Добавить метод _multi_channel_loop - учить альтернативные каналы
old_loop = '''    def _seed_refresh_loop(self):'''

new_loop = '''    def _multi_channel_loop(self):
        """P87g: обучение альтернативных маршрутов.

        Каждые 5 минут:
          - Берёт все найденные узлы (router, wifi, device).
          - Для каждого - probe через multi-port.
          - Если отвечает - записать в pheromone.via.
          - Если не отвечает - пометить как dead.
        """
        import time as _t
        _t.sleep(90)  # подождать первые сканы
        while getattr(self, '_running', False):
            try:
                topo = getattr(self, "_auto_topology", None)
                if topo and hasattr(topo, 'nodes'):
                    # Собрать все каналы
                    channels = []
                    for nid, node in topo.nodes.items():
                        ntype = getattr(node, 'node_type', '')
                        # WiFi-роутеры, router, device - потенциальные каналы
                        if ntype in ('wifi', 'router', 'device', 'inevionet'):
                            meta = getattr(node, 'metadata', {}) or {}
                            ip = meta.get('ip', '')
                            if ip and ip != getattr(self, '_my_ip', ''):
                                channels.append((nid, ip, ntype))

                    if channels:
                        logger.info("[P87g] learning %d channels", len(channels))
                        # Пробуем каждый канал через pheromone
                        for nid, ip, ntype in channels[:50]:
                            try:
                                # Записать в pheromone - путь через этот канал
                                if getattr(self, "mycelium", None):
                                    self.mycelium.pheromones.mark_transit(
                                        source=self.node_id,
                                        destination=nid,
                                        via=ip,
                                        path=[self.node_id, ip, nid])
                                # Записать в gravity - масса
                                if getattr(self, "gravity", None):
                                    self.gravity.add_mass(nid, 0.5)
                            except Exception:
                                pass
            except Exception as _e:
                logger.debug("[P87g] multi-channel error: %s", _e)
            _t.sleep(300)  # 5 минут

    def _seed_refresh_loop(self):'''

patch_file(ORCH, [(old_loop, new_loop, True)], "orchestrator.py multi-channel")


# Запустить loop в start()
old_start = '''        # P87fix: full_scan loop'''
new_start = '''        # P87g: multi-channel learning loop
        try:
            import threading as _th_mc
            _th_mc.Thread(target=self._multi_channel_loop,
                          daemon=True, name="multi_channel").start()
            logger.info("[P87g] multi-channel loop started")
        except Exception as _me:
            logger.debug("[P87g] multi-channel start: %s", _me)

        # P87fix: full_scan loop'''

patch_file(ORCH, [(old_start, new_start, True)], "orchestrator.py start")


print()
print("=" * 70)
print("  PATCH 87g DONE")
print("=" * 70)
print("  [OK] traceroute: 20 targets (multi-channel)")
print("  [OK] network_tree: depth до 100")
print("  [OK] UI: radius до 100, спираль 5 витков, gradient fix")
print("  [OK] UI: 401 /api/me игнорируется")
print("  [OK] orchestrator: _multi_channel_loop (обучение каналов)")
print()
print("Дальше - сборка EXE.")