; Inno Setup script for YAAMT (Yet Another Audio Metadata Tool)
;
; This script creates a Windows installer from the PyInstaller output.
;
; Preprocessor defines (passed via /D on command line):
;   AppVersion   - Version string (e.g., "0.1.0" or "d6b6cd1")
;   SourceDir    - Path to the PyInstaller output folder (e.g., build/.../yaamt)
;   OutputDir    - Directory to place the installer .exe
;   Arch         - Architecture string for filename (e.g., "x64" or "arm64")

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif

#ifndef Arch
  #define Arch "x64"
#endif

[Setup]
AppName=YAAMT
AppVersion={#AppVersion}
AppPublisher=Lyjia
AppPublisherURL=https://github.com/lyjia/yaamt
AppSupportURL=https://github.com/lyjia/yaamt/issues
DefaultDirName={autopf}\YAAMT
DefaultGroupName=YAAMT
AllowNoIcons=yes
; Output settings
OutputBaseFilename=yaamt-{#AppVersion}-windows-{#Arch}-setup
Compression=lzma2/ultra64
SolidCompression=yes
; Installer behavior
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
; Architecture
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Visual
WizardStyle=modern
; Uninstaller
UninstallDisplayName=YAAMT
UninstallDisplayIcon={app}\yaamt-gui.exe

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "addtopath"; Description: "Add YAAMT CLI to system PATH"; GroupDescription: "System Integration:"

[Files]
; Install everything from the PyInstaller output folder
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\YAAMT GUI"; Filename: "{app}\yaamt-gui.exe"
Name: "{group}\YAAMT CLI"; Filename: "{cmd}"; Parameters: "/k ""{app}\yaamt.exe"" --help"; IconFilename: "{app}\yaamt.exe"
Name: "{group}\{cm:UninstallProgram,YAAMT}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\YAAMT"; Filename: "{app}\yaamt-gui.exe"; Tasks: desktopicon

[Registry]
; Add to PATH if selected
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{olddata};{app}"; Tasks: addtopath; Check: NeedsAddPath(ExpandConstant('{app}'))

[Run]
Filename: "{app}\yaamt-gui.exe"; Description: "{cm:LaunchProgram,YAAMT}"; Flags: nowait postinstall skipifsilent

[Code]
function NeedsAddPath(Param: string): Boolean;
var
  OrigPath: string;
begin
  if not RegQueryStringValue(HKEY_CURRENT_USER, 'Environment', 'Path', OrigPath) then
  begin
    Result := True;
    exit;
  end;
  { Look for the path with leading and trailing semicolons to avoid partial matches }
  Result := Pos(';' + UpperCase(Param) + ';', ';' + UpperCase(OrigPath) + ';') = 0;
end;
