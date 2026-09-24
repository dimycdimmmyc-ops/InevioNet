# Patch 12c: Deployment to second PC
$ErrorActionPreference = "Stop"
$ProjectRoot = "E:\InevioNet"
$DeployDir = Join-Path $ProjectRoot "deploy"

New-Item -ItemType Directory -Path $DeployDir -Force | Out-Null

# === 1. install_remote.bat ===
$installBat = @'
@echo off
chcp 65001 >nul
title InevioNet - Remote Install

echo ============================================================
echo   INEVIONET REMOTE INSTALL
echo ============================================================
echo.
echo This script installs InevioNet on THIS computer.
echo Requirements:
echo   - Windows 10/11
echo   - Python 3.10+ (with "Add to PATH")
echo   - 2 GB free space
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [!!] Python not found!
    echo     Download: https://www.python.org/downloads/
    echo     IMPORTANT: Check "Add Python to PATH"
    pause
    exit /b 1
)
echo [OK] Python found
python --version
echo.

REM Create venv
if not exist "venv" (
    echo [1/4] Creating virtual environment...
    python -m venv venv
    echo [OK] venv created
) else (
    echo [--] venv exists
)

REM Activate venv
call venv\Scripts\activate.bat

REM Install dependencies
echo.
echo [2/4] Installing dependencies...
pip install --quiet --upgrade pip
if exist "requirements.txt" (
    pip install --quiet -r requirements.txt
)
echo [OK] Dependencies installed

REM Optional: aiortc for WebRTC
echo.
echo [3/4] Installing optional packages...
pip install --quiet aiortc 2>nul
echo [OK] aiortc (WebRTC)

REM I2P check
echo.
echo [4/4] I2P check...
if exist "tor\tor.exe" (
    echo [--] Tor found
) else (
    echo [--] Tor not installed (optional)
)
echo.

echo ============================================================
echo   INSTALL COMPLETE
echo ============================================================
echo.
echo Next steps:
echo   1. Run start_remote.bat
echo   2. Open browser: https://localhost:8080
echo   3. Accept certificate
echo.
pause
'@

$installPath = Join-Path $DeployDir "install_remote.bat"
[System.IO.File]::WriteAllText($installPath, $installBat, [System.Text.Encoding]::ASCII)
Write-Host "[OK] Created: deploy\install_remote.bat" -ForegroundColor Green

# === 2. start_remote.bat ===
$startBat = @'
@echo off
chcp 65001 >nul
title InevioNet
cd /d "%~dp0\.."
call venv\Scripts\activate.bat

REM Start Tor if available
if exist "tor\tor.exe" (
    tasklist /FI "IMAGENAME eq tor.exe" 2>NUL | find /I /N "tor.exe">NUL
    if errorlevel 1 (
        echo Starting Tor...
        start /B "" "tor\tor.exe" -f "tor\torrc"
        timeout /t 3 >nul
    )
)

echo.
echo ============================================================
echo   INEVIONET STARTING
echo ============================================================
echo   Local:   https://localhost:8080
echo   Network: https://YOUR_IP:8080
echo.
echo   Press Ctrl+C to stop
echo ============================================================
echo.

python -m web.app
pause
'@

$startPath = Join-Path $DeployDir "start_remote.bat"
[System.IO.File]::WriteAllText($startPath, $startBat, [System.Text.Encoding]::ASCII)
Write-Host "[OK] Created: deploy\start_remote.bat" -ForegroundColor Green

# === 3. check_connection.ps1 ===
$checkPs = @'
# Check P2P connection between two nodes
param(
    [string]$RemoteHost = "192.168.1.100",
    [int]$RemotePort = 8080
)

Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  INEVIONET - P2P CONNECTION CHECK" -ForegroundColor Cyan
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host ""

# Test 1: Ping
Write-Host "[1/4] Ping test..." -ForegroundColor Yellow
$ping = Test-Connection -ComputerName $RemoteHost -Count 3 -Quiet
if ($ping) {
    Write-Host "  [OK] Host reachable" -ForegroundColor Green
} else {
    Write-Host "  [!!] Host not reachable" -ForegroundColor Red
}
Write-Host ""

# Test 2: Port 8080
Write-Host "[2/4] Port $RemotePort test..." -ForegroundColor Yellow
$port = Test-NetConnection -ComputerName $RemoteHost -Port $RemotePort -WarningAction SilentlyContinue
if ($port.TcpTestSucceeded) {
    Write-Host "  [OK] Port open" -ForegroundColor Green
} else {
    Write-Host "  [!!] Port closed" -ForegroundColor Red
}
Write-Host ""

