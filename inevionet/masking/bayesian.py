"""InevioNet Bayesian Updater."""
import math
from typing import Dict, List


class BayesianUpdater:
    def __init__(self, prior_alpha=1.0, prior_beta=1.0, decay=0.99):
        self.prior_alpha = prior_alpha
        self.prior_beta = prior_beta
        self.decay = decay
        self.channels: Dict[str, Dict[str, float]] = {}

    def update(self, channel, success, weight=1.0):
        if channel not in self.channels:
            self.channels[channel] = {"alpha": self.prior_alpha, "beta": self.prior_beta}
        if self.decay < 1.0:
            self.channels[channel]["alpha"] *= self.decay
            self.channels[channel]["beta"] *= self.decay
        if success:
            self.channels[channel]["alpha"] += weight
        else:
            self.channels[channel]["beta"] += weight

    def update_batch(self, channel, results):
        for r in results:
            self.update(channel, r)

    def get_probability(self, channel):
        if channel not in self.channels:
            return self.prior_alpha / (self.prior_alpha + self.prior_beta)
        alpha = self.channels[channel]["alpha"]
        beta = self.channels[channel]["beta"]
        if alpha + beta == 0:
            return 0.5
        return alpha / (alpha + beta)

    def get_uncertainty(self, channel):
        if channel not in self.channels:
            alpha = self.prior_alpha
            beta = self.prior_beta
        else:
            alpha = self.channels[channel]["alpha"]
            beta = self.channels[channel]["beta"]
        total = alpha + beta
        if total <= 0 or total + 1 <= 0:
            return 0.25
        return (alpha * beta) / (total * total * (total + 1))

    def get_confidence_interval(self, channel, confidence=0.95):
        p = self.get_probability(channel)
        variance = self.get_uncertainty(channel)
        std = math.sqrt(variance)
        z_scores = {0.90: 1.645, 0.95: 1.96, 0.99: 2.576}
        z = z_scores.get(confidence, 1.96)
        return (max(0.0, p - z * std), min(1.0, p + z * std))

    def get_observations_count(self, channel):
        if channel not in self.channels:
            return 0
        alpha = self.channels[channel]["alpha"]
        beta = self.channels[channel]["beta"]
        return int(alpha + beta - self.prior_alpha - self.prior_beta)

    def select_best_channel(self, channels, exploration_rate=0.1):
        if not channels:
            raise ValueError("Empty channels")
        if len(channels) == 1:
            return channels[0]
        total_obs = sum(self.get_observations_count(c) for c in channels)
        ucb_scores = {}
        for channel in channels:
            p = self.get_probability(channel)
            n = self.get_observations_count(channel)
            if n == 0:
                ucb_scores[channel] = float("inf")
            else:
                exploration = exploration_rate * math.sqrt(2.0 * math.log(max(2, total_obs)) / n)
                ucb_scores[channel] = p + exploration
        return max(ucb_scores.keys(), key=lambda c: ucb_scores[c])

    def get_stats(self):
        return {
            "channels": len(self.channels),
            "details": {ch: {
                "probability": self.get_probability(ch),
                "uncertainty": self.get_uncertainty(ch),
                "observations": self.get_observations_count(ch),
            } for ch in self.channels},
        }

    def reset(self, channel=None):
        if channel:
            self.channels.pop(channel, None)
        else:
            self.channels.clear()

    def __repr__(self):
        return f"BayesianUpdater(channels={len(self.channels)})"


if __name__ == "__main__":
    print("Testing BayesianUpdater...")
    b = BayesianUpdater()
    for _ in range(10):
        b.update("HTTP", True)
    for _ in range(3):
        b.update("HTTP", False)
    print(f"P(HTTP): {b.get_probability('HTTP'):.4f}")
    print(f"Observations: {b.get_observations_count('HTTP')}")
    best = b.select_best_channel(["HTTP", "DNS", "ICMP"])
    print(f"Best (UCB): {best}")
    print("OK")
