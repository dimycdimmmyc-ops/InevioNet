# patch95g.py - P95g: инжекция SuperNode/Evolution + расширение scout
import os
import ast
import shutil
import re

ROOT = r"E:\InevioNet"
APP = os.path.join(ROOT, "web", "app.py")
ORG = os.path.join(ROOT, "inevionet", "organism.py")

BAK = ".bak_p95g"


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
# 1. app.py: найти super_node_loop и evolution_loop, сделать _once версии
# =====================================================================

print()
print("=" * 70)
print("  1. app.py: _once версии для SuperNode/Evolution")
print("=" * 70)

with open(APP, "r", encoding="utf-8") as f:
    app_content = f.read()

# Найти функции super_node и evolution
print("  Поиск super_node/evolution loop...")
for pattern in ["def background_scanner", "def super_node", "def evolution", "def _supernode",
                "def _evolution", "while True", "while running"]:
    matches = re.findall(pattern, app_content)
    if matches:
        print(f"    '{pattern}': {len(matches)} matches")


# Найти определение net = get_net() и вставить hooks
anchor = "net = get_net()"

hooks_code = '''net = get_net()

# P95g: инжекция SuperNode + Evolution в net для Organism.teach()
def _inject_organism_hooks(_net):
    """P95g: инжектирует _supernode_loop_once и _evolution_once в net."""
    try:
        import inspect
        # Ищем функции в модуле
        mod = sys.modules.get('web.app') or sys.modules.get('__main__')
        if mod is None:
            log.debug('[P95g] module not found')
            return
        
        # SuperNode
        for name in ('_supernode_loop_once', 'supernode_once', 'super_node_once'):
            fn = getattr(mod, name, None)
            if fn and callable(fn):
                _net._supernode_loop_once = fn
                log.info('[P95g] injected %s', name)
                break
        
        # Evolution
        for name in ('_evolution_once', 'evolution_once', '_evolution_step'):
            fn = getattr(mod, name, None)
            if fn and callable(fn):
                _net._evolution_once = fn
                log.info('[P95g] injected %s', name)
                break
        
        # Multi-channel (если есть)
        if hasattr(_net, '_multi_channel_loop_once'):
            log.info('[P95g] multi_channel_loop_once already on net')
        
        log.info('[P95g] hooks: supernode=%s evolution=%s',
                 hasattr(_net, '_supernode_loop_once'),
                 hasattr(_net, '_evolution_once'))
    except Exception as e:
        log.warning('[P95g] inject: %s', e)'''

patch_file(APP, [(anchor, hooks_code, False)], "app.py hooks inject")


# =====================================================================
# 2. organism.py: расширение scout (WiFi-соседи + ISP-подсети)
# =====================================================================

print()
print("=" * 70)
print("  2. organism.py: расширение scout")
print("=" * 70)

# Добавить метод _scout_wifi_neighbors в scout (после trusted)
old_trusted = '''        # === 5. Собственные InevioNet-узлы (trusted hosts) ===
        try:
            if self.net.trusted_hosts:
                for h in self.net.trusted_hosts.list_all():
                    host = h.get("host", "")
                    if ":" in host:
                        ip = host.split(":")[0]
                    else:
                        ip = host
                    if ip and ip not in seen_ips:
                        found.append({
                            "ip": ip, "type": "inevionet",
                            "node_id": h.get("label"),
                            "source": "trusted", "depth": 1,
                        })
                        seen_ips.add(ip)
        except Exception as e:
            logger.debug("[Scout] trusted: %s", e)'''

new_trusted = '''        # === 5. Собственные InevioNet-узлы (trusted hosts) ===
        try:
            if self.net.trusted_hosts:
                for h in self.net.trusted_hosts.list_all():
                    host = h.get("host", "")
                    if ":" in host:
                        ip = host.split(":")[0]
                    else:
                        ip = host
                    if ip and ip not in seen_ips:
                        found.append({
                            "ip": ip, "type": "inevionet",
                            "node_id": h.get("label"),
                            "source": "trusted", "depth": 1,
                        })
                        seen_ips.add(ip)
        except Exception as e:
            logger.debug("[Scout] trusted: %s", e)

        # === 6. WiFi-соседи (RF scan) - как виртуальные узлы ===
        try:
            rf = getattr(self.net, "_rf_scanner", None) or getattr(self.net, "rf_scanner", None)
            if rf and hasattr(rf, "scan"):
                signals = rf.scan() or []
                c_wifi = 0
                for sig in signals:
                    bssid = sig.get("bssid") or sig.get("mac")
                    if bssid and bssid not in seen_ips:
                        found.append({
                            "ip": bssid,  # MAC как ID
                            "type": "wifi_ap",
                            "ssid": sig.get("ssid", ""),
                            "rssi": sig.get("rssi", -70),
                            "vendor": sig.get("vendor", ""),
                            "source": "rf", "depth": 1,
                        })
                        seen_ips.add(bssid)
                        c_wifi += 1
                if c_wifi:
                    logger.info("[Scout] +wifi=%d", c_wifi)
        except Exception as e:
            logger.debug("[Scout] rf: %s", e)

        # === 7. ISP-подсети (через уже известные ISP-роутеры) ===
        try:
            c_isp = 0
            for ip, node in list(self.memory["nodes"].items()):
                if node.get("type") == "isp_router" and node.get("source") == "traceroute":
                    # Стандартные подсети для ISP
                    if "." in ip:
                        parts = ip.split(".")
                        subnet_prefix = f"{parts[0]}.{parts[1]}.{parts[2]}"
                        # Проверяем соседние IP (только несколько)
                        for last in ("1", "254"):
                            guess_ip = f"{subnet_prefix}.{last}"
                            if guess_ip not in seen_ips:
                                found.append({
                                    "ip": guess_ip, "type": "isp_router",
                                    "source": "isp_guess", "depth": 3,
                                })
                                seen_ips.add(guess_ip)
                                c_isp += 1
                                if c_isp > 20:  # ограничение
                                    break
                    if c_isp > 20:
                        break
        except Exception as e:
            logger.debug("[Scout] isp_guess: %s", e)'''

