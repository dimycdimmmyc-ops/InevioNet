# patch80.py - P80: отключить автозапуск I2P (P26)
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
APP = os.path.join(ROOT, "web", "app.py")

with open(APP, "r", encoding="utf-8") as f:
    content = f.read()

if "# P80: I2P autostart disabled" in content:
    print("  [--] P80 already applied")
else:
    # 1. Обернуть функцию _ensure_i2p_running проверкой env
    old1 = '''def _ensure_i2p_running():
    """P26: start I2P router in background if not running."""'''

    new1 = '''def _ensure_i2p_running():
    """P26: start I2P router in background if not running.

    P80: отключено по умолчанию. Включается через INEVIO_I2P_AUTOSTART=1.
    """
    # P80: I2P autostart disabled
    import os as _os
    if _os.environ.get("INEVIO_I2P_AUTOSTART", "0") != "1":
        return
    '''

    if old1 in content:
        content = content.replace(old1, new1, 1)
        print("  [OK] _ensure_i2p_running guarded by env")
    else:
        print("  [!!] anchor 1 NOT FOUND")

    # 2. Найти вызов _ensure_i2p_running и обернуть
    # (он уже обёрнут в try/except, но нужно проверить что вызов не циклится)

    # 3. Закомментировать вызов в _ensure_ (там где он вызывается на каждом запросе)
    old3 = '''            # P26: ensure I2P running
            try:
                _ensure_i2p_running()
            except Exception as _e:
                log.debug('[I2P] autostart error: %s', _e)'''

    new3 = '''            # P80: I2P autostart disabled (не используем)
            # try:
            #     _ensure_i2p_running()
            # except Exception as _e:
            #     log.debug('[I2P] autostart error: %s', _e)'''

    if old3 in content:
        content = content.replace(old3, new3, 1)
        print("  [OK] call disabled")
    else:
        print("  [!!] anchor 3 NOT FOUND (может быть, уже отключено)")

    # Backup
    b = APP + ".bak_p80"
    shutil.copy2(APP, b)
    print("  [BK] " + os.path.basename(b))

    # Записать
    with open(APP, "w", encoding="utf-8") as f:
        f.write(content)

    # Проверить
    try:
        ast.parse(content)
        print("  [OK] syntax app.py")
    except SyntaxError as e:
        print("  [!!] syntax: " + str(e))
        shutil.copy2(b, APP)
        print("  [--] rolled back")

with open(APP, "r", encoding="utf-8") as f:
    check = f.read()
print("  P80 marker: " + str("# P80: I2P autostart disabled" in check))