$jsCode = @'
// P13: Industrial / Stego / Evolution functions
async function scanIndustrial() {
    const target = document.getElementById('industrialTarget').value.trim();
    if (!target) { addLog('Enter target', 'error'); return; }
    addLog('Industrial scan: ' + target, 'info');
    const el = document.getElementById('industrialResults');
    el.textContent = 'Scanning...';
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
                out.push(proto + ': ' + (res.found ? 'FOUND' : 'no'));
            }
            el.textContent = out.join(' | ');
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
    if (!target || !data) { addLog('Fill target and data', 'error'); return; }
    addLog('Stego ' + method + ' -> ' + target, 'info');
    try {
        const r = await fetch('/api/stego/send', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ target, method, data })
        });
        const d = await r.json();
        if (d.success) {
            addLog('Stego OK: ' + d.bytes_sent + 'B', 'success');
        } else {
            addLog('Stego FAIL: ' + (d.error || 'unknown'), 'error');
        }
    } catch (e) {
        addLog('Stego exception: ' + e, 'error');
    }
}

async function forceCatastrophe() {
    addLog('Forcing catastrophe...', 'warn');
    try {
        const r = await fetch('/api/evolution/catastrophe', { method: 'POST' });
        const d = await r.json();
        if (d.success) {
            addLog('Catastrophe gen ' + d.generation, 'warn');
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
            el.innerHTML = 'gen:' + d.generation +
                ' pen:' + (d.best.penetration || '-') +
                ' mask:' + (d.best.masking || '-') +
                ' stego:' + (d.best.stego || '-') +
                ' ind:' + (d.best.industrial || '-');
            addLog('Best strategies loaded', 'success');
        }
    } catch (e) {
        addLog('Best strategies: ' + e, 'error');
    }
}

'@

$ProjectRoot = "E:\InevioNet"
$path = Join-Path $ProjectRoot "web\templates\index.html"
$content = [System.IO.File]::ReadAllText($path, [System.Text.Encoding]::UTF8)
$content = $content -replace "`r`n", "`n"

if ($content.Contains("async function scanIndustrial")) {
    Write-Host "[!!] JS already added" -ForegroundColor Yellow
    return
}

$marker = "checkAuth();"
$pos = $content.IndexOf($marker)

if ($pos -lt 0) {
    Write-Host "[!!] checkAuth not found" -ForegroundColor Red
    return
}

Write-Host "checkAuth at: $pos" -ForegroundColor Cyan

$content = $content.Substring(0, $pos) + $jsCode + $content.Substring($pos)

$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($path, $content, $utf8)
Write-Host "[OK] JS inserted" -ForegroundColor Green