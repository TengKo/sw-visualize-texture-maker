; Inno Setup recipe: packs the PyInstaller folder build into one Setup.exe.
; Build the folder first (TM_ONEFILE=0, see texture_maker.spec), then from the repo root:
;   powershell -ExecutionPolicy Bypass -File packaging\build_installer.ps1     -> dist\SW-Visualize-Texture-Maker-Setup.exe
; build_installer.ps1 finds Inno Setup and passes the version from texture_maker\__init__.py.

#ifndef AppVersion
  #error Pass the version: iscc /DAppVersion=1.2.3 packaging\installer.iss (build_installer.ps1 does this)
#endif

#define AppName "SW Visualize Texture Maker"
#define AppExe "SW-Visualize-Texture-Maker.exe"
#define RepoUrl "https://github.com/TengKo/sw-visualize-texture-maker"

[Setup]
; AppId is how Windows recognizes the app. Never change it, or new versions install beside old ones instead of upgrading.
AppId={{D9D94A54-4094-4061-9FD2-3A9CBF7C77BC}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Teng Maceren
AppPublisherURL={#RepoUrl}
AppSupportURL={#RepoUrl}/issues
AppUpdatesURL={#RepoUrl}/releases
VersionInfoVersion={#AppVersion}
; Current user by default (no admin prompt, goes to %LOCALAPPDATA%\Programs). The first page offers "all users",
; and /CURRENTUSER or /ALLUSERS pick it on the command line.
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog commandline
DefaultDirName={autopf}\{#AppName}
DisableProgramGroupPage=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
SetupIconFile=..\texture_maker\assets\icon.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
WizardStyle=modern
Compression=lzma2/max
SolidCompression=yes
OutputDir=..\dist
OutputBaseFilename=SW-Visualize-Texture-Maker-Setup

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[InstallDelete]
; Clear the previous version's libraries first, so an upgrade never mixes old and new files.
Type: filesandordirs; Name: "{app}\_internal"

[Files]
Source: "..\dist\SW-Visualize-Texture-Maker\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: nowait postinstall skipifsilent
