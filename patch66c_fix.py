# patch66c_fix.py - InevioNet: P66c-fix — insert HTML block
import os
import shutil

ROOT = r"E:\InevioNet"
TARGET = os.path.join(ROOT, "web", "templates", "index.html")

with open(TARGET, "r", encoding="utf-8") as f:
    content = f.read()

if 'id="public-addr-box"' in content:
    print("  [--] P66c-fix already applied")
else:
    # Точный якорь: между </div> (status-bar) и <div class="metrics-bar">
    anchor = ('      <span id="statusText">\u041f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u0435...</span>\n'
              '    </div>\n'
              '    <div class="metrics-bar">')

    insert = ('      <span id="statusText">\u041f\u043e\u0434\u043a\u043b\u044e\u0447\u0435\u043d\u0438\u0435...</span>\n'
              '    </div>\n'
              '    <div class="public-addr" id="public-addr-box">\n'
              '      <span>\U0001f310</span>\n'
              '      <span class="addr" id="public-ip">\u2014</span>\n'
              '      <span class="nat" id="public-nat"></span>\n'
              '    </div>\n'
              '    <div class="metrics-bar">')

    if anchor in content:
        content = content.replace(anchor, insert, 1)
        print("  [OK] HTML block inserted")
    else:
        print("  [!!] anchor NOT FOUND")
        # Показать строки 264-270
        lines = content.splitlines()
        for i in range(263, min(271, len(lines))):
            print("    " + str(i+1) + ": " + repr(lines[i]))

    bak = TARGET + ".bak_p66cfix"
    shutil.copy2(TARGET, bak)
    print("  [BK] " + os.path.basename(bak))

    with open(TARGET, "w", encoding="utf-8") as f:
        f.write(content)
    print("  [OK] saved")

with open(TARGET, "r", encoding="utf-8") as f:
    check = f.read()
print("  public-addr-box: " + str('id="public-addr-box"' in check))