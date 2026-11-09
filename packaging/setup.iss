; Installer di Flight Analyzer (Inno Setup 6).
;
; Prima si crea la cartella dist\FlightAnalyzer con PyInstaller, poi:
;     "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" /DAppVersion=1.1.0 packaging\setup.iss
; Il risultato è dist\FlightAnalyzer-<versione>-setup.exe.
;
; All'avvio l'installer chiede la lingua (italiano o inglese): la stessa lingua
; viene scritta nelle impostazioni dell'app (HKCU\Software\ZefiroMDV\FlightAnalyzer,
; valore «lingua»), così Flight Analyzer si apre già nella lingua scelta.
; Non servono permessi di amministratore: l'app si installa per l'utente corrente.

#ifndef AppVersion
  #define AppVersion "1.1.0"
#endif
#define AppName "Flight Analyzer"
#define AppExe "FlightAnalyzer.exe"

[Setup]
AppId={{7E1C1B6A-5D2F-4C47-9A8E-3F0B2C9D4E11}
AppName={#AppName}
AppVersion={#AppVersion}
AppVerName={#AppName} {#AppVersion}
AppPublisher=Team Zefiro - Politecnico di Torino
AppPublisherURL=https://www.zefiropolito.it
DefaultDirName={autopf}\Flight Analyzer
DefaultGroupName=Flight Analyzer
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir=..\dist
OutputBaseFilename=FlightAnalyzer-{#AppVersion}-setup
SetupIconFile=..\flight_analyzer\resources\icona.ico
UninstallDisplayIcon={app}\{#AppExe}
UninstallDisplayName={#AppName}
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
ShowLanguageDialog=yes
UsePreviousLanguage=no
LanguageDetectionMethod=uilanguage
ChangesAssociations=yes
CloseApplications=yes

[Languages]
Name: "it"; MessagesFile: "compiler:Languages\Italian.isl"
Name: "en"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
it.DesktopIconTask=Crea un'icona sul desktop
en.DesktopIconTask=Create a desktop shortcut
it.AssocTask=Apri i file .ulg con Flight Analyzer (doppio clic sul log)
en.AssocTask=Open .ulg files with Flight Analyzer (double-click on the log)
it.LaunchApp=Avvia Flight Analyzer
en.LaunchApp=Launch Flight Analyzer
it.UlgFile=Log di volo PX4
en.UlgFile=PX4 flight log

[Tasks]
Name: "desktopicon"; Description: "{cm:DesktopIconTask}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "assoc"; Description: "{cm:AssocTask}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "..\dist\FlightAnalyzer\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Flight Analyzer"; Filename: "{app}\{#AppExe}"
Name: "{autodesktop}\Flight Analyzer"; Filename: "{app}\{#AppExe}"; Tasks: desktopicon

[Registry]
; lingua dell'interfaccia (letta dall'app con QSettings)
Root: HKCU; Subkey: "Software\ZefiroMDV\FlightAnalyzer"; ValueType: string; ValueName: "lingua"; ValueData: "{language}"; Flags: uninsdeletekeyifempty
; la scorciatoia sul desktop la gestisce l'installer: l'app non la propone di nuovo
Root: HKCU; Subkey: "Software\ZefiroMDV\FlightAnalyzer"; ValueType: string; ValueName: "desktop_shortcut_prompted"; ValueData: "true"
; associazione dei file .ulg (facoltativa)
Root: HKA; Subkey: "Software\Classes\.ulg\OpenWithProgids"; ValueType: string; ValueName: "FlightAnalyzer.ulg"; ValueData: ""; Flags: uninsdeletevalue; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\FlightAnalyzer.ulg"; ValueType: string; ValueName: ""; ValueData: "{cm:UlgFile}"; Flags: uninsdeletekey; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\FlightAnalyzer.ulg\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\{#AppExe},0"; Tasks: assoc
Root: HKA; Subkey: "Software\Classes\FlightAnalyzer.ulg\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\{#AppExe}"" ""%1"""; Tasks: assoc

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchApp}"; Flags: nowait postinstall skipifsilent
