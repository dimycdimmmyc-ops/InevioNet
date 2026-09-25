# patch64a2.py - InevioNet: P64a-2 — async_mode='threading'
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
TARGET = os.path.join(ROOT, "web", "app.py")

with open(TARGET, "r", encoding="utf-8") as f:
    content = f.read()

if "async_mode='threading'" in content:
    print("  [--] P64a-2 already applied")
else:
    old = (
        "socketio = SocketIO(\n"
        "    app,\n"
        "    cors_allowed_origins=\"*\",\n"
        "\n"
        "    manage_session=False,\n"
        "    logger=False,\n"
        "    engineio_logger=False,\n"
        ")"
    )

    new = (
        "socketio = SocketIO(\n"
        "    app,\n"
        "    async_mode='threading',\n"
        "    cors_allowed_origins=\"*\",\n"
        "\n"
        "    manage_session=False,\n"
        "    logger=False,\n"
        "    engineio_logger=False,\n"
        ")"
    )

    if old in content:
        content = content.replace(old, new, 1)
        print("  [OK] async_mode=threading inserted")
    else:
        print("  [!!] anchor NOT FOUND")
        for i, line in enumerate(content.splitlines()):
            if "SocketIO(" in line:
                print("    line " + str(i+1) + ": " + repr(line))
                for j in range(i+1, min(i+10, len(content.splitlines()))):
                    print("    line " + str(j+1) + ": " + repr(content.splitlines()[j]))

    bak = TARGET + ".bak_p64a2"
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

with open(TARGET, "r", encoding="utf-8") as f:
    check = f.read()
print("  async_mode='threading': " + str("async_mode='threading'" in check))