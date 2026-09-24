# analyze_project.py - полный анализ структуры InevioNet
import os
import ast
import sys
import json
from collections import defaultdict

ROOT = r"E:\InevioNet"
INEV = os.path.join(ROOT, "inevionet")
WEB = os.path.join(ROOT, "web")

# ============================================================
# 1. Все Python файлы
# ============================================================

def find_all_py(root):
    result = []
    for dirpath, dirnames, filenames in os.walk(root):
        # skip
        skip = ("__pycache__", "venv", ".git", "build", "dist",
                "dist_capsule", "_backup", "installer_output", "tor")
        if any(s in dirpath for s in skip):
            continue
        for f in filenames:
            if f.endswith(".py"):
                result.append(os.path.join(dirpath, f))
    return result


# ============================================================
# 2. Парсинг файла: классы, методы, импорты
# ============================================================

def parse_py(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
    except Exception as e:
        return {"error": str(e)}

    classes = []
    functions = []
    imports = []
    routes = []

    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            methods = []
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    methods.append(item.name)
            classes.append({"name": node.name, "methods": methods})

        elif isinstance(node, ast.FunctionDef):
            # только верхнеуровневые
            if node.col_offset == 0:
                functions.append(node.name)

        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for alias in node.names:
                imports.append({"from": module, "import": alias.name})

        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.append({"from": "", "import": alias.name})

        # Декораторы @app.route
        elif isinstance(node, ast.FunctionDef):
            for dec in node.decorator_list:
                if isinstance(dec, ast.Call):
                    if isinstance(dec.func, ast.Attribute):
                        if dec.func.attr == "route":
                            if dec.args:
                                try:
                                    route = ast.literal_eval(dec.args[0])
                                    routes.append({
                                        "function": node.name,
                                        "route": route,
                                    })
                                except Exception:
                                    pass

    return {
        "classes": classes,
        "functions": functions,
        "imports": imports,
        "routes": routes,
    }


# ============================================================
# 3. Анализ
# ============================================================

print()
print("=" * 78)
print("  INEVIONET PROJECT ANALYSIS")
print("=" * 78)
print()

files = find_all_py(INEV) + find_all_py(WEB)
print(f"Всего Python файлов: {len(files)}")
print()

# --- Группировка по модулям ---
modules = defaultdict(list)
for f in files:
    rel = os.path.relpath(f, ROOT)
    parts = rel.replace("\\", "/").split("/")
    if len(parts) >= 2:
        module = parts[1] if parts[0] == "inevionet" else parts[0]
    else:
        module = "root"
    modules[module].append((rel, f))

print("=" * 78)
print("  СТРУКТУРА ПО МОДУЛЯМ")
print("=" * 78)
for module in sorted(modules.keys()):
    print(f"\n📁 {module}/")
    for rel, f in sorted(modules[module]):
        size = os.path.getsize(f)
        print(f"   {rel}  ({size} bytes)")

# --- Парсинг всех файлов ---
print()
print("=" * 78)
print("  КЛАССЫ И МЕТОДЫ")
print("=" * 78)

all_classes = {}
all_imports = []
all_routes = []

for f in files:
    rel = os.path.relpath(f, ROOT)
    parsed = parse_py(f)
    if "error" in parsed:
        continue
    for cls in parsed["classes"]:
        all_classes[f"{rel}::{cls['name']}"] = cls["methods"]
    all_imports.extend(parsed["imports"])
    for r in parsed["routes"]:
        all_routes.append({**r, "file": rel})

# --- Классы ---
for key in sorted(all_classes.keys()):
    methods = all_classes[key]
    print(f"\n🔷 {key}")
    for m in methods[:30]:  # limit
        print(f"     · {m}")
    if len(methods) > 30:
        print(f"     ... и ещё {len(methods) - 30}")

# --- Импорты (агрегация) ---
print()
print("=" * 78)
print("  ИМПОРТЫ (агрегировано)")
print("=" * 78)

imp_count = defaultdict(int)
for imp in all_imports:
    key = f"{imp['from']} -> {imp['import']}" if imp['from'] else f"import {imp['import']}"
    imp_count[key] += 1

for key, cnt in sorted(imp_count.items(), key=lambda x: -x[1])[:40]:
    print(f"  {cnt:3d}x  {key}")

# --- API endpoints ---
print()
print("=" * 78)
print("  API ENDPOINTS")
print("=" * 78)

for r in sorted(all_routes, key=lambda x: x["route"]):
    print(f"  {r['route']:<45} → {r['function']}  [{r['file']}]")

# ============================================================
# 4. Что задействовано в orchestrator
# ============================================================

print()
print("=" * 78)
print("  ЧТО ЗАДЕЙСТВОВАНО (из orchestrator.py + web/app.py)")
print("=" * 78)

def find_used_names(files_to_check):
    """Собрать все имена, которые упоминаются в файлах."""
    used = set()
    for f in files_to_check:
        if not os.path.exists(f):
            continue
        try:
            with open(f, "r", encoding="utf-8") as fh:
                text = fh.read()
        except Exception:
            continue
        # Ищем импорты и вызовы классов
        for node in ast.walk(ast.parse(text)):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    used.add(alias.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    used.add(alias.name.split(".")[0])
            elif isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    used.add(node.func.id)
                elif isinstance(node.func, ast.Attribute):
                    used.add(node.func.attr)
    return used

orchestrator = os.path.join(INEV, "orchestrator.py")
app_py = os.path.join(WEB, "app.py")

used = find_used_names([orchestrator, app_py])

# Все классы, определённые в inevionet
defined_classes = set()
for key in all_classes.keys():
    cls_name = key.split("::")[-1]
    defined_classes.add(cls_name)

print(f"\nВсего классов определено: {len(defined_classes)}")
print(f"Упоминается в orchestrator/app: {len(defined_classes & used)}")
print()

# --- НЕ задействованные классы ---
unused = defined_classes - used
if unused:
    print("❌ НЕ ЗАДЕЙСТВОВАНЫ (не упоминаются в orchestrator.py / app.py):")
    for c in sorted(unused):
        print(f"   · {c}")
else:
    print("✅ Все классы задействованы")

# --- Задействованные классы ---
used_classes = defined_classes & used
if used_classes:
    print()
    print("✅ ЗАДЕЙСТВОВАНЫ:")
    for c in sorted(used_classes):
        print(f"   · {c}")

# ============================================================
# 5. Точки входа
# ============================================================

print()
print("=" * 78)
print("  ТОЧКИ ВХОДА")
print("=" * 78)

entry_points = [
    ("run_app.py", "EXE entry"),
    ("web/app.py", "Flask app (main)"),
    ("run_capsule.py", "Capsule entry"),
    ("inevionet/orchestrator.py", "Orchestrator test"),
    ("inevionet/__init__.py", "Package export"),
]

for rel, desc in entry_points:
    p = os.path.join(ROOT, rel.replace("/", os.sep))
    if os.path.exists(p):
        print(f"  ✅ {rel:<40} — {desc}")
    else:
        print(f"  ❌ {rel:<40} — {desc}")

# ============================================================
# 6. Итоговая сводка
# ============================================================

print()
print("=" * 78)
print("  ИТОГОВАЯ СВОДКА")
print("=" * 78)
print(f"  Файлов Python: {len(files)}")
print(f"  Модулей: {len(modules)}")
print(f"  Классов: {len(all_classes)}")
print(f"  Методов: {sum(len(m) for m in all_classes.values())}")
print(f"  API endpoints: {len(all_routes)}")
print(f"  Импортов: {len(all_imports)}")
print(f"  Не задействовано классов: {len(unused)}")
print()
print("=" * 78)