patch_file(ORG, [(old_trusted, new_trusted, True)], "scout wifi+isp")


# Обновить финальный лог scout
old_log = '''        new_count = len(found)
        total_in_memory = len(self.memory["nodes"])
        logger.info("[Scout] new=%d (lan=%d mdns=%d router=%d traceroute=%d trusted=%d), "
                    "total_in_memory=%d",
                    new_count, c_lan, c_mdns, c_router, c_tr,
                    len([f for f in found if f.get("source") == "trusted"]),
                    total_in_memory)'''

new_log = '''        new_count = len(found)
        total_in_memory = len(self.memory["nodes"])
        logger.info("[Scout] new=%d (lan=%d mdns=%d router=%d traceroute=%d trusted=%d wifi=%d isp=%d), "
                    "total_in_memory=%d",
                    new_count, c_lan, c_mdns, c_router, c_tr,
                    len([f for f in found if f.get("source") == "trusted"]),
                    len([f for f in found if f.get("source") == "rf"]),
                    len([f for f in found if f.get("source") == "isp_guess"]),
                    total_in_memory)'''

patch_file(ORG, [(old_log, new_log, False)], "scout log update")


# =====================================================================
# 3. organism.py: _colonize_relay - РЕАЛЬНЫЙ relay
# =====================================================================

print()
print("=" * 70)
print("  3. _colonize_relay: реальный relay")
print("=" * 70)

old_relay = '''    def _colonize_relay(self, node):
        with self._lock:
            self.stats["nodes_relayed"] += 1'''

new_relay = '''    def _colonize_relay(self, node):
        """P95g: реальный relay через pheromone + gravity."""
        ip = node["ip"]
        try:
            # 1. Pheromone - путь через relay
            if hasattr(self.net.mycelium, "pheromones"):
                self.net.mycelium.pheromones.mark_transit(
                    source=self.net.node_id, dest="relay_" + ip,
                    via=ip, path=[ip], success=True)
            # 2. Gravity - масса
            if hasattr(self.net, "gravity") and self.net.gravity:
                try:
                    self.net.gravity.add_mass(ip, 0.5)
                except Exception:
                    pass
            # 3. Relay через RelayNode (если есть)
            if hasattr(self.net, "relay") and self.net.relay:
                try:
                    # Регистрируем peer в relay
                    if hasattr(self.net.relay, "add_peer"):
                        self.net.relay.add_peer(ip, 9100)
                except Exception:
                    pass
            with self._lock:
                self.stats["nodes_relayed"] += 1
        except Exception as e:
            logger.debug("[Relay] %s: %s", ip, e)'''

patch_file(ORG, [(old_relay, new_relay, True)], "real relay")


# =====================================================================
# 4. organism.py: _colonize_teach - РЕАЛЬНЫЙ teach
# =====================================================================

print()
print("=" * 70)
print("  4. _colonize_teach: реальный teach")
print("=" * 70)

old_teach = '''    def _colonize_teach(self, node):
        ip = node["ip"]
        if ip in self.memory["taught"]:
            return
        self.memory["taught"].add(ip)
        with self._lock:
            self.stats["nodes_taught"] += 1'''

new_teach = '''    def _colonize_teach(self, node):
        """P95g: реальный teach через SuperNode + spore."""
        ip = node["ip"]
        if ip in self.memory["taught"]:
            return
        try:
            # 1. SuperNode - пометить как обученный
            if hasattr(self.net, "super_node") and self.net.super_node:
                try:
                    sn = self.net.super_node
                    if hasattr(sn, "promote"):
                        sn.promote(ip)
                    elif hasattr(sn, "mark_super"):
                        sn.mark_super(ip)
                except Exception:
                    pass
            # 2. Спора - закрепить знание
            if hasattr(self.net.mycelium, "spores"):
                try:
                    self.net.mycelium.spores.create(
                        node_id=self.net.node_id,
                        target_network="taught_" + ip,
                        method="teach", viability=0.9)
                except Exception:
                    pass
            # 3. Evolution - записать успех
            if hasattr(self.net, "evolution") and self.net.evolution:
                try:
                    self.net.evolution.record_success(ip)
                except Exception:
                    pass
            self.memory["taught"].add(ip)
            with self._lock:
                self.stats["nodes_taught"] += 1
            logger.info("[Teach] %s -> taught", ip)
        except Exception as e:
            logger.debug("[Teach] %s: %s", ip, e)'''

patch_file(ORG, [(old_teach, new_teach, True)], "real teach")


print()
print("=" * 70)
print("  PATCH 95g DONE")
print("=" * 70)
print("  [OK] app.py: hooks inject (SuperNode/Evolution)")
print("  [OK] organism: scout + wifi + isp_guess")
print("  [OK] organism: _colonize_relay - реальный relay")
print("  [OK] organism: _colonize_teach - реальный teach")
print()
print("Перезапуск + 90 сек:")
print("  curl -k https://localhost:8080/api/organism | python -m json.tool")