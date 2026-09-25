# patch77_78.py - InevioNet: P77 (Audit chain) + P78 (Contextual AI)
#
# P77: audit/chain.py - hash-chain событий (расширение stats_aggregator идеи)
# P78: ai/selector.py - contextual extension (расширение ProtocolSelector)

import os
import ast
import shutil

ROOT = r"E:\InevioNet"
INEV = os.path.join(ROOT, "inevionet")
ORCH = os.path.join(INEV, "orchestrator.py")
APP = os.path.join(ROOT, "web", "app.py")
SELECTOR = os.path.join(INEV, "ai", "selector.py")


def patch_file(path, replacements, label):
    if not os.path.exists(path):
        print("  [!!] NOT FOUND: " + path)
        return False
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    b = path + ".bak_p77_78"
    shutil.copy2(path, b)
    print("  [BK] " + os.path.basename(b))
    changed = 0
    for old, new, required in replacements:
        if new in content and old not in content:
            print("  [--] already applied")
            continue
        if old in content:
            content = content.replace(old, new, 1)
            changed += 1
            print("  [OK] " + old[:50].strip())
        else:
            if required:
                print("  [!!] NOT FOUND: " + old[:50].strip())
    if changed > 0:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        try:
            ast.parse(content)
            print("  [OK] syntax " + label)
            return True
        except SyntaxError as e:
            print("  [!!] syntax: " + str(e))
            shutil.copy2(b, path)
            print("  [--] rolled back")
            return False
    return True


# =====================================================================
# P78: Contextual AI - расширение selector.py
# =====================================================================

print()
print("=" * 70)
print("  P78: Contextual AI extension to selector.py")
print("=" * 70)

P78_CODE = '''

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
'''

# Добавить в конец selector.py
with open(SELECTOR, "r", encoding="utf-8") as f:
    content = f.read()

if "class ContextualSelector" in content:
    print("  [--] P78 already applied")
else:
    content = content.rstrip() + "\n" + P78_CODE + "\n"
    b = SELECTOR + ".bak_p77_78"
    shutil.copy2(SELECTOR, b)
    print("  [BK] " + os.path.basename(b))
    with open(SELECTOR, "w", encoding="utf-8") as f:
        f.write(content)
    try:
        ast.parse(content)
        print("  [OK] ContextualSelector added to ai/selector.py")
    except SyntaxError as e:
        print("  [!!] syntax: " + str(e))
        shutil.copy2(b, SELECTOR)
        print("  [--] rolled back")


# =====================================================================
# P77: Audit chain - новый модуль
# =====================================================================

print()
print("=" * 70)
print("  P77: audit/chain.py (hash-chain событий)")
print("=" * 70)

audit_dir = os.path.join(INEV, "audit")
if not os.path.exists(audit_dir):
    os.makedirs(audit_dir)

# P77a: __init__
p77a = '''"""InevioNet Audit - hash-chain журнал событий сети."""
from .chain import AuditChain, AuditEvent

__all__ = ["AuditChain", "AuditEvent"]
'''

init_path = os.path.join(audit_dir, "__init__.py")
if os.path.exists(init_path):
    with open(init_path, "r", encoding="utf-8") as f:
        existing = f.read()
    if "AuditChain" not in existing:
        b = init_path + ".bak_p77_78"
        shutil.copy2(init_path, b)
        with open(init_path, "w", encoding="utf-8") as f:
            f.write(p77a)
        print("  [OK] audit/__init__.py rewritten")
        print("  [BK] " + os.path.basename(b))
    else:
        print("  [--] audit/__init__.py already ok")
else:
    with open(init_path, "w", encoding="utf-8") as f:
        f.write(p77a)
    print("  [OK] audit/__init__.py created")


