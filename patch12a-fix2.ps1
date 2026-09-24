# Patch 12a-fix2: exact multiline fix
$ErrorActionPreference = "Stop"
$ProjectRoot = "E:\InevioNet"

# === 1. Add root.propagate = False ===
$appPath = Join-Path $ProjectRoot "web\app.py"
$app = [System.IO.File]::ReadAllText($appPath, [System.Text.Encoding]::UTF8)
$app = $app -replace "`r`n", "`n"

if ($app.Contains("root.propagate = False")) {
    Write-Host "[--] propagate already set" -ForegroundColor Yellow
} else {
    $old = "    root.setLevel(logging.INFO)"
    $new = "    root.setLevel(logging.INFO)`n    root.propagate = False"
    
    $count = ([regex]::Matches($app, [regex]::Escape($old))).Count
    Write-Host "Found $count occurrences of root.setLevel" -ForegroundColor Cyan
    
    if ($count -gt 0) {
        $pos = $app.IndexOf($old)
        $app = $app.Substring(0, $pos) + $new + $app.Substring($pos + $old.Length)
        Write-Host "[OK] root.propagate = False added" -ForegroundColor Green
    }
}

# === 2. Better handler cleanup ===
$oldCleanup = @'
    # Убираем дубли
    streams = [h for h in root.handlers
               if isinstance(h, logging.StreamHandler)
               and not isinstance(h, SocketLogHandler)]
    for h in streams[1:]:
        root.removeHandler(h)
'@
$newCleanup = @'
    # P13: remove ALL handlers, then re-add
    for h in list(root.handlers):
        root.removeHandler(h)
'@

if ($app.Contains($oldCleanup)) {
    $app = $app.Replace($oldCleanup, $newCleanup)
    Write-Host "[OK] handler cleanup simplified" -ForegroundColor Green
}

$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($appPath, $app, $utf8)
python -c "import ast; ast.parse(open(r'$appPath', encoding='utf-8').read()); print('OK')"

# === 3. Multiline COLORS fix ===
$htmlPath = Join-Path $ProjectRoot "web\templates\index.html"
$html = [System.IO.File]::ReadAllText($htmlPath, [System.Text.Encoding]::UTF8)
$html = $html -replace "`r`n", "`n"

if ($html.Contains("ble:'#00cec9'")) {
    Write-Host "[--] COLORS already patched" -ForegroundColor Yellow
} else {
    $oldColors = @'
const COLORS = {
    self:'#00ff9c', wifi:'#2ed573', bluetooth:'#4a9eff',
    peer:'#00ffff', spore:'#ff6b9d'
};
'@

    $newColors = @'
const COLORS = {
    self:'#00ff9c', wifi:'#2ed573', bluetooth:'#4a9eff',
    peer:'#00ffff', spore:'#ff6b9d',
    ble:'#00cec9', cellular:'#fdcb6e',
    industrial:'#e17055', super:'#ffeaa7'
};
'@

    if ($html.Contains($oldColors)) {
        $html = $html.Replace($oldColors, $newColors)
        Write-Host "[OK] COLORS replaced (multiline)" -ForegroundColor Green
    } else {
        Write-Host "[!!] COLORS multiline pattern not found" -ForegroundColor Red
        # Fallback: insert before closing brace
        $pos1 = $html.IndexOf("spore:'#ff6b9d'")
        if ($pos1 -gt 0) {
            $html = $html.Substring(0, $pos1 + 16) + ",`n    ble:'#00cec9', cellular:'#fdcb6e',`n    industrial:'#e17055', super:'#ffeaa7'" + $html.Substring($pos1 + 16)
            Write-Host "[OK] COLORS inserted (fallback)" -ForegroundColor Green
        }
    }
}

$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($htmlPath, $html, $utf8)
Write-Host "[OK] index.html saved" -ForegroundColor Green

Write-Host ""
Write-Host "Restart server to apply." -ForegroundColor Cyan