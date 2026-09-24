# Patch 12d: EXE release via PyInstaller
$ErrorActionPreference = "Stop"
$ProjectRoot = "E:\InevioNet"
$DistDir = Join-Path $ProjectRoot "dist"
$BuildDir = Join-Path $ProjectRoot "build"

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  INEVIONET - EXE RELEASE" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Clean old build
Write-Host "[1/5] Cleaning old build..." -ForegroundColor Yellow
if (Test-Path $DistDir) { Remove-Item $DistDir -Recurse -Force }
if (Test-Path $BuildDir) { Remove-Item $BuildDir -Recurse -Force }
Write-Host "[OK] Clean" -ForegroundColor Green

# 2. Create .spec file
Write-Host ""
Write-Host "[2/5] Creating InevioNet.spec..." -ForegroundColor Yellow

$specLines = @(
    "# -*- mode: python ; coding: utf-8 -*-",
    "",
    "from PyInstaller.utils.hooks import collect_submodules, collect_data_files",
    "",
    "# Collect hidden imports",
    "hiddenimports = []",
    "hiddenimports += collect_submodules('flask')",
    "hiddenimports += collect_submodules('flask_socketio')",
    "hiddenimports += collect_submodules('engineio')",
    "hiddenimports += collect_submodules('socketio')",
    "hiddenimports += collect_submodules('eventlet')",
    "hiddenimports += ['inevionet', 'inevionet.network', 'inevionet.mycelium',",
    "                  'inevionet.evolution', 'inevionet.masking',",
    "                  'inevionet.steganography', 'inevionet.industrial',",
    "                  'inevionet.identity', 'inevionet.mesh', 'inevionet.symbiotic',",
    "                  'inevionet.ai', 'inevionet.capsule', 'inevionet.users']",
    "",
    "# Collect data files",
    "datas = []",
    "datas += collect_data_files('flask')",
    "datas += collect_data_files('flask_socketio')",
    "datas += [('web/templates', 'web/templates'),",
    "          ('web/static', 'web/static')]",
    "",
    "block_cipher = None",
    "",
    "a = Analysis(",
    "    ['run_app.py'],",
    "    pathex=[r'" + $ProjectRoot + "'],",
    "    binaries=[],",
    "    datas=datas,",
    "    hiddenimports=hiddenimports,",
    "    hookspath=[],",
    "    runtime_hooks=[],",
    "    excludes=['tkinter', 'matplotlib', 'numpy', 'PIL'],",
    "    win_no_prefer_redirects=False,",
    "    win_private_assemblies=False,",
    "    cipher=block_cipher,",
    "    noarchive=False,",
    ")",
    "",
    "pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)",
    "",
    "exe = EXE(",
    "    pyz,",
    "    a.scripts,",
    "    a.binaries,",
    "    a.zipfiles,",
    "    a.datas,",
    "    [],",
    "    name='InevioNet',",
    "    debug=False,",
    "    bootloader_ignore_signals=False,",
    "    strip=False,",
    "    upx=True,",
    "    upx_exclude=[],",
    "    runtime_tmpdir=None,",
    "    console=True,",
    "    disable_windowed_traceback=False,",
    "    argv_emulation=False,",
    "    target_arch=None,",
    "    codesign_identity=None,",
    "    entitlements_file=None,",
    "    icon=None,",
    ")"
)

[System.IO.File]::WriteAllLines((Join-Path $ProjectRoot "InevioNet.spec"), $specLines, [System.Text.UTF8Encoding]::new($false))
Write-Host "[OK] InevioNet.spec" -ForegroundColor Green

# 3. Create run_app.py (entry point)
Write-Host ""
Write-Host "[3/5] Creating run_app.py..." -ForegroundColor Yellow

$runApp = @(
    '"""InevioNet EXE entry point."""',
    'import os',
    'import sys',
    'import webbrowser',
    'import threading',
    'import time',
    '',
    '# UTF-8 for Windows',
    'if sys.platform == "win32":',
    '    try:',
    '        sys.stdout.reconfigure(encoding="utf-8", errors="replace")',
    '        sys.stderr.reconfigure(encoding="utf-8", errors="replace")',
    '    except Exception:',
    '        pass',
    '',
    '# Add project root to path',
    'if getattr(sys, "frozen", False):',
    '    BASE_DIR = sys._MEIPASS',
    'else:',
    '    BASE_DIR = os.path.dirname(os.path.abspath(__file__))',
    '',
    'sys.path.insert(0, BASE_DIR)',
    '',
    '# Open browser after 3 seconds',
    'def open_browser():',
    '    time.sleep(3)',
    '    try:',
    '        webbrowser.open("https://localhost:8080")',
    '    except Exception:',
    '        pass',
    '',
    'print("=" * 60)',
    'print("  INEVIONET v1.0.0")',
    'print("  Guaranteed Delivery Protocol")',
    'print("=" * 60)',
    'print("")',
    'print("  Starting server...")',
    'print("  Browser will open automatically")',
    'print("  If not - open: https://localhost:8080")',
    'print("")',
    'print("  Press Ctrl+C to stop")',
    'print("=" * 60)',
    'print("")',
    '',
    '# Open browser in background',
    'threading.Thread(target=open_browser, daemon=True).start()',
    '',
    '# Start server',
    'from web.app import app, socketio, install_log_bridge',
    'install_log_bridge()',
    '',
    'if __name__ == "__main__":',
    '    socketio.run(',
    '        app,',
    '        host="0.0.0.0",',
    '        port=8080,',
    '        debug=False,',
    '        allow_unsafe_werkzeug=True,',
    '    )'
)

