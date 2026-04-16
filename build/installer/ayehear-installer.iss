; AYE Hear — Inno Setup 6 installer script
; Replaces the NSIS baseline (ayehear-installer.nsi).
; Requires Inno Setup 6.x — https://jrsoftware.org/isinfo.php
;
; Build via Build-WindowsPackage.ps1 -BuildInstaller, or manually:
;   iscc /DProductVersion=0.1.0 /DDistDir="G:\Repo\aye-hear\dist\AyeHear" ayehear-installer.iss
;
; ADR refs: ADR-0002 (Stack), ADR-0006 (PostgreSQL), ADR-0009 (Encryption)
; Task: HEAR-035 / HEAR-017

#ifndef ProductVersion
  #define ProductVersion "0.0.0-dev"
#endif

#ifndef DistDir
  #error "DistDir must point to the PyInstaller onedir bundle (dist\AyeHear)"
#endif

; ---------------------------------------------------------------------------
[Setup]
; ---------------------------------------------------------------------------
AppName=AYE Hear
AppVersion={#ProductVersion}
AppVerName=AYE Hear {#ProductVersion}
AppPublisher=AYE Hear
AppPublisherURL=https://github.com/AYESELL/AYE-Hear
AppSupportURL=https://github.com/AYESELL/AYE-Hear/issues
AppUpdatesURL=https://github.com/AYESELL/AYE-Hear/releases

; Installation path (consistent with ADR-0006 and WINDOWS_PACKAGING_RUNBOOK)
DefaultDirName=C:\AyeHear\app
DefaultGroupName=AYE Hear

; Output
OutputDir=..\..\dist
OutputBaseFilename=AyeHear-Setup-{#ProductVersion}
Compression=lzma2/ultra64
SolidCompression=yes

; Visuals
WizardStyle=modern
WizardSizePercent=120
WizardImageFile=..\..\assets\installer-sidebar.bmp
WizardSmallImageFile=..\..\assets\installer-header.bmp
SetupIconFile=..\..\assets\ayehear.ico
UninstallDisplayIcon={app}\AyeHear.exe
UninstallDisplayName=AYE Hear {#ProductVersion}

; Privileges & architecture
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; Misc
DisableDirPage=no
DisableProgramGroupPage=yes
ShowLanguageDialog=no
DisableWelcomePage=no
AllowNoIcons=yes
VersionInfoVersion={#ProductVersion}
VersionInfoCompany=AYE Hear
VersionInfoDescription=AYE Hear Setup

; ---------------------------------------------------------------------------
[Languages]
; ---------------------------------------------------------------------------
Name: "english"; MessagesFile: "compiler:Default.isl"

; ---------------------------------------------------------------------------
[Tasks]
; ---------------------------------------------------------------------------
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; \
  GroupDescription: "{cm:AdditionalIcons}"

; ---------------------------------------------------------------------------
[Files]
; ---------------------------------------------------------------------------
Source: "{#DistDir}\*"; DestDir: "{app}"; \
  Flags: ignoreversion recursesubdirs createallsubdirs

; Runtime install notes (ADR-0006 / ADR-0009 compliance reminders)
Source: "runtime-install-notes.txt"; DestDir: "{app}"; Flags: ignoreversion

; PostgreSQL provisioning scripts — copied to a persistent tools folder outside
; the versioned app dir so they survive upgrades.
Source: "..\..\tools\scripts\Install-PostgresRuntime.ps1"; \
  DestDir: "{commonappdata}\AYE Hear\scripts"; Flags: ignoreversion
Source: "..\..\tools\scripts\Start-AyeHearRuntime.ps1"; \
  DestDir: "{commonappdata}\AYE Hear\scripts"; Flags: ignoreversion

; Bundled PostgreSQL 16 installer (optional — place alongside this .iss before
; building for offline/enterprise deployments; omit for online-install path).
; Source: "pg-installer\postgresql-16.4-1-windows-x64.exe"; \
;   DestDir: "{commonappdata}\AYE Hear\pg-installer"; Flags: ignoreversion

; ---------------------------------------------------------------------------
[Icons]
; ---------------------------------------------------------------------------
Name: "{group}\AYE Hear";            Filename: "{app}\AyeHear.exe"
Name: "{group}\Uninstall AYE Hear";  Filename: "{uninstallexe}"
Name: "{commondesktop}\AYE Hear";    Filename: "{app}\AyeHear.exe"; \
  Tasks: desktopicon

; ---------------------------------------------------------------------------
[Run]
; ---------------------------------------------------------------------------
; Step 1: Provision PostgreSQL 16 runtime (ADR-0006).
;   Runs elevated (installer already has admin); -Force omitted so re-installs
;   are non-destructive.  InstallDir is derived dynamically from the chosen
;   install directory so non-default paths (e.g. D:\AyeHear) work correctly.
Filename: "powershell.exe"; \
  Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{commonappdata}\AYE Hear\scripts\Install-PostgresRuntime.ps1"" -InstallDir ""{code:GetInstallRoot}"" -AppBinDir ""{app}"""; \
  Description: "Provisioning local database (PostgreSQL 16)..."; \
  Flags: runhidden waituntilterminated; \
  StatusMsg: "Setting up local database..."

; Step 2: Post-install health check — verifies DB is ready before first launch.
Filename: "powershell.exe"; \
  Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{commonappdata}\AYE Hear\scripts\Start-AyeHearRuntime.ps1"" -InstallDir ""{code:GetInstallRoot}"""; \
  Description: "Validating database health..."; \
  Flags: runhidden waituntilterminated; \
  StatusMsg: "Validating database health..."

; Step 3: Launch app after install (user-selectable).
Filename: "{app}\AyeHear.exe"; \
  Description: "{cm:LaunchProgram,AYE Hear}"; \
  Flags: nowait postinstall skipifsilent

; ---------------------------------------------------------------------------
[UninstallRun]
; ---------------------------------------------------------------------------
; Stop the AyeHearDB service on uninstall (data directory preserved by default).
Filename: "powershell.exe"; \
  Parameters: "-NoProfile -ExecutionPolicy Bypass -Command ""Stop-Service AyeHearDB -ErrorAction SilentlyContinue"""; \
  RunOnceId: "StopAyeHearDB"; \
  Flags: runhidden waituntilterminated

; ---------------------------------------------------------------------------
[UninstallDelete]
; ---------------------------------------------------------------------------
; Remove the runtime notes file on uninstall
Type: files; Name: "{app}\runtime-install-notes.txt"

; ---------------------------------------------------------------------------
; Registry: persist install root as a machine-level env var so the app can
; discover it via AYEHEAR_INSTALL_DIR without relying solely on EXE path logic.
; ---------------------------------------------------------------------------
[Registry]
Root: HKLM; \
  Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"; \
  ValueType: string; ValueName: "AYEHEAR_INSTALL_DIR"; \
  ValueData: "{code:GetInstallRoot}"; \
  Flags: uninsdeletevalue

; ---------------------------------------------------------------------------
[Code]
// ---------------------------------------------------------------------------
// Returns the install root directory from the user-selected path.
//
// DefaultDirName = C:\AyeHear\app  ->  install root = C:\AyeHear (parent of \app).
// If the user keeps any path ending in \app the same ascent applies.
// If the user chooses a custom path that does NOT end in \app (e.g. D:\AyeHear),
// that chosen directory IS the install root — do not ascend a further level.
//
// HEAR-089: hardens edge cases identified in HEAR-086/HEAR-088 QA.
function GetInstallRoot(Param: String): String;
var
  DirValue: String;
begin
  DirValue := WizardDirValue;
  if LowerCase(ExtractFileName(DirValue)) = 'app' then
    Result := ExtractFileDir(DirValue)
  else
    Result := DirValue;
end;

// Extra safety: abort on 32-bit Windows (belt-and-suspenders over ArchitecturesAllowed)
function InitializeSetup(): Boolean;
begin
  Result := True;
  if not Is64BitInstallMode then begin
    MsgBox('AYE Hear requires a 64-bit Windows installation.', mbCriticalError, MB_OK);
    Result := False;
  end;
end;
