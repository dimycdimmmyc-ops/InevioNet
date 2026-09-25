# patch95e.py - P95e: фикс scout (devices - не dict?) + диагностика
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
ORG = os.path.join(ROOT, "inevionet", "organism.py")

BAK = ".bak_p95e"


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
# 1. Диагностика devices - ЧТО именно в local_map.build()
# =====================================================================

print()
print("=" * 70)
print("  1. Диагностика: devices в scout()")
print("=" * 70)

old_lan_block = '''                if local:
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
                            seen_ips.add(ip)'''

new_lan_block = '''                if local:
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
                            logger.info("[Scout] +lan_device %s", ip)'''

patch_file(ORG, [(old_lan_block, new_lan_block, True)], "scout devices diag")


# =====================================================================
# 2. Простой тест: вывести devices в отдельный лог
# =====================================================================

print()
print("=" * 70)
print("  2. Добавить debug-метод: dump_devices()")
print("=" * 70)

old_log_phase = '''    def _log_phase(self, phase, elapsed, extra=""):'''

new_log_phase = '''    def dump_devices(self):
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

    def _log_phase(self, phase, elapsed, extra=""):'''

patch_file(ORG, [(old_log_phase, new_log_phase, True)], "dump_devices method")


# =====================================================================
# 3. Endpoint /api/organism/dump в app.py
# =====================================================================

print()
print("=" * 70)
print("  3. app.py: /api/organism/dump")
print("=" * 70)

APP = os.path.join(ROOT, "web", "app.py")

anchor = "@app.route('/api/network/public')"

new_ep = '''@app.route('/api/organism/dump')
def api_organism_dump():
    """P95e: диагностика local_map для Organism."""
    try:
        n = get_net()
        org = getattr(n, "organism", None)
        if org is None:
            return jsonify({'success': False, 'error': 'organism not running'})
        return jsonify({
            'success': True,
            'dump': org.dump_devices(),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/network/public')'''

patch_file(APP, [(anchor, new_ep, True)], "app.py /api/organism/dump")


print()
print("=" * 70)
print("  PATCH 95e DONE")
print("=" * 70)
print("  [OK] scout(): devices диагностика (dict/object/string)")
print("  [OK] dump_devices(): полная диагностика local_map")
print("  [OK] /api/organism/dump endpoint")
print()
print("Перезапуск + 60 сек:")
print("  curl -k https://localhost:8080/api/organism/dump | python -m json.tool")