import os
import ast
import shutil

ROOT = r"E:\InevioNet"
APP = os.path.join(ROOT, "web", "app.py")

with open(APP, "r", encoding="utf-8") as f:
    content = f.read()

# Проверка: уже есть ли "urls" в api_bootstrap_sprout
# Ищем фрагмент P75c, где добавляли texts
old = '''        url = d.get('url', '')
        text = d.get('text', '')
        texts = d.get('texts', [])  # P75: список
        if texts:
            cnt = n.sprout.add_urls_multi(texts)
            return jsonify({'success': True, 'action': 'queued_urls',
                            'count': cnt})'''

new = '''        url = d.get('url', '')
        text = d.get('text', '')
        texts = d.get('texts', [])  # P75: список
        urls = d.get('urls', [])     # P75fix: список URL
        if urls:
            cnt = n.sprout.add_urls_multi(urls)
            return jsonify({'success': True, 'action': 'queued_urls',
                            'count': cnt})
        if texts:
            cnt = n.sprout.add_urls_multi(texts)
            return jsonify({'success': True, 'action': 'queued_urls',
                            'count': cnt})'''

if "urls = d.get('urls'" in content:
    print("  [--] P75-fix already applied")
elif old in content:
    content = content.replace(old, new, 1)
    b = APP + ".bak_p75fix"
    shutil.copy2(APP, b)
    print("  [BK] " + os.path.basename(b))
    with open(APP, "w", encoding="utf-8") as f:
        f.write(content)
    try:
        ast.parse(content)
        print("  [OK] syntax app.py")
    except SyntaxError as e:
        print("  [!!] syntax: " + str(e))
        shutil.copy2(b, APP)
        print("  [--] rolled back")
else:
    print("  [!!] anchor NOT FOUND")
    # Показать текущий api_bootstrap_sprout
    lines = content.splitlines()
    for i, line in enumerate(lines):
        if "def api_bootstrap_sprout" in line:
            for j in range(i, min(i+30, len(lines))):
                print("    " + str(j+1) + ": " + lines[j])

with open(APP, "r", encoding="utf-8") as f:
    check = f.read()
print("  urls в api_bootstrap_sprout: " + str("urls = d.get('urls'" in check))