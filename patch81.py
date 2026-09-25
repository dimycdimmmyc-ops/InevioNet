# patch81.py - P81: fix DataPaths UnboundLocalError
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
ORCH = os.path.join(ROOT, "inevionet", "orchestrator.py")

with open(ORCH, "r", encoding="utf-8") as f:
    content = f.read()

if "# P81: fix DataPaths" in content:
    print("  [--] P81 already applied")
else:
    old = '''            try:
                from .core.constants import DataPaths
                _audit_path = str(DataPaths.get_state_dir() / "audit_chain.json")
            except Exception:
                _audit_path = "audit_chain.json"'''

    new = '''            try:
                # P81: fix DataPaths UnboundLocalError - использовать глобальный import
                _audit_path = str(DataPaths.get_state_dir() / "audit_chain.json")
            except Exception:
                _audit_path = "audit_chain.json"'''

    if old in content:
        content = content.replace(old, new, 1)
        print("  [OK] P77c block fixed")
    else:
        print("  [!!] P77c block NOT FOUND")
        for i, line in enumerate(content.splitlines()):
            if "DataPaths" in line:
                print("    line " + str(i+1) + ": " + line.rstrip())

    b = ORCH + ".bak_p81"
    shutil.copy2(ORCH, b)
    print("  [BK] " + os.path.basename(b))

    with open(ORCH, "w", encoding="utf-8") as f:
        f.write(content)

    try:
        ast.parse(content)
        print("  [OK] syntax")
    except SyntaxError as e:
        print("  [!!] syntax: " + str(e))
        shutil.copy2(b, ORCH)
        print("  [--] rolled back")

with open(ORCH, "r", encoding="utf-8") as f:
    check = f.read()
print("  P81 marker: " + str("# P81: fix DataPaths" in check))
print("  local import removed: " + str("from .core.constants import DataPaths\n                _audit_path" not in check))