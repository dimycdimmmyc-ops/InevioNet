@echo off
chcp 65001 >nul
title InevioNet
cd /d "%~dp0\.."
call venv\Scripts\activate.bat
if exist "tor\tor.exe" (
    tasklist /FI "IMAGENAME eq tor.exe" 2>NUL | find /I /N "tor.exe">NUL
    if errorlevel 1 (start /B "" "tor\tor.exe" -f "tor\torrc")
)
echo.
echo INEVIONET STARTING
echo Open: https://localhost:8080
echo.
python -m web.app
pause
