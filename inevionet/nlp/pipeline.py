"""InevioNet NLP Pipeline - рекурсивный конвейер.

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
    """P98-fix2: ДИНАМИЧЕСКИЙ адаптер - свойства узла -> ситуация."""
    ip = node.get("ip", "unknown")
    ntype = node.get("type", "unknown")
    source = node.get("source", "unknown")
    vendor = node.get("vendor", "")
    ports = node.get("open_ports", [])
    if not isinstance(ports, list):
        ports = []

    # --- VAK: на основе свойств ---
    v = len(ports) + (2 if "router" in ntype else 0)
    a = 3 if node.get("responds") else 1
    k = 2 if vendor else 1
    if node.get("stego_ok"):
        k += 2

    # --- RAPPORT: протоколы узла ---
    if ntype == "router":
        node_protocols = ["HTTP", "HTTPS", "DNS"]
    elif ntype == "lan_device":
        node_protocols = ["ARP", "mDNS"]
    elif ntype == "inevionet":
        node_protocols = ["HTTP", "HTTPS"]
    elif ntype == "service":
        node_protocols = ["mDNS", "SSDP"]
    elif ntype == "isp_router":
        node_protocols = ["BGP", "OSPF"]
    else:
        node_protocols = [str(ntype).upper()]

    therapist_seq = ["HTTP", "HTTPS", "DNS", "ICMP"]

    # --- ANCHOR ---
    anchor_stimulus = vendor if vendor else ntype
    anchor_emotion = "интерес" if vendor else "нейтрал"

    # --- REFRAME: frame по типу ---
    if ntype == "lan_device":
        frame = {"closed": "неизвестен", "open": "сосед"}
        phi = {"неизвестен": "изучаем", "сосед": "соратник"}
        val_map = {"неизвестен": 0, "изучаем": 1, "сосед": 1, "соратник": 1}
    elif ntype == "isp_router":
        frame = {"closed": "чужой", "open": "транзит"}
        phi = {"чужой": "путь", "транзит": "мост"}
        val_map = {"чужой": -1, "путь": 0, "транзит": 1, "мост": 1}
    elif ntype == "inevionet":
        frame = {"closed": "свой", "open": "соратник"}
        phi = {"свой": "орган", "соратник": "симбионт"}
        val_map = {"свой": 1, "орган": 1, "соратник": 1, "симбионт": 1}
    else:
        frame = {"closed": "неизвестен", "open": "потенциал"}
        phi = {"неизвестен": "наблюдаем", "потенциал": "растём"}
        val_map = {"неизвестен": 0, "наблюдаем": 0, "потенциал": 1, "растём": 1}

    # --- SIXSTEP: M1/M2 по типу ---
    if ntype in ("lan_device", "service"):
        actions1 = ["probe", "teach"]
        actions2 = ["ignore", "respond"]
        M1 = [[2, 3], [3, 4]]
        M2 = [[1, 2], [2, 3]]
    elif ntype == "isp_router":
        actions1 = ["route", "skip"]
        actions2 = ["forward", "drop"]
        M1 = [[3, 1], [0, 0]]
        M2 = [[2, 0], [0, 1]]
    elif ntype == "inevionet":
        actions1 = ["merge", "split"]
        actions2 = ["accept", "reject"]
        M1 = [[4, 1], [1, 2]]
        M2 = [[4, 1], [1, 2]]
    else:
        actions1 = ["probe", "wait"]
        actions2 = ["ignore", "respond"]
        M1 = [[3, 1], [1, 1]]
        M2 = [[1, 1], [1, 2]]

    # --- ECOLOGY: f1/f2 по типу (f1=польза нам, f2=польза сети) ---
    if ntype == "lan_device":
        f1 = {"teach": 4, "relay": 2, "capsule": 5, "route": 1, "skip": 1}
        f2 = {"teach": 4, "relay": 3, "capsule": 2, "route": 3, "skip": 4}
    elif ntype == "isp_router":
        f1 = {"teach": 0, "relay": 4, "capsule": 0, "route": 5, "skip": 2}
        f2 = {"teach": 0, "relay": 4, "capsule": 0, "route": 5, "skip": 3}
    elif ntype == "inevionet":
        f1 = {"teach": 5, "relay": 4, "capsule": 0, "route": 3, "skip": 0}
        f2 = {"teach": 5, "relay": 5, "capsule": 0, "route": 4, "skip": 2}
    elif ntype == "service":
        # mDNS - потенциальный relay
        f1 = {"teach": 2, "relay": 4, "capsule": 2, "route": 2, "skip": 1}
        f2 = {"teach": 3, "relay": 4, "capsule": 1, "route": 3, "skip": 3}
    else:
        f1 = {"teach": 3, "relay": 2, "capsule": 3, "route": 2, "skip": 1}
        f2 = {"teach": 3, "relay": 3, "capsule": 1, "route": 3, "skip": 4}

    return {
        "v": v, "a": a, "k": k,
        "client_seq": node_protocols,
        "therapist_seq": therapist_seq,
        "rapport_threshold": 0.5,
        "anchor_stimulus": anchor_stimulus,
        "anchor_emotion": anchor_emotion,
        "frame": frame, "phi": phi, "val_map": val_map,
        "actions1": actions1, "actions2": actions2,
        "M1": M1, "M2": M2,
        "alphas": [0.25, 0.5, 0.75],
        "timeline": [ip, ntype, source],
        "shift_k": 1,
        "states": {ip: "new"},
        "reimprint_state": "colonized",
        "changes": ["teach", "relay", "capsule", "route", "skip"],
        "f1": f1, "f2": f2, "baseline": "skip",
        "reactions": ["respond", "ignore", "redirect"],
        "disturbances": ["port_scan", "syn_flood"],
        "alphabet": ["teach", "relay", "capsule"],
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

        # P98-fix2: план из allowed ∩ pareto
        allowed = outputs.get("allowed") or []
        pareto = outputs.get("pareto") or []
        # Пересечение
        candidates = []
        for x in allowed:
            if x in pareto:
                candidates = _append(candidates, x)
        if not candidates:
            candidates = allowed

        # P99: route+relay synch - если route разрешён, и relay тоже
        if "route" in candidates and "relay" not in candidates:
            candidates = _append(candidates, "relay")

        # Приоритет
        priority = ["capsule", "teach", "relay", "route", "skip"]
        plan = "skip"
        confidence = 0.3
        for p in priority:
            if p in candidates:
                plan = p
                if p in ("teach", "relay"):
                    confidence = 0.85
                elif p == "capsule":
                    confidence = 0.75
                elif p == "route":
                    confidence = 0.65
                else:
                    confidence = 0.3
                break

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
