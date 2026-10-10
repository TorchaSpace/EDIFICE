; Inno Setup betiği: Windows kurulum dosyası (EDIFICE-Setup.exe). Kullanım: iscc /DMyVersion=1.2.0 packaging\\installer.iss
#ifndef MyVersion
  #define MyVersion "1.2.0"
#endif
[Setup]
AppId={{6E3A1F0B-7C41-4C2D-9B55-ED1F1C3E0001}
AppName=EDIFI'CE
AppVersion={#MyVersion}
AppPublisher=EDIFI'CE
DefaultDirName={autopf}\EDIFICE
DefaultGroupName=EDIFI'CE
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=EDIFICE-Setup-{#MyVersion}
SetupIconFile=icon.ico
UninstallDisplayIcon={app}\EDIFICE.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "turkish"; MessagesFile: "compiler:Languages\Turkish.isl"

[Tasks]
Name: "desktopicon"; Description: "Masaüstü kısayolu oluştur"; GroupDescription: "Ek görevler:"

[Files]
Source: "..\dist\EDIFICE\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\EDIFI'CE"; Filename: "{app}\EDIFICE.exe"
Name: "{autodesktop}\EDIFI'CE"; Filename: "{app}\EDIFICE.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\EDIFICE.exe"; Description: "EDIFI'CE'yi başlat"; Flags: nowait postinstall skipifsilent
