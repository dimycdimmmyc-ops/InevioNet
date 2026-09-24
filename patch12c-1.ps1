# Patch 12c-1: deploy .bat files
$ErrorActionPreference = "Stop"
$ProjectRoot = "E:\InevioNet"
$DeployDir = Join-Path $ProjectRoot "deploy"
New-Item -ItemType Directory -Path $DeployDir -Force | Out-Null

$installBat = "echo off`r`nchcp 65001 >nul`r`ntitle InevioNet Install`r`n" +
"echo ============================================================`r`n" +
"echo   INEVIONET REMOTE INSTALL`r`n" +
"echo ============================================================`r`n" +
"echo.`r`npython --version >nul 2>&1`r`n" +
"if errorlevel 1 (`r`n" +
"    echo [!!] Python not found!`r`n" +
"    echo     Download: https://www.python.org/downloads/`r`n" +
"    pause`r`n" +
"    exit /b 1`r`n" +
")`r`necho [OK] Python found`r`n" +
"python --version`r`n" +
"if not exist ""venv"" (python -m venv venv)`r`n" +
"call venv\Scripts\activate.bat`r`n" +
"pip install --quiet --upgrade pip`r`n" +
"if exist ""requirements.txt"" (pip install --quiet -r requirements.txt)`r`n" +
"pip install --quiet aiortc 2>nul`r`n" +
"echo.`r`necho INSTALL COMPLETE`r`n" +
"echo Run: deploy\start_remote.bat`r`n" +
"pause`r`n"

$installPath = Join-Path $DeployDir "install_remote.bat"
[System.IO.File]::WriteAllText($installPath, $installBat, [System.Text.Encoding]::ASCII)
Write-Host "[OK] install_remote.bat" -ForegroundColor Green

$startBat = "@echo off`r`nchcp 65001 >nul`r`ntitle InevioNet`r`n" +
"cd /d ""%~dp0\..""`r`n" +
"call venv\Scripts\activate.bat`r`n" +
"if exist ""tor\tor.exe"" (`r`n" +
"    tasklist /FI ""IMAGENAME eq tor.exe"" 2>NUL | find /I /N ""tor.exe"">NUL`r`n" +
"    if errorlevel 1 (start /B """" ""tor\tor.exe"" -f ""tor\torrc"")`r`n" +
")`r`n" +
"echo.`r`necho INEVIONET STARTING`r`n" +
"echo Open: https://localhost:8080`r`n" +
"echo.`r`npython -m web.app`r`npause`r`n"

$startPath = Join-Path $DeployDir "start_remote.bat"
[System.IO.File]::WriteAllText($startPath, $startBat, [System.Text.Encoding]::ASCII)
Write-Host "[OK] start_remote.bat" -ForegroundColor Green

$syncBat = "@echo off`r`nchcp 65001 >nul`r`n" +
"set /p REMOTE=""Remote path (e.g. \\192.168.1.100\c$\InevioNet): ""`r`n" +
"robocopy ""%REMOTE%"" ""%~dp0\.."" /E /XO /XD venv __pycache__ /XF *.pyc`r`n" +
"pause`r`n"

$syncPath = Join-Path $DeployDir "sync.bat"
[System.IO.File]::WriteAllText($syncPath, $syncBat, [System.Text.Encoding]::ASCII)
Write-Host "[OK] sync.bat" -ForegroundColor Green

Write-Host ""
Write-Host "Next: patch12c-2 for README + PowerShell" -ForegroundColor Cyan