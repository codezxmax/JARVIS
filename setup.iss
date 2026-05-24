; ============================================================
;  JARVIS - Asistente de Voz Personal
;  Script para Inno Setup 6
;  Para compilar: abrir este archivo con Inno Setup Compiler
;  Descarga Inno Setup: https://jrsoftware.org/isdl.php
; ============================================================

#define AppName      "JARVIS Asistente"
#define AppVersion   "2.0"
#define AppPublisher "Maxi"
#define OutputDir    ".\dist"

[Setup]
AppId={{A1B2C3D4-E5F6-7890-ABCD-EF1234567890}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppVerName={#AppName} {#AppVersion}
DefaultDirName={autopf}\JARVIS
DefaultGroupName={#AppName}
AllowNoIcons=yes
OutputDir={#OutputDir}
OutputBaseFilename=JARVIS_Installer_v{#AppVersion}
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
WizardSizePercent=110
DisableWelcomePage=no
; UAC: admin para escribir en Program Files
PrivilegesRequired=admin
UninstallDisplayName={#AppName}
ShowTasksTreeLines=yes

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Messages]
WelcomeLabel1=Bienvenido al instalador de JARVIS
WelcomeLabel2=Este asistente instalará JARVIS Asistente de Voz en su equipo.%n%nJARVIS escucha tu voz y puede:%n%n  • Activarse al decir "Hola Jarvis"%n  • Abrir Chrome, Gmail y tu sistema interno%n  • Controlar Spotify con la voz%n  • Iniciarse automáticamente con Windows%n%nSe recomienda cerrar todas las aplicaciones antes de continuar.

[Tasks]
Name: "startup"; Description: "Iniciar JARVIS automáticamente con Windows"; GroupDescription: "Opciones de inicio:"; Flags: checked
Name: "desktop"; Description: "Crear acceso directo en el escritorio";       GroupDescription: "Accesos directos:"; Flags: checked

[Files]
; Archivos principales — config.py solo se copia si no existe ya
Source: "jarvis.py";       DestDir: "{app}"; Flags: ignoreversion
Source: "config.py";       DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
Source: "gen_launcher.py"; DestDir: "{app}"; Flags: ignoreversion
Source: "interfaz.py";     DestDir: "{app}"; Flags: ignoreversion
Source: "updater.py";      DestDir: "{app}"; Flags: ignoreversion
Source: "commands.json";   DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist
Source: "version.json";    DestDir: "{app}"; Flags: ignoreversion onlyifdoesntexist

[Icons]
; Escritorio
Name: "{autodesktop}\JARVIS Asistente"; Filename: "{sys}\wscript.exe"; Parameters: """{app}\launcher.vbs"""; Comment: "Iniciar JARVIS Asistente de Voz"; Tasks: desktop
Name: "{autodesktop}\Panel de Control JARVIS"; Filename: "{sys}\wscript.exe"; Parameters: """{app}\gui_launcher.vbs"""; WorkingDir: "{app}"; Comment: "Abrir panel de control de JARVIS"; Tasks: desktop
; Menú Inicio
Name: "{group}\JARVIS Asistente";                 Filename: "{sys}\wscript.exe"; Parameters: """{app}\launcher.vbs"""; Comment: "Iniciar JARVIS"
Name: "{group}\Panel de Control JARVIS";           Filename: "{sys}\wscript.exe"; Parameters: """{app}\gui_launcher.vbs"""; WorkingDir: "{app}"; Comment: "Panel gráfico de JARVIS"
Name: "{group}\Editar configuración (config.py)"; Filename: "{app}\config.py"
Name: "{group}\Desinstalar JARVIS";               Filename: "{uninstallexe}"

[Registry]
Root: HKLM; Subkey: "Software\JARVIS"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey

[Run]
; ── Instalar dependencias de Python ──────────────────────────────────────────
Filename: "{code:GetPythonExe}"; Parameters: "-m pip install --upgrade pip --quiet";      StatusMsg: "Actualizando pip...";              Flags: runhidden waituntilterminated
Filename: "{code:GetPythonExe}"; Parameters: "-m pip install SpeechRecognition --quiet";  StatusMsg: "Instalando SpeechRecognition...";  Flags: runhidden waituntilterminated
Filename: "{code:GetPythonExe}"; Parameters: "-m pip install PyAudio --quiet";            StatusMsg: "Instalando PyAudio...";            Flags: runhidden waituntilterminated
Filename: "{code:GetPythonExe}"; Parameters: "-m pip install pyttsx3 --quiet";            StatusMsg: "Instalando pyttsx3 (voz TTS)...";  Flags: runhidden waituntilterminated
Filename: "{code:GetPythonExe}"; Parameters: "-m pip install pyautogui --quiet";          StatusMsg: "Instalando pyautogui...";          Flags: runhidden waituntilterminated
; ── Generar launcher.vbs con la ruta de Python de ESTE equipo ─────────────────
Filename: "{code:GetPythonExe}"; Parameters: """{app}\gen_launcher.py"""; StatusMsg: "Configurando inicio automático..."; Flags: runhidden waituntilterminated

[UninstallRun]
Filename: "{cmd}"; Parameters: "/c del /f /q ""{userstartup}\jarvis.vbs"""; Flags: runhidden

; =============================================================
;  CÓDIGO PASCAL — Detección de Python + Página personalizada
; =============================================================
[Code]

var
  PythonExePath:  String;
  PythonPage:     TWizardPage;
  PythonEdit:     TEdit;
  PythonHint:     TLabel;
  PythonBrowse:   TButton;

{ ── Busca python.exe en rutas conocidas ─────────────────── }
function FindPython(): String;
var
  Paths: TArrayOfString;
  I: Integer;
begin
  Result := '';
  SetArrayLength(Paths, 12);
  Paths[0]  := 'C:\Python313\python.exe';
  Paths[1]  := 'C:\Python312\python.exe';
  Paths[2]  := 'C:\Python311\python.exe';
  Paths[3]  := 'C:\Python310\python.exe';
  Paths[4]  := 'C:\Python39\python.exe';
  Paths[5]  := ExpandConstant('{localappdata}\Programs\Python\Python313\python.exe');
  Paths[6]  := ExpandConstant('{localappdata}\Programs\Python\Python312\python.exe');
  Paths[7]  := ExpandConstant('{localappdata}\Programs\Python\Python311\python.exe');
  Paths[8]  := ExpandConstant('{localappdata}\Programs\Python\Python310\python.exe');
  Paths[9]  := ExpandConstant('{pf}\Python313\python.exe');
  Paths[10] := ExpandConstant('{pf}\Python312\python.exe');
  Paths[11] := ExpandConstant('{pf}\Python311\python.exe');
  for I := 0 to GetArrayLength(Paths) - 1 do
    if FileExists(Paths[I]) then
    begin
      Result := Paths[I];
      Break;
    end;
end;

{ ── Devuelve la ruta de Python para los [Run] entries ───── }
function GetPythonExe(Param: String): String;
begin
  Result := PythonExePath;
end;

{ ── Botón "Examinar" ────────────────────────────────────── }
procedure BrowseClick(Sender: TObject);
var
  F: String;
begin
  F := '';
  if GetOpenFileName('Selecciona python.exe', F, 'C:\', 'Ejecutable Python|python.exe', 'exe') then
  begin
    PythonEdit.Text := F;
    PythonExePath   := F;
    PythonHint.Caption := 'Ruta actualizada manualmente.';
  end;
end;

{ ── Página personalizada: Verificación de Python ────────── }
procedure CreatePythonPage();
var
  Lbl: TLabel;
begin
  PythonPage := CreateCustomPage(wpWelcome,
    'Verificación de Python',
    'JARVIS requiere Python 3.9 o superior instalado en este equipo.');

  Lbl := TLabel.Create(PythonPage);
  Lbl.Parent   := PythonPage.Surface;
  Lbl.Left     := 0;
  Lbl.Top      := 6;
  Lbl.Width    := PythonPage.SurfaceWidth;
  Lbl.Caption  := 'Ruta de python.exe:';

  PythonEdit := TEdit.Create(PythonPage);
  PythonEdit.Parent := PythonPage.Surface;
  PythonEdit.Left   := 0;
  PythonEdit.Top    := 24;
  PythonEdit.Width  := PythonPage.SurfaceWidth - 92;
  PythonEdit.Text   := PythonExePath;

  PythonBrowse := TButton.Create(PythonPage);
  PythonBrowse.Parent   := PythonPage.Surface;
  PythonBrowse.Left     := PythonPage.SurfaceWidth - 88;
  PythonBrowse.Top      := 22;
  PythonBrowse.Width    := 88;
  PythonBrowse.Caption  := 'Examinar...';
  PythonBrowse.OnClick  := @BrowseClick;

  PythonHint := TLabel.Create(PythonPage);
  PythonHint.Parent    := PythonPage.Surface;
  PythonHint.Left      := 0;
  PythonHint.Top       := 56;
  PythonHint.Width     := PythonPage.SurfaceWidth;
  PythonHint.WordWrap  := True;
  PythonHint.Height    := 60;

  if PythonExePath <> '' then
    PythonHint.Caption := 'Python detectado correctamente. Puedes continuar o cambiar la ruta.'
  else
    PythonHint.Caption :=
      'No se encontró Python en este equipo.' + #13#10 +
      'Descárgalo desde https://www.python.org/downloads/' + #13#10 +
      'IMPORTANTE: marcar "Add Python to PATH" al instalar.' + #13#10 +
      'Una vez instalado, usa "Examinar" para localizarlo.';
end;

{ ── Validar antes de avanzar ────────────────────────────── }
function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if CurPageID = PythonPage.ID then
  begin
    PythonExePath := PythonEdit.Text;
    if (PythonExePath = '') or (not FileExists(PythonExePath)) then
    begin
      MsgBox(
        'La ruta de Python no es válida.' + #13#10 +
        'Usa el botón "Examinar" para seleccionar python.exe.',
        mbError, MB_OK);
      Result := False;
    end;
  end;
end;

{ ── Copiar launcher.vbs al Startup ──────────────────────── }
procedure CopyLauncherToStartup();
begin
  FileCopy(
    ExpandConstant('{app}\launcher.vbs'),
    ExpandConstant('{userstartup}\jarvis.vbs'),
    False);
end;

{ ── Eventos del instalador ───────────────────────────────── }
procedure InitializeWizard();
begin
  PythonExePath := FindPython();
  CreatePythonPage();
end;

procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssPostInstall then
    if IsTaskSelected('startup') then
      CopyLauncherToStartup();
end;
