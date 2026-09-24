param(
    [switch]$Rebuild,   # Пересобрать EXE (PyInstaller)
    [switch]$Clean      # Очистить всё
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "==========================================" -ForegroundColor Cyan
Write-Host "  InevioNet Installer Builder" -ForegroundColor Cyan
Write-Host "==========================================" -ForegroundColor Cyan

# === 1. Проверка PyInstaller ===
if (-not (Get-Command pyinstaller -ErrorAction SilentlyContinue)) {
    Write-Host "[*] Устанавливаю PyInstaller..." -ForegroundColor Yellow
    pip install pyinstaller
}

# === 2. Очистка ===
if ($Clean) {
    Remove-Item -Recurse -Force build, dist, installer_output -ErrorAction SilentlyContinue
    Write-Host "[+] Очищено" -ForegroundColor Green
}

# === 3. Сборка EXE (PyInstaller) ===
if ($Rebuild -or -not (Test-Path "dist\InevioNet\InevioNet.exe")) {
    Write-Host "[*] Собираю EXE (PyInstaller)..." -ForegroundColor Yellow
    pyinstaller InevioNet.spec --clean --noconfirm
    Write-Host "[+] EXE готов: dist\InevioNet\InevioNet.exe" -ForegroundColor Green
} else {
    Write-Host "[--] EXE уже есть: dist\InevioNet\InevioNet.exe" -ForegroundColor DarkGray
}

# === 4. Проверка Inno Setup (P61: per-user + registry) ===
function Find-ISCC {
    $candidates = @(
        "$env:LOCALAPPDATA\Programs\Inno Setup 6\ISCC.exe",
        "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
        "C:\Program Files\Inno Setup 6\ISCC.exe",
        "$env:ProgramFiles\Inno Setup 6\ISCC.exe",
        "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
    )
    foreach ($p in $candidates) {
        if (Test-Path $p) { return $p }
    }
    try {
        $reg = Get-ItemProperty "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1" -ErrorAction SilentlyContinue
        if ($reg -and $reg.InstallLocation) {
            $p = Join-Path $reg.InstallLocation "ISCC.exe"
            if (Test-Path $p) { return $p }
        }
    } catch {}
    try {
        $reg = Get-ItemProperty "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\Inno Setup 6_is1" -ErrorAction SilentlyContinue
        if ($reg -and $reg.InstallLocation) {
            $p = Join-Path $reg.InstallLocation "ISCC.exe"
            if (Test-Path $p) { return $p }
        }
    } catch {}
    return $null
}

$iscc = Find-ISCC

if (-not $iscc) {
    Write-Host "[!!] Inno Setup не найден!" -ForegroundColor Red
    Write-Host "     Скачай: https://jrsoftware.org/isdl.php" -ForegroundColor Yellow
    Write-Host "     Или: winget install JRSoftware.InnoSetup" -ForegroundColor Yellow
    exit 1
}

Write-Host "[+] Inno Setup: $iscc" -ForegroundColor Green

# === 5. Сборка установщика (Inno Setup) ===
Write-Host "[*] Собираю установщик (Inno Setup)..." -ForegroundColor Yellow
& $iscc "InevioNet_Setup.iss"

if ($LASTEXITCODE -ne 0) {
    Write-Host "[!!] Ошибка сборки установщика" -ForegroundColor Red
    exit 1
}

# === 6. Результат ===
$setup = Get-ChildItem "installer_output\*.exe" | Select-Object -First 1
if ($setup) {
    $size_mb = [math]::Round($setup.Length / 1MB, 1)
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor Green
    Write-Host " УСТАНОВЩИК ГОТОВ" -ForegroundColor Green
    Write-Host "==========================================" -ForegroundColor Green
    Write-Host " Файл: $($setup.FullName)" -ForegroundColor Cyan
    Write-Host " Размер: $size_mb MB" -ForegroundColor Cyan
    Write-Host "==========================================" -ForegroundColor Green
    Write-Host ""
    Write-Host " Теперь можно отправлять пользователям!" -ForegroundColor Yellow
    Write-Host " Они запускают: $($setup.Name)" -ForegroundColor Yellow
    Write-Host " Next -> Next -> Finish -> Готово!" -ForegroundColor Yellow
}