#ifndef SourceRoot
  #error "Build with /DSourceRoot=<repository-root>"
#endif
#ifndef AppVersion
  #define AppVersion "0.2.0-alpha.5"
#endif

[Setup]
AppId=DeviceShare.Tools.SetupEXE
AppName=DeviceShare
AppVersion={#AppVersion}
AppVerName=DeviceShare {#AppVersion}
AppPublisher=MT Tech Services LLC
AppPublisherURL=https://github.com/migtam628/DeviceShare
AppSupportURL=https://github.com/migtam628/DeviceShare/issues
DefaultDirName={autopf}\DeviceShare Setup
DefaultGroupName=DeviceShare
OutputDir={#SourceRoot}\release-assets
OutputBaseFilename=DeviceShare-Setup-windows-x64
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\deviceshare-hub-windows-x64.exe
DisableProgramGroupPage=yes
CloseApplications=yes
RestartApplications=no
SetupLogging=yes

[Files]
Source: "{#SourceRoot}\dist\deviceshare-agent-windows-x64.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\dist\deviceshare-hub-windows-x64.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "{#SourceRoot}\config\agent.example.json"; DestDir: "{app}\config"; Flags: ignoreversion
Source: "{#SourceRoot}\docs\INSTALL_NATIVE.md"; DestDir: "{app}\docs"; Flags: ignoreversion
Source: "{#SourceRoot}\SECURITY.md"; DestDir: "{app}\docs"; Flags: ignoreversion

[Icons]
Name: "{autoprograms}\DeviceShare - Setup Guide"; Filename: "{app}\docs\INSTALL_NATIVE.md"

[Run]
Filename: "{app}\docs\INSTALL_NATIVE.md"; Description: "Open setup instructions"; Flags: postinstall shellexec skipifsilent nowait
