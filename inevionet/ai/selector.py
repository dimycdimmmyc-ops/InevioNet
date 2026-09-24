"""InevioNet AI Protocol Selector — узел сам учится выбирать протокол.

Интегрируется с:
  - EvolutionEngine (GA) — оптимизация параметров
  - BayesianUpdater — обновление вероятностей по сети
  - ChannelSelector — выбор канала маскировки
  - Все имеющиеся в проекте AI-модули

НЕ используется:
  - Внешние API (OpenAI, Anthropic)
  - Новые нейросети (TensorFlow, PyTorch)
  - Всё, чего нет в проекте

Философия:
  - Узел САМ решает, какой протокол использовать
  - Узел САМ учится на каждом успехе/провале
  - Узел САМ делится опытом через SuperNode
"""
import time
import random
import logging
import threading
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict

try:
    from ..core.logger import get_logger
    log = get_logger("inevionet.ai.selector")
except ImportError:
    log = logging.getLogger("inevionet.ai.selector")


# ==============================================================
# PROTOCOL SCORING
# ==============================================================
class ProtocolScore:
    """Счёт протокола для конкретной цели."""

    def __init__(self, protocol: str):
        self.protocol = protocol
        self.attempts = 0
        self.successes = 0
        self.total_latency_ms = 0.0
        self.last_attempt_ts = 0.0
        self.last_success_ts = 0.0

    @property
    def success_rate(self) -> float:
        if self.attempts == 0:
            return 0.5  # оптимистичный старт
        return self.successes / self.attempts

    @property
    def avg_latency_ms(self) -> float:
        if self.successes == 0:
            return 0.0
        return self.total_latency_ms / self.successes

    def record(self, success: bool, latency_ms: float = 0.0):
        self.attempts += 1
        self.last_attempt_ts = time.time()
        if success:
            self.successes += 1
            self.total_latency_ms += latency_ms
            self.last_success_ts = time.time()

    def score(self) -> float:
        """Итоговый счёт. Больше = лучше.

        Формула (использует Bayesian + latency):
          base = (successes + 1) / (attempts + 2)   ← Laplace smoothing
          latency_bonus = 1 / (1 + avg_latency_ms / 1000)
          freshness = 1 / (1 + (now - last_success) / 300)
        """
        base = (self.successes + 1) / (self.attempts + 2)
        latency_bonus = 1.0 / (1.0 + self.avg_latency_ms / 1000.0)
        if self.last_success_ts > 0:
            age = time.time() - self.last_success_ts
            freshness = 1.0 / (1.0 + age / 300.0)
        else:
            freshness = 0.5
        return base * (0.7 + 0.2 * latency_bonus + 0.1 * freshness)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "protocol": self.protocol,
            "attempts": self.attempts,
            "successes": self.successes,
            "success_rate": round(self.success_rate, 4),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "score": round(self.score(), 4),
        }


