#define MyAppName "FinTrack Advanced"
#define MyAppVersion "1.0.0"
#define MyAppExeName "FinTrackAdvanced.exe"
[Setup]
AppId={{9BA0BAE1-AF2C-4775-BD20-69CEAE4F77A9}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
DefaultDirName={localappdata}\Programs\FinTrackAdvanced
DefaultGroupName={#MyAppName}
OutputDir=instalador
OutputBaseFilename=FinTrackAdvanced_Setup
SetupIconFile=FinTrackAdvanced.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
WizardStyle=modern
[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
[Tasks]
Name: "desktopicon"; Description: "Criar atalho na area de trabalho"; GroupDescription: "Atalhos:"; Flags: checkedonce
[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon
[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Abrir FinTrack Advanced"; Flags: nowait postinstall skipifsilent
