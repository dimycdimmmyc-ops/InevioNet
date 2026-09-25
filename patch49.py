# patch49.py - InevioNet: per-port inbox/state files
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
APP = os.path.join(ROOT, "web", "app.py")


def backup(path):
    if os.path.exists(path):
        b = path + ".bak_p49"
        shutil.copy2(path, b)
        print(f"  [BK] {os.path.basename(b)}")


def save_py(path, code):
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    try:
        ast.parse(code)
        print(f"  [OK] syntax: {os.path.basename(path)}")
    except SyntaxError as e:
        print(f"  [!!] syntax error: {e}")
        if os.path.exists(path + ".bak_p49"):
            shutil.copy2(path + ".bak_p49", path)


print()
print("=" * 70)
print("  P49: per-port inbox/state files")
print("=" * 70)
backup(APP)

with open(APP, "r", encoding="utf-8") as f:
    content = f.read()

# Replace INBOX_FILE and STATE_FILE with per-port
old = '''BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_FILE = os.path.join(BASE_DIR, 'data', 'web_state.json')
INBOX_FILE = os.path.join(BASE_DIR, 'data', 'p2_inbox.json')'''

new = '''BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# P49: per-port files (so PC-A and PC-B don't share)
_PORT = os.environ.get('INEVIO_PORT', '8080')
STATE_FILE = os.path.join(BASE_DIR, 'data', 'web_state_%s.json' % _PORT)
INBOX_FILE = os.path.join(BASE_DIR, 'data', 'p2_inbox_%s.json' % _PORT)'''

if old in content:
    content = content.replace(old, new, 1)
    print("  [OK] per-port files")
elif 'p2_inbox_%s.json' in content:
    print("  [--] already applied")
else:
    print("  [!!] NOT FOUND")

save_py(APP, content)

print()
print("=" * 70)
print("  PATCH 49 DONE")
print("=" * 70)
print()
print("Перезапусти ОБА сервера:")
print("  python -m web.app")
print("  $env:INEVIO_PORT=8081; python -m web.app")
print()
print("ВАЖНО: очисти кеш браузера (Ctrl+Shift+Delete) + открой в инкогнито")