# Patch 12a-fix3: exact log fix - check BOTH handlers
$ErrorActionPreference = "Stop"
$ProjectRoot = "E:\InevioNet"

$appPath = Join-Path $ProjectRoot "web\app.py"
$app = [System.IO.File]::ReadAllText($appPath, [System.Text.Encoding]::UTF8)
$app = $app -replace "`r`n", "`n"

if ($app.Contains("# P13-HARD-V2")) {
    Write-Host "[--] already applied" -ForegroundColor Yellow
    return
}

# Найти функцию install_log_bridge
$startPos = $app.IndexOf("def install_log_bridge():")
$endPos = $app.IndexOf("`ndef ", $startPos + 10)

if ($startPos -lt 0 -or $endPos -lt 0) {
    Write-Host "[!!] function not found" -ForegroundColor Red
    return
}

$newFunc = @'
def install_log_bridge():
    # P13-HARD-V2: prevent duplicate StreamHandler
    fmt = logging.Formatter(
        '[%(asctime)s] [%(levelname)s] %(name)s: %(message)s',
        datefmt='%H:%M:%S',
    )
    root = logging.getLogger('inevionet')
    
    # Check if already has our handlers
    has_stream = any(
        isinstance(h, logging.StreamHandler) and not isinstance(h, SocketLogHandler)
        for h in root.handlers
    )
    has_socket = any(isinstance(h, SocketLogHandler) for h in root.handlers)
    
    if has_stream and has_socket:
        # Already installed, just update level
        root.setLevel(logging.INFO)
        return
    
    # Remove ALL and reinstall
    for h in list(root.handlers):
        try:
            root.removeHandler(h)
        except Exception:
            pass
    
    sh = logging.StreamHandler(sys.stdout)
    try:
        sh.stream.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass
    sh.setFormatter(fmt)
    root.addHandler(sh)
    
    bh = SocketLogHandler()
    bh.setFormatter(fmt)
    root.addHandler(bh)
    
    root.setLevel(logging.INFO)
    root.propagate = False
'@

$app = $app.Substring(0, $startPos) + $newFunc + $app.Substring($endPos)

$utf8 = New-Object System.Text.UTF8Encoding($false)
[System.IO.File]::WriteAllText($appPath, $app, $utf8)
Write-Host "[OK] exact log fix applied" -ForegroundColor Green

python -c "import ast; ast.parse(open(r'$appPath', encoding='utf-8').read()); print('OK')"

Write-Host ""
Write-Host "Restart server: python -m web.app" -ForegroundColor Cyan