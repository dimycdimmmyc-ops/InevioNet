"""InevioNet Detection - KL divergence and detection probability."""
import math
from typing import Dict, List


class KLDivergence:
    @staticmethod
    def compute(p, q, smoothing=1e-10):
        all_keys = set(p.keys()) | set(q.keys())
        p_sum = sum(p.values()) + smoothing * len(all_keys)
        q_sum = sum(q.values()) + smoothing * len(all_keys)
        kl = 0.0
        for key in all_keys:
            p_i = (p.get(key, 0.0) + smoothing) / p_sum
            q_i = (q.get(key, 0.0) + smoothing) / q_sum
            if p_i > 0:
                kl += p_i * math.log(p_i / q_i)
        return max(0.0, kl)

    @staticmethod
    def symmetric(p, q):
        all_keys = set(p.keys()) | set(q.keys())
        m = {key: 0.5 * (p.get(key, 0.0) + q.get(key, 0.0)) for key in all_keys}
        kl_pm = KLDivergence.compute(p, m)
        kl_qm = KLDivergence.compute(q, m)
        return math.sqrt(0.5 * kl_pm + 0.5 * kl_qm)

    @staticmethod
    def from_samples(samples_p, samples_q):
        from collections import Counter
        p_counter = Counter(samples_p)
        q_counter = Counter(samples_q)
        total_p = sum(p_counter.values())
        total_q = sum(q_counter.values())
        p_dist = {k: v / total_p for k, v in p_counter.items()}
        q_dist = {k: v / total_q for k, v in q_counter.items()}
        return KLDivergence.compute(p_dist, q_dist)

    @staticmethod
    def is_similar(p, q, threshold=0.1):
        return KLDivergence.compute(p, q) < threshold


class DetectionProbability:
    def __init__(self, baseline_entropy=0.3, baseline_size=1400):
        self.baseline_entropy = baseline_entropy
        self.baseline_size = baseline_size

    def estimate(self, features, weights=None):
        weights = weights or {"entropy": 0.3, "size": 0.2, "timing": 0.2, "structure": 0.3}
        scores = {}
        entropy = features.get("entropy", 0.5)
        scores["entropy"] = self._entropy_score(entropy)
        size = features.get("size", 1400)
        scores["size"] = self._size_score(size)
        timing = features.get("timing_variance", 0.5)
        scores["timing"] = abs(timing - 0.5) * 2
        structure = features.get("structure", 1.0)
        scores["structure"] = 1.0 - structure
        total = sum(scores[k] * weights.get(k, 0.25) for k in scores)
        total_weight = sum(weights.values())
        if total_weight > 0:
            total /= total_weight
        return min(1.0, max(0.0, total))

    def _entropy_score(self, entropy):
        if entropy < self.baseline_entropy:
            return 0.0
        return min(1.0, (entropy - self.baseline_entropy) / (1.0 - self.baseline_entropy))

    def _size_score(self, size):
        if 64 <= size <= self.baseline_size:
            return 0.0
        return min(1.0, abs(size - self.baseline_size) / self.baseline_size)

    def estimate_with_kl(self, observed_dist, reference_dist, kl_threshold=0.1):
        kl = KLDivergence.compute(observed_dist, reference_dist)
        p_detect = 1.0 - math.exp(-kl / max(kl_threshold, 0.001))
        return min(1.0, max(0.0, p_detect))


if __name__ == "__main__":
    print("Testing Detection...")
    kl = KLDivergence.compute({"A": 0.7, "B": 0.3}, {"A": 0.6, "B": 0.4})
    print(f"D_KL: {kl:.4f}")
    det = DetectionProbability()
    p = det.estimate({"entropy": 0.8, "size": 1400})
    print(f"P_detect: {p:.4f}")
    print("OK")