# P77b: chain.py
p77b = '''"""InevioNet Audit Chain - append-only журнал событий сети.

Каждое событие имеет hash = SHA256(prev_hash + event + ts + node_id).
Цепочка не блокчейн - нет блоков. Просто события с хэш-ссылками.
Любая подмена ломает цепочку. Verify пересчитывает все хэши.

События:
  - start    - узел стартовал
  - merge    - слита карта соседа
  - sprout   - проращён seed
  - relay    - переслан GDPPacket
  - deploy   - задеплоена капсула
  - punch    - hole punching
  - manual   - ручное событие (для теста)
"""
import os
import time
import json
import hashlib
from dataclasses import dataclass, field, asdict
from typing import List, Dict, Any, Optional

from ..core.logger import get_logger

logger = get_logger("inevionet.audit.chain")


@dataclass
class AuditEvent:
    """Событие в audit-журнале."""
    event_type: str
    node_id: str
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: float = 0.0
    prev_hash: str = ""
    hash: str = ""

    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()

    def compute_hash(self) -> str:
        payload = (
            self.prev_hash +
            self.event_type +
            self.node_id +
            json.dumps(self.data, sort_keys=True) +
            str(self.timestamp)
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def seal(self):
        self.hash = self.compute_hash()

    def verify(self) -> bool:
        return self.hash == self.compute_hash()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, d):
        return cls(**d)


class AuditChain:
    """Append-only hash-chain журнал событий сети."""

    def __init__(self, node_id: str, persist_path: Optional[str] = None,
                 max_events: int = 10000):
        self.node_id = node_id
        self.persist_path = persist_path
        self.max_events = max_events
        self.events: List[AuditEvent] = []
        self._stats = {
            "started_at": time.time(),
            "by_type": {},
        }
        self._load()
        if not self.events:
            self.add_event("start", {"mode": "init"}, initial=True)

    def add_event(self, event_type: str, data: Dict[str, Any],
                  initial: bool = False) -> AuditEvent:
        prev_hash = self.events[-1].hash if self.events else "0" * 64
        ev = AuditEvent(
            event_type=event_type,
            node_id=self.node_id,
            data=data or {},
            prev_hash=prev_hash,
        )
        ev.seal()
        self.events.append(ev)
        self._stats["by_type"][event_type] = self._stats["by_type"].get(event_type, 0) + 1
        if len(self.events) > self.max_events:
            self.events = self.events[-self.max_events:]
        self._save()
        return ev

    def verify(self) -> Dict[str, Any]:
        errors = []
        prev = "0" * 64
        for i, ev in enumerate(self.events):
            if ev.prev_hash != prev:
                errors.append({"index": i, "error": "prev_hash_mismatch"})
            if not ev.verify():
                errors.append({"index": i, "error": "hash_mismatch"})
            prev = ev.hash
        return {
            "valid": len(errors) == 0,
            "events": len(self.events),
            "errors": errors[:10],
        }

    def get_recent(self, n: int = 20) -> List[Dict[str, Any]]:
        return [ev.to_dict() for ev in self.events[-n:]]

    def get_by_type(self, event_type: str, limit: int = 50) -> List[Dict[str, Any]]:
        result = []
        for ev in reversed(self.events):
            if ev.event_type == event_type:
                result.append(ev.to_dict())
                if len(result) >= limit:
                    break
        return result

    def get_stats(self) -> Dict[str, Any]:
        return {
            "events_total": len(self.events),
            "by_type": dict(self._stats["by_type"]),
            "latest_hash": self.events[-1].hash[:16] if self.events else "",
            "genesis_ts": self.events[0].timestamp if self.events else 0,
            "uptime_sec": round(time.time() - self._stats["started_at"], 1),
        }

    def _save(self):
        if not self.persist_path:
            return
        try:
            with open(self.persist_path, "w", encoding="utf-8") as f:
                json.dump({
                    "node_id": self.node_id,
                    "events": [ev.to_dict() for ev in self.events[-1000:]],
                }, f)
        except Exception as e:
            logger.debug("[Audit] save: %s", e)

    def _load(self):
        if not self.persist_path or not os.path.exists(self.persist_path):
            return
        try:
            with open(self.persist_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.events = [AuditEvent.from_dict(d) for d in data.get("events", [])]
            logger.info("[Audit] loaded %d events", len(self.events))
        except Exception as e:
            logger.debug("[Audit] load: %s", e)
'''

chain_path = os.path.join(audit_dir, "chain.py")
if os.path.exists(chain_path):
    b = chain_path + ".bak_p77_78"
    shutil.copy2(chain_path, b)
    print("  [BK] " + os.path.basename(b))
with open(chain_path, "w", encoding="utf-8") as f:
    f.write(p77b)
try:
    ast.parse(p77b)
    print("  [OK] audit/chain.py")
except SyntaxError as e:
    print("  [!!] syntax: " + str(e))


# P77c: orchestrator - создать audit_chain
print()
print("  P77c: orchestrator audit_chain")

anchor_orch_p77 = '''        self.seed = None
        self.seed_url = None
        self.sprout = None
        self.gravity = None'''

repl_orch_p77 = '''        self.seed = None
        self.seed_url = None
        self.sprout = None
        self.gravity = None

        # P77c: audit chain
        self.audit = None
        try:
            from .audit import AuditChain
            _audit_path = None
            try:
                from .core.constants import DataPaths
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
            logger.debug("[P78c] contextual: %s", _e)'''

patch_file(ORCH, [(anchor_orch_p77, repl_orch_p77, True)], "orchestrator.py P77c/P78c")


# P77d: audit в start
print()
print("  P77d: audit start event")

anchor_start_p77 = '''        logger.info(f"InevioNet started: {self.node_id}")'''

