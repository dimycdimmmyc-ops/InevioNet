@echo off
chcp 65001 >nul
title InevioNet
cd /d "%~dp0"
echo ============================================================
echo   INEVIONET v3.0.0
echo   Живая сеть
echo ============================================================
echo.
echo Запускаю InevioNet...
echo Открою браузер через 3 секунды.
echo Если не открылся - открой вручную: http://localhost:8080
echo.
echo Нажми Ctrl+C для остановки.
echo.
InevioNet.exe
pause
