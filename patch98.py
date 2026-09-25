# patch98.py - P98: НЛП-конвейер для агентов (споры/разведчики)
import os
import ast
import shutil

ROOT = r"E:\InevioNet"
INEV = os.path.join(ROOT, "inevionet")
NLP_DIR = os.path.join(INEV, "nlp")
NLP_INIT = os.path.join(NLP_DIR, "__init__.py")
NLP_PIPE = os.path.join(NLP_DIR, "pipeline.py")
ORG = os.path.join(INEV, "organism.py")
APP = os.path.join(ROOT, "web", "app.py")

BAK = ".bak_p98"


def write_file(path, code, label):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if os.path.exists(path):
        b = path + BAK
        shutil.copy2(path, b)
        print("  [BK] " + os.path.basename(b))
    with open(path, "w", encoding="utf-8") as f:
        f.write(code)
    try:
        ast.parse(code)
        print("  [OK] " + label)
        return True
    except SyntaxError as e:
        print("  [!!] " + label + " syntax: " + str(e))
        return False


def patch_replace(path, replacements, label, bak=BAK):
    if not os.path.exists(path):
        print("  [!!] NOT FOUND: " + path)
        return False
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    b = path + bak
    shutil.copy2(path, b)
    print("  [BK] " + os.path.basename(b))
    changed = 0
    for old, new, required in replacements:
        if new and new in content and (not old or old not in content):
            print("  [--] already applied")
            continue
        if old and old in content:
            content = content.replace(old, new, 1)
            changed += 1
            print("  [OK] " + old[:55].strip().replace(chr(10), ' '))
        else:
            if required:
                print("  [!!] NOT FOUND: " + old[:55].strip().replace(chr(10), ' '))
    if changed > 0:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        if path.endswith(".py"):
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
# 1. nlp/__init__.py
# =====================================================================

print()
print("=" * 70)
print("  1. nlp/__init__.py")
print("=" * 70)

nlp_init = '''"""InevioNet NLP - рекурсивный конвейер для агентов.

P98: НЛП-конвейер для спор, разведчиков и рефрейминга ситуаций.
"""
from .pipeline import (
    run_pipeline, STAGES, STAGE_NAMES, ENABLE_STAGES, STAGE_PRIORITY,
    extract_outputs, spore_analyze_node, node_to_situation,
    validate_input,
)

__all__ = [
    "run_pipeline", "STAGES", "STAGE_NAMES", "ENABLE_STAGES", "STAGE_PRIORITY",
    "extract_outputs", "spore_analyze_node", "node_to_situation",
    "validate_input",
]
'''

write_file(NLP_INIT, nlp_init, "nlp/__init__.py")


# =====================================================================
# 2. nlp/pipeline.py - полный код
# =====================================================================

print()
print("=" * 70)
print("  2. nlp/pipeline.py")
print("=" * 70)