[System.IO.File]::WriteAllLines((Join-Path $ProjectRoot "run_app.py"), $runApp, [System.Text.UTF8Encoding]::new($false))
Write-Host "[OK] run_app.py" -ForegroundColor Green

# 4. Build EXE
Write-Host ""
Write-Host "[4/5] Building EXE (this takes 5-10 min)..." -ForegroundColor Yellow
Write-Host ""

Set-Location $ProjectRoot
& python -m PyInstaller InevioNet.spec --clean --noconfirm

if (-not (Test-Path (Join-Path $DistDir "InevioNet.exe"))) {
    Write-Host ""
    Write-Host "[!!] EXE not created!" -ForegroundColor Red
    Write-Host "     Check output above for errors" -ForegroundColor Yellow
    exit 1
}

Write-Host ""
Write-Host "[OK] EXE built" -ForegroundColor Green

# 5. Copy resources
Write-Host ""
Write-Host "[5/5] Copying resources..." -ForegroundColor Yellow

$targetDist = Join-Path $DistDir "InevioNet"
if (Test-Path $targetDist) {
    # Copy web/templates
    $webTpl = Join-Path $targetDist "web\templates"
    New-Item -ItemType Directory -Path $webTpl -Force | Out-Null
    Copy-Item "web\templates\*" $webTpl -Recurse -Force

    # Copy web/static
    $webStatic = Join-Path $targetDist "web\static"
    New-Item -ItemType Directory -Path $webStatic -Force | Out-Null
    if (Test-Path "web\static") {
        Copy-Item "web\static\*" $webStatic -Recurse -Force
    }

    # Copy data dir
    $dataDir = Join-Path $targetDist "data"
    New-Item -ItemType Directory -Path $dataDir -Force | Out-Null

    # Copy tor (if exists)
    if (Test-Path "tor\tor.exe") {
        $torDir = Join-Path $targetDist "tor"
        New-Item -ItemType Directory -Path $torDir -Force | Out-Null
        Copy-Item "tor\*" $torDir -Recurse -Force
        Write-Host "[OK] Tor copied" -ForegroundColor Green
    }

    # Copy docs
    if (Test-Path "docs") {
        $docsDir = Join-Path $targetDist "docs"
        New-Item -ItemType Directory -Path $docsDir -Force | Out-Null
        Copy-Item "docs\*" $docsDir -Recurse -Force
    }

    # Copy README
    if (Test-Path "README_FOR_DUMMIES.md") {
        Copy-Item "README_FOR_DUMMIES.md" $targetDist -Force
    }

    # Copy deploy
    if (Test-Path "deploy") {
        $deployDir = Join-Path $targetDist "deploy"
        New-Item -ItemType Directory -Path $deployDir -Force | Out-Null
        Copy-Item "deploy\*" $deployDir -Recurse -Force
    }

    Write-Host "[OK] Resources copied" -ForegroundColor Green
}

# Create launcher
$launcher = "@echo off`r`n" +
"chcp 65001 >nul`r`n" +
"title InevioNet`r`n" +
"cd /d ""%~dp0""`r`n" +
"echo ============================================================`r`n" +
"echo   INEVIONET v1.0.0`r`n" +
"echo ============================================================`r`n" +
"echo.`r`n" +
"if exist ""tor\tor.exe"" (`r`n" +
"    tasklist /FI ""IMAGENAME eq tor.exe"" 2>NUL | find /I /N ""tor.exe"">NUL`r`n" +
"    if errorlevel 1 (start /B """" ""tor\tor.exe"" -f ""tor\torrc"")`r`n" +
")`r`n" +
"echo Starting InevioNet...`r`n" +
"echo.`r`n" +
"InevioNet.exe`r`n" +
"pause`r`n"

$launcherPath = Join-Path $targetDist "START.bat"
[System.IO.File]::WriteAllText($launcherPath, $launcher, [System.Text.Encoding]::ASCII)
Write-Host "[OK] START.bat" -ForegroundColor Green

# Final report
Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  EXE RELEASE DONE" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

$exePath = Join-Path $targetDist "InevioNet.exe"
$exeSize = [math]::Round((Get-Item $exePath).Length / 1MB, 1)

Write-Host "Release folder: $targetDist" -ForegroundColor Cyan
Write-Host "Main EXE: $exeSize MB" -ForegroundColor Cyan
Write-Host ""
Write-Host "Contents:" -ForegroundColor Yellow
Get-ChildItem $targetDist | ForEach-Object {
    if ($_.PSIsContainer) {
        Write-Host "  [DIR]  $($_.Name)/" -ForegroundColor White
    } else {
        Write-Host "  [FILE] $($_.Name) ($([math]::Round($_.Length/1KB, 1)) KB)" -ForegroundColor White
    }
}

Write-Host ""
Write-Host "How to use:" -ForegroundColor Yellow
Write-Host "  1. Copy 'dist\InevioNet' folder to any PC" -ForegroundColor White
Write-Host "  2. Double-click START.bat" -ForegroundColor White
Write-Host "  3. Browser opens automatically" -ForegroundColor White
Write-Host ""
Write-Host "NO PYTHON NEEDED!" -ForegroundColor Green