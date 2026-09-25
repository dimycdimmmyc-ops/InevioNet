# patch15_html.py - только HTML-патч (A)
import re
import sys

HTML = r"E:\InevioNet\web\templates\index.html"

# Backup
with open(HTML, "r", encoding="utf-8") as f:
    html = f.read()
with open(HTML + ".bak_p15h", "w", encoding="utf-8") as f:
    f.write(html)
print(f"Backup: {HTML}.bak_p15h")
print(f"Size: {len(html)} bytes")

# === 1. Add CSS ===
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
    if "</head>" in html:
        html = html.replace("</head>", css + "\n</head>", 1)
        print("[OK] AI CSS added")
else:
    print("[--] AI CSS already exists")

# === 2. Replace AI card ===
old_pattern = re.compile(
    r'<div class="card">\s*<h3>🤖 AI Селектор</h3>.*?</div>\s*(?=<div class="card">|</div>\s*<script>)',
    re.DOTALL
)

new_card = '''<div class="card">
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

if old_pattern.search(html):
    html = old_pattern.sub(new_card, html, count=1)
    print("[OK] AI card replaced")
else:
    print("[--] AI card pattern not found")
    # Fallback: find AI card div and replace its content
    if "aiStatsContainer" in html:
        # Find enclosing card
        idx = html.index("aiStatsContainer")
        back = html.rindex('<div class="card">', 0, idx)
        # Find closing (next </div>\n</div> or similar)
        end = html.index('</div>\n</div>', idx)
        end += len('</div>\n</div>')
        html = html[:back] + new_card + html[end:]
        print("[OK] AI card replaced (fallback)")

# === 3. Replace loadAIStats JS ===
old_js = re.compile(
    r'async function loadAIStats\(\)\s*\{.*?\n\}',
    re.DOTALL
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

        const best = sel.best_protocol || '—';
        const bestScore = sel.best_score || 0;
        const bestEl = document.getElementById('aiBestName');
        if (bestEl) bestEl.textContent = best;
        const scoreEl = document.getElementById('aiBestScore');
        if (scoreEl) scoreEl.textContent = bestScore.toFixed(3);
        const barEl = document.getElementById('aiBestBar');
        if (barEl) barEl.style.width = Math.round(bestScore * 100) + '%';

        const sorted = [...protos].sort((a, b) =>
            (b.success_rate || 0) - (a.success_rate || 0));
        const medals = ['🥇', '🥈', '🥉'];
        const listEl = document.getElementById('aiTopList');
        if (listEl) {
            if (sorted.length > 0) {
                listEl.innerHTML = sorted.slice(0, 3).map((p, i) => {
                    const pct = Math.round((p.success_rate || 0) * 100);
                    return '<div class="ai-protocol-row">' +
                        '<span><span class="ai-medal">' + (medals[i] || '•') + '</span>' +
                        '<span class="ai-protocol-name">' + p.protocol + '</span></span>' +
                        '<span class="ai-protocol-score">' + pct + '% (' + p.attempts + 'x)</span>' +
                        '</div>';
                }).join('');
            } else {
                listEl.innerHTML = '<div class="empty" style="padding:10px">Нет данных</div>';
            }
        }

        const recEl = document.getElementById('aiRecords');
        if (recEl) recEl.textContent = sel.total_records || 0;
        const tgtEl = document.getElementById('aiTargets');
        if (tgtEl) tgtEl.textContent = sel.unique_targets || 0;
        const callsEl = document.getElementById('aiCalls');
        if (callsEl) callsEl.textContent = rec.total_calls || 0;
        const rateEl = document.getElementById('aiRate');
        if (rateEl) rateEl.textContent = Math.round((rec.success_rate || 0) * 100) + '%';

        addLog('AI: ' + best + ' score=' + bestScore.toFixed(2), 'success');
    } catch (e) {
        addLog('AI: ' + e, 'error');
    }
}'''

if old_js.search(html):
    html = old_js.sub(new_js, html, count=1)
    print("[OK] loadAIStats replaced")
else:
    print("[--] loadAIStats pattern not found")

# Save (no ast check - HTML!)
with open(HTML, "w", encoding="utf-8") as f:
    f.write(html)
print(f"New size: {len(html)} bytes")
print("Saved")
print()
print("=== PATCH 15-HTML DONE ===")
print("Restart: python -m web.app")
print("Then Ctrl+F5 in browser")