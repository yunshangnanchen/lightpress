; 轻压 · Windows 安装包脚本（Inno Setup 6.3+）
; 由 GitHub Actions 在 PyInstaller 生成 dist\LightPress 之后调用：
;   ISCC.exe /DMyAppVersion=1.2.3 installer\lightpress.iss
;
; 注意：本文件含中文，必须保存为 “UTF-8 with BOM”，
; 否则 Inno Setup 会按 ANSI 读取并出现乱码。

#define MyAppName "轻压"
#define MyAppNameEn "LightPress"
#define MyAppPublisher "LightPress"
#define MyAppExeName "LightPress.exe"

#ifndef MyAppVersion
  #define MyAppVersion "1.2"
#endif

[Setup]
AppId={{6C2B0F5A-7D3E-4B8A-9C41-2E0B0A7F1D53}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppNameEn}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=..\dist\installer
OutputBaseFilename=LightPress-{#MyAppVersion}-Setup
SetupIconFile=..\assets\logo.ico
UninstallDisplayIcon={app}\{#MyAppExeName}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; 默认按当前用户安装（{autopf} → %LocalAppData%\Programs），无需管理员权限。
; 应用会把 settings.json / error.log 写在 _internal 目录，因此不要装进只读的 Program Files。
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
CloseApplications=yes
RestartApplications=no

[Languages]
; Inno Setup 只自带 Default.isl；如需中文向导，请自备 ChineseSimplified.isl
; 放入 installer\Languages 后改为：MessagesFile: "Languages\ChineseSimplified.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
; Source 指向 PyInstaller --onedir 的输出目录（仓库根目录下的 dist\LightPress）
Source: "..\dist\LightPress\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; 应用运行时在 _internal 里生成的 settings.json / error.log 一并清掉
Type: filesandordirs; Name: "{app}\_internal"