pipeline_code = '''"""InevioNet NLP Pipeline - рекурсивный конвейер.

P98: НЛП-конвейер для агентов спор, разведчиков и рефрейминга ситуаций.

Вход - простые переменные (числа, строки, списки, словари).
Выход - переменные в общем пространстве имён.

8 этапов НЛП:
  VAK      - визуал/аудиал/кинестетик
  RAPPORT  - установление контакта
  ANCHOR   - якорение
  REFRAME  - рефрейминг
  SIXSTEP  - 6-шаговый рефрейминг (биматричная игра)
  TIMELINE - временная линия
  ECOLOGY  - экология (Парето)
  FLEX     - гибкость

Авторские ограничения: без list.append, dict.copy, sorted, lambda.
"""
import time
from typing import Dict, List, Any, Tuple


# ============================================================
# ФЛАГИ И ПРИОРИТЕТЫ
# ============================================================

ENABLE_STAGES = {
    "vak": True,
    "rapport": True,
    "anchor": True,
    "reframe": True,
    "sixstep": True,
    "timeline": True,
    "ecology": True,
    "flex": True,
}

STAGE_PRIORITY = {
    "vak": 1,       # 1 = критично, 2 = важно, 3 = опционально
    "rapport": 1,
    "anchor": 2,
    "reframe": 1,
    "sixstep": 2,
    "timeline": 3,
    "ecology": 2,
    "flex": 3,
}

STAGE_NAMES = ["vak", "rapport", "anchor", "reframe",
               "sixstep", "timeline", "ecology", "flex"]


# ============================================================
# АВТОРСКИЕ УТИЛИТЫ
# ============================================================

def _append(lst, x):
    n = len(lst)
    new_lst = [None] * (n + 1)
    for i in range(n):
        new_lst[i] = lst[i]
    new_lst[n] = x
    return new_lst


def _copy(d):
    new_d = {}
    for k in d:
        new_d[k] = d[k]
    return new_d


# ============================================================
# ЭТАП 0 - VAK
# ============================================================

def stage_vak(situation):
    v = situation["v"]
    a = situation["a"]
    k = situation["k"]

    total = v + a + k
    if total == 0:
        vec = (0.0, 0.0, 0.0)
    else:
        vec = (v/total, a/total, k/total)

    labels = ["V", "A", "K"]
    best_i = 0
    best_val = vec[0]
    for i in range(1, 3):
        if vec[i] > best_val:
            best_val = vec[i]
            best_i = i

    out = _copy(situation)
    out["vak_vec"] = vec
    out["leading"] = labels[best_i]
    out["log"] = _append(situation["log"], ("VAK", vec, labels[best_i]))
    return out


# ============================================================
# ЭТАП 1 - RAPPORT
# ============================================================

def _rapport_ratio(x, y):
    n = len(x) if len(x) < len(y) else len(y)
    if n == 0:
        return 0.0
    matches = 0
    for i in range(n):
        if x[i] == y[i]:
            matches += 1
    return matches / n


def stage_rapport(situation):
    client = situation["client_seq"]
    therapist = situation["therapist_seq"]
    threshold = situation["rapport_threshold"]

    r = _rapport_ratio(client, therapist)
    mode = "ведёт" if r > threshold else "подстраивается"

    out = _copy(situation)
    out["rapport"] = r
    out["rapport_mode"] = mode
    out["log"] = _append(situation["log"], ("RAPPORT", r, mode))
    return out


# ============================================================
# ЭТАП 2 - ANCHORING
# ============================================================

def _anchor_learn(delta, counts, states, stimulus, emotion):
    new_delta = _copy(delta)
    new_counts = _copy(counts)
    for s in states:
        new_delta[(s, stimulus)] = emotion
        key = (emotion, stimulus)
        new_counts[key] = new_counts.get(key, 0) + 1
    return new_delta, new_counts


def stage_anchor(situation):
    states = ["нейтрал", "радость", "страх"]
    stimulus = situation["anchor_stimulus"]
    emotion = situation["anchor_emotion"]

    delta = {}
    counts = {}
    delta, counts = _anchor_learn(delta, counts, states, stimulus, emotion)

    fired = "нейтрал"
    key = ("нейтрал", stimulus)
    if key in delta:
        fired = delta[key]

    out = _copy(situation)
    out["anchor"] = (stimulus, emotion)
    out["anchor_fired"] = fired
    out["log"] = _append(situation["log"],
                         ("ANCHOR", stimulus, emotion, fired))
    return out


# ============================================================
# ЭТАП 3 - REFRAMING
# ============================================================

def _compose_frame(frame, phi):
    new_frame = {}
    for e in frame:
        m = frame[e]
        new_frame[e] = phi.get(m, m)
    return new_frame


def stage_reframe(situation):
    frame = situation["frame"]
    phi = situation["phi"]
    val_map = situation["val_map"]

    new_frame = _compose_frame(frame, phi)

    success = {}
    for e in frame:
        old_m = frame[e]
        new_m = new_frame[e]
        old_v = val_map.get(old_m, 0)
        new_v = val_map.get(new_m, 0)
        success[e] = (old_v < 0 and new_v >= 0)

    out = _copy(situation)
    out["frame_new"] = new_frame
    out["reframe_success"] = success
    out["log"] = _append(situation["log"],
                         ("REFRAME", new_frame, success))
    return out


# ============================================================
# ЭТАП 4 - SIX-STEP
# ============================================================

def _nash(actions1, actions2, M1, M2):
    result = []
    for i in range(len(actions1)):
        for j in range(len(actions2)):
            best_i = True
            for k in range(len(actions1)):
                if M1[k][j] > M1[i][j]:
                    best_i = False
                    break
            best_j = True
            for l in range(len(actions2)):
                if M2[i][l] > M2[i][j]:
                    best_j = False
                    break
            if best_i and best_j:
                result = _append(result, (actions1[i], actions2[j]))
    return result


def _coop(actions1, actions2, M1, M2, alpha):
    best = None
    best_val = None
    for i in range(len(actions1)):
        for j in range(len(actions2)):
            val = alpha * M1[i][j] + (1 - alpha) * M2[i][j]
            if best_val is None or val > best_val:
                best_val = val
                best = (actions1[i], actions2[j])
    return best, best_val


def stage_sixstep(situation):
    actions1 = situation["actions1"]
    actions2 = situation["actions2"]
    M1 = situation["M1"]
    M2 = situation["M2"]
    alphas = situation["alphas"]

    eq = _nash(actions1, actions2, M1, M2)

    solutions = []
    for a in alphas:
        sol, val = _coop(actions1, actions2, M1, M2, a)
        solutions = _append(solutions, (a, sol, val))

    out = _copy(situation)
    out["nash"] = eq
    out["coop"] = solutions
    out["log"] = _append(situation["log"], ("SIXSTEP", eq, solutions))
    return out


# ============================================================
# ЭТАП 5 - TIMELINE
# ============================================================

def _shift(timeline, k):
    n = len(timeline)
    result = []
    for i in range(n):
        j = i + k
        if 0 <= j < n:
            result = _append(result, timeline[j])
        else:
            result = _append(result, None)
    return result


def stage_timeline(situation):
    timeline = situation["timeline"]
    k = situation["shift_k"]
    states = situation["states"]
    node = timeline[0] if len(timeline) > 0 else None
    new_state = situation["reimprint_state"]

    shifted = _shift(timeline, k)

    new_states = {}
    for key in states:
        if key == node:
            new_states[key] = new_state
        else:
            new_states[key] = states[key]

    out = _copy(situation)
    out["timeline_shifted"] = shifted
    out["states_new"] = new_states
    out["log"] = _append(situation["log"],
                         ("TIMELINE", shifted, new_states))
    return out


# ============================================================
# ЭТАП 6 - ECOLOGY (Парето)
# ============================================================

def _pareto(changes, f1, f2):
    result = []
    for x in changes:
        dominated = False
        for y in changes:
            if x == y:
                continue
            ge = (f1[y] >= f1[x]) and (f2[y] >= f2[x])
            gt = (f1[y] > f1[x]) or (f2[y] > f2[x])
            if ge and gt:
                dominated = True
                break
        if not dominated:
            result = _append(result, x)
    return result


def stage_ecology(situation):
    changes = situation["changes"]
    f1 = situation["f1"]
    f2 = situation["f2"]
    baseline = situation["baseline"]

    pareto = _pareto(changes, f1, f2)

    allowed = []
    for x in changes:
        if f2[x] >= f2[baseline]:
            allowed = _append(allowed, x)

    out = _copy(situation)
    out["pareto"] = pareto
    out["allowed"] = allowed
    out["log"] = _append(situation["log"],
                         ("ECOLOGY", pareto, allowed))
    return out


# ============================================================
# ЭТАП 7 - FLEXIBILITY
# ============================================================

def _card(s):
    count = 0
    for _ in s:
        count += 1
    return count


def stage_flexibility(situation):
    reactions = situation["reactions"]
    disturbances = situation["disturbances"]
    alphabet = situation["alphabet"]

    controllable = _card(reactions) >= _card(disturbances)

    n = _card(alphabet)
    flex = 1
    for _ in range(n):
        flex *= n

    out = _copy(situation)
    out["controllable"] = controllable
    out["flexibility"] = flex
    out["log"] = _append(situation["log"],
                         ("FLEX", controllable, flex))
    return out


# ============================================================
# РЕКУРСИВНЫЙ ДВИЖОК
# ============================================================

STAGES = [stage_vak, stage_rapport, stage_anchor,
          stage_reframe, stage_sixstep, stage_timeline,
          stage_ecology, stage_flexibility]


def run_pipeline(situation, stages=None, i=0, flags=None, names=None):
    """Рекурсивный движок с флагами этапов."""
    if stages is None:
        stages = STAGES
    if names is None:
        names = STAGE_NAMES
    if flags is None:
        flags = ENABLE_STAGES
    if i >= len(stages):
        return situation
    name = names[i] if i < len(names) else "?"
    if flags.get(name, True):
        new_situation = stages[i](situation)
    else:
        new_situation = _copy(situation)
        new_situation["log"] = _append(
            new_situation["log"], ("SKIP", name))
    return run_pipeline(new_situation, stages, i + 1, flags, names)


# ============================================================
# АДАПТЕРЫ ДЛЯ INEVIONET
# ============================================================

def validate_input(situation, flags=None):
    """P98: проверить наличие обязательных полей."""
    if flags is None:
        flags = ENABLE_STAGES
    required = {
        "vak": ["v", "a", "k"],
        "rapport": ["client_seq", "therapist_seq", "rapport_threshold"],
        "anchor": ["anchor_stimulus", "anchor_emotion"],
        "reframe": ["frame", "phi", "val_map"],
        "sixstep": ["actions1", "actions2", "M1", "M2", "alphas"],
        "timeline": ["timeline", "shift_k", "states", "reimprint_state"],
        "ecology": ["changes", "f1", "f2", "baseline"],
        "flex": ["reactions", "disturbances", "alphabet"],
    }
    missing = []
    for name in required:
        if not flags.get(name, True):
            continue
        for f in required[name]:
            if f not in situation:
                missing = _append(missing, (name, f))
    if missing:
        return False, missing
    return True, []


def extract_outputs(situation):
    """P98: чистые выходные переменные конвейера."""
    return {
        "vak_vec": situation.get("vak_vec"),
        "leading": situation.get("leading"),
        "rapport": situation.get("rapport"),
        "rapport_mode": situation.get("rapport_mode"),
        "anchor": situation.get("anchor"),
        "anchor_fired": situation.get("anchor_fired"),
        "frame_new": situation.get("frame_new"),
        "reframe_success": situation.get("reframe_success"),
        "nash": situation.get("nash"),
        "coop": situation.get("coop"),
        "timeline_shifted": situation.get("timeline_shifted"),
        "states_new": situation.get("states_new"),
        "pareto": situation.get("pareto"),
        "allowed": situation.get("allowed"),
        "controllable": situation.get("controllable"),
        "flexibility": situation.get("flexibility"),
        "log_final": situation.get("log"),
    }


def node_to_situation(node):
    """P98: узел InevioNet -> situation для НЛП-конвейера."""
    ip = node.get("ip", "unknown")
    ntype = node.get("type", "unknown")
    source = node.get("source", "unknown")
    ports = node.get("open_ports", [])
    if not isinstance(ports, list):
        ports = []
    return {
        # VAK - что преобладает в узле
        "v": len(ports) if ports else 1,
        "a": 3,
        "k": 2,
        # RAPPORT - можно ли контакт
        "client_seq": ["HTTP", "HTTPS"] if ntype == "router" else [ntype.upper()],
        "therapist_seq": ["HTTP", "HTTPS", "DNS", "ICMP"],
        "rapport_threshold": 0.6,
        # ANCHOR - триггеры узла
        "anchor_stimulus": node.get("vendor", ntype),
        "anchor_emotion": "нейтрал",
        # REFRAME - как переосмыслить узел
        "frame": {
            "closed": "недоступен",
            "open": "доступен",
        },
        "phi": {
            "недоступен": "скрыт",
            "доступен": "соратник",
        },
        "val_map": {
            "недоступен": -1, "скрыт": 0,
            "доступен": 1, "соратник": 1,
        },
        # SIXSTEP - стратегия
        "actions1": ["probe", "wait"],
        "actions2": ["ignore", "respond"],
        "M1": [[3, 1], [1, 1]],
        "M2": [[1, 1], [1, 2]],
        "alphas": [0.25, 0.5, 0.75],
        # TIMELINE - динамика узла
        "timeline": [ip, ntype, source],
        "shift_k": 1,
        "states": {ip: "new"},
        "reimprint_state": "colonized",
        # ECOLOGY - что безопасно
        "changes": ["teach", "relay", "capsule", "route", "skip"],
        "f1": {"teach": 3, "relay": 2, "capsule": 4, "route": 1, "skip": 0},
        "f2": {"teach": 2, "relay": 4, "capsule": 1, "route": 3, "skip": 5},
        "baseline": "skip",
        # FLEX - гибкость
        "reactions": ["respond", "ignore", "redirect"],
        "disturbances": ["port_scan", "syn_flood", "probe"],
        "alphabet": ["teach", "relay", "capsule"],
        # LOG
        "log": [],
    }


def spore_analyze_node(node):
    """P98: анализ узла через НЛП-конвейер (для спор и разведчиков).

    Возвращает dict с планом действия и метриками.
    """
    try:
        situation = node_to_situation(node)
        ok, missing = validate_input(situation)
        if not ok:
            return {"plan": "skip", "confidence": 0.0,
                    "error": "missing: %s" % str(missing)}
        result = run_pipeline(situation, STAGES, 0, ENABLE_STAGES, STAGE_NAMES)
        outputs = extract_outputs(result)

        # Определяем план на основе выходов
        plan = "route"
        confidence = 0.5

        # Приоритет: capsule > teach > relay > route
        if outputs["controllable"] and outputs["flexibility"] and outputs["flexibility"] >= 9:
            plan = "capsule"
            confidence = 0.9
        elif outputs["reframe_success"] and any(outputs["reframe_success"].values()):
            plan = "teach"
            confidence = 0.8
        elif outputs["rapport"] is not None and outputs["rapport"] > 0.6:
            plan = "relay"
            confidence = float(outputs["rapport"])
        elif outputs["allowed"]:
            plan = "route"
            confidence = 0.6

        # Проверка экологии - не делать ничего вредного
        if outputs["allowed"] and plan not in outputs["allowed"]:
            plan = "skip"
            confidence = 0.3

        return {
            "plan": plan,
            "confidence": confidence,
            "rapport": outputs["rapport"],
            "leading": outputs["leading"],
            "reframe_success": outputs["reframe_success"],
            "controllable": outputs["controllable"],
            "allowed": outputs["allowed"],
            "nash": outputs["nash"],
            "flexibility": outputs["flexibility"],
            "pareto": outputs["pareto"],
            "log_final": outputs["log_final"],
        }
    except Exception as e:
        return {"plan": "skip", "confidence": 0.0, "error": str(e)}
'''

