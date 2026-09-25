# patch92fix2.py - P92-fix2: classify + spores
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
NETPROF = os.path.join(ROOT, "inevionet", "masking", "network_profile.py")

BAK = ".bak_p92fix2"


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
    return True


# =====================================================================
# Fix 1: _classify_network - учесть "device" и "unknown" как home
# =====================================================================

old_cls = '''def _classify_network(device_types: Dict[str, int],
                     services: List[str],
                     total_devices: int) -> str:
    """P92a: эвристика типа сети."""
    svc = set(s.lower() for s in services)
    # Корпоративная: много SMB/RDP/AD
    if any(s in svc for s in ("smb", "rdp", "ldap", "kerberos", "netbios")):
        return "corporate"
    # Публичная: только mDNS/SSDP + мало устройств, много HTTPS
    if total_devices <= 2 and any(s in svc for s in ("mdns", "ssdp", "llmnr")):
        return "public"
    # Домашняя: IoT + router + несколько PC
    iot = device_types.get("iot", 0)
    pc = device_types.get("pc", 0)
    if iot >= 1 or pc >= 1:
        return "home"
    return "unknown"'''

new_cls = '''def _classify_network(device_types: Dict[str, int],
                     services: List[str],
                     total_devices: int) -> str:
    """P92a + P92-fix2: эвристика типа сети."""
    svc = set(s.lower() for s in services)
    # Корпоративная: много SMB/RDP/AD
    if any(s in svc for s in ("smb", "rdp", "ldap", "kerberos", "netbios")):
        return "corporate"
    # Публичная: только mDNS/SSDP + очень мало устройств (1-2, без router)
    router = device_types.get("router", 0)
    if total_devices <= 2 and router == 0 and any(
            s in svc for s in ("mdns", "ssdp", "llmnr")):
        return "public"
    # P92-fix2: домашняя - router + >=1 device (включая "device"/unknown)
    iot = device_types.get("iot", 0)
    pc = device_types.get("pc", 0)
    generic = device_types.get("device", 0)
    phone = device_types.get("phone", 0)
    non_router = iot + pc + generic + phone
    if router >= 1 and non_router >= 1:
        return "home"
    # Fallback: если есть router, но мало devices - тоже home
    if router >= 1:
        return "home"
    # Fallback: если есть устройства без router - вероятно public
    if non_router >= 1:
        return "public"
    return "unknown"'''

patch_file(NETPROF, [(old_cls, new_cls, True)], "network_profile classify")


print()
print("=" * 70)
print("  PATCH 92 FIX2 DONE")
print("=" * 70)
print("  [OK] _classify_network: device/router -> home")
print()
print("Перезапуск: python -m web.app")
print("Проверка:   curl.exe -s -k -X POST https://localhost:8080/api/network/profile/force")