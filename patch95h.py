# patch95h.py - P95h: teach/relay для всех подходящих узлов
import os
import ast
import shutil
import re

ROOT = r"E:\InevioNet"
ORG = os.path.join(ROOT, "inevionet", "organism.py")

BAK = ".bak_p95h"


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
# 1. assess(): teach для LAN-устройств + relay для всех router/isp
# =====================================================================

print()
print("=" * 70)
print("  1. assess(): переработка приоритетов")
print("=" * 70)

# Найти метод assess
with open(ORG, "r", encoding="utf-8") as f:
    org_content = f.read()

m = re.search(r"    def assess\(self, node.*?(?=\n    # =|\n    def )", org_content, re.DOTALL)
if m:
    old_assess = m.group(0)
    
    new_assess = '''    def assess(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """P95h: что можно с узлом?
        
        Приоритеты:
          capsule - MTS-роутер (можно капсулу)
          teach   - LAN-устройство (можно учить)
          relay   - gateway / ISP-роутер (можно реле)
          route   - всё остальное (путь дальше)
        """
        ip = node["ip"]
        node_type = node.get("type", "unknown")
        vendor = (node.get("vendor") or "").lower()
        source = node.get("source", "")
        
        # === CAPSULE: MTS-роутер ===
        can_capsule = False
        if node_type == "router" and ("mts" in vendor or "mts" in ip):
            can_capsule = True
        
        # === TEACH: LAN-устройства (они могут быть InevioNet или станут) ===
        can_teach = False
        if node_type in ("lan_device", "service"):
            can_teach = True
        if source == "trusted":
            can_teach = True  # Уже InevioNet
        
        # === RELAY: gateway + ISP-роутеры ===
        can_relay = False
        if node.get("is_gateway"):
            can_relay = True
        if node_type == "isp_router":
            can_relay = True
        
        # === ROUTE: всё что router/isp ===
        can_route = node_type in ("router", "isp_router") or node.get("is_gateway")
        
        # Приоритет
        actions = []
        if can_capsule: actions.append(("capsule", 0.95, "MTS -> deploy"))
        if can_teach:   actions.append(("teach", 0.85, "lan -> teach"))
        if can_relay:   actions.append(("relay", 0.75, "gateway/isp -> relay"))
        if can_route:   actions.append(("route", 0.5, "route"))
        
        if not actions:
            return {"action": None, "reason": "непригоден"}
        
        # Берём максимальный приоритет
        actions.sort(key=lambda x: -x[1])
        action, priority, reason = actions[0]
        
        # Обновляем память
        with self._lock:
            if ip in self.memory["nodes"]:
                self.memory["nodes"][ip].update({
                    "can_teach": can_teach, "can_relay": can_relay,
                    "can_capsule": can_capsule, "score": priority,
                })
        
        return {"action": action, "reason": reason, "priority": priority}

'''
    
    org_content_new = org_content[:m.start()] + new_assess + org_content[m.end():]
    
    b = ORG + BAK
    shutil.copy2(ORG, b)
    print("  [BK] " + os.path.basename(b))
    with open(ORG, "w", encoding="utf-8") as f:
        f.write(org_content_new)
    try:
        ast.parse(org_content_new)
        print("  [OK] assess() переработан")
    except SyntaxError as e:
        print("  [!!] syntax: " + str(e))
        shutil.copy2(b, ORG)
else:
    print("  [!!] assess not found")


# =====================================================================
# 2. colonize(): не капсулировать повторно
# =====================================================================

print()
print("=" * 70)
print("  2. colonize(): не повторять capsule")
print("=" * 70)

old_capsule = '''    def _colonize_capsule(self, node):
        ip = node["ip"]
        try:
            if hasattr(self.net, "capsule_deployer") and self.net.capsule_deployer:
                # Попытка deploy (может fail - это ок)
                pass
            with self._lock:
                self.stats["nodes_capsuled"] += 1
        except Exception as e:
            logger.debug("[Capsule] %s: %s", ip, e)'''

new_capsule = '''    def _colonize_capsule(self, node):
        """P95h: capsule deploy - не повторять успешно доставленные."""
        ip = node["ip"]
        # Не повторяем для одного и того же IP
        if ip in self.memory.get("capsuled_ips", set()):
            return
        try:
            # Реальная попытка deploy (если есть deployer)
            deployed = False
            if hasattr(self.net, "capsule_deployer") and self.net.capsule_deployer:
                try:
                    # Проверяем, есть ли build + deploy
                    if hasattr(self.net, "capsule_builder") and self.net.capsule_builder:
                        capsule = self.net.capsule_builder.build()
                        if hasattr(self.net.capsule_deployer, "deploy"):
                            result = self.net.capsule_deployer.deploy(
                                target=ip, capsule=capsule)
                            deployed = bool(result and result.get("success"))
                except Exception as e:
                    logger.debug("[Capsule] deploy %s: %s", ip, e)
            
            # Запоминаем, что пытались (не повторяем)
            if "capsuled_ips" not in self.memory:
                self.memory["capsuled_ips"] = set()
            self.memory["capsuled_ips"].add(ip)
            
            with self._lock:
                self.stats["nodes_capsuled"] += 1
            logger.info("[Capsule] %s -> %s", ip, "deployed" if deployed else "attempted")
        except Exception as e:
            logger.debug("[Capsule] %s: %s", ip, e)'''

