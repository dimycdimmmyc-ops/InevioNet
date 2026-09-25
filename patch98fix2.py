# patch98fix2.py - P98-fix2: динамический node_to_situation
import os
import ast
import shutil
import re

ROOT = r"E:\InevioNet"
PIPE = os.path.join(ROOT, "inevionet", "nlp", "pipeline.py")

BAK = ".bak_p98fix2"


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


# Заменить весь node_to_situation и spore_analyze_node
print()
print("=" * 70)
print("  P98-fix2: динамический node_to_situation")
print("=" * 70)

with open(PIPE, "r", encoding="utf-8") as f:
    content = f.read()

# Найти старую функцию
old_func = re.compile(
    r"def node_to_situation\(node\):.*?(?=\ndef |\Z)",
    re.DOTALL
)
m = old_func.search(content)
if m:
    new_func = '''def node_to_situation(node):
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
        node_protocols = ["mDNS"]
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

'''
    content = content[:m.start()] + new_func + content[m.end():]
    
    # Обновить spore_analyze_node — выбрать план по allowed+pareto
    old_plan = '''        # Определяем план на основе выходов
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
            confidence = 0.3'''
    
    new_plan = '''        # P98-fix2: план из allowed ∩ pareto
        allowed = outputs.get("allowed") or []
        pareto = outputs.get("pareto") or []
        # Пересечение
        candidates = []
        for x in allowed:
            if x in pareto:
                candidates = _append(candidates, x)
        if not candidates:
            candidates = allowed

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
                break'''
    
    if old_plan in content:
        content = content.replace(old_plan, new_plan, 1)
        print("  [OK] spore_analyze_node plan")
    else:
        print("  [!!] plan block not found")
    
    with open(PIPE, "w", encoding="utf-8") as f:
        f.write(content)
    try:
        ast.parse(content)
        print("  [OK] syntax pipeline.py")
    except SyntaxError as e:
        print("  [!!] syntax: " + str(e))
else:
    print("  [!!] node_to_situation not found")


print()
print("=" * 70)
print("  PATCH 98-FIX2 DONE")
print("=" * 70)
print("  [OK] node_to_situation: динамический (по типу узла)")
print("  [OK] spore_analyze_node: план из allowed ∩ pareto")
print()
print("Стоп + перезапуск + 60 сек")