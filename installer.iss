; TantuSpank v1.0.0 — Inno Setup installer script
; No admin required. Installs to %LOCALAPPDATA%\TantuSpank.

#define MyAppName "TantuSpank"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "TantuCore"
#define MyAppURL "https://tantucore.online"
#define MyAppExeName "TantuSpank.exe"

[Setup]
AppId={{D37F2C0B-4E38-4F41-86EF-7D9C3A3B43BA}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={localappdata}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=setup
SetupIconFile=icon.ico
Compression=none
SolidCompression=no
WizardStyle=modern
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany=TantuCore Studio
VersionInfoDescription=TantuSpank Utility
VersionInfoCopyright=Copyright (C) 2026 Samarjeet Chand
VersionInfoProductName=TantuSpank
VersionInfoOriginalFileName=TantuSpank.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\TantuSpank\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; Assets and sound-packs are already in the dist\TantuSpank folder thanks to COLLECT

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; IconFilename: "{app}\icon.ico"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
