# patch56.py - InevioNet: fix async_mode in PyInstaller
import os
import ast
import re
import shutil

ROOT = r"E:\InevioNet"
APP = os.path.join(ROOT, "web", "app.py")
SPEC = os.path.join(ROOT, "InevioNet.spec")
RUN = os.path.join(ROOT, "run_app.py")


def backup(path):
    if os.path.exists(path):
        b = path + ".bak_p56"
        shutil.copy2(path, b)
        print(f"  [BK] {os.path.basename(b)}")


# === P56a: web/app.py — убрать async_mode (auto-detect) ===
print()
print("=" * 70)
print("  P56a: web/app.py — remove async_mode")
print("=" * 70)
backup(APP)
with open(APP, "r", encoding="utf-8") as f:
    content = f.read()

# Убираем строку async_mode='...'
m = re.search(r"\n\s*async_mode\s*=\s*['\"][^'\"]+['\"],?", content)
if m:
    content = content[:m.start()] + "\n" + content[m.end():]
    print(f"  [OK] removed: {m.group(0).strip()}")

try:
    ast.parse(content)
    with open(APP, "w", encoding="utf-8") as f:
        f.write(content)
    print("  [OK] syntax: app.py")
except SyntaxError as e:
    print(f"  [!!] syntax error: {e}")
    shutil.copy2(APP + ".bak_p56", APP)

with open(APP, "r", encoding="utf-8") as f:
    check = f.read()
if 'async_mode' not in check:
    print("  [OK] async_mode fully removed")
else:
    for line in check.splitlines():
        if 'async_mode' in line:
            print(f"  [!!] still: {line.strip()}")


# === P56b: InevioNet.spec — hiddenimports ===
print()
print("=" * 70)
print("  P56b: InevioNet.spec — hiddenimports")
print("=" * 70)
backup(SPEC)
with open(SPEC, "r", encoding="utf-8") as f:
    spec = f.read()

old = "hiddenimports=hiddenimports,"
new = """hiddenimports=hiddenimports + [
        'engineio.async_drivers.threading',
        'engineio.async_drivers.eventlet',
        'engineio.async_drivers.gevent',
        'engineio.async_drivers._websocket_wsgi',
        'socketio',
        'engineio',
        'eventlet',
        'eventlet.hubs',
        'eventlet.hubs.epolls',
        'eventlet.hubs.kqueue',
        'eventlet.hubs.selects',
        'eventlet.green.threading',
        'eventlet.green.ssl',
        'flask_socketio',
    ],"""

if old in spec and "'engineio.async_drivers.threading'" not in spec:
    spec = spec.replace(old, new, 1)
    print("  [OK] hiddenimports extended")
elif "'engineio.async_drivers.threading'" in spec:
    print("  [--] already extended")
else:
    print("  [!!] NOT FOUND: 'hiddenimports=hiddenimports,'")

with open(SPEC, "w", encoding="utf-8") as f:
    f.write(spec)
print("  [OK] spec saved")


# === P56c: run_app.py — env для threading ===
print()
print("=" * 70)
print("  P56c: run_app.py — env")
print("=" * 70)
backup(RUN)
with open(RUN, "r", encoding="utf-8") as f:
    run = f.read()

if "SOCKETIO_ASYNC_MODE" not in run:
    # Вставить после первого import os
    marker = "import os\n"
    if marker in run:
        run = run.replace(
            marker,
            marker + "os.environ['SOCKETIO_ASYNC_MODE'] = 'threading'\nos.environ['ENGINEIO_ASYNC_MODE'] = 'threading'\n",
            1,
        )
        print("  [OK] env added")
    else:
        print("  [!!] 'import os' not found")
    with open(RUN, "w", encoding="utf-8") as f:
        f.write(run)
    print("  [OK] run_app.py saved")
else:
    print("  [--] already has SOCKETIO_ASYNC_MODE")

print()
print("=" * 70)
print("  PATCH 56 DONE")
print("=" * 70)
print()
print("Пересобери:")
print("  Get-Process InevioNet,python -ErrorAction SilentlyContinue | Stop-Process -Force")
print("  cd E:\\InevioNet")
print("  Remove-Item dist,build -Recurse -Force -ErrorAction SilentlyContinue")
print("  .\\venv\\Scripts\\Activate.ps1")
print("  pyinstaller InevioNet.spec --clean --noconfirm")