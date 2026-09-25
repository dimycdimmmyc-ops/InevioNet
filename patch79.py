import os
import ast
import shutil

ROOT = r"E:\InevioNet"
ORCH = os.path.join(ROOT, "inevionet", "orchestrator.py")

with open(ORCH, "r", encoding="utf-8") as f:
    content = f.read()

if "INEVIO_NO_I2P" in content:
    print("  [--] already applied")
else:
    old = '''        try:
            if getattr(self, 'i2p', None):
                avail = self.i2p.is_available()
                logger.info('[Auto] I2P: %s', 'available' if avail else 'not running')
        except Exception:
            pass'''

    new = '''        # P79: I2P проверка отключена (не используем)
        import os as _os
        if _os.environ.get("INEVIO_NO_I2P") != "1":
            try:
                if getattr(self, 'i2p', None):
                    avail = self.i2p.is_available()
                    logger.info('[Auto] I2P: %s', 'available' if avail else 'not running')
            except Exception:
                pass'''

    if old in content:
        content = content.replace(old, new, 1)
        b = ORCH + ".bak_p79"
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
print("  INEVIO_NO_I2P: " + str("INEVIO_NO_I2P" in check))