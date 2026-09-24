echo off
chcp 65001 >nul
title InevioNet Install
echo ============================================================
echo   INEVIONET REMOTE INSTALL
echo ============================================================
echo.
python --version >nul 2>&1
if errorlevel 1 (
    echo [!!] Python not found!
    echo     Download: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python found
python --version
if not exist "venv" (python -m venv venv)
call venv\Scripts\activate.bat
pip install --quiet --upgrade pip
if exist "requirements.txt" (pip install --quiet -r requirements.txt)
pip install --quiet aiortc 2>nul
echo.
echo INSTALL COMPLETE
echo Run: deploy\start_remote.bat
pause
