# patch53.py - InevioNet: Inno Setup installer
import os

ROOT = r"E:\InevioNet"

# === 1. installer.iss — Inno Setup script ===
ISS = r'''; -- InevioNet_Setup.iss
; Inno Setup script for InevioNet
; Build: iscc InevioNet_Setup.iss

#define MyAppName "InevioNet"
#define MyAppVersion "3.0.0"
#define MyAppPublisher "InevioNet Project"
#define MyAppURL "https://github.com/inevionet"
#define MyAppExeName "InevioNet.exe"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
LicenseFile=docs\LICENSE.txt
OutputDir=installer_output
OutputBaseFilename=InevioNet_Setup_v{#MyAppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesInstallIn64BitMode=x64
ArchitecturesAllowed=x64
UninstallDisplayIcon={app}\{#MyAppExeName}
DisableProgramGroupPage=yes

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "autostart"; Description: "Запускать InevioNet при входе в Windows"; GroupDescription: "Автозапуск:"; Flags: unchecked

[Files]
; Основные файлы из dist\InevioNet\
Source: "dist\InevioNet\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Документация
Source: "docs\*"; DestDir: "{app}\docs"; Flags: ignoreversion recursesubdirs
; README для пользователя
Source: "README_FOR_DUMMIES.md"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[Registry]
; Автозапуск (опционально)
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "InevioNet"; ValueData: """{app}\{#MyAppExeName}"""; Flags: uninsdeletevalue; Tasks: autostart

[UninstallDelete]
Type: filesandordirs; Name: "{app}\logs"
Type: filesandordirs; Name: "{app}\data\cache"
Type: files; Name: "{app}\data\*.tmp"

[Code]
function InitializeSetup(): Boolean;
var
  Version: TWindowsVersion;
begin
  GetWindowsVersionEx(Version);
  if Version.Major < 10 then
  begin
    MsgBox('InevioNet требует Windows 10 или выше.', mbError, MB_OK);
    Result := False;
    Exit;
  end;
  Result := True;
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
  begin
    // Создать папки для данных
    ForceDirectories(ExpandConstant('{app}\data'));
    ForceDirectories(ExpandConstant('{app}\data\users'));
    ForceDirectories(ExpandConstant('{app}\data\users\qr_codes'));
    ForceDirectories(ExpandConstant('{app}\logs'));
  end;
end;
'''

with open(os.path.join(ROOT, 'InevioNet_Setup.iss'), 'w', encoding='utf-8') as f:
    f.write(ISS)
print('[OK] InevioNet_Setup.iss')

# === 2. build_installer.ps1 — сборка установщика ===
BUILD = r'''param(
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

# === 4. Проверка Inno Setup ===
$inno_paths = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe"
)
$iscc = $null
foreach ($p in $inno_paths) {
    if (Test-Path $p) {
        $iscc = $p
        break
    }
}

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
'''

with open(os.path.join(ROOT, 'build_installer.ps1'), 'w', encoding='utf-8-sig') as f:
    f.write(BUILD)
print('[OK] build_installer.ps1')

# === 3. LICENSE.txt ===
LICENSE = '''InevioNet - Живая сеть
Copyright (c) 2026 InevioNet Project

Разрешается свободное использование, модификация и распространение
в некоммерческих целях.

ПРОГРАММА ПРЕДОСТАВЛЯЕТСЯ "КАК ЕСТЬ", БЕЗ КАКИХ-ЛИБО ГАРАНТИЙ.
АВТОРЫ НЕ НЕСУТ ОТВЕТСТВЕННОСТИ ЗА ЛЮБОЙ УЩЕРБ.

Философия: Сети видят выбор, но выбора нет. Пакет всегда доставляется.
'''
os.makedirs(os.path.join(ROOT, 'docs'), exist_ok=True)
with open(os.path.join(ROOT, 'docs', 'LICENSE.txt'), 'w', encoding='utf-8') as f:
    f.write(LICENSE)
print('[OK] docs/LICENSE.txt')

# === 4. README_FOR_DUMMIES.md ===
README = '''# InevioNet — инструкция для пользователя

## Что это

**InevioNet** — децентрализованная живая сеть. Она сама находит сети,
сама растёт, сама эволюционирует. Работает без VPN, без серверов.

## Установка

1. **Двойной клик** на `InevioNet_Setup.exe`
2. **Next** → **Next** → **Finish**
3. На рабочем столе появится **ярлык InevioNet**
4. **Двойной клик** на ярлык — сеть запустится

## Запуск

- **Двойной клик** на ярлыке → откроется браузер с UI
- Или: `Пуск` → `InevioNet`
- **Первый раз**: зарегистрируйся (имя + пароль)
- **Готово!** Сеть работает

## Что нужно

- **Windows 10/11** (64-bit)
- **Wi-Fi адаптер** (для сканирования сетей)
- **4 GB RAM** минимум
- **Python НЕ нужен** — всё включено

## Что внутри

- **InevioNet.exe** — главный файл
- **tor/** — Tor Expert Bundle (анонимность)
- **data/** — твои данные (пользователи, сообщения)
- **web/** — UI
- **docs/** — документация

## Отправка сообщений

1. **UI** → **Мой QR** → **Скопировать ID**
2. Отправь ID другу (Telegram, SMS и т.д.)
3. Друг отправит **свой** ID тебе
4. **UI** → **Контакты** → **Добавить контакт** → вставь ID
5. **UI** → **Написать** → **Кому**: имя друга → **Отправить**

## Обновление

Скачай **новый** `InevioNet_Setup.exe` → запусти → он **обновит** старую версию.
**Данные сохранятся.**

## Удаление

**Пуск** → **InevioNet** → **Uninstall**.
Или: **Параметры** → **Приложения** → **InevioNet** → **Удалить**.

## Если не работает

1. **Антивирус** — добавь в исключения
2. **Firewall** — разреши доступ к сети
3. **Порт 8080 занят** — закрой другой сервер
4. **Логи** — `C:\\Program Files\\InevioNet\\logs\\inevionet.log`

## Безопасность

- **Не** делись `data/users/` — там пароли
- **I2P** — опционально (если установлен)
- **Tor** — опционально (если есть `tor/tor.exe`)

## Философия

> Сети видят выбор, но выбора нет. Пакет всегда доставляется.

**Мицелий растёт. Сеть живёт. Сообщения доходят.**
'''

with open(os.path.join(ROOT, 'README_FOR_DUMMIES.md'), 'w', encoding='utf-8') as f:
    f.write(README)
print('[OK] README_FOR_DUMMIES.md')

print()
print("=" * 70)
print("  PATCH 53 DONE")
print("=" * 70)
print()
print("Теперь:")
print("  1. Установи Inno Setup:")
print("     winget install JRSoftware.InnoSetup")
print()
print("  2. Собери всё:")
print("     .\\build_installer.ps1 -Clean -Rebuild")
print()
print("Результат:")
print("  installer_output\\InevioNet_Setup_v3.0.0.exe")
print()
print("Отправляй этот файл пользователям!")