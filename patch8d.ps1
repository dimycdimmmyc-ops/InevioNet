# Patch 8d v2: Auto-installer (ASCII only)
$ErrorActionPreference = "Stop"
$ProjectRoot = "E:\InevioNet"

# === install.bat ===
$installBat = @'
@echo off
chcp 65001 >nul
title InevioNet Installer

echo ============================================================
echo   INEVIONET AUTO-INSTALLER
echo ============================================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo [!!] Python not found!
    echo     Download: https://www.python.org/downloads/
    echo     IMPORTANT: check "Add Python to PATH"
    pause
    exit /b 1
)
echo [OK] Python found
python --version

if not exist "venv" (
    echo.
    echo [1/5] Creating venv...
    python -m venv venv
    echo [OK] venv created
) else (
    echo [--] venv exists
)

call venv\Scripts\activate.bat

echo.
echo [2/5] Installing dependencies...
pip install --quiet --upgrade pip
if exist "requirements.txt" (
    pip install --quiet -r requirements.txt
)
echo [OK] Dependencies installed

echo.
echo [3/5] Installing Tor...
if not exist "tor\tor.exe" (
    powershell -ExecutionPolicy Bypass -File "%~dp0patch8b.ps1"
) else (
    echo [--] Tor already installed
)

echo.
echo [4/5] Visual C++ Build Tools - skip
echo     For BLE: run patch8c.ps1 as admin

echo.
echo [5/5] Starting InevioNet...
echo ============================================================
echo   OPEN BROWSER: https://localhost:8080
echo   ACCEPT CERTIFICATE (self-signed)
echo ============================================================
echo.
echo Press Ctrl+C to stop
echo.

python -m web.app
pause
'@

$installPath = Join-Path $ProjectRoot "install.bat"
[System.IO.File]::WriteAllText($installPath, $installBat, [System.Text.Encoding]::ASCII)
Write-Host "[OK] install.bat" -ForegroundColor Green

# === start.bat ===
$startBat = @'
@echo off
chcp 65001 >nul
title InevioNet
cd /d "%~dp0"
call venv\Scripts\activate.bat

if exist "tor\tor.exe" (
    tasklist /FI "IMAGENAME eq tor.exe" 2>NUL | find /I /N "tor.exe">NUL
    if errorlevel 1 (
        echo Starting Tor...
        start /B "" "tor\tor.exe" -f "tor\torrc"
        timeout /t 5 >nul
    ) else (
        echo Tor already running
    )
)

echo Starting InevioNet...
echo Open: https://localhost:8080
echo.
python -m web.app
pause
'@

$startPath = Join-Path $ProjectRoot "start.bat"
[System.IO.File]::WriteAllText($startPath, $startBat, [System.Text.Encoding]::ASCII)
Write-Host "[OK] start.bat" -ForegroundColor Green

# === README ===
$readmeLines = @(
    "# InevioNet - Quick Start",
    "",
    "## What is it?",
    "",
    "Decentralized P2P network with self-evolution.",
    "Works like mycelium - finds networks, infiltrates, grows.",
    "",
    "## Install (once)",
    "",
    "1. Download Python 3.11+: https://www.python.org/downloads/",
    "   IMPORTANT: check 'Add Python to PATH'",
    "2. Double-click install.bat",
    "3. Wait 5-10 min",
    "",
    "## Run (every time)",
    "",
    "1. Double-click start.bat",
    "2. Open browser: https://localhost:8080",
    "3. Accept certificate",
    "",
    "## UI sections",
    "",
    "- Network map - nodes, WiFi, spores",
    "- Industrial - Modbus/MQTT/OPCUA/DNP3 scan",
    "- Stego - hidden transmission",
    "- Evolution - catastrophes + best strategies",
    "- Network Scanners - Tor, BLE, LTE",
    "",
    "## Tor test",
    "",
    "1. Click 'Check Tor'",
    "2. If AVAILABLE - works",
    "",
    "## Troubleshooting",
    "",
    "Tor not working:",
    "- Check tor\tor.exe exists",
    "- Run start_tor.bat manually",
    "- Test-NetConnection 127.0.0.1 -Port 9050",
    "",
    "BLE not finding:",
    "- Install Visual C++ Build Tools (patch8c.ps1 as admin)",
    "",
    "Server not starting:",
    "- python --version",
    "- venv\Scripts\activate",
    "- pip list",
    "",
    "## Philosophy",
    "",
    "Networks see choice, but there is no choice.",
    "The packet is always delivered."
)

$readmePath = Join-Path $ProjectRoot "README_FOR_DUMMIES.md"
[System.IO.File]::WriteAllLines($readmePath, $readmeLines, [System.Text.UTF8Encoding]::new($false))
Write-Host "[OK] README_FOR_DUMMIES.md" -ForegroundColor Green

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  READY" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Files created:" -ForegroundColor Cyan
Write-Host "  install.bat           - install (once)" -ForegroundColor White
Write-Host "  start.bat             - run (every time)" -ForegroundColor White
Write-Host "  README_FOR_DUMMIES.md - manual" -ForegroundColor White