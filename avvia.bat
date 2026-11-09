@echo off
rem Avvio di Flight Analyzer con finestra di console: se qualcosa va storto, l'errore resta visibile.
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (set PY=py) else (set PY=python)
%PY% -c "import numpy, matplotlib, PySide6, reportlab" 2>nul
if errorlevel 1 (
    echo Installo le librerie necessarie, solo la prima volta...
    %PY% -m pip install -r requirements.txt
)
%PY% -m flight_analyzer %*
if errorlevel 1 (
    echo.
    echo Si e' verificato un errore: copia il testo qui sopra e mandalo.
    pause
)
