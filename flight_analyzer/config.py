"""Impostazioni dell'utente condivise da grafici, report e interfaccia.

La GUI le carica da QSettings all'avvio e le salva; la riga di comando usa i
valori predefiniti (più le opzioni passate). I grafici leggono ``CFG``.
"""

from __future__ import annotations

import numpy as np

from .i18n import N_

DEG = 180.0 / np.pi

# chiavi delle schede che si possono nascondere (ordine = ordine nella finestra)
TAB_KEYS = ["overview", "pid", "steps", "attitude", "rates", "position", "controls", "power", "outputs", "rpm", "vibration",
            "system", "flags", "params", "messages", "explore"]
TAB_LABELS = {
    "overview": N_("Panoramica"), "pid": N_("Analisi PID"), "steps": N_("Prove a gradino"), "attitude": N_("Assetto"),
    "rates": N_("Velocità angolari"), "position": N_("Posizione e velocità"), "controls": N_("Comandi e spinta"),
    "power": N_("Potenza"), "outputs": N_("Motori e servi"), "rpm": N_("Giri motore"),
    "vibration": N_("Vibrazioni e spettri"), "system": N_("Sistema"), "flags": N_("Flag"),
    "params": N_("Parametri"), "messages": N_("Messaggi"), "explore": N_("Esplora dati"),
}

DEFAULTS = {
    "language": "it",            # it | en
    "theme": "light",            # light | dark | system
    "angle_unit": "deg",         # deg | rad
    "speed_unit": "m/s",         # m/s | km/h | kn
    "alt_unit": "m",             # m | ft
    "background": "both",        # both | phases | modes | none
    "max_points": 2500,          # punti per curva dopo la decimazione
    "line_width": 1.0,           # moltiplicatore dello spessore delle linee
    "font_scale": 1.0,           # moltiplicatore del testo nei grafici
    "legend_toggle": True,       # clic sulla legenda nasconde la curva
    "wheel_zoom": True,          # rotella = zoom, trascinamento = spostamento
    "hidden_tabs": [],           # schede nascoste
    "default_phase": "auto",     # auto | MC | FW
    "analyze_on_open": True,
    "export_format": "pdf",      # pdf | html
    "export_frequency": True,    # grafici della risposta in frequenza nel report
    "export_parameters": True,   # parametri di valutazione in fondo al report
    "responsible": "",           # nomi per la scheda di taratura
    "verifier": "",
}

CFG = dict(DEFAULTS)


def reset():
    CFG.clear()
    CFG.update(DEFAULTS)


def update(values: dict):
    for k, v in values.items():
        if k in DEFAULTS:
            CFG[k] = v


# ------------------------------------------------------------------ unità


def angle_scale():
    """(fattore da rad, simbolo) per gli angoli."""
    return (DEG, "°") if CFG.get("angle_unit", "deg") == "deg" else (1.0, "rad")


SPEED_UNITS = {"m/s": 1.0, "km/h": 3.6, "kn": 1.0 / 0.514444}
ALT_UNITS = {"m": 1.0, "ft": 1.0 / 0.3048}


def speed_scale():
    u = CFG.get("speed_unit", "m/s")
    return SPEED_UNITS.get(u, 1.0), u if u in SPEED_UNITS else "m/s"


def alt_scale():
    u = CFG.get("alt_unit", "m")
    return ALT_UNITS.get(u, 1.0), u if u in ALT_UNITS else "m"


def font(size):
    return size * float(CFG.get("font_scale", 1.0) or 1.0)


def lw(width):
    return width * float(CFG.get("line_width", 1.0) or 1.0)
