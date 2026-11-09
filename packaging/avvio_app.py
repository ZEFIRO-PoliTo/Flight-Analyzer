"""Punto di ingresso dell'eseguibile Windows (PyInstaller).

Senza argomenti apre l'applicazione; con un file .ulg (doppio clic su un log
associato) lo apre subito; «report …» e «punteggio …» funzionano come con
python -m flight_analyzer.
"""

import sys

from flight_analyzer.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
