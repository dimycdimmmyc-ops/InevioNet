# patch16_fix.py - исправить пути в CapsuleBuilder
import os
import shutil
import ast
import sys

PATH = r"E:\InevioNet\inevionet\mycelium\capsule.py"

with open(PATH, "r", encoding="utf-8") as f:
    code = f.read()

shutil.copy2(PATH, PATH + ".bak_fix")
print(f"Backup: {PATH}.bak_fix")

# Исправить __init__
old_init = '''    def __init__(self, project_root: Optional[str] = None):
        if project_root is None:
            project_root = os.path.dirname(os.path.dirname(
                os.path.abspath(__file__)))
        self.project_root = project_root
        self.inev_dir = os.path.join(project_root, "inevionet")'''

new_init = '''    def __init__(self, project_root: Optional[str] = None):
        # __file__ = E:\\InevioNet\\inevionet\\mycelium\\capsule.py
        # parent  = E:\\InevioNet\\inevionet\\mycelium
        # parent2 = E:\\InevioNet\\inevionet         ← это self.inev_dir
        # parent3 = E:\\InevioNet                     ← это project_root
        if project_root is None:
            capsule_file = os.path.abspath(__file__)
            inev_dir = os.path.dirname(os.path.dirname(capsule_file))
            project_root = os.path.dirname(inev_dir)
        self.project_root = project_root
        self.inev_dir = os.path.join(project_root, "inevionet")
        print(f"[CapsuleBuilder] project_root={self.project_root}")
        print(f"[CapsuleBuilder] inev_dir={self.inev_dir}")'''

if old_init in code:
    code = code.replace(old_init, new_init)
    print("[OK] __init__ fixed")
else:
    print("[!!] __init__ pattern not found")

# Исправить walk: сделать относительный путь правильным
old_walk = '''                for dirpath, dirnames, filenames in os.walk(mod_path):
                    dirnames[:] = [d for d in dirnames if d != "__pycache__"]
                    for fname in filenames:
                        if not fname.endswith(".py"):
                            continue
                        full = os.path.join(dirpath, fname)
                        rel = os.path.relpath(full, self.project_root)
                        tar.add(full, arcname=rel)'''

new_walk = '''                for dirpath, dirnames, filenames in os.walk(mod_path):
                    dirnames[:] = [d for d in dirnames if d != "__pycache__"]
                    for fname in filenames:
                        if not fname.endswith(".py"):
                            continue
                        full = os.path.join(dirpath, fname)
                        # arcname = "inevionet/module/file.py"
                        rel = os.path.relpath(full, self.project_root)
                        tar.add(full, arcname=rel.replace("\\\\", "/"))
                        print(f"[CapsuleBuilder] added: {rel}")'''

if old_walk in code:
    code = code.replace(old_walk, new_walk)
    print("[OK] walk fixed (with logging)")
else:
    print("[!!] walk pattern not found")

# Сохранить
with open(PATH, "w", encoding="utf-8") as f:
    f.write(code)

try:
    ast.parse(code)
    print("[OK] syntax valid")
except SyntaxError as e:
    print(f"[!!] syntax error: {e}")
    shutil.copy2(PATH + ".bak_fix", PATH)
    print("[!!] restored")
    sys.exit(1)

print()
print("=" * 70)
print("  FIX DONE")
print("=" * 70)
print()
print("Test:")
print("  python -c \"from inevionet.mycelium.capsule import CapsuleBuilder; b = CapsuleBuilder(); print('Size:', len(b.build_minimal()), 'bytes')\"")