# patch95c.py - P95c: async scout (traceroute в фоне) + INFO-логи по фазам
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
ORG = os.path.join(ROOT, "inevionet", "organism.py")

BAK = ".bak_p95c"


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
# 1. live(): INFO-логи + тайминг фаз
# =====================================================================

print()
print("=" * 70)
print("  1. live(): INFO-логи по фазам")
print("=" * 70)

old_live = '''                # === ВДОХ ===
                self.wake()
                found = self.scout()
                for node in found:
                    plan = self.assess(node)
                    if plan.get("action"):
                        self.colonize(node, plan)
                
                # === ВЫДОХ ===
                self.expand()
                self.teach()
                
                with self._lock:
                    self.stats["cycles"] += 1
                elapsed = time.time() - t0'''

new_live = '''                # === ВДОХ ===
                _t1 = time.time()
                self.wake()
                logger.info("[Organism] wake: %.1fs", time.time() - _t1)

                _t2 = time.time()
                found = self.scout()
                logger.info("[Organism] scout: %.1fs, found=%d", time.time() - _t2, len(found))

                if found:
                    _t3 = time.time()
                    for node in found:
                        plan = self.assess(node)
                        if plan.get("action"):
                            self.colonize(node, plan)
                    logger.info("[Organism] colonize: %.1fs", time.time() - _t3)

                # === ВЫДОХ ===
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
                            self.stats["cycles"], elapsed, self._adaptive_sleep(0, len(found)))'''

patch_file(ORG, [(old_live, new_live, True)], "live() INFO logs")


# =====================================================================
# 2. scout(): traceroute в фоне (async)
# =====================================================================

print()
print("=" * 70)
print("  2. scout(): traceroute в фоне")
print("=" * 70)

# Добавить _tr_result и _tr_thread в __init__
old_init = '''        # === АДАПТИВНЫЙ HEARTBEAT ===
        self._load = 0.0
        self._phase_log = deque(maxlen=200)
        self._lock = threading.Lock()'''

new_init = '''        # === АДАПТИВНЫЙ HEARTBEAT ===
        self._load = 0.0
        self._phase_log = deque(maxlen=200)
        self._lock = threading.Lock()

        # P95c: async traceroute (не блокирует scout)
        self._tr_result = []
        self._tr_thread = None
        self._tr_running = False'''

patch_file(ORG, [(old_init, new_init, True)], "init async tr")


# Заменить блок traceroute в scout на async
old_tr_block = '''        # 4. Traceroute (10 targets - быстро)
        try:
            if self.net.traceroute_scan:
                tr = self.net.traceroute_scan.scan_multi(
                    targets=TRACEROUTE_TARGETS_FAST) or {}
                for hop in tr.get("hops", []):
                    ip = hop.get("ip")
                    if ip and ip not in seen_ips:
                        found.append({
                            "ip": ip, "type": "isp_router",
                            "source": "traceroute", "depth": 2,
                        })
                        c_tr += 1
        except Exception as e:
            logger.debug("[Scout] traceroute: %s", e)'''

new_tr_block = '''        # 4. Traceroute - ASYNC (P95c: не блокируем scout)
        # Запускаем в фоне (если ещё не запущен)
        if not self._tr_running and self.net.traceroute_scan:
            self._tr_running = True
            self._tr_thread = threading.Thread(
                target=self._tr_worker, daemon=True, name="organism_traceroute")
            self._tr_thread.start()
        # Забираем результаты ПРЕДЫДУЩЕГО запуска
        for hop in self._tr_result:
            ip = hop.get("ip")
            if ip and ip not in seen_ips:
                found.append({
                    "ip": ip, "type": "isp_router",
                    "source": "traceroute", "depth": 2,
                })
                c_tr += 1
                seen_ips.add(ip)
        # Сбрасываем
        self._tr_result = []'''

patch_file(ORG, [(old_tr_block, new_tr_block, True)], "scout async traceroute")


# Добавить метод _tr_worker перед _log_phase
old_util = '''    def _log_phase(self, phase, elapsed, extra=""):'''

new_util = '''    def _tr_worker(self):
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

    def _log_phase(self, phase, elapsed, extra=""):'''

patch_file(ORG, [(old_util, new_util, True)], "scout tr_worker method")


print()
print("=" * 70)
print("  PATCH 95c DONE")
print("=" * 70)
print("  [OK] live(): INFO-логи по фазам + тайминг")
print("  [OK] scout(): traceroute в фоне (не блокирует)")
print()
print("Перезапуск:")
print("  python -m web.app")
print()
print("Проверка через 90 сек:")
print("  curl -k https://localhost:8080/api/organism | python -m json.tool")