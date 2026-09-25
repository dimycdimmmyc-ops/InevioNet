# patch14_ai.py
import re
import ast
import sys

ROOT = r"E:\InevioNet"
ORCH = ROOT + r"\inevionet\orchestrator.py"
APP = ROOT + r"\web\app.py"
HTML = ROOT + r"\web\templates\index.html"

# === 1. Patch orchestrator.py ===
print("=== Patching orchestrator.py ===")
with open(ORCH, "r", encoding="utf-8") as f:
    content = f.read()

with open(ORCH + ".bak_p14", "w", encoding="utf-8") as f:
    f.write(content)
print(f"  Backup: {ORCH}.bak_p14")

# 1.1 select() → select(receiver)
if "self.selector.select(receiver)" in content:
    print("  [--] select already patched")
else:
    old = "protocol = self.selector.select() or \"HTTPS\""
    new = "protocol = self.selector.select(receiver) or \"HTTPS\""
    if old in content:
        content = content.replace(old, new)
        print("  [OK] select(receiver) fixed")
    else:
        print("  [!!] select pattern not found")

# 1.2 record_success(protocol) → record_success(receiver, protocol)
if "record_success(receiver, protocol)" in content:
    print("  [--] record_success already fixed")
else:
    old = "self.selector.record_success(protocol)"
    new = "self.selector.record_success(receiver, protocol)"
    if old in content:
        content = content.replace(old, new)
        print("  [OK] record_success(receiver, protocol) fixed")
    else:
        print("  [!!] record_success pattern not found")

# 1.3 record_failure(protocol) → record_failure(receiver, protocol)
if "record_failure(receiver, protocol)" in content:
    print("  [--] record_failure already fixed")
else:
    old = "self.selector.record_failure(protocol)"
    new = "self.selector.record_failure(receiver, protocol)"
    if old in content:
        content = content.replace(old, new)
        print("  [OK] record_failure(receiver, protocol) fixed")
    else:
        print("  [!!] record_failure pattern not found")

# Save
with open(ORCH, "w", encoding="utf-8") as f:
    f.write(content)

try:
    ast.parse(content)
    print("  [OK] syntax valid")
except SyntaxError as e:
    print(f"  [!!] syntax error: {e}")
    with open(ORCH + ".bak_p14", "r", encoding="utf-8") as f:
        orig = f.read()
    with open(ORCH, "w", encoding="utf-8") as f:
        f.write(orig)
    print("  [!!] restored")
    sys.exit(1)

# === 2. Add /api/ai/stats to web/app.py ===
print()
print("=== Patching web/app.py ===")
with open(APP, "r", encoding="utf-8") as f:
    app = f.read()

with open(APP + ".bak_p14", "w", encoding="utf-8") as f:
    f.write(app)
print(f"  Backup: {APP}.bak_p14")

if "/api/ai/stats" in app:
    print("  [--] ai/stats already exists")
else:
    ai_endpoints = '''
@app.route('/api/ai/stats')
def api_ai_stats():
    """AI selector + recursion stats."""
    try:
        n = get_net()
        return jsonify({
            'success': True,
            'selector': n.selector.get_stats() if n.selector else {},
            'protocols': n.selector.get_all_protocol_stats() if n.selector else {},
            'recursion': n.recursion.get_stats() if n.recursion else {},
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ai/reset', methods=['POST'])
def api_ai_reset():
    """Reset AI learning."""
    try:
        n = get_net()
        if n.selector:
            n.selector.reset()
        if n.recursion:
            n.recursion.reset_stats()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


'''
    marker = "@socketio.on('connect')"
    if marker in app:
        app = app.replace(marker, ai_endpoints + marker, 1)
        with open(APP, "w", encoding="utf-8") as f:
            f.write(app)
        print("  [OK] /api/ai/stats + /api/ai/reset added")
    else:
        print("  [!!] socketio marker not found")

try:
    ast.parse(app)
    print("  [OK] syntax valid")
except SyntaxError as e:
    print(f"  [!!] syntax error: {e}")
    with open(APP + ".bak_p14", "r", encoding="utf-8") as f:
        orig = f.read()
    with open(APP, "w", encoding="utf-8") as f:
        f.write(orig)
    print("  [!!] restored")
    sys.exit(1)

# === 3. Add AI card to index.html ===
print()
print("=== Patching index.html ===")
with open(HTML, "r", encoding="utf-8") as f:
    html = f.read()

with open(HTML + ".bak_p14", "w", encoding="utf-8") as f:
    f.write(html)
print(f"  Backup: {HTML}.bak_p14")

if "aiStatsContainer" in html:
    print("  [--] AI card already exists")
