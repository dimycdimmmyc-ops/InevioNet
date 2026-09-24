# audit.py - что задействовано, а что нет
import os
import re
import ast

ROOT = r"E:\InevioNet"
INEV = os.path.join(ROOT, "inevionet")

print("=" * 70)
print("  INEVIONET - АУДИТ ПРОЕКТА")
print("=" * 70)
print()

# ============================================================
# 1. Все Python-модули в inevionet/
# ============================================================
print("=== 1. ВСЕ МОДУЛИ inevionet/ ===")
print()

all_modules = []
for dirpath, dirnames, filenames in os.walk(INEV):
    dirnames[:] = [d for d in dirnames if d != "__pycache__"]
    for fname in filenames:
        if fname.endswith(".py") and fname != "__init__.py":
            full = os.path.join(dirpath, fname)
            rel = os.path.relpath(full, ROOT).replace("\\", ".")
            rel = rel.replace(".py", "")
            all_modules.append(rel)

all_modules.sort()
for m in all_modules:
    print(f"  {m}")

print()
print(f"  ВСЕГО: {len(all_modules)} модулей")
print()

# ============================================================
# 2. Что импортируется в orchestrator.py
# ============================================================
print("=" * 70)
print("=== 2. ИМПОРТЫ В orchestrator.py ===")
print()

orch_path = os.path.join(INEV, "orchestrator.py")
with open(orch_path, "r", encoding="utf-8") as f:
    orch_content = f.read()

# Найти все "from .X import" и "from .X.Y import"
imports = re.findall(r'from \.([\w\.]+) import', orch_content)
imports = sorted(set(imports))
for imp in imports:
    print(f"  {imp}")

print()
print(f"  ВСЕГО: {len(imports)} импортов")
print()

# ============================================================
# 3. Что модули используются в orchestrator?
# ============================================================
print("=" * 70)
print("=== 3. ИСПОЛЬЗОВАНИЕ МОДУЛЕЙ ===")
print()

used = set()
unused = []

for m in all_modules:
    # Короткое имя модуля
    short = m.split(".")[-1]
    # Ищем упоминание в orchestrator
    if short in orch_content:
        used.add(m)
    else:
        unused.append(m)

print("  ЗАДЕЙСТВОВАНЫ:")
for m in sorted(used):
    print(f"    ✅ {m}")
print()
print("  НЕ ЗАДЕЙСТВОВАНЫ (возможно мёртвый код):")
for m in sorted(unused):
    print(f"    ❌ {m}")
print()
print(f"  ИТОГО: {len(used)} использовано, {len(unused)} не использовано")
print()

# ============================================================
# 4. Что импортируется и используется в web/app.py
# ============================================================
print("=" * 70)
print("=== 4. WEB APP - ENDPOINTS ===")
print()

app_path = os.path.join(ROOT, "web", "app.py")
with open(app_path, "r", encoding="utf-8") as f:
    app_content = f.read()

routes = re.findall(r"@app\.route\(['\"]([^'\"]+)['\"]", app_content)
methods = re.findall(r"@app\.route\(['\"]([^'\"]+)['\"],\s*methods=\[([^\]]+)\]", app_content)

print(f"  Всего routes: {len(routes)}")
print()
for r in routes:
    print(f"    {r}")
print()

# ============================================================
# 5. Методы InevioNet (enable_*, send_*, get_*)
# ============================================================
print("=" * 70)
print("=== 5. ПУБЛИЧНЫЕ МЕТОДЫ InevioNet ===")
print()

# Парсим orchestrator.py как Python-код
try:
    tree = ast.parse(orch_content)
    
    methods = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "InevioNet":
            for item in node.body:
                if isinstance(item, ast.FunctionDef):
                    if not item.name.startswith("_"):
                        methods.append(item.name)
    
    print(f"  Всего публичных методов: {len(methods)}")
    print()
    for m in sorted(methods):
        print(f"    {m}()")
except Exception as e:
    print(f"  [!!] Ошибка парсинга: {e}")

print()

# ============================================================
# 6. Monkey-patch методы (добавленные через .method = ...)
# ============================================================
print("=" * 70)
print("=== 6. MONKEY-PATCH МЕТОДЫ ===")
print()

patches = re.findall(r'InevioNet\.(\w+)\s*=', orch_content)
patches = sorted(set(patches))
for p in patches:
    print(f"    {p}")
print()
print(f"  ВСЕГО: {len(patches)} monkey-patched методов")
print()

# ============================================================
# 7. UI кнопки (onclick)
# ============================================================
print("=" * 70)
print("=== 7. UI КНОПКИ (onclick) ===")
print()

html_path = os.path.join(ROOT, "web", "templates", "index.html")
with open(html_path, "r", encoding="utf-8") as f:
    html_content = f.read()

onclicks = re.findall(r'onclick="(\w+)\(', html_content)
onclicks = sorted(set(onclicks))
for oc in onclicks:
    print(f"    {oc}()")
print()
print(f"  ВСЕГО: {len(onclicks)} кнопок")
print()

# ============================================================
# 8. Какие JS функции определены
# ============================================================
print("=" * 70)
print("=== 8. JS ФУНКЦИИ В UI ===")
print()

js_funcs = re.findall(r'(?:async\s+)?function\s+(\w+)\s*\(', html_content)
js_funcs = sorted(set(js_funcs))
for jf in js_funcs:
    print(f"    {jf}()")
print()
print(f"  ВСЕГО: {len(js_funcs)} функций")
print()

# ============================================================
# 9. Мёртвые JS функции (определены, но не вызываются)
# ============================================================
print("=" * 70)
print("=== 9. МЁРТВЫЕ JS ФУНКЦИИ ===")
print()

dead_funcs = []
for jf in js_funcs:
    # Ищем вызовы (не определения)
    calls = len(re.findall(rf'(?<!function )\b{jf}\s*\(', html_content))
    if calls == 0:
        dead_funcs.append(jf)

if dead_funcs:
    for df in dead_funcs:
        print(f"    ❌ {df}() — определена, но не вызывается")
else:
    print("    ✅ Все JS функции вызываются")

print()

# ============================================================
# 10. ИТОГ
# ============================================================
print("=" * 70)
print("=== 10. ИТОГ ===")
print()
print(f"  Модулей:           {len(all_modules)}")
print(f"  Импортов в orch:   {len(imports)}")
print(f"  Использовано:      {len(used)}")
print(f"  Не использовано:   {len(unused)}")
print(f"  API endpoints:     {len(routes)}")
print(f"  Методов InevioNet: {len(methods)}")
print(f"  Monkey-patches:    {len(patches)}")
print(f"  UI кнопок:         {len(onclicks)}")
print(f"  JS функций:        {len(js_funcs)}")
print(f"  Мёртвых JS:        {len(dead_funcs)}")
print()
print("=" * 70)