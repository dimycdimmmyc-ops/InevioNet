import os, ast, re, shutil
ROOT = r"E:\InevioNet"
APP = os.path.join(ROOT, "web", "app.py")
ARP = os.path.join(ROOT, "inevionet", "network", "arp_scanner.py")

def backup(path):
    if os.path.exists(path):
        shutil.copy2(path, path + ".bak_p59")
        print(f"  [BK] {os.path.basename(path)}.bak_p59")

def save_py(path, code):
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    try:
        ast.parse(code)
        print(f"  [OK] syntax: {os.path.basename(path)}")
    except SyntaxError as e:
        print(f"  [!!] syntax error: {e}")
        if os.path.exists(path + ".bak_p59"):
            shutil.copy2(path + ".bak_p59", path)

print("=" * 70)
print("  P59: hide console windows from subprocess")
print("=" * 70)

backup(APP)
with open(APP, "r", encoding="utf-8") as f:
    content = f.read()

# 1. CREATE_NO_WINDOW
if 'CREATE_NO_WINDOW' not in content:
    marker = "log = logging.getLogger('inevionet.web')"
    if marker in content:
        content = content.replace(marker,
            marker + "\n\n# P59: hide console windows\nCREATE_NO_WINDOW = 0x08000000\n", 1)
        print("  [OK] CREATE_NO_WINDOW added")

# 2. scan_bt powershell
old = """            ['powershell', '-Command', ps],
            capture_output=True, text=True, timeout=5,
            encoding='utf-8', errors='ignore',
        )"""
new = """            ['powershell', '-NoProfile', '-NonInteractive', '-WindowStyle', 'Hidden', '-Command', ps],
            capture_output=True, text=True, timeout=5,
            encoding='utf-8', errors='ignore',
            creationflags=CREATE_NO_WINDOW,
        )"""
if old in content:
    content = content.replace(old, new)
    print("  [OK] scan_bt: powershell hidden")
else:
    print("  [--] scan_bt already patched or not found")

# 3. scan_wifi netsh
old = """        r = subprocess.run(
            ['netsh', 'wlan', 'show', 'networks', 'mode=bssid'],
            capture_output=True, timeout=5,
        )"""
new = """        r = subprocess.run(
            ['netsh', 'wlan', 'show', 'networks', 'mode=bssid'],
            capture_output=True, timeout=5,
            creationflags=CREATE_NO_WINDOW,
        )"""
if old in content:
    content = content.replace(old, new)
    print("  [OK] scan_wifi: netsh hidden")
else:
    print("  [--] scan_wifi already patched or not found")

# 4. _sp.run(['netsh', ...]) — все
content, n = re.subn(
    r"(_sp\.run\(\s*\[[^\]]+\][^)]*?)(\))",
    lambda m: m.group(1).rstrip() + ",\n                creationflags=CREATE_NO_WINDOW,\n            )"
              if 'creationflags' not in m.group(0) else m.group(0),
    content,
)
if n: print(f"  [OK] {n} _sp.run(['...']) hidden")

# 5. I2P Popen
old_popen = """            creationflags=_sp.CREATE_NEW_PROCESS_GROUP | _sp.DETACHED_PROCESS if sys.platform == "win32" else 0,"""
new_popen = """            creationflags=(_sp.CREATE_NEW_PROCESS_GROUP | _sp.DETACHED_PROCESS | 0x08000000) if sys.platform == "win32" else 0,"""
if old_popen in content:
    content = content.replace(old_popen, new_popen)
    print("  [OK] I2P Popen hidden")

save_py(APP, content)

# === arp_scanner.py ===
if os.path.exists(ARP):
    backup(ARP)
    with open(ARP, "r", encoding="utf-8") as f:
        arp = f.read()
    if 'CREATE_NO_WINDOW' not in arp:
        marker = "logger = get_logger"
        if marker in arp:
            arp = arp.replace(marker, "CREATE_NO_WINDOW = 0x08000000\n\n" + marker, 1)
    arp, n = re.subn(
        r"(subprocess\.run\(\s*\[[^\]]+\][^)]*?)(\))",
        lambda m: m.group(1).rstrip() + ",\n            creationflags=CREATE_NO_WINDOW,\n        )"
                  if 'creationflags' not in m.group(0) else m.group(0),
        arp,
    )
    print(f"  [OK] arp_scanner.py: {n} subprocess hidden")
    save_py(ARP, arp)

print()
print("=" * 70)
print("  PATCH 59 DONE")
print("=" * 70)
print()
print("Пересобери:")
print("  Get-Process InevioNet,python -ErrorAction SilentlyContinue | Stop-Process -Force")
print("  cd E:\\InevioNet")
print("  Remove-Item dist,build -Recurse -Force -ErrorAction SilentlyContinue")
print("  .\\venv\\Scripts\\Activate.ps1")
print("  pyinstaller InevioNet.spec --clean --noconfirm")