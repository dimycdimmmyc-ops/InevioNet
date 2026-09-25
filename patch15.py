# patch15.py - A + B + C at once
import re
import ast
import sys
import os

ROOT = r"E:\InevioNet"
ORCH = ROOT + r"\inevionet\orchestrator.py"
APP = ROOT + r"\web\app.py"
HTML = ROOT + r"\web\templates\index.html"


def backup(path):
    bak = path + ".bak_p15"
    with open(path, "r", encoding="utf-8") as f:
        data = f.read()
    with open(bak, "w", encoding="utf-8") as f:
        f.write(data)
    print(f"  Backup: {bak}")
    return data


def save(path, data):
    with open(path, "w", encoding="utf-8") as f:
        f.write(data)
    try:
        ast.parse(data)
        print("  [OK] syntax valid")
    except SyntaxError as e:
        print(f"  [!!] syntax error: {e}")
        with open(path + ".bak_p15", "r", encoding="utf-8") as f:
            orig = f.read()
        with open(path, "w", encoding="utf-8") as f:
            f.write(orig)
        print("  [!!] restored from backup")
        sys.exit(1)


# ============================================================
# B) Fix _resolve_target to add https:// scheme
# ============================================================
print("=== B) Fix _resolve_target ===")
content = backup(ORCH)

if '"https://" + r' in content:
    print("  [--] already patched")
else:
    # Find the block that returns r for IP:port
    old_block = '''        if re.match(r'^\\d+\\.\\d+\\.\\d+\\.\\d+:\\d+$', r):
            return r
        # IP
        if re.match(r'^\\d+\\.\\d+\\.\\d+\\.\\d+$', r):
            return r'''
    new_block = '''        if re.match(r'^\\d+\\.\\d+\\.\\d+\\.\\d+:\\d+$', r):
            return "https://" + r  # P15: with scheme
        # IP
        if re.match(r'^\\d+\\.\\d+\\.\\d+\\.\\d+$', r):
            return "https://" + r  # P15: with scheme'''

    if old_block in content:
        content = content.replace(old_block, new_block)
        print("  [OK] _resolve_target fixed (adds https://)")
    else:
        # Alternative: just find 127.0.0.1:8080
        old2 = 'return "127.0.0.1:8080"'
        new2 = 'return "https://127.0.0.1:8080"  # P15'
        if old2 in content:
            content = content.replace(old2, new2)
            print("  [OK] self-target fixed (https://)")
        else:
            print("  [--] pattern not found, skip")

    save(ORCH, content)


# ============================================================
# C) Add relay chain to api_p2_send in web/app.py
# ============================================================
print()
print("=== C) Add relay chain to api_p2_send ===")
app = backup(APP)

if "send_with_guarantee" in app and "/api/p2/send" in app:
    # Check if already calls send_with_guarantee
    if "n.send_with_guarantee(" in app:
        print("  [--] already uses send_with_guarantee")
    else:
        # Find api_p2_send function
        # It has: packet = n.send(receiver, message)
        old_send = '''    packet = None
    try:
        packet = n.send(receiver, message)
    except Exception:
        pass'''

        new_send = '''    packet = None
    # P15: try send_with_guarantee first (uses relay chain)
    try:
        success_g, packet_g = n.send_with_guarantee(
            receiver, message, max_attempts=3, expect_ack=False)
        if success_g:
            packet = packet_g
            log.info('[P2] guaranteed delivery: %s', packet.packet_id[:16])
    except Exception as _e:
        log.debug('[P2] send_with_guarantee failed: %s', _e)

    # Fallback: regular send
    if packet is None:
        try:
            packet = n.send(receiver, message)
        except Exception:
            pass'''

        if old_send in app:
            app = app.replace(old_send, new_send)
            print("  [OK] api_p2_send now uses send_with_guarantee")
        else:
            print("  [--] pattern not found in api_p2_send, skip")

    save(APP, app)
else:
    print("  [--] skip (no marker)")


# ============================================================
# A) Beautiful AI UI
# ============================================================
print()
print("=== A) Beautiful AI UI ===")
html = backup(HTML)

# 1. Add CSS for AI card
if "ai-score-bar" not in html:
    css = '''<style>
.ai-score-bar {
    height: 8px;
    background: rgba(120,120,128,0.24);
    border-radius: 4px;
    overflow: hidden;
    margin: 6px 0;
}
.ai-score-fill {
    height: 100%;
    background: linear-gradient(90deg, #ff453a 0%, #ffd60a 50%, #30d158 100%);
    border-radius: 4px;
    transition: width 0.6s ease;
}
.ai-protocol-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 8px 10px;
    background: rgba(120,120,128,0.16);
    border-radius: 10px;
    margin-bottom: 6px;
    border: 0.5px solid var(--separator);
}
.ai-protocol-name {
    font-weight: 600;
    font-size: 0.95em;
}
.ai-protocol-score {
    font-family: monospace;
    font-size: 0.85em;
    color: var(--dim);
}
.ai-medal {
    font-size: 1.2em;
    margin-right: 6px;
}
.ai-stat-line {
    display: flex;
    justify-content: space-between;
    padding: 4px 0;
    font-size: 0.85em;
}
.ai-stat-line .label { color: var(--dim); }
.ai-stat-line .value { font-weight: 600; }
</style>'''
    # Insert before </head>
    if "</head>" in html:
        html = html.replace("</head>", css + "\n</head>", 1)
        print("  [OK] AI CSS added")

