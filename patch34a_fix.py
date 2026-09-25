# patch34a_fix.py - InevioNet: _auto_deploy_callback -> recon method
import os
import ast
import shutil

ORCH = r"E:\InevioNet\inevionet\orchestrator.py"


def backup(path):
    if os.path.exists(path):
        b = path + ".bak_p34a"
        shutil.copy2(path, b)
        print(f"  [BK] {os.path.basename(b)}")


print()
print("=" * 70)
print("  P34a-fix: _auto_deploy_callback -> recon method")
print("=" * 70)
backup(ORCH)

with open(ORCH, "r", encoding="utf-8") as f:
    content = f.read()

old = '''        logger.info("[AutoDeploy] trying %d trusted hosts", len(trusted))
        deployed = 0
        failed = 0
        for h in trusted[:5]:  # max 5
            host = h.get("host")
            if not host:
                continue
            try:
                ok = self.capsule_deployer.deploy(host, code, method="auto")
                if ok:
                    deployed += 1
                    logger.info("[AutoDeploy] OK %s", host)
                else:
                    failed += 1
                    logger.info("[AutoDeploy] FAIL %s", host)
            except Exception as e:
                logger.debug("[AutoDeploy] %s error: %s", host, e)

        logger.warning("[AutoDeploy] DONE: deployed=%d failed=%d", deployed, failed)'''

new = '''        logger.info("[AutoDeploy] trying %d trusted hosts", len(trusted))
        deployed = 0
        failed = 0
        for h in trusted[:5]:  # max 5
            host = h.get("host")
            if not host:
                continue
            # P34: recon method for this host
            ip = host.split(':')[0]
            method = "auto"
            try:
                from .network.router_recon import identify_firmware
                recon = identify_firmware(ip, "")
                if recon.get('can_deploy'):
                    method = recon.get('deploy_method', 'auto')
                    logger.info("[AutoDeploy] %s -> method=%s (vendor=%s)",
                                host, method, recon.get('vendor'))
            except Exception as _re:
                logger.debug("[AutoDeploy] recon error: %s", _re)
            try:
                ok = self.capsule_deployer.deploy(host, code, method=method)
                if ok:
                    deployed += 1
                    logger.info("[AutoDeploy] OK %s", host)
                else:
                    failed += 1
                    logger.info("[AutoDeploy] FAIL %s", host)
            except Exception as e:
                logger.debug("[AutoDeploy] %s error: %s", host, e)

        logger.warning("[AutoDeploy] DONE: deployed=%d failed=%d", deployed, failed)'''

if 'P34: recon method for this host' in content:
    print("  [--] already applied")
elif old in content:
    content = content.replace(old, new, 1)
    try:
        ast.parse(content)
        with open(ORCH, "w", encoding="utf-8") as f:
            f.write(content)
        print("  [OK] replaced + syntax OK")
    except SyntaxError as e:
        print(f"  [!!] syntax error: {e}")
        shutil.copy2(ORCH + ".bak_p34a", ORCH)
        print("  [--] rolled back")
else:
    print("  [!!] NOT FOUND")

print()
print("Перезапусти: python -m web.app")