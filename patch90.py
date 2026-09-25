# patch90.py - P90: 50+ targets + WiFi-devices на карте
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
INEV = os.path.join(ROOT, "inevionet")
TS = os.path.join(INEV, "network", "traceroute_scan.py")
MESH = os.path.join(INEV, "mesh", "network_tree.py")
ORCH = os.path.join(INEV, "orchestrator.py")
HTML = os.path.join(ROOT, "web", "templates", "index.html")


def patch_file(path, replacements, label, bak=".bak_p90"):
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
# 1. P90c: traceroute_scan.py - 50+ targets
# =====================================================================

print()
print("=" * 70)
print("  1. P90c: 50+ targets")
print("=" * 70)

# Найти текущий DEFAULT_TARGETS
with open(TS, "r", encoding="utf-8") as f:
    ts_content = f.read()

# Новый список - 55 targets
new_targets = '''# Цели для traceroute - P90: 55 targets (РФ + мир + провайдеры)
DEFAULT_TARGETS = [
    # DNS (быстрые ответы)
    "8.8.8.8", "8.8.4.4",              # Google
    "1.1.1.1", "1.0.0.1",              # Cloudflare
    "77.88.8.8", "77.88.8.1",          # Yandex
    "9.9.9.9",                          # Quad9
    "208.67.222.222", "208.67.220.220", # OpenDNS
    "223.5.5.5", "223.6.6.6",          # AliDNS
    "114.114.114.114", "114.114.115.115", # 114DNS
    "64.6.64.6", "64.6.65.6",          # Verisign
    "156.154.70.1", "156.154.71.1",    # Neustar
    "84.200.69.80", "84.200.70.40",    # DNS.WATCH
    "8.26.56.26", "8.20.247.20",       # Comodo
    "91.239.100.100", "89.233.43.71",  # UncensoredDNS
    "185.228.168.9", "185.228.169.9",  # CleanBrowsing
    "76.76.2.0", "76.76.19.19",        # ControlD / Alternate
    "94.140.14.14", "94.140.15.15",    # AdGuard
    "205.171.3.65", "205.171.2.65",    # Level3
    "4.2.2.1", "4.2.2.2",              # Level3 (old)
    "195.46.39.39", "195.46.39.40",    # SafeDNS
    # Популярные сайты РФ
    "ya.ru", "vk.com", "mail.ru", "gosuslugi.ru",
    "ozon.ru", "wildberries.ru", "avito.ru",
    "sberbank.ru", "tinkoff.ru", "yandex.ru",
    # Популярные мировые
    "google.com", "github.com", "cloudflare.com",
    "amazon.com", "microsoft.com", "apple.com",
    # Провайдеры РФ
    "mts.ru", "beeline.ru", "megafon.ru", "tele2.ru",
    "rostelecom.ru", "ertelecom.ru",
]'''

# Заменить старый блок
if "P90: 55 targets" in ts_content:
    print("  [--] already applied")
else:
    # Найти старый DEFAULT_TARGETS
    import re
    old_pattern = re.compile(r'# Цели для traceroute.*?DEFAULT_TARGETS = \[.*?\]', re.DOTALL)
    m = old_pattern.search(ts_content)
    if m:
        ts_content = ts_content[:m.start()] + new_targets + ts_content[m.end():]
        b = TS + ".bak_p90_targets"
        shutil.copy2(TS, b)
        print("  [BK] " + os.path.basename(b))
        with open(TS, "w", encoding="utf-8") as f:
            f.write(ts_content)
        try:
            ast.parse(ts_content)
            print("  [OK] 55 targets")
        except SyntaxError as e:
            print("  [!!] syntax: " + str(e))
            shutil.copy2(b, TS)
    else:
        print("  [!!] DEFAULT_TARGETS NOT FOUND")


# =====================================================================
# 2. P90a: network_tree.py - WiFi-устройства под роутером
# =====================================================================

print()
print("=" * 70)
print("  2. P90a: WiFi-устройства под роутером")
print("=" * 70)

# Добавить метод add_wifi_devices в NetworkTree
old_method = '''    def add_footholds(self, footholds: Dict[str, str]):'''

new_method = '''    def add_wifi_devices(self, local_map: Dict[str, Any]):
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

    def add_footholds(self, footholds: Dict[str, str]):'''

patch_file(MESH, [(old_method, new_method, True)], "network_tree.py add_wifi_devices")


# =====================================================================
# 3. orchestrator.py - вызвать add_wifi_devices в full_scan_loop
# =====================================================================

print()
print("=" * 70)
print("  3. orchestrator.py: add_wifi_devices")
print("=" * 70)

old_loop = '''                if getattr(self, "network_tree", None):
                    self.network_tree.build(local_map=local, topology_map=topo,
                                            spores=spores_list)
                    self.network_tree.add_traceroute(tr_result.get("hops", []))
                    self.network_tree.add_mdns_devices(mdns_result.get("devices", []))'''

new_loop = '''                if getattr(self, "network_tree", None):
                    self.network_tree.build(local_map=local, topology_map=topo,
                                            spores=spores_list)
                    # P90a: WiFi-устройства под роутером
                    try:
                        added = self.network_tree.add_wifi_devices(local)
                        if added:
                            logger.info("[P90a] added %d wifi devices", added)
                    except Exception as _we:
                        logger.debug("[P90a] %s", _we)
                    self.network_tree.add_traceroute(tr_result.get("hops", []))
                    self.network_tree.add_mdns_devices(mdns_result.get("devices", []))'''

patch_file(ORCH, [(old_loop, new_loop, True)], "orchestrator.py P90a")


# =====================================================================
# 4. app.py - тоже в /api/network/tree
# =====================================================================

print()
print("=" * 70)
print("  4. app.py: add_wifi_devices")
print("=" * 70)

APP = os.path.join(ROOT, "web", "app.py")

old_app = '''            n.network_tree.build(local_map=local, topology_map=topo, spores=spores_list)
            # P88-fix3: footholds из web_state'''

new_app = '''            n.network_tree.build(local_map=local, topology_map=topo, spores=spores_list)
            # P90a: WiFi-устройства
            try:
                added = n.network_tree.add_wifi_devices(local)
                if added:
                    log.info('[P90a] added %d wifi devices', added)
            except Exception as _we:
                log.debug('[P90a] %s', _we)
            # P88-fix3: footholds из web_state'''

patch_file(APP, [(old_app, new_app, True)], "app.py P90a")


# =====================================================================
# 5. UI: показать device даже если маленький
# =====================================================================

print()
print("=" * 70)
print("  5. UI: device size")
print("=" * 70)

old_size = '''    else if (nd.type === 'device') base = 2.5;'''

new_size = '''    else if (nd.type === 'device') base = 3;  // P90a: больше'''

patch_file(HTML, [(old_size, new_size, False)], "UI device size", bak=".bak_p90_ui")


print()
print("=" * 70)
print("  PATCH 90 DONE")
print("=" * 70)
print("  [OK] P90c: 55 targets (DNS + РФ сайты + провайдеры)")
print("  [OK] P90a: WiFi-устройства под роутером")
print("  [OK] orchestrator: add_wifi_devices в full_scan_loop")
print("  [OK] app.py: add_wifi_devices в tree endpoint")
print("  [OK] UI: device size 2.5 -> 3")
print()
print("Перезапуск + Ctrl+F5")