# ==============================================================
# PROTOCOL SELECTOR
# ==============================================================
class ProtocolSelector:
    """Выбор протокола на основе обучения.

    Ключ обучения: receiver (node_id / IP / SSID).
    Для каждого получателя ведём статистику по каждому протоколу.
    Учимся на каждом результате.
    """

    DEFAULT_PROTOCOLS = [
        "HTTPS", "DNS", "HTTP", "ICMP", "WebSocket",
        "MQTT", "MODBUS", "DNP3", "OPCUA",
    ]

    def __init__(self, evolution_engine=None, bayesian=None, exploration_rate: float = 0.1):
        self.evolution = evolution_engine
        self.bayesian = bayesian
        self.exploration_rate = exploration_rate

        # receiver → protocol → ProtocolScore
        self._scores: Dict[str, Dict[str, ProtocolScore]] = defaultdict(dict)
        self._lock = threading.RLock()

        # общая статистика
        self._stats = {
            "total_selections": 0,
            "total_records": 0,
            "unique_targets": 0,
        }

    # ----------------------------------------------------------
    # SELECT
    # ----------------------------------------------------------
    def select(self, receiver: str = None,
               protocols: Optional[List[str]] = None) -> str:
        """Выбрать лучший протокол для получателя.

        Логика:
          1. Если для receiver есть история — выбираем лучший по score
          2. Если истории нет — используем exploration (random из top-3)
          3. Если ничего — возвращаем HTTPS
        """
        with self._lock:
            self._stats["total_selections"] += 1

        if receiver is None:
            receiver = "__default__"

        if protocols is None:
            protocols = self._protocols_for(receiver)

        if not protocols:
            return "HTTPS"

        # exploration vs exploitation
        if random.random() < self.exploration_rate:
            return random.choice(protocols)

        # сортируем по score
        scored = []
        with self._lock:
            for proto in protocols:
                sc = self._scores.get(receiver, {}).get(proto)
                if sc is None:
                    # Новый протокол — даём шанс (оптимистичный старт 0.5)
                    scored.append((proto, 0.5))
                else:
                    scored.append((proto, sc.score()))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0][0]

    def _protocols_for(self, receiver: str) -> List[str]:
        """Список протоколов, которые уже известны для получателя."""
        with self._lock:
            if receiver in self._scores and self._scores[receiver]:
                return list(self._scores[receiver].keys())
        # нет истории — берём все доступные
        return list(self.DEFAULT_PROTOCOLS)

    def select_top_n(self, receiver: str = None, n: int = 3) -> List[str]:
        """Топ-N протоколов для получателя (для рекурсивного перебора)."""
        if receiver is None:
            receiver = "__default__"
        with self._lock:
            scores = self._scores.get(receiver, {})
            if not scores:
                return list(self.DEFAULT_PROTOCOLS[:n])
            scored = [(p, s.score()) for p, s in scores.items()]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [p for p, _ in scored[:n]]

    # ----------------------------------------------------------
    # RECORD
    # ----------------------------------------------------------
    def record_success(self, receiver: str, protocol: str, latency_ms: float = 0.0):
        """Записать успех."""
        self._record(receiver, protocol, True, latency_ms)

    def record_failure(self, receiver: str, protocol: str):
        """Записать провал."""
        self._record(receiver, protocol, False)

    def _record(self, receiver: str, protocol: str, success: bool, latency_ms: float):
        if not receiver:
            receiver = "__default__"
        with self._lock:
            if protocol not in self._scores[receiver]:
                self._scores[receiver][protocol] = ProtocolScore(protocol)
            self._scores[receiver][protocol].record(success, latency_ms)
            self._stats["total_records"] += 1
            self._stats["unique_targets"] = len(self._scores)

            # Синхронизация с Bayesian
            if self.bayesian is not None:
                try:
                    key = f"{receiver}:{protocol}"
                    self.bayesian.update(key, success)
                except Exception as e:
                    log.debug("[selector] bayesian update: %s", e)

        log.debug("[selector] %s → %s: %s (%.1fms)",
                  receiver, protocol, "OK" if success else "FAIL", latency_ms)

    # ----------------------------------------------------------
    # STATS
    # ----------------------------------------------------------
    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            total_targets = len(self._scores)
            total_protocols = sum(len(v) for v in self._scores.values())
            best_protocol = None
            best_score = 0.0
            for receiver, protos in self._scores.items():
                for proto, sc in protos.items():
                    s = sc.score()
                    if s > best_score:
                        best_score = s
                        best_protocol = proto
            return {
                **self._stats,
                "total_protocols_known": total_protocols,
                "best_protocol": best_protocol,
                "best_score": round(best_score, 4),
            }

    def get_all_protocol_stats(self) -> List[Dict[str, Any]]:
        """Все протоколы со статистикой (для UI)."""
        result = []
        with self._lock:
            # Агрегируем по протоколу через всех получателей
            agg: Dict[str, Dict[str, float]] = defaultdict(lambda: {"attempts": 0, "successes": 0, "latency": 0.0})
            for receiver, protos in self._scores.items():
                for proto, sc in protos.items():
                    agg[proto]["attempts"] += sc.attempts
                    agg[proto]["successes"] += sc.successes
                    agg[proto]["latency"] += sc.total_latency_ms
            for proto, data in agg.items():
                attempts = data["attempts"]
                successes = data["successes"]
                result.append({
                    "protocol": proto,
                    "attempts": attempts,
                    "successes": successes,
                    "success_rate": round(successes / attempts, 4) if attempts else 0.0,
                    "avg_latency_ms": round(data["latency"] / successes, 2) if successes else 0.0,
                })
        result.sort(key=lambda x: (-x["success_rate"], -x["successes"]))
        return result

    def reset(self, receiver: str = None):
        with self._lock:
            if receiver:
                self._scores.pop(receiver, None)
            else:
                self._scores.clear()

    def __repr__(self):
        return f"ProtocolSelector(targets={len(self._scores)})"


