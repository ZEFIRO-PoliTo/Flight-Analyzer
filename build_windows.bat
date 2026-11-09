@echo off
rem Crea l'eseguibile di Flight Analyzer e, se Inno Setup 6 e' installato, l'installer.
rem Risultati:
rem   dist\FlightAnalyzer-<versione>-setup.exe   installer (da dare ai ragazzi)
rem   dist\portable\FlightAnalyzer.exe           eseguibile unico, senza installazione
rem   dist\FlightAnalyzer\                       cartella dell'app (quella che l'installer copia)
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (set PY=py) else (set PY=python)

echo [1/5] Librerie
%PY% -m pip install --upgrade -r requirements.txt pyinstaller
if errorlevel 1 goto errore

echo [2/5] Controllo delle traduzioni
%PY% tests\check_i18n.py
if errorlevel 1 goto errore

echo [3/5] Applicazione (cartella)
%PY% -m PyInstaller --noconfirm packaging\flight_analyzer.spec
if errorlevel 1 goto errore

echo [4/5] Eseguibile portatile (un solo file)
set FA_ONEFILE=1
%PY% -m PyInstaller --noconfirm --distpath dist\portable --workpath build\portable packaging\flight_analyzer.spec
if errorlevel 1 goto errore
set FA_ONEFILE=

echo [5/5] Installer
for /f %%v in ('%PY% -c "import flight_analyzer; print(flight_analyzer.__version__)"') do set VER=%%v
set ISCC="%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not exist %ISCC% set ISCC="%LocalAppData%\Programs\Inno Setup 6\ISCC.exe"
if exist %ISCC% (
    %ISCC% /DAppVersion=%VER% packaging\setup.iss
    if errorlevel 1 goto errore
) else (
    echo Inno Setup 6 non trovato: installer saltato. Si scarica da https://jrsoftware.org/isdl.php
)

echo.
echo Fatto. I file sono nella cartella dist.
pause
exit /b 0

:errore
echo.
echo Errore durante la creazione: copia il testo qui sopra e mandalo.
pause
exit /b 1
