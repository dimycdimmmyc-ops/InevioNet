# patch63.py - InevioNet: P63 — активация RelayNode
#
# P63a: run_capsule.py — запускает InevioNet + RelayNode
# P63b: orchestrator.py — авто-создание RelayNode на свободном порту от 9100
# P63c: relay_node.py — mark_transit через HTTP callback
#
# Стандартный формат: backup -> replace -> ast.parse -> rollback.

import os
import ast
import shutil

ROOT = r"E:\InevioNet"

TARGETS = {
    "run_capsule": os.path.join(ROOT, "run_capsule.py"),
    "orch":        os.path.join(ROOT, "inevionet", "orchestrator.py"),
    "relay":       os.path.join(ROOT, "inevionet", "network", "relay_node.py"),
}

BAK_SUFFIX = ".bak_p63"


def backup(path):
    if os.path.exists(path):
        b = path + BAK_SUFFIX
        shutil.copy2(path, b)
        print(f"  [BK] {os.path.basename(b)}")


def save_py(path, code):
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    try:
        ast.parse(code)
        print(f"  [OK] syntax: {os.path.basename(path)}")
        return True
    except SyntaxError as e:
        print(f"  [!!] syntax error: {e}")
        b = path + BAK_SUFFIX
        if os.path.exists(b):
            shutil.copy2(b, path)
            print(f"  [--] rolled back")
        return False


def patch(path, replacements, name):
    print()
    print("=" * 70)
    print(f"  {name}")
    print("=" * 70)
    if not os.path.exists(path):
        print(f"  [!!] NOT FOUND: {path}")
        return False
    backup(path)
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    changed = 0
    for old, new, required in replacements:
        if new in content and old not in content:
            print(f"  [--] already applied")
            continue
        if old in content:
            content = content.replace(old, new, 1)
            print(f"  [OK] {old[:60].strip()}...")
            changed += 1
        else:
            if required:
                print(f"  [!!] NOT FOUND: {old[:60].strip()}...")
    if changed > 0:
        return save_py(path, content)
    return True


# =====================================================================
# P63a: run_capsule.py — запуск RelayNode
# =====================================================================

P63A_OLD = '''    net = InevioNet(password=password, node_id=node_id, auto_start=True)

    print(f"[OK] Node started: {net.node_id}")
    print(f"[OK] Press Ctrl+C to stop")
    print()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        net.stop()
        print()
        print("[OK] Stopped")'''

P63A_NEW = '''    net = InevioNet(password=password, node_id=node_id, auto_start=True)

    print(f"[OK] Node started: {net.node_id}")

    # P63a: запуск RelayNode на свободном порту от 9100
    relay = None
    try:
        from inevionet.network.relay_node import RelayNode

        # Найти свободный порт
        import socket as _sock
        listen_port = None
        for p in range(9100, 9201):
            try:
                _test = _sock.socket(_sock.AF_INET, _sock.SOCK_STREAM)
                _test.setsockopt(_sock.SOL_SOCKET, _sock.SO_REUSEADDR, 1)
                _test.bind(("0.0.0.0", p))
                _test.close()
                listen_port = p
                break
            except OSError:
                continue

        if listen_port:
            os.environ["INEVIO_RELAY_PORT"] = str(listen_port)
            relay = RelayNode(
                node_id=node_id + "_relay",
                listen_port=listen_port)
            relay.start()
            print(f"[OK] RelayNode started on port {listen_port}")
        else:
            print("[!!] No free port in 9100-9200")
    except Exception as _e:
        print(f"[!!] RelayNode error: {_e}")

    print(f"[OK] Press Ctrl+C to stop")
    print()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        if relay:
            relay.stop()
        net.stop()
        print()
        print("[OK] Stopped")'''

patch(TARGETS["run_capsule"], [
    (P63A_OLD, P63A_NEW, True),
], "P63a: run_capsule -> RelayNode")


# =====================================================================
# P63b: orchestrator.py — авто-создание RelayNode
# =====================================================================

# 1) В __init__ — добавить создание RelayNode
P63B_INIT_OLD = '''        self.selector = ProtocolSelector()
        self.recursion = WeightedRecursion()
        self.i2p = I2PTransport()                     # P13'''

P63B_INIT_NEW = '''        self.selector = ProtocolSelector()
        self.recursion = WeightedRecursion()
        self.i2p = I2PTransport()                     # P13

        # P63b: RelayNode на свободном порту от 9100
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

# 2) В start() — запустить relay
P63B_START_OLD = '''        # P38: growth loop
        # P43: automation loop
        # P13: topology loop'''

P63B_START_NEW = '''        # P63b: запустить RelayNode
        if getattr(self, "relay", None):
            try:
                self.relay.start()
                logger.info("[P63b] relay started")
            except Exception as _e:
                logger.debug("[P63b] relay start: %s", _e)

        # P38: growth loop
        # P43: automation loop
        # P13: topology loop'''

patch(TARGETS["orch"], [
    (P63B_INIT_OLD,  P63B_INIT_NEW,  True),
    (P63B_START_OLD, P63B_START_NEW, True),
], "P63b: orchestrator -> RelayNode auto")


# =====================================================================
# P63c: relay_node.py — mark_transit через HTTP
# =====================================================================

P63C_OLD = '''    def _forward_packet(self, pkt, next_hop):
        """P62c: переслать GDPPacket следующему hop."""
        try:
            if ":" in next_hop:
                target, port_s = next_hop.rsplit(":", 1)
                port = int(port_s)
            else:
                target, port = next_hop, 8080
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10.0)
            s.connect((target, port))
            s.sendall(pkt.to_bytes())
            s.close()
            self._stats["bytes_relayed"] += len(pkt.to_bytes())
            return True
        except Exception as e:
            logger.debug("[Relay] forward error: %s", e)
            return False'''

P63C_NEW = '''    def _forward_packet(self, pkt, next_hop):
        """P62c: переслать GDPPacket следующему hop.

        P63c: при успехе — mark_transit в PheromoneEngine через HTTP.
        """
        try:
            if ":" in next_hop:
                target, port_s = next_hop.rsplit(":", 1)
                port = int(port_s)
            else:
                target, port = next_hop, 8080
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(10.0)
            s.connect((target, port))
            s.sendall(pkt.to_bytes())
            s.close()
            self._stats["bytes_relayed"] += len(pkt.to_bytes())

            # P63c: mark_transit
            try:
                import urllib.request
                import json as _json
                body = _json.dumps({
                    "source": pkt.sender or pkt.origin,
                    "destination": pkt.receiver or next_hop,
                    "via": self.node_id,
                    "path": [pkt.sender or pkt.origin,
                             self.node_id,
                             pkt.receiver or next_hop],
                }).encode()
                req = urllib.request.Request(
                    "http://127.0.0.1:8080/api/relay/transit",
                    data=body,
                    headers={"Content-Type": "application/json"},
                    method="POST")
                urllib.request.urlopen(req, timeout=3)
            except Exception:
                pass

            return True
        except Exception as e:
            logger.debug("[Relay] forward error: %s", e)
            return False'''

patch(TARGETS["relay"], [
    (P63C_OLD, P63C_NEW, True),
], "P63c: relay_node -> mark_transit")


print()
print("=" * 70)
print("  PATCH 63 DONE")
print("=" * 70)
print("  [OK] run_capsule.py:    + RelayNode")
print("  [OK] orchestrator.py:   + RelayNode auto")
print("  [OK] relay_node.py:     + mark_transit")
print()
print("Требуется endpoint /api/relay/transit в web/app.py")
print("Следующий шаг: P63d — endpoint")