; Inno Setup script - Telegram Downloader Setup (edition parameterized)
; Compiled by build\build_edition.ps1 with /D defines. Kept encoding-safe ASCII.
;
; Overridable defines (see build_edition.ps1):
;   AppName, AppVersion, AppExeName, AppId, AppFolderName, AppPublisher,
;   OutputBaseFilename, BuildDir, OutputDir

#ifndef AppName
#define AppName "Telegram Downloader"
#endif
#ifndef AppVersion
#define AppVersion "1.0.1"
#endif
#ifndef AppPublisher
#define AppPublisher "Ali Khanmohammadi"
#endif
#ifndef AppPublisherURL
#define AppPublisherURL "https://alikhanmohammadi.ir/"
#endif
#ifndef AppSupportURL
#define AppSupportURL "https://alikhanmohammadi.ir/"
#endif
#ifndef AppUpdatesURL
#define AppUpdatesURL "https://alikhanmohammadi.ir/"
#endif
#ifndef AppExeName
#define AppExeName "TelegramDownloader.exe"
#endif
#ifndef AppId
#define AppId "9B2A6D3E-5F4C-4A7B-9E11-3C0D1E2F4A56"
#endif
#ifndef AppFolderName
#define AppFolderName "TelegramDownloader"
#endif
#ifndef BuildDir
#define BuildDir "..\dist\TelegramDownloader\TelegramDownloader.exe"
#endif
#ifndef OutputDir
#define OutputDir "..\dist"
#endif
#ifndef OutputBaseFilename
#define OutputBaseFilename "TelegramDownloader-Setup"
#endif

[Setup]
AppId={{#AppId}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppPublisherURL}
AppSupportURL={#AppSupportURL}
AppUpdatesURL={#AppUpdatesURL}
DefaultDirName={autopf}\{#AppFolderName}
DefaultGroupName={#AppName}
UninstallDisplayName={#AppName}
AllowNoIcons=yes
UninstallDisplayIcon={app}\{#AppExeName}
VersionInfoVersion={#AppVersion}
VersionInfoCompany={#AppPublisher}
VersionInfoDescription={#AppName} Setup
VersionInfoProductName={#AppName}
VersionInfoProductVersion={#AppVersion}
OutputDir={#OutputDir}
OutputBaseFilename={#OutputBaseFilename}
SetupIconFile=..\resources\icons\app.ico
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
MinVersion=10.0
DisableProgramGroupPage=yes

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Extra icons:"

[Files]
Source: "{#BuildDir}"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExeName}"; IconFilename: "{app}\{#AppExeName}"
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon; IconFilename: "{app}\{#AppExeName}"

[Run]
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName}"; Flags: nowait postinstall skipifsilent

[Code]
var
  RemoveData: Boolean;

function InitializeUninstall: Boolean;
var
  Answer: Integer;
begin
  RemoveData := False;
  Answer := MsgBox('Additionally delete all app data (settings, database, session, history)?' + #13#10 +
                   'Choose Yes to remove everything, No to keep your data for later reinstall.',
                   mbConfirmation, MB_YESNOCANCEL or MB_DEFBUTTON2);
  if Answer = IDCANCEL then
    Result := False
  else begin
    RemoveData := (Answer = IDYES);
    Result := True;
  end;
end;

procedure CurUninstallStepChanged(CurStep: TUninstallStep);
begin
  if (CurStep = usPostUninstall) and RemoveData then
  begin
    DelTree(ExpandConstant('{userappdata}\TelegramDownloader'), True, True, True);
    DelTree(ExpandConstant('{localappdata}\TelegramDownloader'), True, True, True);
  end;
end;