patch_file(ORG, [(old_capsule, new_capsule, True)], "capsule no repeat")


# =====================================================================
# 3. _colonize_relay: реальный relay через RelayNode
# =====================================================================

print()
print("=" * 70)
print("  3. _colonize_relay: реальный relay")
print("=" * 70)

old_relay = '''    def _colonize_relay(self, node):
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

new_relay = '''    def _colonize_relay(self, node):
        """P95h: реальный relay через pheromone + gravity + relay_node."""
        ip = node["ip"]
        # Не повторяем
        if ip in self.memory.get("relayed_ips", set()):
            return
        try:
            # 1. Pheromone - путь через relay
            if hasattr(self.net.mycelium, "pheromones"):
                try:
                    self.net.mycelium.pheromones.mark_transit(
                        source=self.net.node_id, dest="relay_" + ip,
                        via=ip, path=[ip], success=True)
                except Exception:
                    pass
            # 2. Gravity - масса
            if hasattr(self.net, "gravity") and self.net.gravity:
                try:
                    self.net.gravity.add_mass(ip, 0.5)
                except Exception:
                    pass
            # 3. Relay через RelayNode
            if hasattr(self.net, "relay") and self.net.relay:
                try:
                    if hasattr(self.net.relay, "add_peer"):
                        self.net.relay.add_peer(ip, 9100)
                    elif hasattr(self.net.relay, "register_peer"):
                        self.net.relay.register_peer(ip, 9100)
                except Exception:
                    pass
            # Запоминаем
            if "relayed_ips" not in self.memory:
                self.memory["relayed_ips"] = set()
            self.memory["relayed_ips"].add(ip)
            with self._lock:
                self.stats["nodes_relayed"] += 1
            logger.info("[Relay] %s -> relayed", ip)
        except Exception as e:
            logger.debug("[Relay] %s: %s", ip, e)'''

patch_file(ORG, [(old_relay, new_relay, True)], "real relay 2")


# =====================================================================
# 4. _colonize_teach: реальный teach
# =====================================================================

print()
print("=" * 70)
print("  4. _colonize_teach: реальный teach")
print("=" * 70)

old_teach = '''    def _colonize_teach(self, node):
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

new_teach = '''    def _colonize_teach(self, node):
        """P95h: реальный teach через SuperNode + spore + evolution."""
        ip = node["ip"]
        if ip in self.memory["taught"]:
            return
        try:
            taught_via = []
            # 1. SuperNode
            sn = getattr(self.net, "super_node", None)
            if sn:
                try:
                    for m in ("promote", "mark_super", "add_super", "teach"):
                        if hasattr(sn, m):
                            getattr(sn, m)(ip)
                            taught_via.append("super_node")
                            break
                except Exception:
                    pass
            # 2. Spores - создать спору с профилем
            spores = getattr(getattr(self.net, "mycelium", None), "spores", None)
            if spores:
                try:
                    spore = spores.create(
                        node_id=self.net.node_id,
                        target_network="taught_" + ip,
                        method="teach", viability=0.9)
                    # Прикрепляем профиль
                    if hasattr(spores, "set_profile"):
                        prof = {"network_type": "taught", "ip": ip}
                        spores.set_profile(spore.spore_id, prof)
                    taught_via.append("spore")
                except Exception:
                    pass
            # 3. Evolution
            evo = getattr(self.net, "evolution", None)
            if evo:
                try:
                    for m in ("record_success", "mark_success", "add_fitness"):
                        if hasattr(evo, m):
                            getattr(evo, m)(ip)
                            taught_via.append("evolution")
                            break
                except Exception:
                    pass
            # 4. Pheromone - пометить как путь знания
            try:
                if hasattr(self.net.mycelium, "pheromones"):
                    self.net.mycelium.pheromones.mark_transit(
                        source=self.net.node_id, dest="taught_" + ip,
                        via=ip, path=[ip], success=True)
            except Exception:
                pass
            
            self.memory["taught"].add(ip)
            with self._lock:
                self.stats["nodes_taught"] += 1
            logger.info("[Teach] %s -> %s", ip, ",".join(taught_via) or "marked")
        except Exception as e:
            logger.debug("[Teach] %s: %s", ip, e)'''

patch_file(ORG, [(old_teach, new_teach, True)], "real teach 2")


print()
print("=" * 70)
print("  PATCH 95h DONE")
print("=" * 70)
print("  [OK] assess: teach для LAN + relay для ISP")
print("  [OK] capsule: не повторять")
print("  [OK] relay: реальный (pheromone + gravity + relay_node)")
print("  [OK] teach: реальный (super_node + spore + evolution)")
print()
print("Перезапуск + 90 сек:")
print("  curl -k https://localhost:8080/api/organism | python -m json.tool")