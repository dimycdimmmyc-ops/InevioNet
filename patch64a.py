import os
import ast
import shutil

ROOT = r"E:\InevioNet"
TARGET = os.path.join(ROOT, "web", "app.py")

with open(TARGET, "r", encoding="utf-8") as f:
    content = f.read()

changed = 0

# P64a-1: fix socketio.run
old_run = (
    "    socketio.run(\n"
    "        app,\n"
    "        host='0.0.0.0',\n"
    "        port=PORT,\n"
    "        debug=False,\n"
    "        allow_unsafe_werkzeug=True,\n"
    "        ssl_context=ssl_ctx if use_tls else None,\n"
    "    )"
)

new_run = (
    "    # P64a: eventlet does not accept ssl_context in wsgi.server\n"
    "    _run_kwargs = dict(\n"
    "        host='0.0.0.0',\n"
    "        port=PORT,\n"
    "        debug=False,\n"
    "        allow_unsafe_werkzeug=True,\n"
    "    )\n"
    "    try:\n"
    "        _am = getattr(socketio, 'async_mode', '') or ''\n"
    "    except Exception:\n"
    "        _am = ''\n"
    "    if use_tls and _am != 'eventlet':\n"
    "        _run_kwargs['ssl_context'] = ssl_ctx\n"
    "    socketio.run(app, **_run_kwargs)"
)

if old_run in content:
    content = content.replace(old_run, new_run, 1)
    print("  [OK] socketio.run fixed")
    changed += 1
else:
    print("  [!!] socketio.run anchor NOT FOUND")

# P64a-2: force threading async_mode
old_sio = "socketio = SocketIO(app, cors_allowed_origins='*')"
new_sio = "socketio = SocketIO(app, cors_allowed_origins='*', async_mode='threading')"

if old_sio in content:
    content = content.replace(old_sio, new_sio, 1)
    print("  [OK] SocketIO async_mode=threading")
    changed += 1
else:
    old_sio2 = "socketio = SocketIO(app)"
    new_sio2 = "socketio = SocketIO(app, async_mode='threading')"
    if old_sio2 in content:
        content = content.replace(old_sio2, new_sio2, 1)
        print("  [OK] SocketIO async_mode=threading (alt)")
        changed += 1
    else:
        print("  [!!] SocketIO anchor NOT FOUND")
        for i, line in enumerate(content.splitlines()):
            if "SocketIO(" in line and "=" in line and "socketio" in line.lower():
                print("    line " + str(i+1) + ": " + repr(line))

if changed > 0:
    bak = TARGET + ".bak_p64a"
    shutil.copy2(TARGET, bak)
    print("  [BK] " + os.path.basename(bak))
    with open(TARGET, "w", encoding="utf-8") as f:
        f.write(content)
    print("  [OK] saved")
    try:
        ast.parse(content)
        print("  [OK] syntax")
    except SyntaxError as e:
        print("  [!!] syntax error: " + str(e))
        shutil.copy2(bak, TARGET)
        print("  [--] rolled back")
else:
    print("  [--] nothing changed")

with open(TARGET, "r", encoding="utf-8") as f:
    check = f.read()
has_run = "# P64a:" in check
has_async = "async_mode='threading'" in check
print("  P64a-1 (fix run):    " + str(has_run))
print("  P64a-2 (async_mode): " + str(has_async))