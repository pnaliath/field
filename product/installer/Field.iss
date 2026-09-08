[Setup]
AppId={{F58F6161-9433-4824-AE91-72178FB98A4E}
AppName=Field 1 Release Candidate
AppVersion=1.0.0-rc.1
AppPublisher=Field
DefaultDirName={autopf}\Field
OutputDir=..\..\dist
OutputBaseFilename=Field-1.0.0-rc.1-FL-Windows-x64-Setup
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
Compression=lzma2
SolidCompression=yes
UninstallDisplayName=Field 1 Release Candidate
WizardStyle=modern
LicenseFile=..\..\LICENSE
InfoBeforeFile=..\docs\DEMO-NOTICE.txt

[Files]
Source: "..\..\package\Field 1 Beta\*"; DestDir: "{code:FLPath}\Plugins\Fruity\Effects\Field 1 Beta"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\docs\USER-GUIDE.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\docs\RELEASE-GATES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\docs\DEMO-NOTICE.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\LICENSE"; DestDir: "{app}"; DestName: "FIELD-LICENSE.txt"; Flags: ignoreversion

[Code]
var FLPage: TInputDirWizardPage;

function IsFLFolder(Path: String): Boolean;
begin
  Result := FileExists(AddBackslash(Path) + 'FL64.exe');
end;

function DetectFLStudio: String;
var
  Candidate: String;
begin
  Result := '';

  Candidate := ExpandConstant('{autopf}\Image-Line\FL Studio 2026');
  if IsFLFolder(Candidate) then begin Result := Candidate; Exit; end;

  Candidate := ExpandConstant('{autopf}\Image-Line\FL Studio 2025');
  if IsFLFolder(Candidate) then begin Result := Candidate; Exit; end;

  Candidate := ExpandConstant('{autopf}\Image-Line\FL Studio 2024');
  if IsFLFolder(Candidate) then begin Result := Candidate; Exit; end;

  Candidate := ExpandConstant('{autopf}\Image-Line\FL Studio 21');
  if IsFLFolder(Candidate) then begin Result := Candidate; Exit; end;

  Candidate := ExpandConstant('{autopf}\Image-Line\FL Studio 20');
  if IsFLFolder(Candidate) then begin Result := Candidate; Exit; end;

  Candidate := ExpandConstant('{pf32}\Image-Line\FL Studio 2026');
  if IsFLFolder(Candidate) then begin Result := Candidate; Exit; end;

  Candidate := ExpandConstant('{pf32}\Image-Line\FL Studio 2025');
  if IsFLFolder(Candidate) then begin Result := Candidate; Exit; end;

  Candidate := ExpandConstant('{pf32}\Image-Line\FL Studio 2024');
  if IsFLFolder(Candidate) then begin Result := Candidate; Exit; end;
end;

procedure InitializeWizard;
var
  Detected: String;
begin
  FLPage := CreateInputDirPage(wpSelectDir, 'FL Studio installation',
    'Select the folder containing FL64.exe.', 'Field installs only the FL Studio native one-instance plugin. An installed FL Studio version is selected automatically when found.', False, '');
  FLPage.Add('FL Studio folder:');
  Detected := DetectFLStudio;
  if Detected <> '' then
    FLPage.Values[0] := Detected
  else
    FLPage.Values[0] := ExpandConstant('{autopf}\Image-Line');
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = FLPage.ID then
    if not IsFLFolder(FLPage.Values[0]) then begin
      MsgBox('Select the existing FL Studio folder containing FL64.exe.', mbError, MB_OK);
      Result := False;
    end;
end;

function FLPath(Param: String): String;
begin
  Result := FLPage.Values[0];
end;