else:
    # Insert AI card before "Network Scanners"
    ai_card = '''<div class="card">
<h3>🤖 AI Селектор</h3>
<div id="aiStatsContainer" style="font-size:0.85em">
  <div id="aiBest">Лучший протокол: —</div>
  <div id="aiTop" style="color:var(--dim);margin-top:6px">Топ-3: —</div>
  <div id="aiCalls" style="color:var(--dim);margin-top:6px">Вызовов: 0</div>
</div>
<button class="btn btn-glass" style="margin-top:10px" onclick="loadAIStats()">📊 Обновить</button>
<button class="btn btn-sm btn-glass" onclick="resetAI()">🔄 Сбросить обучение</button>
</div>

'''
    # Find marker
    markers = ['<h3>Network Scanners</h3>', '<h3>Сканирование сетей</h3>', 'id="networkScanners"']
    inserted = False
    for marker in markers:
        if marker in html:
            # Find enclosing <div class="card"> before marker
            idx = html.index(marker)
            back = html.rindex('<div class="card">', 0, idx)
            html = html[:back] + ai_card + html[back:]
            inserted = True
            print(f"  [OK] AI card inserted before '{marker}'")
            break

    if not inserted:
        # Fallback: before logContainer
        marker = 'id="logContainer"'
        if marker in html:
            idx = html.index(marker)
            back = html.rindex('<div class="card">', 0, idx)
            html = html[:back] + ai_card + html[back:]
            print("  [OK] AI card inserted before logs")
        else:
            print("  [!!] no marker found")

    # Add JS functions
    js_code = '''
async function loadAIStats() {
    try {
        const r = await fetch('/api/ai/stats');
        const d = await r.json();
        if (d.success) {
            const sel = d.selector || {};
            document.getElementById('aiBest').textContent =
                'Лучший: ' + (sel.best_protocol || '—') +
                ' (score: ' + (sel.best_score || 0).toFixed(2) + ')';
            const top = d.protocols || {};
            const topList = Object.entries(top)
                .sort((a, b) => (b[1].score || 0) - (a[1].score || 0))
                .slice(0, 3)
                .map(([k, v]) => k + '(' + (v.score || 0).toFixed(2) + ')')
                .join(', ');
            document.getElementById('aiTop').textContent = 'Топ-3: ' + (topList || '—');
            const rec = d.recursion || {};
            document.getElementById('aiCalls').textContent =
                'Вызовов: ' + (rec.total_calls || 0) +
                ' | Success: ' + (rec.success_rate || 0).toFixed(2);
            addLog('AI stats loaded', 'success');
        }
    } catch (e) {
        addLog('AI: ' + e, 'error');
    }
}

async function resetAI() {
    try {
        const r = await fetch('/api/ai/reset', { method: 'POST' });
        const d = await r.json();
        if (d.success) {
            addLog('AI reset', 'success');
            loadAIStats();
        }
    } catch (e) {
        addLog('Reset: ' + e, 'error');
    }
}

'''
    js_marker = 'checkAuth();'
    if js_marker in html:
        html = html.replace(js_marker, js_code + '\n' + js_marker, 1)
        print("  [OK] JS functions added")

    with open(HTML, "w", encoding="utf-8") as f:
        f.write(html)
    print("  [OK] index.html saved")

# === 4. Create test_ai.py ===
print()
print("=== Creating test_ai.py ===")
test_content = '''# test_ai.py
from inevionet.ai.selector import ProtocolSelector
from inevionet.ai.recursion import WeightedRecursion

print("=== ProtocolSelector test ===")
s = ProtocolSelector()
print("Initial select:", s.select())

# Correct call: record_success(receiver, protocol)
for i in range(5):
    s.record_success("example.com", "HTTPS")
for i in range(3):
    s.record_success("example.com", "DNS")
s.record_failure("example.com", "ICMP")

print("After training:")
print("  select():", s.select("example.com"))
print("  top-3:", s.select_top_n("example.com", 3))
print("  stats:", s.get_stats())

print()
print("=== WeightedRecursion test ===")
r = WeightedRecursion(max_depth=5, probability_threshold=0.95)

alternatives = [
    {"name": "HTTPS", "metrics": {"reliability": 0.9, "speed": 0.6, "stealth": 0.6}},
    {"name": "DNS",   "metrics": {"reliability": 0.7, "speed": 0.5, "stealth": 0.95}},
    {"name": "ICMP",  "metrics": {"reliability": 0.5, "speed": 0.6, "stealth": 0.9}},
]

def try_func(alt, depth):
    print(f"  Trying: {alt['name']} (depth={depth})")
    return alt['name'] == 'HTTPS', 0.9

result = r.execute(alternatives=alternatives, try_func=try_func)
print("Result:", result)
print("Stats:", r.get_stats())
'''
with open(ROOT + r"\test_ai.py", "w", encoding="utf-8") as f:
    f.write(test_content)
print(f"  [OK] Created: {ROOT}\\test_ai.py")

print()
print("=== PATCH 14 DONE ===")
print("Restart: python -m web.app")