# ==============================================================
# ADAPTIVE SENDER — интеграция с send_with_guarantee
# ==============================================================
class AdaptiveSender:
    """Узел САМ выбирает протокол для каждого получателя.

    Не требует ручного управления. Учится на каждом пакете.
    """

    def __init__(self, transport, selector: ProtocolSelector, bayesian=None):
        self.transport = transport
        self.selector = selector
        self.bayesian = bayesian
        self._stats = {
            "sent": 0,
            "delivered": 0,
            "failed": 0,
        }
        self._lock = threading.RLock()

    def send_adaptive(self, receiver: str, data: bytes,
                      max_attempts: int = 5) -> Tuple[bool, str, float]:
        """Отправить data получателю, перебирая протоколы.

        Возвращает (success, protocol, latency_ms).
        """
        # 1. Топ-N протоколов для получателя
        protocols = self.selector.select_top_n(receiver, n=max_attempts)
        if not protocols:
            protocols = list(ProtocolSelector.DEFAULT_PROTOCOLS[:max_attempts])

        last_error = ""
        for proto in protocols:
            t0 = time.time()
            try:
                result = self.transport.send(data, protocol=proto, target=receiver)
                latency_ms = (time.time() - t0) * 1000
                if result.success:
                    self.selector.record_success(receiver, proto, latency_ms)
                    with self._lock:
                        self._stats["sent"] += 1
                        self._stats["delivered"] += 1
                    return True, proto, latency_ms
                else:
                    self.selector.record_failure(receiver, proto)
                    last_error = result.error or "unknown"
            except Exception as e:
                self.selector.record_failure(receiver, proto)
                last_error = str(e)

        with self._lock:
            self._stats["sent"] += 1
            self._stats["failed"] += 1
        return False, "", 0.0

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            stats = dict(self._stats)
        rate = 0.0
        if stats["sent"] > 0:
            rate = stats["delivered"] / stats["sent"]
        stats["delivery_rate"] = round(rate, 4)
        return stats


if __name__ == "__main__":
    print("Testing ProtocolSelector...")
    sel = ProtocolSelector()

    # симулируем обучение
    for i in range(5):
        sel.record_success("receiver_1", "HTTPS", 50.0)
    for i in range(5):
        sel.record_failure("receiver_1", "DNS")

    print("Stats:", sel.get_stats())
    print("Best protocol for receiver_1:", sel.select("receiver_1"))
    print("Top-3:", sel.select_top_n("receiver_1", n=3))
    print("All stats:", sel.get_all_protocol_stats())
    print("OK")


