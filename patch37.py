# patch37.py - InevioNet: _auto_deploy_callback MAC from label
import os
import ast
import shutil

ORCH = r"E:\InevioNet\inevionet\orchestrator.py"


def backup(path):
    if os.path.exists(path):
        b = path + ".bak_p37"
        shutil.copy2(path, b)
        print(f"  [BK] {os.path.basename(b)}")


print()
print("=" * 70)
print("  P37: _auto_deploy_callback MAC from label")
print("=" * 70)
backup(ORCH)

with open(ORCH, "r", encoding="utf-8") as f:
    content = f.read()

old = '''        for h in trusted[:5]:  # max 5
            host = h.get("host")
            if not host:
                continue
            # P34: recon method for this host
            ip = host.split(':')[0]
            method = "auto"
            try:
                from .network.router_recon import identify_firmware
                recon = identify_firmware(ip, "")'''

new = '''        for h in trusted[:5]:  # max 5
            host = h.get("host")
            if not host:
                continue
            # P37: MAC from label (arp_XXXX)
            label = h.get("label", "")
            ip = host.split(':')[0]
            mac = ""
            if label.startswith("arp_"):
                _raw = label[4:]
                if len(_raw) == 12:
                    mac = ':'.join(_raw[i:i+2] for i in range(0, 12, 2))
            method = "auto"
            try:
                from .network.router_recon import identify_firmware
                recon = identify_firmware(ip, mac)'''

if old in content:
    content = content.replace(old, new, 1)
    print("  [OK] replaced (MAC from label)")
elif 'P37: MAC from label' in content:
    print("  [--] already applied")
else:
    print("  [!!] NOT FOUND")

# Also update logger.info to show mac
old2 = '''                if recon.get('can_deploy'):
                    method = recon.get('deploy_method', 'auto')
                    logger.info("[AutoDeploy] %s -> method=%s (vendor=%s)",
                                host, method, recon.get('vendor'))'''
new2 = '''                if recon.get('can_deploy'):
                    method = recon.get('deploy_method', 'auto')
                    logger.info("[AutoDeploy] %s -> method=%s (mac=%s, vendor=%s)",
                                host, method, mac or "none", recon.get('vendor'))'''

if old2 in content:
    content = content.replace(old2, new2, 1)
    print("  [OK] logger updated")
else:
    print("  [--] logger line unchanged")

try:
    ast.parse(content)
    with open(ORCH, "w", encoding="utf-8") as f:
        f.write(content)
    print("  [OK] syntax OK")
except SyntaxError as e:
    print(f"  [!!] syntax error: {e}")
    shutil.copy2(ORCH + ".bak_p37", ORCH)
    print("  [--] rolled back")

print()
print("Перезапусти: python -m web.app")