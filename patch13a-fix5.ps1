# Patch 13a-fix5: force wifi rescan (disconnect/connect)
$ErrorActionPreference = "Stop"
$ProjectRoot = "E:\InevioNet"
$appPath = Join-Path $ProjectRoot "web\app.py"

# Backup
$backupDir = Join-Path $ProjectRoot "_backup_wifi_force"
New-Item -ItemType Directory -Path $backupDir -Force | Out-Null
Copy-Item $appPath (Join-Path $backupDir "app.py") -Force
Write-Host "Backup: $backupDir\app.py" -ForegroundColor Cyan

$app = [System.IO.File]::ReadAllText($appPath, [System.Text.Encoding]::UTF8)
$app = $app -replace "`r`n", "`n"

if ($app.Contains("_force_wifi_rescan")) {
    Write-Host "[--] already patched" -ForegroundColor Yellow
    exit 0
}

# === 1. Р”РѕР±Р°РІРёС‚СЊ РіР»РѕР±Р°Р»СЊРЅС‹Рµ РїРµСЂРµРјРµРЅРЅС‹Рµ Рё С„СѓРЅРєС†РёСЋ force_rescan ===
$scanStart = $app.IndexOf("def scan_wifi():")
if ($scanStart -lt 0) {
    Write-Host "[!!] scan_wifi not found" -ForegroundColor Red
    exit 1
}
Write-Host "scan_wifi at: $scanStart" -ForegroundColor Cyan

# Р’СЃС‚Р°РІРёС‚СЊ РїРµСЂРµРјРµРЅРЅС‹Рµ + С„СѓРЅРєС†РёСЋ РїРµСЂРµРґ def scan_wifi
$globalsAndHelper = "# P13: force wifi rescan`n" +
"_last_forced_rescan = 0.0`n" +
"_FORCED_RESCAN_INTERVAL = 300  # 5 minutes`n" +
"`n" +
"def _force_wifi_rescan():`n" +
"    import subprocess as _sp`n" +
"    import time as _t`n" +
"    global _last_forced_rescan`n" +
"    now = _t.time()`n" +
"    if now - _last_forced_rescan < _FORCED_RESCAN_INTERVAL:`n" +
"        return False`n" +
"    try:`n" +
"        # Get current SSID`n" +
"        r = _sp.run(['netsh', 'wlan', 'show', 'interfaces'],`n" +
"                    capture_output=True, timeout=3)`n" +
"        try:`n" +
"            raw = r.stdout.decode('cp866', errors='replace')`n" +
"        except Exception:`n" +
"            raw = r.stdout.decode('utf-8', errors='replace')`n" +
"        current_ssid = ''`n" +
"        for line in raw.splitlines():`n" +
"            if 'SSID' in line and 'BSSID' not in line and ':' in line:`n" +
"                parts = line.split(':', 1)`n" +
"                if len(parts) == 2:`n" +
"                    current_ssid = parts[1].strip()`n" +
"                    break`n" +
"        # Disconnect`n" +
"        _sp.run(['netsh', 'wlan', 'disconnect'],`n" +
"                capture_output=True, timeout=3)`n" +
"        _t.sleep(1.5)`n" +
"        # Trigger scan`n" +
"        _sp.run(['netsh', 'wlan', 'show', 'networks'],`n" +
"                capture_output=True, timeout=5)`n" +
"        # Reconnect`n" +
"        if current_ssid:`n" +
"            _sp.run(['netsh', 'wlan', 'connect', 'name=' + current_ssid],`n" +
"                    capture_output=True, timeout=5)`n" +
"        _last_forced_rescan = now`n" +
"        log.info('[WiFi] forced rescan complete (saved=%s)', current_ssid)`n" +
"        return True`n" +
"    except Exception as e:`n" +
"        log.debug('[WiFi] force rescan error: %s', e)`n" +
"        return False`n" +
"`n"

$app = $app.Substring(0, $scanStart) + $globalsAndHelper + $app.Substring($scanStart)
Write-Host "[OK] _force_wifi_rescan() added" -ForegroundColor Green

# === 2. Р’С‹Р·РІР°С‚СЊ _force_wifi_rescan() РІ РЅР°С‡Р°Р»Рµ scan_wifi() ===
$scanFnStart = $app.IndexOf("def scan_wifi():")
$outIdx = $app.IndexOf("out = []", $scanFnStart)
if ($outIdx -lt 0) {
    Write-Host "[!!] out = [] not found" -ForegroundColor Red
    exit 1
}

# Р’СЃС‚Р°РІРёС‚СЊ РІС‹Р·РѕРІ РїРµСЂРµРґ "out = []"
$call = "    # P13: force rescan if needed`n" +
"    try:`n" +
"        _force_wifi_rescan()`n" +
"    except Exception:`n" +
"        pass`n" +
"    out = []"

$app = $app.Substring(0, $outIdx) + $call + $app.Substring($outIdx + 8)
Write-Host "[OK] scan_wifi() patched" -ForegroundColor Green

# Save + check
$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($appPath, $app, $utf8)
Write-Host "[OK] app.py saved" -ForegroundColor Green

$syntax = python -c "import ast; ast.parse(open(r'$appPath', encoding='utf-8').read()); print('OK')" 2>&1
Write-Host "Syntax: $syntax"

if ($syntax -notmatch "OK") {
    Write-Host "[!!] restoring backup" -ForegroundColor Red
    Copy-Item (Join-Path $backupDir "app.py") $appPath -Force
    exit 1
}

Write-Host ""
Write-Host "=== PATCH 13a-fix5 DONE ===" -ForegroundColor Cyan
Write-Host "What it does:" -ForegroundColor Yellow
Write-Host "  - Force rescan every 5 min (disconnect/connect)" -ForegroundColor White
Write-Host "  - Should give 11+ WiFi instead of 1" -ForegroundColor White
Write-Host ""
Write-Host "Restart: python -m web.app" -ForegroundColor Cyan