# Test 3: HTTP check
Write-Host "[3/4] HTTP check..." -ForegroundColor Yellow
try {
    $url = "https://${RemoteHost}:${RemotePort}/api/me"
    $response = Invoke-WebRequest -Uri $url -UseBasicParsing -SkipCertificateCheck -TimeoutSec 5 -ErrorAction SilentlyContinue
    if ($response.StatusCode -eq 401 -or $response.StatusCode -eq 200) {
        Write-Host "  [OK] InevioNet responding (HTTP $($response.StatusCode))" -ForegroundColor Green
    }
} catch {
    Write-Host "  [--] Cannot verify (might need cert)" -ForegroundColor Yellow
}
Write-Host ""

# Test 4: Multicast discovery
Write-Host "[4/4] Multicast discovery..." -ForegroundColor Yellow
Write-Host "  Sending beacon on 224.0.0.251:9555..." -ForegroundColor Gray
try {
    $udp = New-Object System.Net.Sockets.UdpClient
    $udp.EnableBroadcast = $true
    $msg = [System.Text.Encoding]::UTF8.GetBytes('{"type":"inevionet_probe"}')
    $udp.Send($msg, $msg.Length, "224.0.0.251", 9555) | Out-Null
    $udp.Close()
    Write-Host "  [OK] Beacon sent" -ForegroundColor Green
} catch {
    Write-Host "  [!!] Beacon failed: $_" -ForegroundColor Red
}

Write-Host ""
Write-Host "============================================================" -ForegroundColor Cyan
Write-Host "  DONE" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Cyan
'@

$checkPath = Join-Path $DeployDir "check_connection.ps1"
[System.IO.File]::WriteAllText($checkPath, $checkPs, [System.Text.UTF8Encoding]::new($false))
Write-Host "[OK] Created: deploy\check_connection.ps1" -ForegroundColor Green

# === 4. sync.bat ===
$syncBat = @'
@echo off
chcp 65001 >nul
title InevioNet Sync

echo ============================================================
echo   INEVIONET SYNC
echo ============================================================
echo.

set /p REMOTE="Enter remote PC path (e.g. \\192.168.1.100\c$\InevioNet): "

if "%REMOTE%"=="" (
    echo [!!] No path entered
    pause
    exit /b 1
)

echo.
echo [1/3] Syncing code...
robocopy "%REMOTE%" "%~dp0\.." /E /XO /XD venv __pycache__ .git /XF *.pyc *.log

echo.
echo [2/3] Syncing data...
robocopy "%REMOTE%\data" "%~dp0\..\data" /E /XO

echo.
echo [3/3] Done
echo.
echo Note: venv is NOT synced (platform-specific)
echo       Run install_remote.bat on remote PC first
echo.
pause
'@

$syncPath = Join-Path $DeployDir "sync.bat"
[System.IO.File]::WriteAllText($syncPath, $syncBat, [System.Text.Encoding]::ASCII)
Write-Host "[OK] Created: deploy\sync.bat" -ForegroundColor Green

# === 5. README.md ===
$readme = @'
# InevioNet - Deployment Guide

## Quick Start (Second PC)

### Step 1: Copy project

Copy `E:\InevioNet` to second PC (anywhere, e.g. `C:\InevioNet`).

You can:
- **USB flash** - copy folder manually
- **Network share** - `robocopy \\PC1\E$\InevioNet C:\InevioNet /E`
- **Git** - `git clone <repo>`

### Step 2: Install

On second PC:
1. Install **Python 3.10+** from https://www.python.org/downloads/
   - **IMPORTANT**: Check "Add Python to PATH"
2. Open `deploy\install_remote.bat` (double click)
3. Wait 3-5 minutes

### Step 3: Run

Double-click `deploy\start_remote.bat`.

Open browser: `https://localhost:8080`

Accept certificate.

## P2P Connection

### Between two PCs on same LAN

**PC1** (yours):
- Open UI: `https://localhost:8080`
- Note your IP: run `ipconfig` → look for IPv4 (e.g. `192.168.1.180`)

**PC2** (remote):
- Open UI: `https://localhost:8080`
- Note your IP: `ipconfig` → (e.g. `192.168.1.100`)

### Test connection

On PC1:
```powershell
cd deploy
powershell -ExecutionPolicy Bypass -File check_connection.ps1 -RemoteHost 192.168.1.100