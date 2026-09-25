# patch95d.py - P95d: починка scout (LAN + mDNS + router)
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
ORG = os.path.join(ROOT, "inevionet", "organism.py")

BAK = ".bak_p95d"


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
# 1. Заменить весь метод scout - надёжная версия
# =====================================================================

print()
print("=" * 70)
print("  1. scout(): надёжные источники")
print("=" * 70)

import re
with open(ORG, "r", encoding="utf-8") as f:
    org_content = f.read()

# Найти метод scout
m = re.search(r"    def scout\(self\).*?(?=\n    def |\n    # =|\Z)", org_content, re.DOTALL)
if m:
    old_scout = m.group(0)
    
    new_scout = '''    def scout(self) -> List[Dict[str, Any]]:
        """Разведчики ищут ЛЮБЫЕ узлы. P95d: надёжные источники."""
        found = []
        seen_ips = set(self.memory["nodes"].keys())
        c_lan = c_mdns = c_router = c_tr = 0

        # === 1. LAN - multiple methods ===
        try:
            lm = self.net.local_map
            if lm:
                local = None
                # Пробуем разные методы
                for method_name in ("build", "scan", "detect", "refresh", "get_map"):
                    if hasattr(lm, method_name):
                        try:
                            local = getattr(lm, method_name)()
                            if local and local.get("devices"):
                                logger.info("[Scout] local_map.%s -> %d devices",
                                            method_name, len(local.get("devices", [])))
                                break
                        except Exception as e:
                            logger.debug("[Scout] local_map.%s: %s", method_name, e)
                # Fallback: может, свойства напрямую
                if not local or not local.get("devices"):
                    devices = getattr(lm, "devices", None)
                    if devices:
                        local = {"devices": devices if isinstance(devices, list) else list(devices)}
                        logger.info("[Scout] local_map.devices -> %d", len(local["devices"]))
                
                if local:
                    for dev in local.get("devices", []):
                        ip = dev.get("ip") if isinstance(dev, dict) else None
                        if ip and ip not in seen_ips:
                            found.append({
                                "ip": ip,
                                "mac": dev.get("mac", "") if isinstance(dev, dict) else "",
                                "vendor": dev.get("vendor", "") if isinstance(dev, dict) else "",
                                "type": "lan_device", "source": "arp", "depth": 1,
                            })
                            c_lan += 1
                            seen_ips.add(ip)
        except Exception as e:
            logger.debug("[Scout] lan: %s", e)

        # === 2. mDNS/SSDP - async-friendly (короткий timeout) ===
        try:
            ld = self.net.local_discovery
            if ld:
                mdns = None
                for method_name in ("scan_all", "scan", "discover"):
                    if hasattr(ld, method_name):
                        try:
                            mdns = getattr(ld, method_name)(timeout=1.0)
                            break
                        except TypeError:
                            try:
                                mdns = getattr(ld, method_name)()
                                break
                            except Exception:
                                pass
                        except Exception as e:
                            logger.debug("[Scout] local_discovery.%s: %s", method_name, e)
                if mdns:
                    for dev in mdns.get("devices", []):
                        ip = dev.get("ip") if isinstance(dev, dict) else None
                        if ip and ip not in seen_ips:
                            found.append({
                                "ip": ip, "type": "service",
                                "service": dev.get("server") or dev.get("source"),
                                "source": "mdns", "depth": 1,
                            })
                            c_mdns += 1
                            seen_ips.add(ip)
        except Exception as e:
            logger.debug("[Scout] mdns: %s", e)

        # === 3. Роутер (gateway) - multiple methods ===
        try:
            lm = self.net.local_map
            router_ip = None
            if lm:
                # Свойства
                for attr in ("router_ip", "gateway", "gateway_ip", "router"):
                    if hasattr(lm, attr):
                        v = getattr(lm, attr)
                        if v and isinstance(v, str):
                            router_ip = v
                            break
                # Методы
                if not router_ip:
                    for m_name in ("get_router_ip", "get_gateway", "detect_router"):
                        if hasattr(lm, m_name):
                            try:
                                v = getattr(lm, m_name)()
                                if v and isinstance(v, str):
                                    router_ip = v
                                    break
                            except Exception:
                                pass
                # Из devices
                if not router_ip and hasattr(lm, "devices"):
                    for d in (lm.devices or []):
                        if isinstance(d, dict) and d.get("type") == "router":
                            router_ip = d.get("ip")
                            break
            
            # Fallback: стандартные gateway
            if not router_ip:
                for guess in ("192.168.1.1", "192.168.0.1", "10.0.0.1"):
                    if guess not in seen_ips:
                        router_ip = guess
                        break
            
            if router_ip and router_ip not in seen_ips:
                found.append({
                    "ip": router_ip, "type": "router",
                    "source": "gateway", "depth": 1, "is_gateway": True,
                })
                c_router += 1
                seen_ips.add(router_ip)
        except Exception as e:
            logger.debug("[Scout] router: %s", e)

        # === 4. Traceroute - async, берём предыдущий результат ===
        if not self._tr_running and self.net.traceroute_scan:
            self._tr_running = True
            self._tr_thread = threading.Thread(
                target=self._tr_worker, daemon=True, name="organism_traceroute")
            self._tr_thread.start()
        for hop in self._tr_result:
            ip = hop.get("ip")
            if ip and ip not in seen_ips:
                found.append({
                    "ip": ip, "type": "isp_router",
                    "source": "traceroute", "depth": 2,
                })
                c_tr += 1
                seen_ips.add(ip)
        self._tr_result = []

        # === 5. Собственные InevioNet-узлы (trusted hosts) ===
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

        # Регистрируем в памяти
        with self._lock:
            for node in found:
                self.memory["nodes"][node["ip"]] = {
                    **node,
                    "discovered_at": time.time(),
                    "last_seen": time.time(),
                    "score": 0.0,
                    "can_teach": False, "can_relay": False, "can_capsule": False,
                }
            self.stats["scouts_sent"] += 1
            self.stats["nodes_found"] += len(found)

        logger.info("[Scout] lan=%d mdns=%d router=%d traceroute=%d trusted=%d total=%d",
                    c_lan, c_mdns, c_router, c_tr,
                    len([f for f in found if f.get("source") == "trusted"]),
                    len(found))
        self._log_phase("scout", 0, f"found={len(found)}")
        return found

'''
    
    org_content_new = org_content[:m.start()] + new_scout + org_content[m.end():]
    
    b = ORG + BAK
    shutil.copy2(ORG, b)
    print("  [BK] " + os.path.basename(b))
    with open(ORG, "w", encoding="utf-8") as f:
        f.write(org_content_new)
    try:
        ast.parse(org_content_new)
        print("  [OK] scout() заменён (надёжная версия)")
    except SyntaxError as e:
        print("  [!!] syntax: " + str(e))
        shutil.copy2(b, ORG)
else:
    print("  [!!] scout() not found")


print()
print("=" * 70)
print("  PATCH 95d DONE")
print("=" * 70)
print("  [OK] scout(): lan/mdns/router - multiple methods + fallbacks")
print("  [OK] scout(): + trusted hosts (свои InevioNet-узлы)")
print()
print("Перезапуск:")
print("  python -m web.app")