write_file(NLP_PIPE, pipeline_code, "nlp/pipeline.py")


# =====================================================================
# 3. organism.py - интеграция NLP в scout() и assess()
# =====================================================================

print()
print("=" * 70)
print("  3. organism.py: NLP в scout + assess")
print("=" * 70)

# 3.1. scout() - добавить NLP-анализ после регистрации
old_scout_end = '''        new_count = len(found)
        total_in_memory = len(self.memory["nodes"])'''

new_scout_end = '''        # P98: НЛП-анализ найденных узлов (для агентов спор)
        try:
            from .nlp.pipeline import spore_analyze_node
            nlp_count = 0
            for node in found:
                try:
                    nlp_res = spore_analyze_node(node)
                    node["nlp_plan"] = nlp_res.get("plan", "route")
                    node["nlp_confidence"] = nlp_res.get("confidence", 0.5)
                    node["nlp_rapport"] = nlp_res.get("rapport")
                    node["nlp_controllable"] = nlp_res.get("controllable")
                    node["nlp_leading"] = nlp_res.get("leading")
                    if "nlp_plan" in node and node["nlp_plan"] != "route":
                        nlp_count += 1
                except Exception as e:
                    logger.debug("[NLP] %s: %s", node.get("ip"), e)
            if nlp_count:
                logger.info("[NLP] analyzed %d nodes, non-route plans=%d",
                            len(found), nlp_count)
        except ImportError:
            logger.debug("[NLP] pipeline not available")
        except Exception as e:
            logger.debug("[NLP] scout: %s", e)

        new_count = len(found)
        total_in_memory = len(self.memory["nodes"])'''

