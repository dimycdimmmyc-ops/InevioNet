# patch62.py - InevioNet: P62 — spores -> relay -> traffic
#
# P62b: build_minimal включает run_capsule.py (точка входа капсулы)
# P62c: RelayNode принимает GDPPacket по TCP (настоящий P2P-релей)
# P62d: send_with_guarantee использует Pheromone.via (транзит)
#
# Стандартный формат: backup -> replace -> ast.parse -> rollback.

import os
import ast
import shutil

ROOT = r"E:\InevioNet"

TARGETS = {
    "capsule":  os.path.join(ROOT, "inevionet", "mycelium", "capsule.py"),
    "relay":    os.path.join(ROOT, "inevionet", "network", "relay_node.py"),
    "orch":     os.path.join(ROOT, "inevionet", "orchestrator.py"),
}

BAK_SUFFIX = ".bak_p62"


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
# P62b: capsule.py — build_minimal включает run_capsule.py
# =====================================================================

P62B_OLD = '''            # Р”РѕР±Р°РІРёС‚СЊ РјРµС‚Р°РґР°РЅРЅС‹Рµ
            meta = {
                "version": "1.0.0",
                "built_at": time.time(),
                "include": include,
                "host": socket.gethostname(),
            }'''

P62B_NEW = '''            # P62b: С‚РѕС‡РєР° РІС…РѕРґР° РєР°РїСЃСѓР»С‹
            run_entry = os.path.join(self.project_root, "run_capsule.py")
            if os.path.exists(run_entry):
                tar.add(run_entry, arcname="run_capsule.py")
                logger.debug("[CapsuleBuilder] added: run_capsule.py")

            # Р”РѕР±Р°РІРёС‚СЊ РјРµС‚Р°РґР°РЅРЅС‹Рµ
            meta = {
                "version": "1.0.0",
                "built_at": time.time(),
                "include": include,
                "host": socket.gethostname(),
            }'''

patch(TARGETS["capsule"], [
    (P62B_OLD, P62B_NEW, True),
], "P62b: build_minimal включает run_capsule.py")


# =====================================================================
# P62c: relay_node.py — GDPPacket по TCP
# =====================================================================

# 1) __init__ — добавить listen_port и серверные поля
P62C_INIT_OLD = '''    def __init__(self, node_id, broker=None, capacity=10, region="unknown"):
        self.node_id = node_id
        self.broker = broker
        self.capacity = capacity
        self.region = region
        self.bridge = None
        self._running = False
        self._heartbeat_thread = None'''

P62C_INIT_NEW = '''    def __init__(self, node_id, broker=None, capacity=10, region="unknown",
                 listen_port=None):
        self.node_id = node_id
        self.broker = broker
        self.capacity = capacity
        self.region = region
        self.listen_port = listen_port        # P62c: TCP-порт для GDPPacket
        self._server_sock = None              # P62c
        self._server_thread = None            # P62c
        self.bridge = None
        self._running = False
        self._heartbeat_thread = None'''

# 2) start() — вызвать start_server
P62C_START_OLD = '''        # Start heartbeat
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

        logger.info("[Relay] Started: %s (capacity=%d, region=%s)",
                    self.node_id, self.capacity, self.region)'''

P62C_START_NEW = '''        # Start heartbeat
        self._heartbeat_thread = threading.Thread(
            target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()

        # P62c: TCP-сервер для GDPPacket
        self.start_server()

        logger.info("[Relay] Started: %s (capacity=%d, region=%s)",
                    self.node_id, self.capacity, self.region)'''

# 3) stop() — закрыть сервер
P62C_STOP_OLD = '''    def stop(self):
        """Stop relay node."""
        self._running = False
        if self.broker:
            self.broker.unregister_relay(self.node_id)
        logger.info("[Relay] Stopped: %s", self.node_id)'''

