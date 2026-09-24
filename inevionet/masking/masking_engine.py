"""InevioNet Masking Engine — DPI bypass + industrial context."""
import time
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field

from .firewall_model import FirewallModel, DPIModel, FirewallAction, PacketFeatures
from .polymorphic import PolymorphicEncoder, Fragment
from .probing import Prober
from .vulnerability_map import VulnerabilityMap, ChannelState
from .bayesian import BayesianUpdater
from .channel_selector import ChannelSelector

# P11.6-fix-v4: logger для masking_engine
from ..core.logger import get_logger
logger = get_logger("inevionet.masking.masking_engine")
# P11.4: Ambient
try:
    from .ambient import AmbientMasker
except ImportError:
    AmbientMasker = None


@dataclass
class MaskingResult:
    success: bool
    channel: str
    fragments: List[Fragment] = field(default_factory=list)
    total_size: int = 0
    encoding_time_ms: float = 0.0
    error: Optional[str] = None
    metadata: Dict = field(default_factory=dict)

    def __repr__(self):
        status = "OK" if self.success else "FAIL"
        return f"[{status}] MaskingResult(channel={self.channel}, fragments={len(self.fragments)})"


class MaskingEngine:
    def __init__(self, dpi_profile="medium"):
        self.vmap = VulnerabilityMap()
        self.bayesian = BayesianUpdater()
        self.selector = ChannelSelector(self.vmap, self.bayesian)
        self.prober = Prober()
        self.encoder = PolymorphicEncoder()
        self.dpi = DPIModel(profile=dpi_profile)
        # P11.4: Ambient masker
        self.ambient_masker = None
        if AmbientMasker is not None:
            try:
                self.ambient_masker = AmbientMasker(adaptation_strength=0.5)
            except Exception:
                self.ambient_masker = None
        self.stats = {"packets_masked": 0, "nodes_probed": 0, "channels_selected": 0}

    def probe_node(self, node, probe_types=None):
        results = self.prober.probe_all(node, probe_types=probe_types, delay=0.01)
        for r in results:
            self.vmap.record(node, r.probe_type, r.success, r.response_time_ms)
            self.bayesian.update(f"{node}:{r.probe_type}", r.success)
        self.stats["nodes_probed"] += 1
        analysis = self.prober.analyze_results(results)
        analysis["node"] = node
        return analysis

    def mask(self, packet, node, channel=None, polymorphic=False,
             context=None, preferred_channel=None):
        """Замаскировать пакет.

        Параметры:
          channel            — принудительный канал
          polymorphic        — использовать полиморфную инкапсуляцию
          context            — контекст сети (iot/industrial/home/office/...)
          preferred_channel  — предпочитаемый канал (например, "MQTT"
                               если знаем что в сети есть MQTT-брокер)
        """
        start = time.time()
        try:
            payload = packet.to_bytes() if hasattr(packet, "to_bytes") else packet

            # Выбор канала: приоритет — preferred_channel → channel → context → selector
            if preferred_channel and not channel:
                channel = preferred_channel
            if channel is None and context:
                score = self.selector.select_for_context(node, context=context)
                if score:
                    channel = score.channel
            if channel is None:
                score = self.selector.select(node)
                if not score:
                    return MaskingResult(success=False, channel="unknown",
                                         error="No channel available")
                channel = score.channel
            else:
                score = self.selector.score_channel(node, channel)
            self.stats["channels_selected"] += 1
            # P11.4: Ambient — подстройка под фон
            if self.ambient_masker is not None:
                try:
                    _feat = self._extract_features(packet, channel)
                    # P11.6-fix-v4: правильный API — observe(size, protocol, entropy)
                    self.ambient_masker.observe(
                        size=_feat.size_bytes,
                        protocol=_feat.protocol,
                        entropy=_feat.entropy,
                    )
                    _adapted = self.ambient_masker.adapt_to_features(_feat)
                    if _adapted.protocol and _adapted.protocol in self.selector.PROFILES:
                        channel = _adapted.protocol
                except Exception as _e:
                    logger.debug(f"[P11.4] ambient: {_e}")

            if polymorphic:
                fragments = self.encoder.encode(payload)
            else:
                fragments = [Fragment(sequence=0, total_fragments=1,
                                      protocol=channel, data=payload)]
            features = self._extract_features(packet, channel)
            p_detect = self.dpi.detection_probability(features)
            action = self.dpi.decide(features)
            elapsed = (time.time() - start) * 1000
            self.stats["packets_masked"] += 1
            return MaskingResult(
                success=True, channel=channel, fragments=fragments,
                total_size=len(payload), encoding_time_ms=elapsed,
                metadata={
                    "p_detect": p_detect,
                    "dpi_action": action.value,
                    "channel_score": score.score if score else 0.0,
                    "polymorphic": polymorphic,
                    "context": context,
                    "preferred_channel": preferred_channel,
                })
        except Exception as e:
            # P11.6-fix-v3: показать причину
            logger.error(f"[Mask] exception in mask(): {type(e).__name__}: {e}", exc_info=True)
            return MaskingResult(success=False, channel=channel or "unknown", error=str(e))

    def _extract_features(self, packet, channel):
        size = len(packet.payload) if hasattr(packet, "payload") and packet.payload else 0
        entropy = self._estimate_entropy(packet.payload) if hasattr(packet, "payload") and packet.payload else 0.0
        # расширенный port_map с индустриальными протоколами
        port_map = {
            "HTTP": 80, "HTTPS": 443, "DNS": 53, "ICMP": 0,
            "TLS": 443, "WebSocket": 80, "QUIC": 443, "SMTP": 25, "NTP": 123,
            "MQTT": 1883, "MQTTS": 8883,
            "MODBUS": 502, "DNP3": 20000, "OPCUA": 4840,
        }
        port = port_map.get(channel, 80)
        return PacketFeatures(
            port=port, protocol=channel, size_bytes=size,
            entropy=entropy, header_conformance=0.9,
            timing_regularity=0.5, payload_entropy=entropy,
            is_encrypted=getattr(packet, "_is_encrypted", False))

    @staticmethod
    def _estimate_entropy(data):
        if not data:
            return 0.0
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

    def unmask(self, fragments):
        try:
            return self.encoder.decode(fragments)
        except Exception:
            return None

    def unmask_to_packet(self, fragments):
        data = self.unmask(fragments)
        if data is None:
            return None
        try:
            from ..core.packet import GDPPacket
            return GDPPacket.from_bytes(data)
        except Exception:
            return None

    def learn_from_result(self, node, channel, success, time_ms=0.0):
        self.vmap.record(node, channel, success, time_ms)
        self.bayesian.update(f"{node}:{channel}", success)

    def analyze(self, node, context="unknown"):
        recommendations = self.selector.get_recommendations(node, context=context)
        return {
            "node": node,
            "context": context,
            "recommendations": recommendations,
            "vmap_stats": self.vmap.get_stats(),
            "bayesian_stats": self.bayesian.get_stats(),
            "total_stats": dict(self.stats),
        }

    def get_optimal_channels(self, node, n=3, context=None):
        if context:
            scores = self.selector.score_all_channels(node)
            filtered = [s for s in scores
                        if self.selector._context_matches(
                            self.selector.PROFILES.get(s.channel, {}), context)]
            return [(s.channel, s.score) for s in filtered[:n]]
        scores = self.selector.score_all_channels(node)
        return [(s.channel, s.score) for s in scores[:n]]

    def get_stats(self):
        return {
            **self.stats,
            "vmap": self.vmap.get_stats(),
            "bayesian": self.bayesian.get_stats(),
            "dpi_profile": self.dpi.profile,
            "dpi_threshold": self.dpi.threshold,
        }

    def __repr__(self):
        return f"MaskingEngine(DPI={self.dpi.profile}, masked={self.stats['packets_masked']})"


if __name__ == "__main__":
    print("Testing MaskingEngine...")
    engine = MaskingEngine(dpi_profile="medium")
    print(f"Engine: {engine}")
    analysis = engine.probe_node("test.example.com")
    print(f"Probed: {analysis['success_rate']:.2%}")
    stats = engine.get_stats()
    print(f"Stats: {stats['packets_masked']} packets masked")

    # MQTT port detection
    from ..core.packet import create_text_packet
    pkt = create_text_packet("a", "b", "test")
    features = engine._extract_features(pkt, "MQTT")
    print(f"MQTT features: port={features.port}, protocol={features.protocol}")
    features = engine._extract_features(pkt, "MODBUS")
    print(f"MODBUS features: port={features.port}")
    print("OK")