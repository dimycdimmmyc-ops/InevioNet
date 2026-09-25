# patch82fix.py - P82-fix: исправить NetworkTree.build
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
TREE = os.path.join(ROOT, "inevionet", "mesh", "network_tree.py")

with open(TREE, "r", encoding="utf-8") as f:
    content = f.read()

if "# P82fix" in content:
    print("  [--] P82-fix already applied")
else:
    old = '''        with self._stats.__setitem__("builds", self._stats["builds"] + 1):
            pass
'''
    new = '''        # P82fix: fix for NoneType context manager
        self._stats["builds"] = self._stats.get("builds", 0) + 1
'''
    if old in content:
        content = content.replace(old, new, 1)
        print("  [OK] fix applied")
    else:
        print("  [!!] anchor NOT FOUND")
        for i, line in enumerate(content.splitlines()):
            if "_stats.__setitem__" in line:
                print("    line " + str(i+1) + ": " + line.rstrip())

    b = TREE + ".bak_p82fix"
    shutil.copy2(TREE, b)
    print("  [BK] " + os.path.basename(b))

    with open(TREE, "w", encoding="utf-8") as f:
        f.write(content)

    try:
        ast.parse(content)
        print("  [OK] syntax")
    except SyntaxError as e:
        print("  [!!] syntax: " + str(e))
        shutil.copy2(b, TREE)
        print("  [--] rolled back")

with open(TREE, "r", encoding="utf-8") as f:
    check = f.read()
print("  P82fix marker: " + str("# P82fix" in check))