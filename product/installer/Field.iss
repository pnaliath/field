[Setup]
AppId={{F58F6161-9433-4824-AE91-72178FB98A4E}
AppName=Field 1.0 Beta Demo
AppVersion=1.0.0-beta.1
AppPublisher=Field
DefaultDirName={autopf}\Field Beta Demo
OutputDir=..\..\package
OutputBaseFilename=Field-1.0.0-beta.1-Demo-Windows-x64-Setup
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin
Compression=lzma2
SolidCompression=yes
UninstallDisplayName=Field 1.0 Beta Demo
WizardStyle=modern
LicenseFile=..\..\LICENSE
InfoBeforeFile=..\docs\DEMO-NOTICE.txt

[Files]
Source: "..\..\package\Field 1 Beta\*"; DestDir: "{code:FLPath}\Plugins\Fruity\Effects\Field 1 Beta"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\docs\USER-GUIDE.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\docs\RELEASE-GATES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\docs\DEMO-NOTICE.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\LICENSE"; DestDir: "{app}"; DestName: "FIELD-DEMO-LICENSE.txt"; Flags: ignoreversion

[Code]
var FLPage: TInputDirWizardPage;
procedure InitializeWizard;
begin
  FLPage := CreateInputDirPage(wpSelectDir, 'FL Studio installation',
    'Select the folder containing FL64.exe.', 'Field Demo installs only the FL Studio native one-instance plugin.', False, '');
  FLPage.Add('FL Studio folder:');
  FLPage.Values[0] := ExpandConstant('{autopf}\Image-Line\FL Studio 2026');
end;
function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = FLPage.ID then
    if not FileExists(FLPage.Values[0] + '\FL64.exe') then begin
      MsgBox('Select the existing FL Studio folder containing FL64.exe.', mbError, MB_OK);
      Result := False;
    end;
end;
function FLPath(Param: String): String;
begin
  Result := FLPage.Values[0];
end;
