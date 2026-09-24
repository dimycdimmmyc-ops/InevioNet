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