; TantuSpank v1.0.0 — Inno Setup installer script
; No admin required. Installs to %LOCALAPPDATA%\TantuSpank.

#define MyAppName "TantuSpank"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "TantuCore"
#define MyAppURL "https://github.com/chandrana17/TantuSpank"
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
OutputBaseFilename=TantuSpank_Setup_v{#MyAppVersion}
SetupIconFile=icon.ico
Compression=lzma
SolidCompression=yes
WizardStyle=modern

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "sound-packs\*"; DestDir: "{app}\sound-packs"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "assets\crack.png"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "assets\donate_qr.png"; DestDir: "{app}\assets"; Flags: ignoreversion
Source: "icon.ico"; DestDir: "{app}"; Flags: ignoreversion
Source: "icon.png"; DestDir: "{app}"; Flags: ignoreversion
; NOTE: Do NOT bundle settings.json — it is user-specific and created at runtime

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\icon.ico"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; IconFilename: "{app}\icon.ico"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent
