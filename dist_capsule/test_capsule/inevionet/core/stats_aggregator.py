"""InevioNet Stats Aggregator."""
import time
from typing import Dict, Any, List, Optional
from collections import defaultdict

from .logger import get_logger

logger = get_logger("inevionet.core.stats_aggregator")


class StatsAggregator:
    """Aggregates stats from all components."""

    def __init__(self):
        self.components: Dict[str, Any] = {}
        self.stats_history: List[Dict[str, Any]] = []
        self.max_history = 100

    def register(self, name, component):
        self.components[name] = component

    def unregister(self, name):
        if name in self.components:
            del self.components[name]

    def _get_component_stats(self, name, component):
        try:
            if hasattr(component, "get_stats"):
                return component.get_stats()
            elif hasattr(component, "stats"):
                return dict(component.stats) if isinstance(component.stats, dict) else {}
            elif isinstance(component, dict):
                return component
            return {}
        except Exception as e:
            logger.debug(f"Stats error from {name}: {e}")
            return {"error": str(e)}

    def get_all(self):
        result = {"timestamp": time.time(), "components": {}, "summary": {}}
        for name, component in self.components.items():
            result["components"][name] = self._get_component_stats(name, component)
        result["summary"] = self._compute_summary(result["components"])
        self.stats_history.append(result)
        if len(self.stats_history) > self.max_history:
            self.stats_history = self.stats_history[-self.max_history:]
        return result

    def _compute_summary(self, components):
        summary = {
            "total_packets_sent": 0, "total_packets_received": 0,
            "total_packets_delivered": 0, "total_packets_failed": 0,
            "total_bytes_sent": 0, "total_bytes_received": 0,
            "components_count": len(components),
        }
        keys_map = {
            "packets_sent": "total_packets_sent",
            "packets_received": "total_packets_received",
            "packets_delivered": "total_packets_delivered",
            "packets_failed": "total_packets_failed",
            "bytes_sent": "total_bytes_sent",
            "bytes_received": "total_bytes_received",
        }
        for name, stats in components.items():
            if not isinstance(stats, dict):
                continue
            for src_key, dst_key in keys_map.items():
                if src_key in stats and isinstance(stats[src_key], (int, float)):
                    summary[dst_key] += stats[src_key]
        total = summary["total_packets_sent"]
        summary["delivery_rate"] = (summary["total_packets_delivered"] / total
                                    if total > 0 else 0.0)
        return summary

    def get_trend(self, key, n=10):
        if len(self.stats_history) < 2:
            return []
        values = []
        for snap in self.stats_history[-n:]:
            val = snap["summary"].get(key, 0)
            if isinstance(val, (int, float)):
                values.append(val)
        return values

    def get_history(self, limit=100):
        return self.stats_history[-limit:]

    def export_json(self):
        import json
        return json.dumps(self.get_all(), ensure_ascii=False, indent=2, default=str)

    def clear(self):
        self.stats_history.clear()

    def __repr__(self):
        return f"StatsAggregator(components={len(self.components)})"


_global_aggregator = None


def get_global_aggregator():
    global _global_aggregator
    if _global_aggregator is None:
        _global_aggregator = StatsAggregator()
    return _global_aggregator


if __name__ == "__main__":
    print("Testing StatsAggregator...")
    agg = StatsAggregator()

    class FakeComponent:
        def __init__(self, sent, received):
            self.sent = sent
            self.received = received
        def get_stats(self):
            return {
                "packets_sent": self.sent, "packets_received": self.received,
                "packets_delivered": self.sent, "packets_failed": 0,
                "bytes_sent": self.sent * 100, "bytes_received": self.received * 50,
            }

    agg.register("network", FakeComponent(100, 80))
    agg.register("masking", FakeComponent(50, 40))
    stats = agg.get_all()
    print(f"Components: {stats['summary']['components_count']}")
    print(f"Total sent: {stats['summary']['total_packets_sent']}")
    print(f"Delivery rate: {stats['summary']['delivery_rate']:.2%}")
    print("StatsAggregator module OK")
