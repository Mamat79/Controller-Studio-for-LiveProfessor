#define MyAppName "Controller Studio for LiveProfessor"
#define MyAppVersion "2026.5"
#define MyAppPublisher "Mamat"
#define MyAppExeName "Controller-Studio-for-LiveProfessor.exe"
#define MyShortcutName "Controller Studio for LiveProfessor"
#define ProjectRoot "..\.."

[Setup]
AppId={{B4A6A8F2-6F9A-4D0D-B6A4-5E7B4D7D9D1E}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={localappdata}\Programs\Controller Studio for LiveProfessor
DefaultGroupName={#MyShortcutName}
DisableProgramGroupPage=yes
OutputDir={#ProjectRoot}\dist
OutputBaseFilename=Controller-Studio-for-LiveProfessor-Setup-v{#MyAppVersion}
SetupIconFile={#ProjectRoot}\src\silemio_control_hub\assets\controller-studio.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
PrivilegesRequired=lowest
UsedUserAreasWarning=no
UninstallDisplayIcon={app}\{#MyAppExeName}
VersionInfoVersion=2026.5.0.0
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} installer
VersionInfoProductName={#MyAppName}
SetupLogging=yes
CloseApplications=yes
RestartApplications=no
UsePreviousAppDir=no
UsePreviousGroup=no

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
Source: "{#ProjectRoot}\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#ProjectRoot}\THIRD_PARTY_NOTICES.md"; DestDir: "{app}"; Flags: ignoreversion

[InstallDelete]
Type: files; Name: "{app}\Uninstall-SiLeMIO-Controller-Studio.ps1"
Type: files; Name: "{autodesktop}\SiLeMI-O Controller Studio for LiveProfessor.lnk"
Type: files; Name: "{userprograms}\SiLeMI-O Controller Studio for LiveProfessor.lnk"

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Uninstall\SiLeMIOControllerStudio"; Flags: deletekey dontcreatekey

[Icons]
Name: "{group}\{#MyShortcutName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\{#MyShortcutName}"; Filename: "{app}\{#MyAppExeName}"; WorkingDir: "{app}"; IconFilename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: nowait postinstall skipifsilent

[Code]
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    RegDeleteValue(
      HKCU,
      'Software\Microsoft\Windows\CurrentVersion\Run',
      'Controller Studio for LiveProfessor'
    );
end;
