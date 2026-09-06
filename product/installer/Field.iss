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

[Types]
Name: "full"; Description: "VST3 and FL native"
Name: "vst"; Description: "VST3 only"
Name: "custom"; Description: "Custom"; Flags: iscustom

[Components]
Name: "vst"; Description: "Field VST3 and Field Sender"; Types: full vst custom
Name: "native"; Description: "Field native for FL Studio"; Types: full

[Files]
Source: "..\..\package\FieldVST3.vst3\*"; DestDir: "{commoncf64}\VST3\FieldVST3.vst3"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: vst
Source: "..\..\package\Field 1 Beta\*"; DestDir: "{code:FLPath}\Plugins\Fruity\Effects\Field 1 Beta"; Flags: ignoreversion recursesubdirs createallsubdirs; Components: native
Source: "..\docs\USER-GUIDE.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\docs\RELEASE-GATES.md"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\docs\DEMO-NOTICE.txt"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\..\LICENSE"; DestDir: "{app}"; DestName: "FIELD-DEMO-LICENSE.txt"; Flags: ignoreversion

[Code]
var FLPage: TInputDirWizardPage;
procedure InitializeWizard;
begin
  FLPage := CreateInputDirPage(wpSelectComponents, 'FL Studio installation',
    'Select the folder containing FL64.exe.', 'The native plugin is installed inside this FL Studio installation.', False, '');
  FLPage.Add('FL Studio folder:');
  FLPage.Values[0] := ExpandConstant('{autopf}\Image-Line\FL Studio 2026');
end;
function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := (PageID = FLPage.ID) and not WizardIsComponentSelected('native');
end;
function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = FLPage.ID) and WizardIsComponentSelected('native') then
    if not FileExists(FLPage.Values[0] + '\FL64.exe') then begin
      MsgBox('Select the existing FL Studio folder containing FL64.exe.', mbError, MB_OK);
      Result := False;
    end;
end;
function FLPath(Param: String): String;
begin
  Result := FLPage.Values[0];
end;
