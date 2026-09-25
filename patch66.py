# patch66.py - InevioNet: P66 — public IP via STUN
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
ORCH = os.path.join(ROOT, "inevionet", "orchestrator.py")
APP = os.path.join(ROOT, "web", "app.py")


def backup(path):
    b = path + ".bak_p66"
    shutil.copy2(path, b)
    print("  [BK] " + os.path.basename(b))


def save_py(path, code):
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    try:
        ast.parse(code)
        print("  [OK] syntax: " + os.path.basename(path))
        return True
    except SyntaxError as e:
        print("  [!!] syntax error: " + str(e))
        b = path + ".bak_p66"
        if os.path.exists(b):
            shutil.copy2(b, path)
            print("  [--] rolled back")
        return False


# =====================================================================
# P66a: orchestrator.py — STUN в фоне
# =====================================================================

with open(ORCH, "r", encoding="utf-8") as f:
    orch = f.read()

if "# P66a: network info loop" in orch:
    print("  [--] P66a already applied")
else:
    changed = 0

    # 1) __init__ — добавить public_addr и nat_type
    anchor_init = "        self.relay = None\n        try:\n            from .network.relay_node import RelayNode"
    repl_init = ("        self.relay = None\n"
                 "        # P66a: public addr (STUN)\n"
                 "        self.public_addr = None\n"
                 "        self.nat_type = \"unknown\"\n"
                 "        try:\n"
                 "            from .network.relay_node import RelayNode")

    if anchor_init in orch:
        orch = orch.replace(anchor_init, repl_init, 1)
        print("  [OK] P66a: __init__")
        changed += 1
    else:
        print("  [!!] P66a: __init__ anchor NOT FOUND")

    # 2) start() — запустить поток
    anchor_start = "        # P63b: start RelayNode"
    repl_start = ("        # P66a: network info loop\n"
                  "        try:\n"
                  "            import threading as _th_net\n"
                  "            _th_net.Thread(target=self._network_info_loop,\n"
                  "                           daemon=True,\n"
                  "                           name='net_info').start()\n"
                  "            logger.info('[P66a] network info loop started')\n"
                  "        except Exception as _nie:\n"
                  "            logger.debug('[P66a] start error: %s', _nie)\n\n"
                  "        # P63b: start RelayNode")

    if anchor_start in orch:
        orch = orch.replace(anchor_start, repl_start, 1)
        print("  [OK] P66a: start")
        changed += 1
    else:
        print("  [!!] P66a: start anchor NOT FOUND")

    # 3) метод _network_info_loop — добавить перед _topology_loop
    anchor_method = "    def _topology_loop(self):"
    repl_method = (
        "    def _network_info_loop(self):\n"
        "        # P66a: STUN discover public IP, every 5 min\n"
        "        import time as _t\n"
        "        _t.sleep(5)\n"
        "        while getattr(self, '_running', False):\n"
        "            try:\n"
        "                from .network.udp import UDPHolePuncher\n"
        "                p = UDPHolePuncher()\n"
        "                addr = p.discover_public()\n"
        "                if addr:\n"
        "                    self.public_addr = addr\n"
        "                    # NAT type: cone vs symmetric\n"
        "                    _t.sleep(0.5)\n"
        "                    addr2 = None\n"
        "                    try:\n"
        "                        p2 = UDPHolePuncher()\n"
        "                        addr2 = p2.discover_public()\n"
        "                        p2.close()\n"
        "                    except Exception:\n"
        "                        pass\n"
        "                    if addr2 and addr2[1] == addr[1]:\n"
        "                        self.nat_type = 'cone'\n"
        "                    else:\n"
        "                        self.nat_type = 'symmetric'\n"
        "                    logger.info('[P66a] public %s:%d nat=%s',\n"
        "                                addr[0], addr[1], self.nat_type)\n"
        "                p.close()\n"
        "            except Exception as _e:\n"
        "                logger.debug('[P66a] stun error: %s', _e)\n"
        "            _t.sleep(300)\n\n"
        "    def _topology_loop(self):")

    if anchor_method in orch:
        orch = orch.replace(anchor_method, repl_method, 1)
        print("  [OK] P66a: method")
        changed += 1
    else:
        print("  [!!] P66a: method anchor NOT FOUND")

    if changed > 0:
        backup(ORCH)
        save_py(ORCH, orch)

# =====================================================================
# P66b: app.py — endpoint /api/network/public
# =====================================================================

with open(APP, "r", encoding="utf-8") as f:
    app = f.read()

if "/api/network/public" in app:
    print("  [--] P66b already applied")
else:
    anchor_app = "@app.route('/api/relay/port')"
    repl_app = (
        "@app.route('/api/network/public')\n"
        "def api_network_public():\n"
        "    \"\"\"P66b: public IP:port via STUN.\"\"\"\n"
        "    try:\n"
        "        n = get_net()\n"
        "        addr = getattr(n, 'public_addr', None)\n"
        "        if addr:\n"
        "            return jsonify({\n"
        "                'success': True,\n"
        "                'public_ip': addr[0],\n"
        "                'public_port': addr[1],\n"
        "                'nat_type': getattr(n, 'nat_type', 'unknown'),\n"
        "                'node_id': n.node_id,\n"
        "            })\n"
        "        return jsonify({'success': False, 'error': 'no_addr'})\n"
        "    except Exception as e:\n"
        "        return jsonify({'success': False, 'error': str(e)}), 500\n\n\n"
        "@app.route('/api/relay/port')")

    if anchor_app in app:
        app = app.replace(anchor_app, repl_app, 1)
        print("  [OK] P66b: endpoint")
        backup(APP)
        save_py(APP, app)
    else:
        print("  [!!] P66b: anchor NOT FOUND")

print()
print("=" * 70)
print("  PATCH 66 DONE (P66a + P66b)")
print("=" * 70)
print("P66c (UI) — отдельно")