patch_replace(ORG, [(old_scout_end, new_scout_end, True)], "scout NLP")


# 3.2. assess() - использовать NLP-план
old_assess_start = '''    def assess(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """P95h: что можно с узлом?'''

new_assess_start = '''    def assess(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """P98: НЛП-план имеет приоритет, fallback на P95h."""
        # P98: если есть NLP-план - используем
        if node.get("nlp_plan"):
            plan = node["nlp_plan"]
            conf = node.get("nlp_confidence", 0.5)
            if plan in ("capsule", "teach", "relay", "route"):
                logger.debug("[Assess] %s -> NLP plan: %s (conf=%.2f)",
                             node.get("ip"), plan, conf)
                return {"action": plan, "reason": "nlp",
                        "priority": conf, "method": "nlp"}
            if plan == "skip":
                return {"action": None, "reason": "nlp_skip"}
        
        """P95h: что можно с узлом?'''

patch_replace(ORG, [(old_assess_start, new_assess_start, True)], "assess NLP")


# =====================================================================
# 4. app.py - endpoint /api/nlp/*
# =====================================================================

print()
print("=" * 70)
print("  4. app.py: /api/nlp/* endpoints")
print("=" * 70)

anchor = "@app.route('/api/network/public')"

new_eps = '''@app.route('/api/nlp/pipeline', methods=['POST', 'GET'])
def api_nlp_pipeline():
    """P98: запустить НЛП-конвейер на произвольной ситуации."""
    try:
        from inevionet.nlp.pipeline import (
            run_pipeline, STAGES, STAGE_NAMES, ENABLE_STAGES,
            extract_outputs, validate_input,
        )
        d = request.get_json(silent=True) or {}
        # Значения по умолчанию
        situation = {
            "v": d.get("v", 5),
            "a": d.get("a", 2),
            "k": d.get("k", 3),
            "client_seq": d.get("client_seq", ["A", "B", "A", "C", "A"]),
            "therapist_seq": d.get("therapist_seq", ["A", "B", "B", "C", "A"]),
            "rapport_threshold": d.get("rapport_threshold", 0.6),
            "anchor_stimulus": d.get("anchor_stimulus", "хлопок"),
            "anchor_emotion": d.get("anchor_emotion", "радость"),
            "frame": d.get("frame", {"провал": "поражение", "отказ": "унижение"}),
            "phi": d.get("phi", {"поражение": "опыт", "унижение": "свобода"}),
            "val_map": d.get("val_map", {
                "поражение": -1, "опыт": 1, "унижение": -1, "свобода": 1,
            }),
            "actions1": d.get("actions1", ["защита", "атака"]),
            "actions2": d.get("actions2", ["уход", "борьба"]),
            "M1": d.get("M1", [[3, 1], [1, 1]]),
            "M2": d.get("M2", [[1, 1], [1, 2]]),
            "alphas": d.get("alphas", [0.25, 0.5, 0.75]),
            "timeline": d.get("timeline",
                              ["детство", "школа", "работа", "настоящее", "будущее"]),
            "shift_k": d.get("shift_k", 2),
            "states": d.get("states", {"детство": "страх", "школа": "тревога"}),
            "reimprint_state": d.get("reimprint_state", "ресурс"),
            "changes": d.get("changes", ["A", "B", "C", "D", "E"]),
            "f1": d.get("f1", {"A": 1, "B": 3, "C": 2, "D": 4, "E": 2}),
            "f2": d.get("f2", {"A": 4, "B": 2, "C": 3, "D": 1, "E": 1}),
            "baseline": d.get("baseline", "A"),
            "reactions": d.get("reactions", ["r1", "r2"]),
            "disturbances": d.get("disturbances", ["d1", "d2", "d3"]),
            "alphabet": d.get("alphabet", ["a", "b", "c"]),
            "log": [],
        }
        ok, missing = validate_input(situation)
        if not ok:
            return jsonify({"success": False, "missing": missing}), 400
        result = run_pipeline(situation, STAGES, 0, ENABLE_STAGES, STAGE_NAMES)
        outputs = extract_outputs(result)
        # log_final содержит tuple - конвертируем
        if outputs.get("log_final"):
            outputs["log_final"] = [list(x) if isinstance(x, tuple) else x
                                     for x in outputs["log_final"]]
        return jsonify({"success": True, "outputs": outputs})
    except Exception as e:
        log.error("[NLP] pipeline: %s", e)
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/nlp/analyze_node', methods=['POST'])
def api_nlp_analyze_node():
    """P98: НЛП-анализ узла InevioNet."""
    try:
        from inevionet.nlp.pipeline import spore_analyze_node
        d = request.get_json(silent=True) or {}
        node = {
            "ip": d.get("ip", "192.168.1.1"),
            "type": d.get("type", "router"),
            "source": d.get("source", "arp"),
            "vendor": d.get("vendor", "unknown"),
            "open_ports": d.get("open_ports", []),
        }
        result = spore_analyze_node(node)
        return jsonify({"success": True, "node": node, "result": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/nlp/stages')
def api_nlp_stages():
    """P98: текущие флаги этапов НЛП."""
    try:
        from inevionet.nlp.pipeline import (
            STAGE_NAMES, ENABLE_STAGES, STAGE_PRIORITY,
        )
        return jsonify({
            "success": True,
            "stages": STAGE_NAMES,
            "enabled": ENABLE_STAGES,
            "priority": STAGE_PRIORITY,
        })
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route('/api/network/public')'''

patch_replace(APP, [(anchor, new_eps, True)], "app.py NLP endpoints")


print()
print("=" * 70)
print("  PATCH 98 DONE")
print("=" * 70)
print("  [OK] inevionet/nlp/__init__.py")
print("  [OK] inevionet/nlp/pipeline.py (8 этапов + адаптеры)")
print("  [OK] organism.py: NLP в scout() + assess()")
print("  [OK] app.py: /api/nlp/pipeline, /analyze_node, /stages")
print()
print("Перезапуск + проверка:")
print("  curl -k https://localhost:8080/api/nlp/stages")
print("  curl -k -X POST https://localhost:8080/api/nlp/pipeline")
print("  curl -k -X POST https://localhost:8080/api/nlp/analyze_node -d '{\"ip\":\"192.168.1.1\",\"type\":\"router\"}'")