# 2. Replace AI card
old_ai_card_re = re.compile(
    r'<div class="card">\s*<h3>🤖 AI Селектор</h3>.*?</div>\s*</div>',
    re.DOTALL
)

new_ai_card = '''<div class="card">
<h3>🤖 AI Селектор</h3>
<div style="margin-bottom:12px">
  <div style="display:flex;justify-content:space-between;align-items:center">
    <span style="font-size:0.9em;color:var(--dim)">Лучший протокол</span>
    <span id="aiBestName" style="font-weight:700;color:var(--green);font-size:1.05em">—</span>
  </div>
  <div class="ai-score-bar" style="margin-top:8px">
    <div class="ai-score-fill" id="aiBestBar" style="width:0%"></div>
  </div>
  <div style="text-align:right;font-family:monospace;font-size:0.8em;color:var(--dim)">
    Score: <span id="aiBestScore">0.00</span>
  </div>
</div>

<div style="font-size:0.85em;color:var(--dim);margin-bottom:8px">Топ-3 протокола:</div>
<div id="aiTopList">
  <div class="empty" style="padding:10px">Нет данных</div>
</div>

<div style="margin-top:12px;padding-top:10px;border-top:0.5px solid var(--separator)">
  <div class="ai-stat-line"><span class="label">Всего записей</span><span class="value" id="aiRecords">0</span></div>
  <div class="ai-stat-line"><span class="label">Уникальных target'ов</span><span class="value" id="aiTargets">0</span></div>
  <div class="ai-stat-line"><span class="label">Вызовов recursion</span><span class="value" id="aiCalls">0</span></div>
  <div class="ai-stat-line"><span class="label">Success rate</span><span class="value" id="aiRate">0%</span></div>
</div>

<button class="btn btn-glass" style="margin-top:12px" onclick="loadAIStats()">📊 Обновить</button>
<button class="btn btn-sm btn-glass" onclick="resetAI()">🔄 Сбросить</button>
</div>'''

if old_ai_card_re.search(html):
    html = old_ai_card_re.sub(new_ai_card, html, count=1)
    print("  [OK] AI card replaced (beautiful UI)")
else:
    print("  [--] AI card pattern not found, skip replacement")

# 3. Replace loadAIStats JS function
old_js_re = re.compile(
    r'async function loadAIStats\(\)\s*\{.*?^\}',
    re.DOTALL | re.MULTILINE
)

new_js = '''async function loadAIStats() {
    try {
        const r = await fetch('/api/ai/stats');
        const d = await r.json();
        if (!d.success) {
            addLog('AI stats failed', 'error');
            return;
        }
        const sel = d.selector || {};
        const protos = d.protocols || [];
        const rec = d.recursion || {};

        // Best protocol + bar
        const best = sel.best_protocol || '—';
        const bestScore = sel.best_score || 0;
        document.getElementById('aiBestName').textContent = best;
        document.getElementById('aiBestScore').textContent = bestScore.toFixed(3);
        document.getElementById('aiBestBar').style.width = Math.round(bestScore * 100) + '%';

        // Top-3 list
        const sorted = [...protos].sort((a, b) =>
            (b.success_rate || 0) - (a.success_rate || 0));
        const medals = ['🥇', '🥈', '🥉'];
        if (sorted.length > 0) {
            document.getElementById('aiTopList').innerHTML = sorted.slice(0, 3).map((p, i) => {
                const pct = Math.round((p.success_rate || 0) * 100);
                return '<div class="ai-protocol-row">' +
                    '<span><span class="ai-medal">' + (medals[i] || '•') + '</span>' +
                    '<span class="ai-protocol-name">' + p.protocol + '</span></span>' +
                    '<span class="ai-protocol-score">' + pct + '% (' + p.attempts + 'x)</span>' +
                    '</div>';
            }).join('');
        } else {
            document.getElementById('aiTopList').innerHTML =
                '<div class="empty" style="padding:10px">Нет данных</div>';
        }

        // Stats
        document.getElementById('aiRecords').textContent = sel.total_records || 0;
        document.getElementById('aiTargets').textContent = sel.unique_targets || 0;
        document.getElementById('aiCalls').textContent = rec.total_calls || 0;
        document.getElementById('aiRate').textContent =
            Math.round((rec.success_rate || 0) * 100) + '%';

        addLog('AI: ' + best + ' score=' + bestScore.toFixed(2), 'success');
    } catch (e) {
        addLog('AI: ' + e, 'error');
    }
}'''

if old_js_re.search(html):
    html = old_js_re.sub(new_js, html, count=1)
    print("  [OK] loadAIStats replaced (beautiful UI)")
else:
    print("  [--] loadAIStats pattern not found, skip")

save(HTML, html)

print()
print("=== PATCH 15 DONE ===")
print("Restart: python -m web.app")