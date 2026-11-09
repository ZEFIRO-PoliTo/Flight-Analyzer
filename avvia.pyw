"""Avvio dell'applicazione con doppio clic (Windows: nessuna finestra di console)."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from flight_analyzer.gui import run  # noqa: E402

if __name__ == "__main__":
    sys.exit(run(sys.argv[1] if len(sys.argv) > 1 else None))