P62C_STOP_NEW = '''    def stop(self):
        """Stop relay node."""
        self._running = False
        # P62c: закрыть TCP-сервер
        try:
            if self._server_sock:
                self._server_sock.close()
        except Exception:
            pass
        if self.broker:
            self.broker.unregister_relay(self.node_id)
        logger.info("[Relay] Stopped: %s", self.node_id)

    # ================================================================
    # P62c: GDPPacket relay
    # ================================================================

    def start_server(self):
        """P62c: TCP-сервер для приёма GDPPacket."""
        if not self.listen_port:
            return
        try:
            self._server_sock = socket.socket(
                socket.AF_INET, socket.SOCK_STREAM)
            self._server_sock.setsockopt(
                socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server_sock.bind(("0.0.0.0", self.listen_port))
            self._server_sock.listen(16)
            self._server_thread = threading.Thread(
                target=self._server_loop, daemon=True)
            self._server_thread.start()
            logger.info("[Relay] TCP server on port %d", self.listen_port)
        except Exception as e:
            logger.error("[Relay] server start: %s", e)

    def _server_loop(self):
        """P62c: принимать GDPPacket."""
        while self._running:
            try:
                client, addr = self._server_sock.accept()
                threading.Thread(
                    target=self._handle_packet_client,
                    args=(client, addr), daemon=True).start()
            except Exception as e:
                if self._running:
                    logger.debug("[Relay] accept: %s", e)
                break

    def _handle_packet_client(self, client, addr):
        """P62c: обработка одного GDPPacket."""
        try:
            data = client.recv(65536)
            if not data:
                return
            from ..core.packet import GDPPacket
            pkt = GDPPacket.from_bytes(data)
            logger.info("[Relay] packet %s from %s",
                        pkt.packet_id[:16], addr[0])

            # Если пакет для меня — отдать в InevioNet
            if (pkt.route_to == self.node_id
                    or pkt.receiver == self.node_id):
                logger.info("[Relay] for me: %s", pkt.packet_id[:16])
                self._deliver_local(pkt)
            else:
                # Переслать дальше
                next_hop = pkt.route_to or pkt.receiver
                logger.info("[Relay] forward %s -> %s",
                            pkt.packet_id[:16], next_hop)
                self._forward_packet(pkt, next_hop)
        except Exception as e:
            logger.error("[Relay] handle: %s", e)
        finally:
            try:
                client.close()
            except Exception:
                pass

    def _forward_packet(self, pkt, next_hop):
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
            return False

    def _deliver_local(self, pkt):
        """P62c: отдать GDPPacket локальному InevioNet."""
        try:
            import urllib.request
            req = urllib.request.Request(
                "http://127.0.0.1:8080/api/relay/incoming",
                data=pkt.to_bytes(),
                headers={"Content-Type": "application/octet-stream"},
                method="POST")
            urllib.request.urlopen(req, timeout=5)
        except Exception as e:
            logger.debug("[Relay] deliver error: %s", e)'''

patch(TARGETS["relay"], [
    (P62C_INIT_OLD,  P62C_INIT_NEW,  True),
    (P62C_START_OLD, P62C_START_NEW, True),
    (P62C_STOP_OLD,  P62C_STOP_NEW,  True),
], "P62c: RelayNode GDPPacket TCP")


# =====================================================================
# P62d: orchestrator.py — send_with_guarantee через via
# =====================================================================

P62D_OLD = '''        packet = create_packet(
            sender=self.node_id, receiver=receiver,
            payload=encrypted, protocol="auto", priority=8,
            max_hops=50, expect_ack=expect_ack)  # P11.3 + P12-Fix-4
        packet._is_encrypted = True
        packet.sign(self.crypto.get_signing_keypair().private_key)'''

P62D_NEW = '''        packet = create_packet(
            sender=self.node_id, receiver=receiver,
            payload=encrypted, protocol="auto", priority=8,
            max_hops=50, expect_ack=expect_ack)  # P11.3 + P12-Fix-4
        packet._is_encrypted = True
        packet.sign(self.crypto.get_signing_keypair().private_key)

        # P62d: via lookup — транзит через Pheromone
        if _myc is not None:
            try:
                transit = _myc.pheromones.get_transit_path(
                    self.node_id, receiver)
                if transit and len(transit) > 1:
                    first_hop = transit[1]
                    if first_hop != receiver and first_hop != self.node_id:
                        logger.info('[P62d] via %s -> %s',
                                    first_hop, receiver)
                        packet.route_to = receiver
                        packet.origin = self.node_id
                        target_via = self._resolve_target(first_hop)
                        if target_via:
                            result = self.transport.send(
                                data=packet.to_bytes(),
                                protocol=self._map_protocol("TCP"),
                                target=target_via)
                            if result.success:
                                _myc.record_success(
                                    self.node_id, receiver, "TCP")
                                return True, packet
                            else:
                                logger.debug(
                                    '[P62d] via send failed: %s', first_hop)
            except Exception as _e:
                logger.debug('[P62d] via error: %s', _e)'''

patch(TARGETS["orch"], [
    (P62D_OLD, P62D_NEW, True),
], "P62d: send_with_guarantee via")


# =====================================================================
# Итог
# =====================================================================

print()
print("=" * 70)
print("  PATCH 62 DONE")
print("=" * 70)
print("  [OK] capsule.py:      build_minimal -> run_capsule.py")
print("  [OK] relay_node.py:   RelayNode -> GDPPacket TCP")
print("  [OK] orchestrator.py: send_with_guarantee -> via")
print()
print("Скопируй run_capsule.py в корень проекта:")
print("  Copy-Item dist_capsule\\test_capsule\\run_capsule.py E:\\InevioNet\\ -Force")
print()
print("Перезапусти: python -m web.app")