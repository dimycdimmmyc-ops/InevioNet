# patch63b.py - InevioNet: P63b-fix (RelayNode в orchestrator)
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
TARGET = os.path.join(ROOT, "inevionet", "orchestrator.py")

with open(TARGET, "r", encoding="utf-8") as f:
    content = f.read()

if "# P63b: RelayNode" in content:
    print("  [--] P63b already applied")
else:
    # Якорь 1: точная строка с probability_threshold
    anchor1 = '            probability_threshold=self.config.get("ai", {}).get("probability_threshold", 0.95))'
    
    repl1 = '''            probability_threshold=self.config.get("ai", {}).get("probability_threshold", 0.95))

        # P63b: RelayNode on free port from 9100
        self.relay = None
        try:
            from .network.relay_node import RelayNode
            import socket as _sock
            _listen_port = None
            for _p in range(9100, 9201):
                try:
                    _t = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
                    _t.setsockopt(_sock.SOL_SOCKET, _sock.SO_REUSEADDR, 1)
                    _t.bind(("0.0.0.0", _p))
                    _t.close()
                    _listen_port = _p
                    break
                except OSError:
                    continue
            if _listen_port:
                self.relay = RelayNode(
                    node_id=self.node_id + "_relay",
                    listen_port=_listen_port)
                import os as _os
                _os.environ["INEVIO_RELAY_PORT"] = str(_listen_port)
                logger.info("[P63b] RelayNode on port %d", _listen_port)
        except Exception as _e:
            logger.debug("[P63b] relay init: %s", _e)'''
    
    if anchor1 in content:
        content = content.replace(anchor1, repl1, 1)
        print("  [OK] __init__ updated")
    else:
        print("  [!!] anchor1 NOT FOUND")
        print("  Looking for:", repr(anchor1[:80]))
        # Найти похожие строки
        for i, line in enumerate(content.splitlines()):
            if "probability_threshold" in line:
                print(f"    line {i+1}: {line!r}")
    
    # Якорь 2: growth loop
    anchor2 = "        # P38: mycelium growth loop\n        try:\n            import threading as _th_growth"
    
    repl2 = '''        # P63b: start RelayNode
        if getattr(self, "relay", None):
            try:
                self.relay.start()
                logger.info("[P63b] relay started")
            except Exception as _e:
                logger.debug("[P63b] relay start: %s", _e)

        # P38: mycelium growth loop
        try:
            import threading as _th_growth'''
    
    if anchor2 in content:
        content = content.replace(anchor2, repl2, 1)
        print("  [OK] start() updated")
    else:
        print("  [!!] anchor2 NOT FOUND")
        for i, line in enumerate(content.splitlines()):
            if "growth loop" in line or "_th_growth" in line:
                print(f"    line {i+1}: {line!r}")
    
    # Backup
    bak = TARGET + ".bak_p63b3"
    shutil.copy2(TARGET, bak)
    print(f"  [BK] {os.path.basename(bak)}")
    
    # Записать
    with open(TARGET, "w", encoding="utf-8") as f:
        f.write(content)
    print("  [OK] saved")
    
    # Проверка
    try:
        ast.parse(content)
        print("  [OK] syntax")
    except SyntaxError as e:
        print(f"  [!!] syntax error: {e}")
        shutil.copy2(bak, TARGET)
        print("  [--] rolled back")

# Финальная проверка
with open(TARGET, "r", encoding="utf-8") as f:
    check = f.read()
print(f"  P63b in __init__: {'# P63b: RelayNode' in check}")
print(f"  P63b in start():  {'# P63b: start RelayNode' in check}")