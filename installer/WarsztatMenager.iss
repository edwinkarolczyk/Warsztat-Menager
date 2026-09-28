#define MyAppName "Warsztat Menager"
#ifndef MyAppVersion
  #define MyAppVersion "0.0.0"
#endif
#define MyAppExeName "WarsztatMenager.exe"

[Setup]
AppId={{DBF7E37A-8F6B-4E71-A92E-3D7D3A9322B0}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
DefaultDirName={autopf}\Warsztat Menager
DefaultGroupName=Warsztat Menager
DisableProgramGroupPage=yes
OutputDir=..\dist\installer
OutputBaseFilename=WarsztatMenager_Setup_{#MyAppVersion}
SetupIconFile=..\11.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
CloseApplications=yes
RestartApplications=no
UsePreviousAppDir=yes

[Files]
Source: "..\dist\WarsztatMenager\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "wm_root.default.json"; DestDir: "{app}"; DestName: "wm_root.json"; Flags: onlyifdoesntexist

[Dirs]
Name: "C:\wm"; Permissions: users-modify; Flags: uninsneveruninstall
Name: "C:\wm\data"; Permissions: users-modify; Flags: uninsneveruninstall
Name: "C:\wm\logs"; Permissions: users-modify; Flags: uninsneveruninstall
Name: "C:\wm\backup"; Permissions: users-modify; Flags: uninsneveruninstall
Name: "C:\wm\assets"; Permissions: users-modify; Flags: uninsneveruninstall

[Icons]
Name: "{autoprograms}\Warsztat Menager"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"
Name: "{autodesktop}\Warsztat Menager"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"

[Run]
Filename: "{sys}\icacls.exe"; Parameters: """C:\wm"" /inheritance:e /grant *S-1-5-32-545:(OI)(CI)M /T /C"; Flags: runhidden waituntilterminated
Filename: "{app}\{#MyAppExeName}"; Description: "Uruchom Warsztat Menager"; Flags: nowait postinstall skipifsilent
