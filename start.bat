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