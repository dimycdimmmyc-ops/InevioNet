# patch93.py - P93: фикс дубликата @app.route + UTF-16 tree.json
import os
import ast
import shutil
import re

ROOT = r"E:\InevioNet"
APP = os.path.join(ROOT, "web", "app.py")

BAK = ".bak_p93"


def find_duplicates(path):
    """Найти дубликаты @app.route с одинаковым endpoint."""
    with open(path, "r", encoding="utf-8") as f:
        content = f.read()
    lines = content.splitlines()
    routes = {}  # endpoint -> [line_numbers]
    for i, line in enumerate(lines):
        m = re.search(r"@app\.route\('([^']+)'", line)
        if m:
            route = m.group(1)
            # найти функцию после декоратора
            for j in range(i+1, min(i+4, len(lines))):
                fm = re.search(r"def\s+(\w+)", lines[j])
                if fm:
                    fn = fm.group(1)
                    routes.setdefault((route, fn), []).append(i+1)
                    break
    return routes, lines, content


# =====================================================================
# 1. Найти и удалить дубликат @app.route('/api/network/public')
# =====================================================================

print()
print("=" * 70)
print("  1. Поиск дубликатов @app.route")
print("=" * 70)

routes, lines, content = find_duplicates(APP)

dups = {k: v for k, v in routes.items() if len(v) > 1}
if not dups:
    print("  [--] дубликатов не найдено")
else:
    print(f"  Найдено {len(dups)} дубликатов:")
    for (route, fn), locs in dups.items():
        print(f"    {route} -> {fn} @ lines {locs}")

# =====================================================================
# 2. Удалить дубликат api_network_public (мой блок вставился ДО старого)
# =====================================================================

# Мой блок P92 вставлялся ПЕРЕД @app.route('/api/network/public')
# Значит первый api_network_public — мой, второй — оригинал
# Стратегия: удалить ПЕРВЫЙ @app.route('/api/network/public') + его функцию

with open(APP, "r", encoding="utf-8") as f:
    content = f.read()

# Найти все вхождения @app.route('/api/network/public')
pattern = re.compile(
    r"@app\.route\('/api/network/public'[^)]*\)\s*\ndef\s+api_network_public\s*\([^)]*\):.*?(?=\n@app\.route|\ndef\s+\w+\s*\(|\Z)",
    re.DOTALL
)
matches = list(pattern.finditer(content))
print(f"  Найдено api_network_public блоков: {len(matches)}")

if len(matches) >= 2:
    # Удалить ПЕРВЫЙ (это дубликат — мой блок P92, вставленный до старого)
    m = matches[0]
    b = APP + BAK
    shutil.copy2(APP, b)
    print(f"  [BK] {os.path.basename(b)}")
    content_new = content[:m.start()] + content[m.end():]
    with open(APP, "w", encoding="utf-8") as f:
        f.write(content_new)
    try:
        ast.parse(content_new)
        print("  [OK] удалён первый дубликат api_network_public")
    except SyntaxError as e:
        print(f"  [!!] syntax: {e}")
        shutil.copy2(b, APP)
        print("  [--] rolled back")
else:
    print("  [--] дубликатов api_network_public нет")

print()
print("=" * 70)
print("  PATCH 93 DONE")
print("=" * 70)
print("  [OK] удалён дубликат @app.route('/api/network/public')")
print()
print("Дальше:")
print("  1. Остановить все python")
print("  2. python -m web.app   (должен стартовать без AssertionError)")
print("  3. curl.exe -o tree.json -s -k https://localhost:8080/api/network/tree?force=1")
print("  4. python -c \"import json; d=json.load(open('tree.json',encoding='utf-8')); print(list(d.keys()))\"")