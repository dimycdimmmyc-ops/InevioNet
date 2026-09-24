# Patch 6: index.html - add 3 cards + JS functions
$ErrorActionPreference = "Stop"
$ProjectRoot = "E:\InevioNet"

$path = Join-Path $ProjectRoot "web\templates\index.html"
$content = [System.IO.File]::ReadAllText($path, [System.Text.Encoding]::UTF8)
$content = $content -replace "`r`n", "`n"
$content = $content -replace "`r", "`n"

# Проверка
if ($content.Contains("industrialTarget")) {
    Write-Host "[!!] UI cards already added" -ForegroundColor Yellow
    return
}

# === 6.1. Найдём "Системный лог" и вставим карточки ПЕРЕД ===
$marker = '<div class="card">' + "`n" + '<h3>Системный лог</h3>'
$pos = $content.IndexOf($marker)

if ($pos -lt 0) {
    Write-Host "[!!] Log card not found" -ForegroundColor Red
    return
}

Write-Host "Log card position: $pos" -ForegroundColor Cyan

$newCards = @'
<div class="card">
<h3>Промышленные протоколы</h3>
<div class="form-group"><label>Target (IP или host:port)</label>
<input id="industrialTarget" placeholder="192.168.1.1:502"></div>
<button class="btn secondary" onclick="scanIndustrial()">Scan Modbus/MQTT/OPC-UA/DNP3</button>
<div id="industrialResults" style="margin-top:10px;font-family:monospace;font-size:.75em;max-height:150px;overflow:auto;color:var(--dim)"></div>
</div>

<div class="card">
<h3>Стеганография</h3>
<div class="form-group"><label>Target (URL/domain)</label>
<input id="stegoTarget" value="httpbin.org"></div>
<div class="form-group"><label>Метод</label>
<select id="stegoMethod" style="width:100%;background:rgba(0,0,0,.4);color:var(--text);border:1px solid var(--border);padding:8px;border-radius:6px">
<option>HTTP_HEADERS</option>
<option>HTTP_COOKIE</option>
<option>HTTP_USER_AGENT</option>
<option>DNS_QNAME</option>
<option>DNS_TXT</option>
<option>ICMP_PAYLOAD</option>
<option>TIMING</option>
</select></div>
<div class="form-group"><label>Данные</label>
<textarea id="stegoData" rows="2">test message</textarea></div>
<button class="btn secondary" onclick="sendStego()">Отправить через стего</button>
</div>

<div class="card">
<h3>Эволюция</h3>
<button class="btn secondary" onclick="forceCatastrophe()">Форсировать катастрофу</button>
<button class="btn small" onclick="loadBestStrategies()">Best strategies</button>
<div id="evolutionBest" style="margin-top:10px;font-family:monospace;font-size:.75em;color:var(--dim)"></div>
</div>

'@

$content = $content.Substring(0, $pos) + $newCards + $content.Substring($pos)
Write-Host "[OK] cards inserted" -ForegroundColor Green

# === 6.2. JS-функции перед checkAuth() ===
$jsMarker = "checkAuth();" + "`n" + "setInterval(loadInbox, 10000);"
$jsPos = $content.IndexOf($jsMarker)

if ($jsPos -lt 0) {
    # Альтернативный поиск
    $jsMarker = "checkAuth();"
    $jsPos = $content.IndexOf($jsMarker)
}

if ($jsPos -lt 0) {
    Write-Host "[!!] checkAuth() not found" -ForegroundColor Red
    return
}

Write-Host "checkAuth position: $jsPos" -ForegroundColor Cyan

$newJS = @'
// ===== P13: INDUSTRIAL / STEGO / EVOLUTION =====
async function scanIndustrial() {
    const target = document.getElementById('industrialTarget').value.trim();
    if (!target) { addLog('Введите target', 'error'); return; }
    addLog('Industrial scan: ' + target, 'info');
    const el = document.getElementById('industrialResults');
    el.textContent = 'Сканирую...';
    try {
        const r = await fetch('/api/industrial/scan', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ target })
        });
        const d = await r.json();
        if (d.success) {
            let out = [];
            for (const [proto, res] of Object.entries(d.results || {})) {
                out.push(proto + ': ' + (res.found ? 'FOUND' : 'no') +
                         (res.error ? ' (' + res.error + ')' : ''));
            }
            el.textContent = out.join('\n');
            addLog('Industrial scan OK', 'success');
        } else {
            el.textContent = 'Error: ' + d.error;
            addLog('Industrial scan: ' + d.error, 'error');
        }
    } catch (e) {
        el.textContent = 'Exception: ' + e;
        addLog('Industrial scan: ' + e, 'error');
    }
}

async function sendStego() {
    const target = document.getElementById('stegoTarget').value.trim();
    const method = document.getElementById('stegoMethod').value;
    const data = document.getElementById('stegoData').value;
    if (!target || !data) { addLog('Заполните target и data', 'error'); return; }
    addLog('Stego ' + method + ' -> ' + target + ' (' + data.length + 'B)', 'info');
    try {
        const r = await fetch('/api/stego/send', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ target, method, data })
        });
        const d = await r.json();
        if (d.success) {
            addLog('Stego OK: ' + d.bytes_sent + 'B, overhead ' +
                   (d.overhead ? d.overhead.toFixed(1) + '%' : '0%'), 'success');
        } else {
            addLog('Stego FAIL: ' + (d.error || 'unknown'), 'error');
        }
    } catch (e) {
        addLog('Stego exception: ' + e, 'error');
    }
}

async function forceCatastrophe() {
    addLog('Форсирую катастрофу...', 'warn');
    try {
        const r = await fetch('/api/evolution/catastrophe', { method: 'POST' });
        const d = await r.json();
        if (d.success) {
            const before = d.before.diversity || 0;
            const after = d.after.diversity || 0;
            addLog('Catastrophe gen ' + d.generation +
                   ' div ' + before.toFixed(3) + ' -> ' + after.toFixed(3), 'warn');
        } else {
            addLog('Catastrophe: ' + (d.error || 'fail'), 'error');
        }
    } catch (e) {
        addLog('Catastrophe exception: ' + e, 'error');
    }
}

async function loadBestStrategies() {
    try {
        const r = await fetch('/api/evolution/best_strategies');
        const d = await r.json();
        if (d.success) {
            const el = document.getElementById('evolutionBest');
            el.innerHTML =
                'gen: ' + d.generation + '<br>' +
                'pen: ' + (d.best.penetration || '-') + '<br>' +
                'mask: ' + (d.best.masking || '-') + '<br>' +
                'stego: ' + (d.best.stego || '-') + '<br>' +
                'ind: ' + (d.best.industrial || '-') + '<br>' +
                'best=' + (d.stats.best_fitness || 0).toFixed(3) +
                ' div=' + (d.stats.diversity || 0).toFixed(3);
            addLog('Best strategies loaded', 'success');
        }
    } catch (e) {
        addLog('Best strategies: ' + e, 'error');
    }
}

'@

$content = $content.Substring(0, $jsPos) + $newJS + $content.Substring($jsPos)
Write-Host "[OK] JS functions inserted" -ForegroundColor Green

# Заменяем 'CLEAN BUILD' на 'FULL INTEGRATION'
$content = $content.Replace("InevioNet загружен (CLEAN BUILD)", "InevioNet загружен (FULL INTEGRATION)")

# Сохраняем
$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($path, $content, $utf8)
Write-Host "[OK] index.html saved" -ForegroundColor Green