repl_start_p77 = '''        # P77d: audit start
        if getattr(self, "audit", None):
            try:
                self.audit.add_event("start", {
                    "mode": self.mode,
                    "public_addr": list(self.public_addr or []),
                    "nat_type": getattr(self, "nat_type", "unknown"),
                })
            except Exception:
                pass

        logger.info(f"InevioNet started: {self.node_id}")'''

patch_file(ORCH, [(anchor_start_p77, repl_start_p77, True)], "orchestrator.py P77d")


# P77e: app.py endpoints
print()
print("  P77e: app.py audit endpoints + ai contextual")

anchor_app_p77 = "@app.route('/api/network/public')"

repl_app_p77 = '''@app.route('/api/audit/log')
def api_audit_log():
    """P77: последние события audit-цепочки."""
    try:
        n = get_net()
        if not getattr(n, "audit", None):
            return jsonify({'success': False, 'error': 'no_audit'})
        limit = int(request.args.get('limit', 20))
        ev_type = request.args.get('type', None)
        if ev_type:
            events = n.audit.get_by_type(ev_type, limit=limit)
        else:
            events = n.audit.get_recent(limit)
        return jsonify({
            'success': True,
            'events': events,
            'stats': n.audit.get_stats(),
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/audit/verify')
def api_audit_verify():
    """P77: проверка целостности audit-цепочки."""
    try:
        n = get_net()
        if not getattr(n, "audit", None):
            return jsonify({'success': False, 'error': 'no_audit'})
        return jsonify({'success': True, **n.audit.verify()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/audit/add', methods=['POST'])
def api_audit_add():
    """P77: добавить событие вручную."""
    try:
        n = get_net()
        if not getattr(n, "audit", None):
            return jsonify({'success': False, 'error': 'no_audit'})
        d = request.get_json(silent=True) or {}
        ev = n.audit.add_event(
            d.get('type', 'manual'),
            d.get('data', {}))
        return jsonify({'success': True, 'hash': ev.hash[:16],
                        'timestamp': ev.timestamp})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai/contextual')
def api_ai_contextual():
    """P78: статистика ContextualSelector."""
    try:
        n = get_net()
        sel = getattr(n, "contextual_selector", None)
        if sel is None:
            return jsonify({'success': True, 'contextual': {},
                            'message': 'not_initialized'})
        return jsonify({'success': True, 'contextual': sel.get_stats()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai/contextual/reset', methods=['POST'])
def api_ai_contextual_reset():
    """P78: сброс ContextualSelector."""
    try:
        n = get_net()
        sel = getattr(n, "contextual_selector", None)
        if sel is not None:
            sel.reset()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/network/public')'''

patch_file(APP, [(anchor_app_p77, repl_app_p77, True)], "app.py P77e/P78b")


# P77f: audit merge в api_network_map
print()
print("  P77f: audit merge")

anchor_merge_p77 = '''    # P73: обновить gravity - from_node имеет массу
    try:
        if getattr(n, "gravity", None):'''

repl_merge_p77 = '''    # P77f: audit merge
    try:
        if getattr(n, "audit", None):
            n.audit.add_event("merge", {
                "from_node": from_node,
                "added_nodes": merged.get('added_nodes', 0),
                "added_edges": merged.get('added_edges', 0),
            })
    except Exception:
        pass

    # P73: обновить gravity - from_node имеет массу
    try:
        if getattr(n, "gravity", None):'''

patch_file(APP, [(anchor_merge_p77, repl_merge_p77, True)], "app.py P77f")


# P77g: audit sprout
print()
print("  P77g: audit sprout")

SPROUT = os.path.join(INEV, "bootstrap", "sprout.py")
anchor_sprout_p77 = '''        # P71b: auto-punch в фоне'''

repl_sprout_p77 = '''        # P77g: audit sprout
        try:
            if getattr(self.orch, "audit", None):
                self.orch.audit.add_event("sprout", {
                    "peer_node": seed.node_id,
                    "peer_addr": host,
                    "nat_type": seed.nat_type,
                })
        except Exception:
            pass

        # P71b: auto-punch в фоне'''

patch_file(SPROUT, [(anchor_sprout_p77, repl_sprout_p77, True)], "sprout.py P77g")


print()
print("=" * 70)
print("  PATCH 77-78 DONE")
print("=" * 70)
print("  [OK] P77: audit/chain.py + endpoints + интеграция")
print("  [OK] P78: ContextualSelector + endpoints")
print()
print("Перезапусти: python -m web.app")
print()
print("Проверка:")
print("  curl -k https://localhost:8080/api/audit/log")
print("  curl -k https://localhost:8080/api/audit/verify")
print("  curl -k https://localhost:8080/api/ai/contextual")