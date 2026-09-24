; -- InevioNet_Setup.iss
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
