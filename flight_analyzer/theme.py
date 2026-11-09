"""Tema grafico: colori del team Zefiro, versione chiara e scura.

Unico punto in cui stanno i colori: grafici (matplotlib), interfaccia (Qt) e
report li prendono da qui. Il blu primario è quello del logo Zefiro (#004183).
"""

from __future__ import annotations

from contextlib import contextmanager

import matplotlib as mpl

ZEFIRO_BLUE = "#004183"
ZEFIRO_BLUE_LIGHT = "#1c6fc4"
ZEFIRO_YELLOW = "#ffc400"
POLITO_NAVY = "#003054"

THEMES = {
    "light": {
        "window": "#f4f6f9", "surface": "#ffffff", "surface_alt": "#eef2f7", "border": "#d5dbe3",
        "text": "#1b2430", "text_muted": "#6b7785", "primary": ZEFIRO_BLUE, "primary_hover": "#0a56a8",
        "primary_text": "#ffffff", "accent": ZEFIRO_YELLOW, "selection": "#cfe0f5",
        "ok": "#2b8a3e", "warn": "#e67700", "bad": "#c92a2a",
        # grafici
        "fig_bg": "#ffffff", "ax_bg": "#ffffff", "grid": "#e3e8ee", "spine": "#9aa5b1",
        "legend_bg": "#ffffff", "phase_alpha": 0.22, "mode_alpha": 0.6, "strip_text": "#1b2430",
        "band": "#e9ecef", "ref_line": "#495057", "track_mark": "#343a40",
    },
    "dark": {
        "window": "#0e1622", "surface": "#152131", "surface_alt": "#1b2a3d", "border": "#2c3e55",
        "text": "#e6ebf1", "text_muted": "#9aa7b6", "primary": "#2f7fd6", "primary_hover": "#4a93e0",
        "primary_text": "#ffffff", "accent": ZEFIRO_YELLOW, "selection": "#24476e",
        "ok": "#40c057", "warn": "#ffa94d", "bad": "#ff6b6b",
        "fig_bg": "#152131", "ax_bg": "#152131", "grid": "#26374c", "spine": "#5b6b80",
        "legend_bg": "#1b2a3d", "phase_alpha": 0.16, "mode_alpha": 0.35, "strip_text": "#0e1622",
        "band": "#24364b", "ref_line": "#c3ccd6", "track_mark": "#e6ebf1",
    },
}

_CURRENT = "light"


def set_theme(name: str):
    global _CURRENT
    _CURRENT = name if name in THEMES else "light"
    apply_matplotlib(_CURRENT)


def current() -> str:
    return _CURRENT


def tok(key: str):
    return THEMES[_CURRENT][key]


def apply_matplotlib(name: str):
    t = THEMES[name]
    mpl.rcParams.update({
        "figure.facecolor": t["fig_bg"], "axes.facecolor": t["ax_bg"], "savefig.facecolor": t["fig_bg"],
        "axes.edgecolor": t["spine"], "axes.labelcolor": t["text"], "text.color": t["text"],
        "xtick.color": t["text_muted"], "ytick.color": t["text_muted"], "grid.color": t["grid"],
        "legend.facecolor": t["legend_bg"], "legend.edgecolor": t["border"], "legend.labelcolor": t["text"],
        "axes.titlecolor": t["text"],
    })


@contextmanager
def matplotlib_theme(name: str):
    """Usa temporaneamente un tema (es. chiaro per i report) e poi ripristina quello attivo."""
    global _CURRENT
    old = _CURRENT
    _CURRENT = name
    apply_matplotlib(name)
    try:
        yield
    finally:
        _CURRENT = old
        apply_matplotlib(old)


def qt_stylesheet(name: str) -> str:
    """Foglio di stile Qt nei colori del team."""
    t = THEMES[name]
    return f"""
QMainWindow, QDialog {{ background: {t['window']}; }}
QWidget {{ color: {t['text']}; }}
QToolBar#MainBar {{ background: {t['primary']}; border: none; border-bottom: 3px solid {t['accent']}; padding: 3px;
    spacing: 4px; }}
QToolBar#MainBar QToolButton {{ color: {t['primary_text']}; background: transparent; border-radius: 4px; padding: 4px 10px;
    font-weight: 600; }}
QToolBar#MainBar QToolButton:hover {{ background: rgba(255,255,255,0.16); }}
QToolBar#MainBar QLabel {{ background: transparent; }}
QToolBar {{ background: transparent; border: none; }}
QMenuBar {{ background: {t['surface']}; border-bottom: 1px solid {t['border']}; }}
QMenuBar::item:selected, QMenu::item:selected {{ background: {t['selection']}; color: {t['text']}; }}
QMenu {{ background: {t['surface']}; border: 1px solid {t['border']}; }}
QTabWidget::pane {{ border: 1px solid {t['border']}; background: {t['surface']}; top: -1px; }}
QTabBar::tab {{ background: transparent; color: {t['text_muted']}; padding: 7px 12px; border: none;
    border-bottom: 3px solid transparent; font-weight: 600; }}
QTabBar::tab:selected {{ color: {t['primary']}; border-bottom: 3px solid {t['accent']}; }}
QTabBar::tab:hover {{ color: {t['text']}; }}
QPushButton {{ background: {t['surface']}; border: 1px solid {t['border']}; border-radius: 5px; padding: 4px 12px; }}
QPushButton:hover {{ border-color: {t['primary']}; }}
QPushButton:default, QPushButton[primary="true"] {{ background: {t['primary']}; color: {t['primary_text']};
    border-color: {t['primary']}; font-weight: 600; }}
QPushButton[primary="true"]:hover {{ background: {t['primary_hover']}; }}
QPushButton:disabled {{ color: {t['text_muted']}; background: {t['surface_alt']}; }}
QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox {{ background: {t['surface']}; border: 1px solid {t['border']};
    border-radius: 4px; padding: 3px 6px; selection-background-color: {t['selection']}; }}
QComboBox QAbstractItemView {{ background: {t['surface']}; selection-background-color: {t['selection']}; }}
QTableView, QTableWidget, QTreeWidget, QTreeView, QListWidget, QTextBrowser {{ background: {t['surface']};
    alternate-background-color: {t['surface_alt']}; border: 1px solid {t['border']};
    selection-background-color: {t['selection']}; selection-color: {t['text']}; gridline-color: {t['border']}; }}
QHeaderView::section {{ background: {t['surface_alt']}; color: {t['text']}; border: none;
    border-bottom: 1px solid {t['border']}; padding: 4px 6px; font-weight: 600; }}
QGroupBox {{ border: 1px solid {t['border']}; border-radius: 6px; margin-top: 12px; padding-top: 6px; }}
QGroupBox::title {{ subcontrol-origin: margin; left: 10px; padding: 0 4px; color: {t['primary']}; font-weight: 600; }}
QStatusBar {{ background: {t['surface']}; border-top: 1px solid {t['border']}; color: {t['text_muted']}; }}
QSplitter::handle {{ background: {t['border']}; }}
QToolTip {{ background: {t['surface']}; color: {t['text']}; border: 1px solid {t['border']}; }}
QLabel[role="hint"] {{ color: {t['text_muted']}; }}
QLabel[role="info"] {{ background: {t['surface_alt']}; border-left: 3px solid {t['primary']}; padding: 6px 10px; }}
"""


GRADE_COLORS = {"Ottimo": "ok", "Buono": "ok", "Accettabile": "warn", "Da rivedere": "bad", "Non valutabile": "text_muted"}
