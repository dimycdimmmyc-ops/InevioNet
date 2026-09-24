# Patch 9c: pass wifi_provider from web/app.py
$ErrorActionPreference = "Stop"
$ProjectRoot = "E:\InevioNet"

$appPath = Join-Path $ProjectRoot "web\app.py"
$app = [System.IO.File]::ReadAllText($appPath, [System.Text.Encoding]::UTF8)
$app = $app -replace "`r`n", "`n"

if ($app.Contains("wifi_provider=scan_wifi")) {
    Write-Host "[--] already patched" -ForegroundColor Yellow
    return
}

# Найдём "net.enable_rf_scanning(interface='Wi-Fi')"
$oldCall = "net.enable_rf_scanning(interface='Wi-Fi')"
$newCall = "net.enable_rf_scanning(interface='Wi-Fi', wifi_provider=scan_wifi)"

if ($app.Contains($oldCall)) {
    $app = $app.Replace($oldCall, $newCall)
    Write-Host "[OK] app.py: wifi_provider passed" -ForegroundColor Green
} else {
    Write-Host "[!!] enable_rf_scanning call not found" -ForegroundColor Yellow
    # Попробуем альтернативу
    $alt = "net.enable_rf_scanning()"
    if ($app.Contains($alt)) {
        $app = $app.Replace($alt, $newCall)
        Write-Host "[OK] app.py: wifi_provider passed (alt)" -ForegroundColor Green
    }
}

$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($appPath, $app, $utf8)
Write-Host "[OK] app.py saved" -ForegroundColor Green

python -c "import ast; ast.parse(open(r'$appPath', encoding='utf-8').read()); print('OK')"