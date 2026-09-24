"""InevioNet Weighted Recursion - взвешенная рекурсия."""
import time
import random
from typing import Dict, List, Optional, Any, Callable, Tuple
from dataclasses import dataclass, field

from ..core.logger import get_logger

logger = get_logger("inevionet.ai.recursion")


@dataclass
class RecursionResult:
    """Результат взвешенной рекурсии."""
    success: bool
    depth: int
    path: List[str] = field(default_factory=list)
    probability: float = 0.0
    total_attempts: int = 0
    failed_paths: List[str] = field(default_factory=list)
    duration_ms: float = 0.0
    error: Optional[str] = None

    def __repr__(self):
        status = "OK" if self.success else "FAIL"
        return (f"[{status}] RecursionResult(depth={self.depth}, "
                f"attempts={self.total_attempts}, P={self.probability:.3f}, "
                f"duration={self.duration_ms:.1f}ms)")


class WeightedRecursion:
    """
    Взвешенная рекурсия для гарантированной доставки.
    Перед рекурсивным вызовом вычисляет веса для всех альтернатив.
    """

    def __init__(self, max_depth=10, probability_threshold=0.95,
                 weights=None, adaptive_learning=True):
        self.max_depth = max_depth
        self.probability_threshold = probability_threshold
        self.adaptive_learning = adaptive_learning
        self.weights = weights or {
            "reliability": 0.30, "speed": 0.25, "stealth": 0.20,
            "cost": 0.15, "energy": 0.10,
        }
        self.total_calls = 0
        self.successful_calls = 0

    def calculate_weight(self, alternative):
        score = 0.0
        score += self.weights["reliability"] * alternative.get("reliability", 0.5)
        score += self.weights["speed"] * alternative.get("speed", 0.5)
        score += self.weights["stealth"] * alternative.get("stealth", 0.5)
        score += self.weights["cost"] * (1 - alternative.get("cost", 0.5))
        score += self.weights["energy"] * (1 - alternative.get("energy", 0.5))
        return min(1.0, max(0.0, score))

    def rank_alternatives(self, alternatives):
        ranked = []
        for alt in alternatives:
            metrics = alt.get("metrics", alt)
            weight = self.calculate_weight(metrics)
            ranked.append((alt, weight))
        ranked.sort(key=lambda x: x[1], reverse=True)
        return ranked

    def execute(self, alternatives, try_func, depth=0, failed=None):
        start = time.time()
        failed = failed or []
        self.total_calls += 1

        if depth >= self.max_depth:
            return RecursionResult(
                success=False, depth=depth, failed_paths=failed,
                duration_ms=(time.time() - start) * 1000,
                error="Max depth reached")

        available = [alt for alt in alternatives if alt.get("name", "") not in failed]
        if not available:
            return RecursionResult(
                success=False, depth=depth, failed_paths=failed,
                duration_ms=(time.time() - start) * 1000,
                error="All alternatives exhausted")

        ranked = self.rank_alternatives(available)
        best, weight = ranked[0]
        best_name = best.get("name", str(best))

        try:
            success, probability = try_func(best, depth)
        except Exception as e:
            logger.error(f"try_func error: {e}")
            success = False
            probability = 0.0

        if success and probability >= self.probability_threshold:
            self.successful_calls += 1
            return RecursionResult(
                success=True, depth=depth, path=[best_name],
                probability=probability, total_attempts=depth + 1,
                failed_paths=failed, duration_ms=(time.time() - start) * 1000)

        if self.adaptive_learning:
            self._adjust_weights(weight, success)

        new_failed = failed + [best_name]
        result = self.execute(alternatives, try_func, depth + 1, new_failed)

        if result.success:
            result.path = [best_name] + result.path
            result.total_attempts = depth + 1 + result.total_attempts
            result.duration_ms += (time.time() - start) * 1000
        return result

    def _adjust_weights(self, weight, success):
        if success:
            for key in self.weights:
                self.weights[key] *= (1 + 0.01)
        else:
            for key in self.weights:
                self.weights[key] *= (1 - 0.005)
        total = sum(self.weights.values())
        if total > 0:
            for key in self.weights:
                self.weights[key] /= total

    def get_stats(self):
        return {
            "total_calls": self.total_calls,
            "successful_calls": self.successful_calls,
            "success_rate": (self.successful_calls / self.total_calls
                             if self.total_calls > 0 else 0.0),
            "weights": dict(self.weights),
            "max_depth": self.max_depth,
            "threshold": self.probability_threshold,
        }

    def reset_stats(self):
        self.total_calls = 0
        self.successful_calls = 0

    def __repr__(self):
        return (f"WeightedRecursion(max_depth={self.max_depth}, "
                f"threshold={self.probability_threshold})")


if __name__ == "__main__":
    print("Testing WeightedRecursion...")
    recursion = WeightedRecursion(max_depth=5, probability_threshold=0.9)
    print(f"Recursion: {recursion}")

    attempt_counter = {"n": 0}

    def try_func(alternative, depth):
        attempt_counter["n"] += 1
        name = alternative.get("name", "unknown")
        if attempt_counter["n"] <= 2:
            print(f"   FAIL {name} (depth={depth})")
            return False, 0.3
        else:
            print(f"   OK   {name} (depth={depth})")
            return True, 0.95

    alternatives = [
        {"name": "HTTPS", "metrics": {"reliability": 0.9, "speed": 0.7, "stealth": 0.7}},
        {"name": "DNS", "metrics": {"reliability": 0.6, "speed": 0.8, "stealth": 0.95}},
        {"name": "ICMP", "metrics": {"reliability": 0.5, "speed": 0.6, "stealth": 0.9}},
    ]

    result = recursion.execute(alternatives, try_func)
    print(f"\nResult: {result}")
    print(f"Path: {result.path}")
    print(f"Probability: {result.probability:.3f}")

    print("\nRanking:")
    ranked = recursion.rank_alternatives(alternatives)
    for alt, weight in ranked:
        print(f"   {alt['name']}: weight={weight:.3f}")

    stats = recursion.get_stats()
    print(f"\nStats: {stats['total_calls']} calls, "
          f"{stats['successful_calls']} successful")
    print("WeightedRecursion module OK")
