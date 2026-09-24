@echo off
chcp 65001 >nul
set /p REMOTE="Remote path (e.g. \\192.168.1.100\c$\InevioNet): "
robocopy "%REMOTE%" "%~dp0\.." /E /XO /XD venv __pycache__ /XF *.pyc
pause
