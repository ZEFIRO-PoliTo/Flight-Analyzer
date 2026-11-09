# -*- mode: python ; coding: utf-8 -*-
# Specifica PyInstaller di Flight Analyzer.
#
#   pyinstaller --noconfirm packaging/flight_analyzer.spec
#       -> dist/FlightAnalyzer/FlightAnalyzer.exe   (cartella: è quella che l'installer copia)
#
#   set FA_ONEFILE=1 && pyinstaller --noconfirm --distpath dist/portable --workpath build/portable packaging/flight_analyzer.spec
#       -> dist/portable/FlightAnalyzer.exe          (un solo file, portatile; parte un po' più lentamente)
#
# Di solito non serve lanciarla a mano: build_windows.bat o la GitHub Action fanno tutto.

import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).resolve().parent
sys.path.insert(0, str(ROOT))
from flight_analyzer import __version__  # noqa: E402

RES = ROOT / "flight_analyzer" / "resources"
ONEFILE = os.environ.get("FA_ONEFILE") == "1"

# informazioni di versione mostrate da Windows (Proprietà del file → Dettagli)
nums = tuple(int(x) for x in (__version__.split(".") + ["0", "0", "0"])[:4])
VERSION_FILE = Path(SPECPATH) / "version_info_auto.txt"
VERSION_FILE.write_text(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={nums}, prodvers={nums}, mask=0x3f, flags=0x0, OS=0x40004, fileType=0x1,
                    subtype=0x0, date=(0, 0)),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('CompanyName', 'Team Zefiro - Politecnico di Torino'),
      StringStruct('FileDescription', 'Flight Analyzer - analisi dei log PX4'),
      StringStruct('FileVersion', '{__version__}'),
      StringStruct('InternalName', 'FlightAnalyzer'),
      StringStruct('OriginalFilename', 'FlightAnalyzer.exe'),
      StringStruct('ProductName', 'Flight Analyzer'),
      StringStruct('ProductVersion', '{__version__}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""", encoding="utf-8")

a = Analysis(
    [str(ROOT / "packaging" / "avvio_app.py")],
    pathex=[str(ROOT)],
    datas=[(str(RES), "flight_analyzer/resources"), (str(ROOT / "profili"), "profili")],
    hiddenimports=[
        "flight_analyzer.i18n_en",                 # catalogo inglese, importato solo se serve
        "matplotlib.backends.backend_qtagg",
        "matplotlib.backends.backend_agg",
        "matplotlib.backends.backend_svg",         # grafici SVG nel report HTML
        "matplotlib.backends.backend_pdf",
    ] + collect_submodules("reportlab.pdfbase"),   # metriche dei font standard del PDF
    excludes=[
        "tkinter", "PyQt5", "PyQt6", "PySide2", "IPython", "jupyter", "notebook", "pytest",
        "PySide6.QtWebEngineCore", "PySide6.QtWebEngineWidgets", "PySide6.QtQuick", "PySide6.QtQml",
        "PySide6.Qt3DCore", "PySide6.QtMultimedia", "PySide6.QtCharts", "PySide6.QtDataVisualization",
    ],
    noarchive=False,
)
pyz = PYZ(a.pure)

options = dict(
    name="FlightAnalyzer",
    icon=str(RES / "icona.ico"),
    version=str(VERSION_FILE),
    console=False,          # applicazione a finestre: nessuna console nera
    upx=False,              # UPX fa scattare gli antivirus
    debug=False,
    strip=False,
)

if ONEFILE:
    exe = EXE(pyz, a.scripts, a.binaries, a.datas, [], runtime_tmpdir=None, **options)
else:
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, **options)
    coll = COLLECT(exe, a.binaries, a.datas, name="FlightAnalyzer", upx=False, strip=False)
