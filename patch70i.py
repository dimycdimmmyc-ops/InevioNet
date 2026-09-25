import os
import ast
import shutil

ROOT = r"E:\InevioNet"
ORCH = os.path.join(ROOT, "inevionet", "orchestrator.py")

with open(ORCH, "r", encoding="utf-8") as f:
    content = f.read()

if "check_interval=30" in content:
    print("  [--] P70i already applied")
else:
    old = "self.sprout = SproutEngine(self)"
    new = "self.sprout = SproutEngine(self, check_interval=30)"
    if old in content:
        content = content.replace(old, new, 1)
        b = ORCH + ".bak_p70i"
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
    else:
        print("  [!!] anchor NOT FOUND")

with open(ORCH, "r", encoding="utf-8") as f:
    check = f.read()
print("  check_interval=30: " + str("check_interval=30" in check))