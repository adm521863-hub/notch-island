; Installer Notch Island (Inno Setup 6). Dibangun otomatis oleh GitHub Actions.
#ifndef AppVersion
  #define AppVersion "1.0.0"
#endif

[Setup]
AppId={{8E3D5B7A-2C41-4F6B-9A10-6D2E7C5B4F13}
AppName=Notch Island
AppVersion={#AppVersion}
AppPublisher=Notch Island
DefaultDirName={autopf}\NotchIsland
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=NotchIslandSetup-{#AppVersion}
SetupIconFile=..\assets\icon.ico
UninstallDisplayIcon={app}\NotchIsland.exe
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64
AppMutex=NotchIslandSingleton

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "startup"; Description: "Jalankan Notch Island saat Windows menyala"; GroupDescription: "Tugas tambahan:"
Name: "desktopicon"; Description: "Buat pintasan di desktop"; GroupDescription: "Tugas tambahan:"; Flags: unchecked

[Files]
Source: "..\dist\NotchIsland\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{autoprograms}\Notch Island"; Filename: "{app}\NotchIsland.exe"
Name: "{autodesktop}\Notch Island"; Filename: "{app}\NotchIsland.exe"; Tasks: desktopicon

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "NotchIsland"; ValueData: """{app}\NotchIsland.exe"""; Flags: uninsdeletevalue; Tasks: startup

[Run]
Filename: "{app}\NotchIsland.exe"; Description: "Jalankan Notch Island sekarang"; Flags: nowait postinstall skipifsilent

[UninstallRun]
Filename: "{sys}\taskkill.exe"; Parameters: "/F /IM NotchIsland.exe"; Flags: runhidden; RunOnceId: "StopNotchIsland"