# ==============================================================
# P78: CONTEXTUAL SELECTOR (расширение)
# ==============================================================
class ContextualScore:
    """ProtocolScore + контекст (nat_type, dpi_profile, target_type).

    Использует тот же Laplace-smoothing, что и ProtocolScore,
    но учитывает контекст. Наследуется для совместимости.
    """

    def __init__(self, protocol: str, context: dict = None):
        self.protocol = protocol
        self.context = context or {}
        self.attempts = 0
        self.successes = 0
        self.total_latency_ms = 0.0
        self.last_success_ts = 0.0

    @property
    def success_rate(self) -> float:
        if self.attempts == 0:
            return 0.5
        return self.successes / self.attempts

    @property
    def avg_latency_ms(self) -> float:
        if self.successes == 0:
            return 0.0
        return self.total_latency_ms / self.successes

    def record(self, success: bool, latency_ms: float = 0.0):
        self.attempts += 1
        if success:
            self.successes += 1
            self.total_latency_ms += latency_ms
            self.last_success_ts = time.time()

    def score(self) -> float:
        base = (self.successes + 1) / (self.attempts + 2)
        latency_bonus = 1.0 / (1.0 + self.avg_latency_ms / 1000.0)
        if self.last_success_ts > 0:
            age = time.time() - self.last_success_ts
            freshness = 1.0 / (1.0 + age / 300.0)
        else:
            freshness = 0.5
        return base * (0.7 + 0.2 * latency_bonus + 0.1 * freshness)

    def to_dict(self):
        return {
            "protocol": self.protocol,
            "context": self.context,
            "attempts": self.attempts,
            "successes": self.successes,
            "success_rate": round(self.success_rate, 4),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "score": round(self.score(), 4),
        }


class ContextualSelector:
    """Контекстный селектор - расширение ProtocolSelector.

    Хранит статистику по (context_key, protocol).
    Контекст: nat_type, dpi_profile, target_type.
    """

    def __init__(self, base_selector=None, exploration_rate=0.15):
        self.base = base_selector
        self.exploration_rate = exploration_rate
        self._context_scores = defaultdict(dict)
        self._lock = threading.RLock()
        self._stats = {
            "contexts": 0,
            "total_records": 0,
            "total_selections": 0,
        }

    @staticmethod
    def _context_key(context: dict) -> str:
        if not context:
            return "default"
        parts = []
        for k in sorted(context.keys()):
            parts.append(f"{k}={context[k]}")
        return "|".join(parts)

    def select(self, receiver: str, context: dict = None,
               protocols=None) -> str:
        if protocols is None:
            if self.base is not None:
                protocols = self.base._protocols_for(receiver)
            else:
                protocols = list(ProtocolSelector.DEFAULT_PROTOCOLS)
        if not protocols:
            return "HTTPS"

        with self._lock:
            self._stats["total_selections"] += 1

        key = self._context_key(context)

        if random.random() < self.exploration_rate:
            return random.choice(protocols)

        with self._lock:
            scores = self._context_scores.get(key, {})
            scored = []
            for p in protocols:
                sc = scores.get(p)
                scored.append((p, sc.score() if sc else 0.5))
        scored.sort(key=lambda x: x[1], reverse=True)
        return scored[0][0]

    def record(self, receiver: str, protocol: str, context: dict,
               success: bool, latency_ms: float = 0.0):
        key = self._context_key(context)
        with self._lock:
            if protocol not in self._context_scores[key]:
                self._context_scores[key][protocol] = ContextualScore(
                    protocol, context)
            self._context_scores[key][protocol].record(success, latency_ms)
            self._stats["total_records"] += 1
            self._stats["contexts"] = len(self._context_scores)

        # также обновить базовый
        if self.base is not None:
            if success:
                self.base.record_success(receiver, protocol, latency_ms)
            else:
                self.base.record_failure(receiver, protocol)

    def get_stats(self) -> dict:
        with self._lock:
            by_ctx = {}
            for key, arms in self._context_scores.items():
                by_ctx[key] = {
                    p: sc.to_dict() for p, sc in arms.items()
                }
            return {
                **self._stats,
                "by_context": by_ctx,
            }

    def reset(self):
        with self._lock:
            self._context_scores.clear()
            self._stats = {"contexts": 0, "total_records": 0,
                           "total_selections": 0}

