"""Applicazione desktop (PySide6 + matplotlib)."""

from __future__ import annotations

import html
import json
import math
import os
import re
import subprocess
import sys
import traceback
import weakref
from pathlib import Path

os.environ.setdefault("QT_API", "pyside6")

from PySide6 import QtCore, QtGui, QtWidgets  # noqa: E402
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT  # noqa: E402
from matplotlib.figure import Figure  # noqa: E402

from . import __version__, analysis, config, i18n, plots, report, scoring, steptest, theme  # noqa: E402
from .config import CFG, TAB_KEYS, TAB_LABELS  # noqa: E402
from .flags import SEVERITY_LABELS, SOURCE_LABELS, raised_flags  # noqa: E402
from .i18n import N_, _  # noqa: E402
from .logdata import LogData  # noqa: E402

Qt = QtCore.Qt
APP_NAME = "Flight Analyzer"
ORG = "ZefiroMDV"
RESOURCES = Path(__file__).resolve().parent / "resources"
FROZEN = bool(getattr(sys, "frozen", False))  # True nell'eseguibile creato con PyInstaller
ANALYZE_STYLE = ("QPushButton{background:#2b8a3e;color:white;font-weight:600;padding:4px 16px;border-radius:4px;"
                 "border:1px solid #237032}QPushButton:hover{background:#2f9e44}"
                 "QPushButton:pressed{background:#237032}QPushButton:disabled{background:#adb5bd;border-color:#adb5bd}")
GRADE_COLORS = {"Ottimo": "#2b8a3e", "Buono": "#5c940d", "Accettabile": "#e67700", "Da rivedere": "#c92a2a",
                "Non valutabile": "#868e96"}

# chiavi QSettings: alcune vengono dalle versioni precedenti, «lingua» la scrive anche l'installer
SETTING_KEYS = {"language": "lingua", "angle_unit": "unita_angoli", "background": "sfondo_grafici"}


def _settings():
    return QtCore.QSettings(ORG, "FlightAnalyzer")


def _to_type(value, default):
    if isinstance(default, bool):
        return value if isinstance(value, bool) else str(value).strip().lower() in ("1", "true", "yes", "si", "sì")
    if isinstance(default, int):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return default
    if isinstance(default, float):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
    if isinstance(default, list):
        if isinstance(value, str):
            return [v for v in value.split(",") if v]
        return [str(v) for v in (value or [])]
    return str(value)


def load_config(qs):
    """Carica in config.CFG le impostazioni salvate."""
    for key, default in config.DEFAULTS.items():
        raw = qs.value(SETTING_KEYS.get(key, f"impostazioni/{key}"))
        if raw is not None and raw != "":
            CFG[key] = _to_type(raw, default)
    if CFG.get("language") not in i18n.SUPPORTED:
        CFG["language"] = "it"


def save_config(qs):
    for key, default in config.DEFAULTS.items():
        value = CFG.get(key, default)
        qs.setValue(SETTING_KEYS.get(key, f"impostazioni/{key}"), ",".join(value) if isinstance(default, list) else value)


def score_color(points):
    if points is None:
        return QtGui.QColor(theme.tok("text_muted"))
    if points >= 85:
        return QtGui.QColor(theme.tok("ok"))
    if points >= 70:
        return QtGui.QColor("#5c940d" if theme.current() == "light" else "#94d82d")
    if points >= 55:
        return QtGui.QColor(theme.tok("warn"))
    return QtGui.QColor(theme.tok("bad"))


def hint_label(text):
    lab = QtWidgets.QLabel(text)
    lab.setProperty("role", "hint")
    lab.setWordWrap(True)
    return lab


# ------------------------------------------------------------- tema e scorciatoia


def resolve_theme(name):
    if name == "system":
        try:
            scheme = QtWidgets.QApplication.styleHints().colorScheme()
            return "dark" if scheme == Qt.ColorScheme.Dark else "light"
        except Exception:  # noqa: BLE001 - Qt < 6.5: si usa il chiaro
            return "light"
    return name if name in theme.THEMES else "light"


def apply_theme(app, name):
    """Applica il tema (colori del team) a Qt e matplotlib; restituisce «light» o «dark»."""
    resolved = resolve_theme(name)
    theme.set_theme(resolved)
    t = theme.THEMES[resolved]
    try:
        app.setStyle("Fusion")
    except Exception:  # noqa: BLE001
        pass
    pal = QtGui.QPalette()
    roles = QtGui.QPalette.ColorRole
    for role, key in ((roles.Window, "window"), (roles.Base, "surface"), (roles.AlternateBase, "surface_alt"),
                      (roles.Text, "text"), (roles.WindowText, "text"), (roles.Button, "surface"),
                      (roles.ButtonText, "text"), (roles.Highlight, "selection"), (roles.HighlightedText, "text"),
                      (roles.ToolTipBase, "surface"), (roles.ToolTipText, "text"), (roles.PlaceholderText, "text_muted"),
                      (roles.Link, "primary")):
        pal.setColor(role, QtGui.QColor(t[key]))
    app.setPalette(pal)
    app.setStyleSheet(theme.qt_stylesheet(resolved))
    for panel in list(PlotPanel.instances):
        panel.fig.set_facecolor(t["fig_bg"])
    return resolved


def _create_desktop_shortcut(shortcut_path):
    """Crea un collegamento .lnk sul desktop (Windows) con l'icona di Flight Analyzer."""
    if FROZEN:
        target = Path(sys.executable)
        arguments = ""
        working_directory = target.parent
    else:
        pythonw = Path(sys.executable).with_name("pythonw.exe")
        target = pythonw if pythonw.exists() else Path(sys.executable)
        arguments = "-m flight_analyzer"
        working_directory = RESOURCES.parent.parent
    environment = os.environ.copy()
    environment.update({
        "FLIGHT_ANALYZER_SHORTCUT": str(shortcut_path),
        "FLIGHT_ANALYZER_TARGET": str(target),
        "FLIGHT_ANALYZER_WORKDIR": str(working_directory),
        "FLIGHT_ANALYZER_ICON": str(RESOURCES / "icona.ico"),
    })
    script = (
        "$ErrorActionPreference = 'Stop'\n"
        "$shell = New-Object -ComObject WScript.Shell\n"
        "$shortcut = $shell.CreateShortcut($env:FLIGHT_ANALYZER_SHORTCUT)\n"
        "$shortcut.TargetPath = $env:FLIGHT_ANALYZER_TARGET\n"
        + (f"$shortcut.Arguments = '{arguments}'\n" if arguments else "")
        + "$shortcut.WorkingDirectory = $env:FLIGHT_ANALYZER_WORKDIR\n"
        "$shortcut.IconLocation = $env:FLIGHT_ANALYZER_ICON + ',0'\n"
        "$shortcut.Description = 'Flight Analyzer'\n"
        "$shortcut.Save()\n"
    )
    result = subprocess.run(
        ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", "-"],
        input=script,
        text=True,
        capture_output=True,
        env=environment,
        check=False,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),  # niente finestra nera di PowerShell
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or _("errore non specificato")
        raise RuntimeError(_("Impossibile creare la scorciatoia: {dettaglio}").format(dettaglio=detail))


def desktop_shortcut_path():
    loc = QtCore.QStandardPaths.writableLocation(QtCore.QStandardPaths.StandardLocation.DesktopLocation)
    return Path(loc) / "Flight Analyzer.lnk" if loc else None


# ------------------------------------------------------------------ esecuzione


class _TaskSignals(QtCore.QObject):
    done = QtCore.Signal(int, object)
    failed = QtCore.Signal(int, str)


class Task(QtCore.QRunnable):
    """Esegue una funzione in un thread di lavoro.

    I segnali appartengono a un QObject creato nel thread della GUI, quindi i
    collegamenti verso MainWindow vengono eseguiti nel thread della GUI.
    """

    def __init__(self, task_id, fn):
        super().__init__()
        self.task_id = task_id
        self.fn = fn
        self.signals = _TaskSignals()

    def run(self):
        try:
            result = self.fn()
        except Exception:  # noqa: BLE001 - l'errore viene mostrato all'utente
            self.signals.failed.emit(self.task_id, traceback.format_exc())
        else:
            self.signals.done.emit(self.task_id, result)


# ---------------------------------------------------------- pannelli laterali


class SideToggle(QtWidgets.QToolButton):
    """Pulsantino ◀/▶ che nasconde e mostra un pannello laterale (come in MATLAB)."""

    def __init__(self, side, name, parent=None):
        super().__init__(parent)
        self.side = side
        self.name = name
        self.setAutoRaise(True)
        self.clicked.connect(self.toggle)
        self._update()

    def toggle(self):
        self.side.setHidden(not self.side.isHidden())
        self._update()

    def _update(self):
        hidden = self.side.isHidden()
        self.setText("▶" if hidden else "◀")
        tip = _("Mostra {cosa}") if hidden else _("Nascondi {cosa}")
        self.setToolTip(tip.format(cosa=_(self.name)) + " (Ctrl+B)")


# --------------------------------------------------------------- pannello grafico


NAV_HINT = N_("Rotella: zoom · trascina: sposta · doppio clic: tutto il log · Ctrl+rotella: zoom verticale · "
              "clic sulla legenda: nascondi curva")


class PlotPanel(QtWidgets.QWidget):
    """Figura matplotlib con barra strumenti, reticolo, navigazione e sincronizzazione dei tempi.

    Sui grafici temporali: rotella = zoom sul tempo attorno al mouse, Ctrl+rotella = zoom verticale,
    Maiusc+rotella = scorrimento, trascinamento = spostamento, doppio clic = tutto il log, tastiera:
    frecce, + e −, Home, A (adatta l'asse verticale).
    """

    xrange_changed = QtCore.Signal(float, float)
    status = QtCore.Signal(str)
    instances = weakref.WeakSet()  # per aggiornare lo sfondo delle figure quando cambia il tema

    def __init__(self, parent=None, time_linked=True):
        super().__init__(parent)
        PlotPanel.instances.add(self)
        self.fig = Figure(figsize=(10, 6), dpi=100, layout="constrained", facecolor=theme.tok("fig_bg"))
        self.canvas = FigureCanvasQTAgg(self.fig)
        self.canvas.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Expanding)
        self.canvas.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.toolbar = NavigationToolbar2QT(self.canvas, self)
        self.time_linked = time_linked
        self.tf = None
        self._syncing = False
        self._pending_x = None
        self._drag = None
        bar = QtWidgets.QHBoxLayout()
        bar.setContentsMargins(0, 0, 0, 0)
        bar.addWidget(self.toolbar)
        bar.addStretch(1)
        if time_linked:
            b_fit = QtWidgets.QPushButton(_("Adatta Y"))
            b_fit.setToolTip(_("Riadatta l'asse verticale ai dati visibili (tasto A)"))
            b_fit.clicked.connect(self.fit_y)
            b_all = QtWidgets.QPushButton(_("Tutto il log"))
            b_all.setToolTip(_("Mostra l'intero log (doppio clic o tasto Home)"))
            b_all.clicked.connect(self.full_view)
            bar.addWidget(b_fit)
            bar.addWidget(b_all)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.addLayout(bar)
        lay.addWidget(self.canvas, 1)
        # il reticolo si aggiorna al massimo ~30 volte al secondo
        self._move_timer = QtCore.QTimer(self)
        self._move_timer.setSingleShot(True)
        self._move_timer.setInterval(30)
        self._move_timer.timeout.connect(self._apply_cursor)
        self._range_timer = QtCore.QTimer(self)
        self._range_timer.setSingleShot(True)
        self._range_timer.setInterval(120)
        self._range_timer.timeout.connect(self._emit_range)
        self._bg = None
        for name, handler in (("motion_notify_event", self._on_move), ("figure_leave_event", self._on_leave),
                              ("draw_event", self._on_draw), ("pick_event", self._on_pick),
                              ("scroll_event", self._on_scroll), ("button_press_event", self._on_press),
                              ("button_release_event", self._on_release), ("key_press_event", self._on_key)):
            self.canvas.mpl_connect(name, handler)

    def _on_pick(self, event):
        # clic su una voce di legenda: nasconde/mostra la curva
        if plots.toggle_from_pick(self.fig, event.artist):
            self.canvas.draw_idle()

    def set_timefigure(self, tf):
        self.tf = tf
        if tf is not None and self.time_linked:
            tf.axes[0].callbacks.connect("xlim_changed", self._on_xlim)
        self.canvas.draw_idle()

    def clear_message(self, text):
        self.tf = None
        self.fig.clear()
        ax = self.fig.add_subplot(111)
        ax.text(0.5, 0.5, text, ha="center", va="center", fontsize=11, color=theme.tok("text_muted"), wrap=True)
        ax.set_axis_off()
        self.canvas.draw_idle()

    # -- sincronizzazione dell'asse dei tempi tra le schede
    def _on_xlim(self, _ax):
        if not self._syncing:
            self._range_timer.start()

    def _emit_range(self):
        if self.tf is not None:
            lo, hi = self.tf.axes[0].get_xlim()
            self.xrange_changed.emit(float(lo), float(hi))

    def apply_xrange(self, lo, hi):
        if self.tf is None:
            return
        cur = self.tf.axes[0].get_xlim()
        if abs(cur[0] - lo) < 1e-6 and abs(cur[1] - hi) < 1e-6:
            return
        self._syncing = True
        try:
            self.tf.axes[0].set_xlim(lo, hi)
            self.tf.autoscale_y()
        finally:
            self._syncing = False
        self.canvas.draw_idle()

    def fit_y(self):
        if self.tf is not None:
            self.tf.autoscale_y(reset_user=True)
            self.canvas.draw_idle()

    def full_view(self):
        if self.tf is not None:
            self.tf.full()
            self.tf.autoscale_y(reset_user=True)
            self.canvas.draw_idle()

    # -- navigazione con mouse e tastiera
    def _nav_ok(self, event):
        return (self.tf is not None and CFG.get("wheel_zoom", True) and event.inaxes is not None
                and event.inaxes in self.tf.axes and not getattr(self.toolbar, "mode", ""))

    def _after_nav(self):
        self.tf.autoscale_y()
        self.canvas.draw_idle()

    def _on_scroll(self, event):
        if not self._nav_ok(event):
            return
        up = getattr(event, "button", "up") == "up"
        key = (event.key or "").lower()
        if "control" in key or "ctrl" in key:
            ax = event.inaxes
            lo, hi = ax.get_ylim()
            c = event.ydata if event.ydata is not None else (lo + hi) / 2
            f = 0.8 if up else 1.25
            ax.set_ylim(c - (c - lo) * f, c + (hi - c) * f)
            ax._fa_user_y = True  # scala scelta dall'utente: «Adatta Y» (o il tasto A) la ripristina
            self.canvas.draw_idle()
            return
        if "shift" in key:
            self.tf.pan_x(-0.15 if up else 0.15)
        else:
            self.tf.zoom_x(0.8 if up else 1.25, event.xdata)
        self._after_nav()

    def _on_press(self, event):
        if not self._nav_ok(event) or event.button != 1:
            return
        if getattr(event, "dblclick", False):
            self.full_view()
            return
        bbox = event.inaxes.get_window_extent()
        self._drag = (event.x, self.tf.axes[0].get_xlim(), max(bbox.width, 1.0))

    def _on_release(self, _event):
        if self._drag is not None:
            self._drag = None
            self._after_nav()

    def _on_key(self, event):
        if self.tf is None or not event.key:
            return
        k = event.key.lower()
        if k == "left":
            self.tf.pan_x(-0.2)
        elif k == "right":
            self.tf.pan_x(0.2)
        elif k in ("+", "=", "up"):
            self.tf.zoom_x(0.7)
        elif k in ("-", "down"):
            self.tf.zoom_x(1.4)
        elif k == "home":
            self.tf.full()
        elif k == "a":
            self.fit_y()
            return
        else:
            return
        self._after_nav()

    # -- reticolo
    def _on_move(self, event):
        if self._drag is not None and event.x is not None and self.tf is not None:
            x0, (lo, hi), width_px = self._drag
            d = (event.x - x0) * (hi - lo) / width_px
            self.tf.axes[0].set_xlim(lo - d, hi - d)
            self.canvas.draw_idle()
            return
        if self.tf is None or event.inaxes is None or event.xdata is None or event.inaxes not in self.tf.axes:
            return
        self._pending_x = float(event.xdata)
        if not self._move_timer.isActive():
            self._move_timer.start()

    def _on_draw(self, _event):
        # sfondo senza cursore: poi il cursore si ridisegna da solo (blitting), senza rifare tutta la figura
        self._bg = self.canvas.copy_from_bbox(self.fig.bbox)
        plots.enable_legend_toggle(self.fig)
        if self.tf is not None:
            self.tf.draw_cursor()

    def _apply_cursor(self):
        if self.tf is None or self._pending_x is None:
            return
        self.tf.set_cursor(self._pending_x)
        if self._bg is not None:
            self.canvas.restore_region(self._bg)
            self.tf.draw_cursor()
            self.canvas.blit(self.fig.bbox)
        else:
            self.canvas.draw_idle()
        self.status.emit(self.tf.readout(self._pending_x))

    def _on_leave(self, _event):
        if self.tf is not None:
            self.tf.hide_cursor()
            if self._bg is not None:
                self.canvas.restore_region(self._bg)
                self.canvas.blit(self.fig.bbox)

    def save_image(self, parent):
        path, _f = QtWidgets.QFileDialog.getSaveFileName(
            parent, _("Salva grafico"), "grafico.png", _("Immagine PNG (*.png);;Vettoriale SVG (*.svg);;PDF (*.pdf)"))
        if path:
            self.fig.savefig(path, dpi=150)


class GotoBox(QtWidgets.QComboBox):
    """Menu «Vai a»: porta i grafici su una fase VTOL, un modo di volo o il tratto in volo."""

    chosen = QtCore.Signal(float, float)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumContentsLength(24)
        self.setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.setToolTip(_("Porta tutti i grafici temporali su una fase o un modo di volo"))
        self.activated.connect(self._pick)
        self._segs = []

    def fill(self, log):
        self.blockSignals(True)
        self.clear()
        self._segs = plots.flight_segments(log) if log is not None else []
        for label, _a, _b in self._segs:
            self.addItem(label)
        self.blockSignals(False)

    def _pick(self, index):
        if 0 <= index < len(self._segs):
            _label, a, b = self._segs[index]
            pad = 0.02 * (b - a)
            self.chosen.emit(a - pad, b + pad)


# ----------------------------------------------------------------- schede tempo


class TimeTab(QtWidgets.QWidget):
    """Scheda con un grafico temporale; ``views`` = [(etichetta, funzione)] per avere più viste."""

    def __init__(self, main, builder=None, views=None, parent=None):
        super().__init__(parent)
        self.main = main
        self.views = views or [(None, builder)]
        self.panel = PlotPanel(self)
        top = QtWidgets.QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        self.combo = None
        if len(self.views) > 1:
            top.addWidget(QtWidgets.QLabel(_("Vista:")))
            self.combo = QtWidgets.QComboBox()
            for label, _b in self.views:
                # etichetta semplice o tupla di pezzi da tradurre separatamente
                self.combo.addItem("".join(_(p) for p in label) if isinstance(label, tuple) else _(label))
            self.combo.currentIndexChanged.connect(lambda _i: self.refresh(self.main.log))
            top.addWidget(self.combo)
            top.addSpacing(12)
        self.goto_label = QtWidgets.QLabel(_("Vai a:"))
        top.addWidget(self.goto_label)
        self.goto = GotoBox()
        self.goto.chosen.connect(self._goto)
        top.addWidget(self.goto)
        top.addSpacing(12)
        top.addWidget(hint_label(_(NAV_HINT)), 1)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.addLayout(top)
        lay.addWidget(self.panel, 1)
        self.panel.xrange_changed.connect(main.on_xrange)
        self.panel.status.connect(main.show_readout)

    def _goto(self, lo, hi):
        self.panel.apply_xrange(lo, hi)
        self.main.on_xrange(lo, hi)

    def refresh(self, log):
        if log is None:
            return
        self.goto.fill(log)
        idx = self.combo.currentIndex() if self.combo is not None else 0
        builder = self.views[max(idx, 0)][1]
        tf = builder(self.panel.fig, log)
        tf = tf if isinstance(tf, plots.TimeFigure) else None
        self.panel.set_timefigure(tf)
        self.goto.setEnabled(tf is not None)
        if tf is not None and self.main.xrange is not None:
            self.panel.apply_xrange(*self.main.xrange)
        self.panel.canvas.draw_idle()


def _spectrum_builder(name):
    def build(fig, log):
        plots.build_spectrum(fig, log, name)

    return build


# --------------------------------------------------------------- panoramica


class OverviewTab(QtWidgets.QWidget):
    def __init__(self, main, parent=None):
        super().__init__(parent)
        self.main = main
        self.split = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
        self.table = QtWidgets.QTableWidget(0, 2)
        self.table.setHorizontalHeaderLabels([_("Voce"), _("Valore")])
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.table.setWordWrap(True)
        self.table.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.panel = PlotPanel(self, time_linked=False)
        self.split.addWidget(self.table)
        self.split.addWidget(self.panel)
        self.split.setStretchFactor(0, 2)
        self.split.setStretchFactor(1, 3)
        self.side_toggle = SideToggle(self.table, N_("il riepilogo"))
        head = QtWidgets.QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.addWidget(self.side_toggle)
        head.addWidget(QtWidgets.QLabel(_("Riepilogo del volo")))
        head.addStretch(1)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.addLayout(head)
        lay.addWidget(self.split)
        self._adapt_layout(self.width(), self.height())

    def toggle_side(self):
        self.side_toggle.toggle()

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self._adapt_layout(event.size().width(), event.size().height())

    def _adapt_layout(self, width, height):
        orientation = Qt.Orientation.Vertical if width < 900 else Qt.Orientation.Horizontal
        if self.split.orientation() == orientation:
            return
        self.split.setOrientation(orientation)
        if orientation == Qt.Orientation.Vertical:
            self.split.setStretchFactor(0, 2)
            self.split.setStretchFactor(1, 1)
            self.split.setSizes([int(height * 0.68), int(height * 0.32)])
        else:
            self.split.setStretchFactor(0, 2)
            self.split.setStretchFactor(1, 3)
            self.split.setSizes([int(width * 0.4), int(width * 0.6)])

    def refresh(self, log):
        summary = log.summary()
        self.table.setRowCount(len(summary))
        for row, (k, v) in enumerate(summary.items()):
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(k))
            item = QtWidgets.QTableWidgetItem(str(v))
            item.setToolTip(str(v))
            if str(v).startswith("⚠"):
                item.setForeground(QtGui.QBrush(QtGui.QColor(theme.tok("bad"))))
            self.table.setItem(row, 1, item)
        self.table.resizeRowsToContents()
        plots.build_overview(self.panel.fig, log)
        self.panel.canvas.draw_idle()


# ------------------------------------------------------------------- flag


class FlagsTab(QtWidgets.QWidget):
    """Flag sollevati in volo: tabella con descrizione e diagramma temporale."""

    COLS = (N_("Flag"), N_("Origine"), N_("Gravità"), N_("Prima attivazione [s]"), N_("Attivazioni"),
            N_("Durata totale [s]"), N_("Descrizione"))

    def __init__(self, main, parent=None):
        super().__init__(parent)
        self.main = main
        self.flags = []
        self.side = QtWidgets.QWidget()
        self.side_toggle = SideToggle(self.side, N_("l'elenco dei flag"))
        top = QtWidgets.QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.addWidget(self.side_toggle)
        self.show_info = QtWidgets.QCheckBox(_("Mostra anche i flag informativi"))
        self.show_info.setChecked(True)
        self.show_info.toggled.connect(lambda _b: self.refresh(self.main.log))
        top.addWidget(self.show_info)
        top.addSpacing(12)
        top.addWidget(hint_label(_("Doppio clic su un flag per portare i grafici sulla sua prima attivazione.")), 1)
        self.summary = QtWidgets.QLabel("")
        top.addWidget(self.summary)
        self.table = QtWidgets.QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels([_(c) for c in self.COLS])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.cellDoubleClicked.connect(self._goto)
        sl = QtWidgets.QVBoxLayout(self.side)
        sl.setContentsMargins(0, 0, 0, 0)
        sl.addWidget(self.table)
        self.panel = PlotPanel(self)
        self.panel.xrange_changed.connect(main.on_xrange)
        self.panel.status.connect(main.show_readout)
        split = QtWidgets.QSplitter(Qt.Orientation.Vertical)
        split.addWidget(self.side)
        split.addWidget(self.panel)
        split.setStretchFactor(0, 2)
        split.setStretchFactor(1, 3)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.addLayout(top)
        lay.addWidget(split, 1)

    def toggle_side(self):
        self.side_toggle.toggle()

    def refresh(self, log):
        if log is None:
            return
        self.flags = raised_flags(log, include_info=self.show_info.isChecked())
        self.table.setRowCount(len(self.flags))
        sev_col = {3: theme.tok("bad"), 2: theme.tok("warn"), 1: theme.tok("text_muted")}
        for row, f in enumerate(self.flags):
            src = f.source.split(":")
            source = _(SOURCE_LABELS.get(src[0], src[0])) + (f" [{src[1]}]" if len(src) > 1 else "")
            desc = _(f.description) + (" — " + _("attivo per tutto il log") if f.always_set else "")
            cells = [f.key, source, _(SEVERITY_LABELS[f.severity]), f"{f.first:.2f}", str(f.count), f"{f.total:.2f}",
                     desc]
            for col, txt in enumerate(cells):
                item = QtWidgets.QTableWidgetItem(txt)
                if col == 2:
                    item.setForeground(QtGui.QBrush(QtGui.QColor(sev_col[f.severity])))
                if col in (3, 4, 5):
                    item.setTextAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                item.setToolTip(desc)
                self.table.setItem(row, col, item)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)
        n_crit = sum(1 for f in self.flags if f.severity >= 3)
        if self.flags:
            self.summary.setText(_("{n} flag, di cui {c} critici").format(n=len(self.flags), c=n_crit))
        else:
            self.summary.setText(_("Nessun flag sollevato"))
        tf = plots.build_flags(self.panel.fig, log, self.flags)
        self.panel.set_timefigure(tf)
        if tf is not None and self.main.xrange is not None:
            self.panel.apply_xrange(*self.main.xrange)
        self.panel.canvas.draw_idle()

    def _goto(self, row, _col):
        if 0 <= row < len(self.flags):
            t = self.flags[row].first
            lo, hi = max(0.0, t - 10.0), t + 20.0
            self.panel.apply_xrange(lo, hi)
            self.main.on_xrange(lo, hi)
            self.main.statusBar().showMessage(_("Grafici temporali centrati su t = {t:.1f} s").format(t=t), 5000)


# --------------------------------------------------------------- parametri


class ParamsTab(QtWidgets.QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        top = QtWidgets.QHBoxLayout()
        top.addWidget(QtWidgets.QLabel(_("Filtro:")))
        self.filter = QtWidgets.QLineEdit()
        self.filter.setPlaceholderText(_("es. MC_ROLLRATE, IMU_, FW_R"))
        top.addWidget(self.filter, 1)
        self.only_changed = QtWidgets.QCheckBox(_("Solo diversi dal default"))
        top.addWidget(self.only_changed)
        self.model = QtGui.QStandardItemModel(0, 4)
        self.model.setHorizontalHeaderLabels([_("Parametro"), _("Valore"), _("Default"), _("Modificato in volo")])
        self.proxy = QtCore.QSortFilterProxyModel(self)
        self.proxy.setSourceModel(self.model)
        self.proxy.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.proxy.setFilterKeyColumn(0)
        self.view = QtWidgets.QTableView()
        self.view.setModel(self.proxy)
        self.view.setSortingEnabled(True)
        self.view.setAlternatingRowColors(True)
        self.view.verticalHeader().setVisible(False)
        self.view.horizontalHeader().setStretchLastSection(True)
        self.view.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.filter.textChanged.connect(self.proxy.setFilterFixedString)
        self.only_changed.toggled.connect(self._toggle_changed)
        self.note = QtWidgets.QLabel("")
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.addLayout(top)
        lay.addWidget(self.view, 1)
        lay.addWidget(self.note)
        self._rows_default = []

    def refresh(self, log):
        self.model.removeRows(0, self.model.rowCount())
        changes = {}
        for t, k, v in log.param_changes:
            changes.setdefault(k, []).append(_("{v} a {t:.1f} s").format(v=_fmt_param(v), t=t))
        self._rows_default = []
        bold = QtGui.QFont()
        bold.setBold(True)
        for name in sorted(log.params):
            val = log.params[name]
            dflt = log.defaults.get(name)
            items = [QtGui.QStandardItem(name), QtGui.QStandardItem(_fmt_param(val)),
                     QtGui.QStandardItem("" if dflt is None else _fmt_param(dflt)),
                     QtGui.QStandardItem("; ".join(changes.get(name, [])))]
            differs = dflt is not None and _fmt_param(dflt) != _fmt_param(val)
            if differs:
                for it in items[:2]:
                    it.setFont(bold)
                    it.setForeground(QtGui.QBrush(QtGui.QColor(theme.tok("primary"))))
            if name in changes:
                items[3].setForeground(QtGui.QBrush(QtGui.QColor(theme.tok("bad"))))
            self.model.appendRow(items)
            self._rows_default.append(not differs)
        self.view.resizeColumnsToContents()
        n_diff = sum(1 for d in self._rows_default if not d)
        if log.defaults:
            self.note.setText(_("{n} parametri; {d} diversi dal default").format(n=len(log.params), d=n_diff))
        else:
            self.note.setText(_("{n} parametri (il log non contiene i valori di default)").format(n=len(log.params)))
        self._toggle_changed(self.only_changed.isChecked())

    def _toggle_changed(self, on):
        for row in range(self.model.rowCount()):
            src = self.model.index(row, 0)
            prow = self.proxy.mapFromSource(src).row()
            if prow >= 0:
                self.view.setRowHidden(prow, bool(on and self._rows_default[row]))


def _fmt_param(v):
    if isinstance(v, float):
        return f"{v:.6g}"
    return str(v)


# --------------------------------------------------------------- messaggi


class MessagesTab(QtWidgets.QWidget):
    LEVEL_TOKENS = {"EMERGENZA": "bad", "ALLARME": "bad", "CRITICO": "bad", "ERRORE": "bad", "AVVISO": "warn",
                    "PARAMETRO": "primary"}

    def __init__(self, main, parent=None):
        super().__init__(parent)
        self.main = main
        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels([_("Tempo [s]"), _("Livello"), _("Messaggio")])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.cellDoubleClicked.connect(self._goto)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.addWidget(hint_label(_("Doppio clic su un messaggio per centrare i grafici temporali su quell'istante.")))
        lay.addWidget(self.table, 1)
        self._times = []

    def refresh(self, log):
        rows = [(t, lvl, txt) for t, lvl, txt in log.messages]
        rows += [(t, N_("PARAMETRO"), f"{k} = {_fmt_param(v)}") for t, k, v in log.param_changes]
        rows.sort(key=lambda r: r[0])
        self.table.setRowCount(len(rows))
        self._times = []
        for i, (t, lvl, txt) in enumerate(rows):
            items = [QtWidgets.QTableWidgetItem(f"{t:.3f}"), QtWidgets.QTableWidgetItem(_(lvl)),
                     QtWidgets.QTableWidgetItem(txt)]
            key = self.LEVEL_TOKENS.get(lvl)
            if key:
                for it in items:
                    it.setForeground(QtGui.QBrush(QtGui.QColor(theme.tok(key))))
            for j, it in enumerate(items):
                self.table.setItem(i, j, it)
            self._times.append(t)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)

    def _goto(self, row, _col):
        if 0 <= row < len(self._times):
            t = self._times[row]
            self.main.on_xrange(max(0.0, t - 10.0), t + 10.0)
            self.main.statusBar().showMessage(_("Grafici temporali centrati su t = {t:.1f} s").format(t=t), 5000)


# --------------------------------------------------------------- esplora


class ExplorerTab(QtWidgets.QWidget):
    def __init__(self, main, parent=None):
        super().__init__(parent)
        self.main = main
        split = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
        left = QtWidgets.QWidget()
        ll = QtWidgets.QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText(_("Cerca topic o campo…"))
        self.search.textChanged.connect(self._filter)
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels([_("Topic / campo"), _("Campioni"), "Hz"])
        self.tree.itemChanged.connect(self._changed)
        b_clear = QtWidgets.QPushButton(_("Deseleziona tutto"))
        b_clear.clicked.connect(self._clear)
        ll.addWidget(self.search)
        ll.addWidget(self.tree, 1)
        ll.addWidget(b_clear)
        self.panel = PlotPanel(self)
        self.panel.xrange_changed.connect(main.on_xrange)
        self.panel.status.connect(main.show_readout)
        split.addWidget(left)
        split.addWidget(self.panel)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 3)
        self.side_toggle = SideToggle(left, N_("l'elenco dei topic"))
        head = QtWidgets.QHBoxLayout()
        head.setContentsMargins(0, 0, 0, 0)
        head.addWidget(self.side_toggle)
        head.addWidget(QtWidgets.QLabel(_("Topic e campi")))
        head.addSpacing(12)
        head.addWidget(hint_label(_(NAV_HINT)), 1)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.addLayout(head)
        lay.addWidget(split)
        self._timer = QtCore.QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(300)
        self._timer.timeout.connect(self._redraw)
        self._filling = False

    def toggle_side(self):
        self.side_toggle.toggle()

    def refresh(self, log):
        self._filling = True
        self.tree.clear()
        for topic in log.topic_names():
            for inst in log.instances(topic):
                d = log.dataset(topic, inst)
                label = topic + (f" [{inst}]" if len(log.instances(topic)) > 1 else "")
                top = QtWidgets.QTreeWidgetItem([label, str(len(d)), f"{log.rate(topic, inst):.0f}"])
                top.setData(0, Qt.ItemDataRole.UserRole, None)
                for field in log.fields(topic, inst):
                    it = QtWidgets.QTreeWidgetItem([field, "", ""])
                    it.setFlags(it.flags() | Qt.ItemFlag.ItemIsUserCheckable)
                    it.setCheckState(0, Qt.CheckState.Unchecked)
                    it.setData(0, Qt.ItemDataRole.UserRole, (topic, inst, field))
                    top.addChild(it)
                self.tree.addTopLevelItem(top)
        self.tree.resizeColumnToContents(0)
        self._filling = False
        self._redraw()

    def _filter(self, text):
        text = text.lower().strip()
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            topic_match = text in top.text(0).lower()
            any_child = False
            for j in range(top.childCount()):
                ch = top.child(j)
                vis = topic_match or text in ch.text(0).lower()
                ch.setHidden(not vis)
                any_child |= vis
            top.setHidden(not any_child)
            top.setExpanded(bool(text) and any_child and not topic_match)

    def _changed(self, _item, _col):
        if not self._filling:
            self._timer.start()

    def _selections(self):
        sel = []
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            for j in range(top.childCount()):
                ch = top.child(j)
                if ch.checkState(0) == Qt.CheckState.Checked:
                    sel.append(ch.data(0, Qt.ItemDataRole.UserRole))
        return sel

    def _clear(self):
        self._filling = True
        for i in range(self.tree.topLevelItemCount()):
            top = self.tree.topLevelItem(i)
            for j in range(top.childCount()):
                top.child(j).setCheckState(0, Qt.CheckState.Unchecked)
        self._filling = False
        self._redraw()

    def _redraw(self):
        if self.main.log is None:
            return
        tf = plots.build_explorer(self.panel.fig, self.main.log, self._selections())
        self.panel.set_timefigure(tf)
        if tf is not None and self.main.xrange is not None:
            self.panel.apply_xrange(*self.main.xrange)
        self.panel.canvas.draw_idle()


# ---------------------------------------------------------------- scheda PID


class PidTab(QtWidgets.QWidget):
    def __init__(self, main, parent=None):
        super().__init__(parent)
        self.main = main
        self.results = None  # [(etichetta, AnalysisResult)]
        controls = QtWidgets.QHBoxLayout()
        controls.addWidget(QtWidgets.QLabel(_("Fase:")))
        self.phase = QtWidgets.QComboBox()
        for key in ("MC", "FW", "ALL"):
            self.phase.addItem(_(analysis.PHASES[key]), key)
        controls.addWidget(self.phase)
        controls.addWidget(QtWidgets.QLabel(_("Anello:")))
        self.loop = QtWidgets.QComboBox()
        for key in ("rate", "att"):
            self.loop.addItem(_(analysis.LOOPS[key]), key)
        controls.addWidget(self.loop)
        controls.addWidget(QtWidgets.QLabel(_("Intervallo:")))
        self.range = QtWidgets.QComboBox()
        self.range.addItem(_("Tutto il volo nella fase"), "all")
        self.range.addItem(_("Solo l'intervallo visibile nei grafici temporali"), "view")
        controls.addWidget(self.range)
        controls.addWidget(QtWidgets.QLabel(_("Profilo:")))
        self.prof_combo = QtWidgets.QComboBox()
        self.prof_combo.setToolTip(_("PX4 standard: definizioni rispetto al valore finale. Vespa hover: criteri della "
                                     "scheda di taratura, rispetto all'ampiezza comandata"))
        self.prof_combo.activated.connect(self._profile_chosen)
        controls.addWidget(self.prof_combo)
        self.b_run = QtWidgets.QPushButton(_("Analizza"))
        self.b_run.setDefault(True)
        self.b_run.setStyleSheet(ANALYZE_STYLE)
        self.b_run.clicked.connect(self.run)
        controls.addWidget(self.b_run)
        controls.addSpacing(16)
        b_add = QtWidgets.QPushButton(_("Aggiungi log di confronto…"))
        b_add.clicked.connect(main.add_comparison)
        b_rem = QtWidgets.QPushButton(_("Rimuovi confronti"))
        b_rem.clicked.connect(main.clear_comparisons)
        controls.addWidget(b_add)
        controls.addWidget(b_rem)
        controls.addStretch(1)
        self.cmp_label = QtWidgets.QLabel("")
        controls.addWidget(self.cmp_label)

        # colonna sinistra: punteggi e diagnosi
        left = QtWidgets.QWidget()
        ll = QtWidgets.QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        self.overall = QtWidgets.QLabel(_("Apri un log per iniziare"))
        self.overall.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.overall.setMinimumHeight(54)
        self._overall_idle()
        self.cmp_table = QtWidgets.QTableWidget(0, 5)
        self.cmp_table.setHorizontalHeaderLabels([_("Log"), _("Totale")] + [_(scoring.AXIS_LABELS[a]) for a in scoring.AXES])
        self.cmp_table.verticalHeader().setVisible(False)
        self.cmp_table.horizontalHeader().setStretchLastSection(True)
        self.cmp_table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.cmp_table.setMaximumHeight(130)
        self.cmp_table.setVisible(False)
        self.tree = QtWidgets.QTreeWidget()
        self.tree.setHeaderLabels([_("Asse / metrica"), _("Valore"), _("Punti"), _("Soglie 100/60/0"), _("Peso")])
        self.tree.setAlternatingRowColors(True)
        self.tree.setRootIsDecorated(True)
        self.diag = QtWidgets.QTextBrowser()
        self.diag.setOpenExternalLinks(False)
        ll.addWidget(self.overall)
        ll.addWidget(self.cmp_table)
        ll.addWidget(self.tree, 3)
        ll.addWidget(QtWidgets.QLabel(_("Diagnosi e indicazioni")))
        ll.addWidget(self.diag, 2)

        # colonna destra: grafici
        right = QtWidgets.QWidget()
        rl = QtWidgets.QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        axis_row = QtWidgets.QHBoxLayout()
        axis_row.addWidget(QtWidgets.QLabel(_("Asse per frequenza e dati:")))
        self.axis = QtWidgets.QComboBox()
        for a in scoring.AXES:
            self.axis.addItem(_(scoring.AXIS_LABELS[a]), a)
        self.axis.currentIndexChanged.connect(lambda _i: self._draw_axis_views())
        axis_row.addWidget(self.axis)
        self.show_band = QtWidgets.QCheckBox(_("Mostra incertezza"))
        self.show_band.setChecked(True)
        self.show_band.toggled.connect(lambda _b: self._draw_steps())
        axis_row.addWidget(self.show_band)
        axis_row.addStretch(1)
        self.views = QtWidgets.QTabWidget()
        self.p_step = PlotPanel(self, time_linked=False)
        self.p_freq = PlotPanel(self, time_linked=False)
        self.p_data = PlotPanel(self, time_linked=False)
        # pagina della risposta in frequenza con la spiegazione di |T| (richiudibile)
        freq_page = QtWidgets.QWidget()
        fl = QtWidgets.QVBoxLayout(freq_page)
        fl.setContentsMargins(0, 0, 0, 0)
        self.t_info_btn = QtWidgets.QToolButton()
        self.t_info_btn.setText(_("Cosa significa «anello chiuso |T|»?"))
        self.t_info_btn.setCheckable(True)
        self.t_info_btn.setChecked(True)
        self.t_info_btn.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.t_info_btn.setArrowType(Qt.ArrowType.DownArrow)
        self.t_info = QtWidgets.QLabel(_(plots.T_EXPLANATION))
        self.t_info.setWordWrap(True)
        self.t_info.setProperty("role", "info")
        self.t_info_btn.toggled.connect(self._toggle_t_info)
        fl.addWidget(self.t_info_btn)
        fl.addWidget(self.t_info)
        fl.addWidget(self.p_freq, 1)
        self.views.addTab(self.p_step, _("Risposta al gradino"))
        self.views.addTab(freq_page, _("Risposta in frequenza e robustezza"))
        self.views.addTab(self.p_data, _("Dati usati"))
        rl.addLayout(axis_row)
        rl.addWidget(self.views, 1)

        self.side_toggle = SideToggle(left, N_("punteggi e diagnosi"))
        controls.insertWidget(0, self.side_toggle)
        split = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(left)
        split.addWidget(right)
        split.setStretchFactor(0, 2)
        split.setStretchFactor(1, 3)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.addLayout(controls)
        lay.addWidget(split, 1)
        for p in (self.p_step, self.p_freq, self.p_data):
            p.clear_message(_("Nessuna analisi"))

    def show_profile(self):
        """Riempie la scelta del profilo: PX4 standard, Vespa hover e, se diverso, quello attivo."""
        name = self.main.profile.get("nome", "")
        self.prof_combo.blockSignals(True)
        self.prof_combo.clear()
        self.prof_combo.addItem(_(scoring.DEFAULT_PROFILE["nome"]), "px4")
        self.prof_combo.addItem(_("Vespa hover (scheda di taratura)"), "vespa")
        if name == scoring.DEFAULT_PROFILE["nome"]:
            self.prof_combo.setCurrentIndex(0)
        elif name == "Vespa hover (scheda di taratura)":
            self.prof_combo.setCurrentIndex(1)
        else:
            self.prof_combo.addItem(_(name), "custom")
            self.prof_combo.setCurrentIndex(2)
        self.prof_combo.blockSignals(False)

    def _profile_chosen(self, _i):
        key = self.prof_combo.currentData()
        if key == "px4":
            self.main.use_px4_profile()
        elif key == "vespa":
            self.main.use_vespa_profile()

    def _overall_idle(self):
        self.overall.setStyleSheet(f"font-size:18px;font-weight:600;border-radius:6px;padding:6px;"
                                   f"background:{theme.tok('surface_alt')};color:{theme.tok('text_muted')}")

    def _toggle_t_info(self, on):
        self.t_info.setVisible(on)
        self.t_info_btn.setArrowType(Qt.ArrowType.DownArrow if on else Qt.ArrowType.RightArrow)

    def toggle_side(self):
        self.side_toggle.toggle()

    def current_panel(self):
        w = self.views.currentWidget()
        return w if isinstance(w, PlotPanel) else self.p_freq

    # -- esecuzione
    def run(self):
        log = self.main.log
        if log is None:
            return
        phase = self.phase.currentData()
        loop = self.loop.currentData()
        tr = None
        if self.range.currentData() == "view" and self.main.xrange is not None:
            tr = tuple(self.main.xrange)
        profile = self.main.profile
        logs = [log] + list(self.main.comparisons)
        self.b_run.setEnabled(False)
        self.overall.setText(_("Analisi in corso…"))

        def job():
            return [(lg.name, analysis.analyze(lg, phase, loop, tr if i == 0 else None, profile))
                    for i, lg in enumerate(logs)]

        self.main.run_task(job, self._done, busy=_("Analisi dei controllori…"),
                           on_fail=lambda: self.b_run.setEnabled(True))

    def _done(self, results):
        self.b_run.setEnabled(True)
        self.results = results
        main = results[0][1]
        sc = main.score
        color = GRADE_COLORS.get(main.grade, "#868e96")
        self.overall.setText(f"{main.title}\n{'—' if sc is None else f'{sc:.0f}/100'} · {_(main.grade)}")
        self.overall.setStyleSheet(f"font-size:15px;font-weight:600;border-radius:6px;padding:6px;"
                                   f"background:{color};color:white")
        self._fill_tree(main)
        self._fill_comparison(results)
        self._fill_diag(main)
        self._draw_steps()
        self._draw_axis_views()

    @staticmethod
    def _conf(c):
        return _(scoring.CONFIDENCE.get(c, c))

    def _fill_tree(self, res):
        self.tree.clear()
        bold = QtGui.QFont()
        bold.setBold(True)
        for axis in scoring.AXES:
            ar = res.axes[axis]
            c = ar.card
            head = _(scoring.AXIS_LABELS[axis])
            if ar.available:
                score = "—" if c.score is None else f"{c.score:.0f}/100"
                head += f" — {score} {_(c.grade)} · {_('affidabilità')} {self._conf(c.confidence)}"
            else:
                head += f" — {ar.reason}"
            top = QtWidgets.QTreeWidgetItem([head, "", "", "", ""])
            top.setFont(0, bold)
            top.setForeground(0, QtGui.QBrush(score_color(c.score if ar.available else None)))
            self.tree.addTopLevelItem(top)
            top.setFirstColumnSpanned(True)
            if ar.available:
                for it in c.items:
                    pts = _("n.d.") if it.points is None else f"{it.points:.0f}"
                    ch = QtWidgets.QTreeWidgetItem([it.label, it.display(), pts,
                                                    " / ".join(f"{v:g}" for v in it.thresholds), f"{it.weight:g}"])
                    ch.setToolTip(0, it.note or it.label)
                    ch.setToolTip(1, it.note)
                    ch.setForeground(2, QtGui.QBrush(score_color(it.points)))
                    for col in (1, 2, 3, 4):
                        ch.setTextAlignment(col, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    top.addChild(ch)
                top.setExpanded(True)
        for col in range(5):
            self.tree.resizeColumnToContents(col)

    def _fill_comparison(self, results):
        if len(results) < 2:
            self.cmp_table.setVisible(False)
            return
        self.cmp_table.setVisible(True)
        self.cmp_table.setRowCount(len(results))
        for row, (name, r) in enumerate(results):
            cells = [name, "—" if r.score is None else f"{r.score:.0f}"]
            for a in scoring.AXES:
                ar = r.axes[a]
                if not ar.available or ar.card.score is None:
                    cells.append("—")
                else:
                    cells.append(f"{ar.card.score:.0f} ({self._conf(ar.card.confidence)})")
            for col, txt in enumerate(cells):
                item = QtWidgets.QTableWidgetItem(txt)
                if col == 1:
                    item.setForeground(QtGui.QBrush(score_color(r.score)))
                self.cmp_table.setItem(row, col, item)
        self.cmp_table.resizeColumnsToContents()

    def _fill_diag(self, res):
        warn, muted = theme.tok("warn"), theme.tok("text_muted")
        parts = [f"<p style='color:{warn}'>⚠ {html.escape(w)}</p>" for w in res.warnings]
        for axis in scoring.AXES:
            ar = res.axes[axis]
            parts.append(f"<p><b>{html.escape(_(scoring.AXIS_LABELS[axis]))}</b></p><ul>")
            if not ar.available:
                parts.append(f"<li>{html.escape(ar.reason)}</li>")
            else:
                for d in ar.card.diagnostics:
                    parts.append(f"<li>{html.escape(d)}</li>")
                if ar.card.confidence_reasons:
                    parts.append(f"<li style='color:{muted}'>{html.escape(_('Affidabilità'))} "
                                 f"{html.escape(self._conf(ar.card.confidence))}: "
                                 f"{html.escape('; '.join(ar.card.confidence_reasons))}</li>")
                src = ", ".join(f"{k}: {v}" for k, v in ar.sources.items())
                used = _("{s:.0f} s analizzati").format(s=ar.used_time)
                parts.append(f"<li style='color:{muted}'>{html.escape(_('Segnali'))}: {html.escape(src)} · "
                             f"{ar.fs:.0f} Hz · {html.escape(used)}</li>")
            parts.append("</ul>")
        self.diag.setHtml("".join(parts))

    def _draw_steps(self):
        if not self.results:
            return
        plots.build_step_responses(self.p_step.fig, [r for _n, r in self.results], [n for n, _r in self.results],
                                   show_band=self.show_band.isChecked())
        self.p_step.canvas.draw_idle()

    def _draw_axis_views(self):
        if not self.results:
            return
        axis = self.axis.currentData()
        main = self.results[0][1]
        others = [r.axes[axis] for _n, r in self.results[1:]]
        plots.build_frequency(self.p_freq.fig, main.axes[axis], others, [n for n, _r in self.results])
        self.p_freq.canvas.draw_idle()
        if main.axes[axis].available:
            tf = plots.build_analysis_timeline(self.p_data.fig, self.main.log, main, axis)
            self.p_data.set_timefigure(tf)
        else:
            self.p_data.clear_message(main.axes[axis].reason)
        self.p_data.canvas.draw_idle()

    def update_comparison_label(self):
        names = ", ".join(lg.name for lg in self.main.comparisons)
        self.cmp_label.setText(_("Confronto con: {nomi}").format(nomi=names) if names else "")


# ---------------------------------------------------------- scheda prove a gradino


VERDICT_COLORS = {True: "#2b8a3e", False: "#c92a2a", None: "#868e96"}


def _num(v, nd=3):
    return plots._num(v, nd=nd)


class StepTestTab(QtWidgets.QWidget):
    """Prove a gradino: ogni gradino misurato direttamente e giudicato con i criteri della scheda di taratura."""

    COLS = (N_("#"), N_("Tipo"), N_("Asse"), N_("Verso"), N_("Modo"), N_("Inizio [s]"), N_("Durata [s]"), N_("A"),
            N_("Ritardo [s]"), N_("Sovraelong. [%]"), N_("Assest. [s]"), N_("Errore"), N_("Rimbalzi"),
            N_("Saturaz. [%]"), N_("Esito / motivo"))

    def __init__(self, main, parent=None):
        super().__init__(parent)
        self.main = main
        self.result = None
        self._for_log = None
        controls = QtWidgets.QHBoxLayout()
        self.b_run = QtWidgets.QPushButton(_("Analizza"))
        self.b_run.setStyleSheet(ANALYZE_STYLE)
        self.b_run.clicked.connect(self.run)
        controls.addWidget(self.b_run)
        controls.addWidget(QtWidgets.QLabel(_("Criteri:")))
        self.crit = QtWidgets.QLabel("")
        self.crit.setProperty("role", "hint")
        controls.addWidget(self.crit)
        b_crit = QtWidgets.QPushButton(_("Carica criteri…"))
        b_crit.setToolTip(_("Profilo JSON con le sezioni «gradini» e «tenuta» e i criteri ok degli anelli mc_rate e "
                            "mc_att (come profili/vespa_hover.json)"))
        b_crit.clicked.connect(self.load_criteria)
        controls.addWidget(b_crit)
        b_vespa = QtWidgets.QPushButton(_("Vespa hover"))
        b_vespa.setToolTip(_("Torna ai criteri forniti con l'app (profili/vespa_hover.json)"))
        b_vespa.clicked.connect(self.reset_criteria)
        controls.addWidget(b_vespa)
        controls.addSpacing(12)
        self.ignore_mode = QtWidgets.QCheckBox(_("Ignora il modo"))
        self.ignore_mode.setToolTip(_("Cerca i gradini in tutto il volo in multicottero, non solo in Acro/Offboard/"
                                      "Stabilized: per i log dell'autotune, con gradini iniettati in Hold"))
        controls.addWidget(self.ignore_mode)
        controls.addWidget(QtWidgets.QLabel(_("soglia:")))
        self.threshold = QtWidgets.QDoubleSpinBox()
        self.threshold.setRange(1.0, 200.0)
        self.threshold.setDecimals(1)
        self.threshold.setSuffix(" °/s")
        self.threshold.setValue(10.0)
        self.threshold.setEnabled(False)
        self.ignore_mode.toggled.connect(self.threshold.setEnabled)
        controls.addWidget(self.threshold)
        controls.addSpacing(12)
        self.b_export = QtWidgets.QPushButton(_("Esporta PNG e CSV"))
        self.b_export.setToolTip(_("PNG riassuntivo, CSV (una riga per gradino più il riepilogo) e un PNG per "
                                   "gradino, nella cartella del log"))
        self.b_export.clicked.connect(self.export)
        self.b_export.setEnabled(False)
        controls.addWidget(self.b_export)
        controls.addStretch(1)
        ver = QtWidgets.QLabel(f"Flight Analyzer {__version__}")
        ver.setProperty("role", "hint")
        controls.addWidget(ver)

        # sinistra: parametri, avvisi, riepilogo per asse e verso, FIR affiancato, tenuta
        left = QtWidgets.QWidget()
        ll = QtWidgets.QVBoxLayout(left)
        ll.setContentsMargins(0, 0, 0, 0)
        self.params = QtWidgets.QLabel("")
        self.params.setWordWrap(True)
        self.params.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.warn = QtWidgets.QLabel("")
        self.warn.setWordWrap(True)
        self.warn.setProperty("role", "warn")
        self.summary = QtWidgets.QTableWidget(0, 10)
        self.summary.setHorizontalHeaderLabels(
            [_("Asse"), _("Verso"), _("Validi")] + [_(lab) for _k, lab, _u in steptest.QUANTITIES]
            + [_("Esito")])
        self.summary.verticalHeader().setVisible(False)
        self.summary.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.summary.setToolTip(_("Mediana / caso peggiore dei gradini validi; verde = caso peggiore entro il criterio"))
        self.info = QtWidgets.QTextBrowser()
        ll.addWidget(self.params)
        ll.addWidget(self.warn)
        ll.addWidget(QtWidgets.QLabel(_("Riepilogo per asse e verso (mediana / caso peggiore)")))
        ll.addWidget(self.summary, 2)
        ll.addWidget(QtWidgets.QLabel(_("Stima FIR affiancata e tenuta")))
        ll.addWidget(self.info, 2)

        # destra: elenco dei gradini e grafici
        right = QtWidgets.QWidget()
        rl = QtWidgets.QVBoxLayout(right)
        rl.setContentsMargins(0, 0, 0, 0)
        self.table = QtWidgets.QTableWidget(0, len(self.COLS))
        self.table.setHorizontalHeaderLabels([_(c) for c in self.COLS])
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.itemSelectionChanged.connect(self._draw_selected)
        self.views = QtWidgets.QTabWidget()
        self.p_detail = PlotPanel(self, time_linked=False)
        over = QtWidgets.QWidget()
        ol = QtWidgets.QVBoxLayout(over)
        ol.setContentsMargins(0, 0, 0, 0)
        row = QtWidgets.QHBoxLayout()
        row.addWidget(QtWidgets.QLabel(_("Asse:")))
        self.over_axis = QtWidgets.QComboBox()
        for kind in ("rate", "att"):
            for a in steptest.AXES_OF[kind]:
                self.over_axis.addItem(f"{_(steptest.KINDS[kind])} — {_(scoring.AXIS_LABELS[a]).lower()}", (kind, a))
        self.over_axis.currentIndexChanged.connect(lambda _i: self._draw_overview())
        row.addWidget(self.over_axis)
        row.addStretch(1)
        ol.addLayout(row)
        self.panel = PlotPanel(self)  # tutto il volo: asse dei tempi condiviso con le altre schede
        self.panel.xrange_changed.connect(main.on_xrange)
        self.panel.status.connect(main.show_readout)
        ol.addWidget(self.panel, 1)
        self.views.addTab(self.p_detail, _("Gradino selezionato"))
        self.views.addTab(over, _("Tutto il volo"))
        vsplit = QtWidgets.QSplitter(Qt.Orientation.Vertical)
        vsplit.addWidget(self.table)
        vsplit.addWidget(self.views)
        vsplit.setStretchFactor(0, 1)
        vsplit.setStretchFactor(1, 3)
        rl.addWidget(vsplit, 1)

        self.side_toggle = SideToggle(left, N_("riepilogo e tenuta"))
        controls.insertWidget(0, self.side_toggle)
        split = QtWidgets.QSplitter(Qt.Orientation.Horizontal)
        split.addWidget(left)
        split.addWidget(right)
        split.setStretchFactor(0, 2)
        split.setStretchFactor(1, 3)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(4, 4, 4, 4)
        lay.addLayout(controls)
        lay.addWidget(split, 1)
        self._show_criteria()
        self.p_detail.clear_message(_("Apri un log con prove a gradino"))
        self.panel.clear_message(_("Apri un log con prove a gradino"))

    def toggle_side(self):
        self.side_toggle.toggle()

    def current_panel(self):
        return self.p_detail if self.views.currentIndex() == 0 else self.panel

    # -- criteri
    def _show_criteria(self):
        prof = self.main.step_profile
        self.crit.setText(_(prof.get("nome", "")))

    def load_criteria(self):
        path, _f = QtWidgets.QFileDialog.getOpenFileName(self, _("Carica criteri"), "", _("Profilo JSON (*.json)"))
        if not path:
            return
        try:
            prof = scoring.load_profile(path)
            if "gradini" not in prof or not steptest.definitions_ok(prof):
                raise ValueError(_("il profilo non contiene i criteri della scheda (sezione «gradini» e anelli "
                                   "mc_rate/mc_att con «definizioni»: «scheda»)"))
        except Exception as exc:  # noqa: BLE001
            QtWidgets.QMessageBox.warning(self, _("Profilo non valido"), str(exc))
            return
        self.main.set_step_profile(prof)
        self._show_criteria()
        self.run()

    def reset_criteria(self):
        self.main.set_step_profile(None)
        self._show_criteria()
        self.run()

    # -- esecuzione
    def refresh(self, log):
        if self._for_log is not log:
            self.run()

    def run(self):
        log = self.main.log
        if log is None:
            return
        prof = self.main.step_profile
        ign = self.ignore_mode.isChecked()
        thr = self.threshold.value() if ign else None
        self._for_log = log
        self.b_run.setEnabled(False)
        self.main.run_task(lambda: steptest.detect(log, prof, ign, thr, with_fir=True), self._done,
                           busy=_("Prove a gradino…"), on_fail=lambda: self.b_run.setEnabled(True))

    def _done(self, res):
        self.b_run.setEnabled(True)
        self.result = res
        self.b_export.setEnabled(bool(res.steps))
        self.params.setText("<b>" + html.escape(_("Parametri del volo")) + ":</b> " + html.escape(
            "   ".join(f"{k} = {plots._num(v, nd=4) if isinstance(v, float) else v}" for k, v in res.params)))
        self.warn.setText("\n".join("⚠ " + w for w in res.warnings))
        self.warn.setVisible(bool(res.warnings))
        self._fill_summary(res)
        self._fill_steps(res)
        self._fill_info(res)
        first = next((i for i, s in enumerate(res.steps) if s.valid), 0 if res.steps else None)
        if first is not None:
            self.table.selectRow(first)
        else:
            self.p_detail.clear_message(_("Nessun gradino trovato nel log."))
        keys = list(res.summary)
        if keys:
            idx = self.over_axis.findData(keys[0])
            if idx >= 0:
                self.over_axis.setCurrentIndex(idx)
        self._draw_overview()

    def _fill_summary(self, res):
        rows = [(key, sign, d) for key, sm in res.summary.items() for sign, d in sm.directions.items()]
        self.summary.setRowCount(len(rows))
        bold = QtGui.QFont()
        bold.setBold(True)
        for r, ((kind, axis), sign, d) in enumerate(rows):
            sm = res.summary[(kind, axis)]
            cells = [f"{_(steptest.KIND_SHORT[kind])} {_(scoring.AXIS_LABELS[axis]).lower()}",
                     "+" if sign > 0 else "−", f"{d.n_valid}/{d.n_total}"]
            colors = [None, None, None]
            for qk, _lab, _u in steptest.QUANTITIES:
                m, w = d.median.get(qk), d.worst.get(qk)
                cells.append("—" if w is None else f"{plots._num(m, qk)} / {plots._num(w, qk)}")
                colors.append(d.passed.get(qk))
            verdict = steptest.direction_verdict(d)
            txt = {None: "—", True: _("entro i criteri"), False: _("fuori criterio")}[verdict]
            if sign == next(iter(sm.directions)):
                txt += " · " + ({None: _("asse: non valutabile"), True: _("asse: TARATO"),
                                 False: _("asse: NON TARATO")}[sm.tuned])
            cells.append(txt)
            colors.append(verdict)
            for c, (txt_c, col) in enumerate(zip(cells, colors)):
                it = QtWidgets.QTableWidgetItem(txt_c)
                if col is not None:
                    it.setForeground(QtGui.QBrush(QtGui.QColor(VERDICT_COLORS[col])))
                    if c == len(cells) - 1:
                        it.setFont(bold)
                lim = sm.limits.get(steptest.QUANTITIES[c - 3][0]) if 3 <= c < 3 + len(steptest.QUANTITIES) else None
                if lim is not None:
                    it.setToolTip(_("criterio: ≤ {v}").format(v=plots._num(lim, steptest.QUANTITIES[c - 3][0])))
                self.summary.setItem(r, c, it)
        self.summary.resizeColumnsToContents()

    def _fill_steps(self, res):
        self.table.blockSignals(True)
        self.table.setRowCount(len(res.steps))
        for r, s in enumerate(res.steps):
            rr = s.resp
            cells = [str(s.n), _(steptest.KIND_SHORT[s.kind]), _(scoring.AXIS_LABELS[s.axis]), s.sign_label, s.mode,
                     _num(s.t_start, 2), _num(s.duration, 3), f"{_num(s.amplitude * s.sign, 1)} {steptest.UNITS[s.kind]}",
                     "—" if rr is None or rr.delay is None else _num(rr.delay, 3),
                     "—" if rr is None else _num(rr.overshoot, 1),
                     "—" if rr is None else (_("non assestato") if rr.settling is None else _num(rr.settling, 3)),
                     "—" if rr is None or rr.end_error is None else
                     f"{_num(rr.end_error, 1)} {steptest.error_unit(s.kind)}",
                     "—" if rr is None else str(rr.bounces),
                     "—" if s.saturation is None else _num(s.saturation, 1) + (f" ({s.sat_text()})" if s.sat_text()
                                                                                 else ""),
                     _("valido") if s.valid else "; ".join(s.reasons)]
            for c, txt in enumerate(cells):
                it = QtWidgets.QTableWidgetItem(txt)
                if c == len(cells) - 1:
                    it.setForeground(QtGui.QBrush(QtGui.QColor(VERDICT_COLORS[s.valid])))
                    it.setToolTip("\n".join(s.reasons + s.notes))
                elif s.notes:
                    it.setToolTip("\n".join(s.notes))
                self.table.setItem(r, c, it)
        self.table.resizeColumnsToContents()
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.blockSignals(False)

    def _fill_info(self, res):
        e = html.escape
        muted, warn = theme.tok("text_muted"), theme.tok("warn")
        parts = [f"<p><b>{e(_('Stima FIR (stesse definizioni, profilo dei criteri)'))}</b></p><ul>"]
        if not res.fir:
            parts.append(f"<li>{e(_('nessun asse con gradini'))}</li>")
        for (kind, axis), item in res.fir.items():
            head = f"{_(steptest.KINDS[kind])} — {_(scoring.AXIS_LABELS[axis]).lower()}"
            if "error" in item:
                parts.append(f"<li>{e(head)}: {e(item['error'])}</li>")
                continue
            v, sd = item["values"], item["spread"]

            def pm(k, nd):
                val = v.get(k)
                if val is None:
                    return "—"
                if not math.isfinite(val):
                    return _("non assestato")
                txt = _num(val, nd)
                return txt + (f" ± {_num(sd[k], nd)}" if sd.get(k) is not None else "")

            score = "—" if item["score"] is None else f"{item['score']:.0f}/100"
            parts.append(f"<li><b>{e(head)}</b>: {e(_('ritardo'))} {e(pm('delay', 3))} s · "
                         f"{e(_('sovraelongazione'))} {e(pm('overshoot', 1))}% · {e(_('assestamento'))} "
                         f"{e(pm('settling', 3))} · {e(_('punteggio'))} {e(score)} "
                         f"<span style='color:{muted}'>({e(_('affidabilità'))} "
                         f"{e(_(scoring.CONFIDENCE.get(item['confidence'], item['confidence'])))})</span>")
            for w in item["warnings"]:
                parts.append(f"<br><span style='color:{warn}'>⚠ {e(w)}</span>")
            parts.append("</li>")
        parts.append("</ul>")
        parts.append(f"<p><b>{e(_('Tenuta in Hold/Position (tratti fermi, senza comandi)'))}</b></p>")
        if not res.holds:
            parts.append(f"<p style='color:{muted}'>{e(_('nessun tratto in Hold/Position con velocità richiesta nulla'))}</p>")
        for h in res.holds:
            col = VERDICT_COLORS[h.ok]
            parts.append(f"<p><b style='color:{col}'>{e(h.mode)} {_num(h.t0, 1)}–{_num(h.t1, 1)} s: "
                         f"{e(_('entro i criteri') if h.ok else _('fuori criterio'))}</b>"
                         + "".join(f"<br><span style='color:{muted}'>{e(n)}</span>" for n in h.notes) + "</p><ul>")
            for key, label, unit, _lim in steptest.HOLD_ITEMS:
                val = h.values.get(key)
                if val is None:
                    continue
                if isinstance(val, tuple):
                    txt = (f"{_num(val[0], 3)} ± {_num(val[1], 3)}" if key == "hover"
                           else f"{_num(val[0], 2)} – {_num(val[1], 2)}")
                else:
                    txt = f"{_num(val, 2)} {unit}".strip()
                ok = h.passed.get(key)
                color = "" if ok is None else f" style='color:{VERDICT_COLORS[ok]}'"
                parts.append(f"<li{color}>{e(_(label))}: {e(txt)}</li>")
            rng = h.values.get("roll_range")
            if rng:
                parts.append(f"<li style='color:{muted}'>{e(_('rollio tra'))} {_num(rng[0], 2)}° {e(_('e'))} "
                             f"{_num(rng[1], 2)}°</li>")
            parts.append("</ul>")
        parts.append(f"<p style='color:{muted}'>{e(_('Convenzione dei tempi'))}: {e(_(steptest.TIME_CONVENTION))}</p>")
        self.info.setHtml("".join(parts))

    # -- grafici
    def _selected(self):
        if self.result is None:
            return None
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        if not rows:
            return None
        r = rows[0].row()
        return self.result.steps[r] if 0 <= r < len(self.result.steps) else None

    def _draw_selected(self):
        st = self._selected()
        if st is None or self.main.log is None:
            return
        plots.build_step_detail(self.p_detail.fig, self.main.log, self.result, st)
        self.p_detail.canvas.draw_idle()
        self.views.setCurrentIndex(0)

    def _draw_overview(self):
        if self.result is None or self.main.log is None:
            return
        kind, axis = self.over_axis.currentData()
        tf = plots.build_step_overview(self.panel.fig, self.main.log, self.result, kind, axis)
        self.panel.set_timefigure(tf)
        if self.main.xrange is not None:
            self.panel.apply_xrange(*self.main.xrange)
        self.panel.canvas.draw_idle()

    # -- esportazione
    def export(self):
        log, res = self.main.log, self.result
        if log is None or res is None:
            return

        def done(paths):
            folder = str(Path(paths[0]).parent)
            self.main.statusBar().showMessage(_("Scritti {n} file nella cartella del log:\n{cartella}").format(
                n=len(paths), cartella=folder).replace("\n", " "), 8000)
            answer = QtWidgets.QMessageBox.question(
                self, _("Esportazione completata"),
                _("Scritti {n} file nella cartella del log:\n{cartella}").format(n=len(paths), cartella=folder)
                + "\n\n" + _("Aprire la cartella?"))
            if answer == QtWidgets.QMessageBox.StandardButton.Yes:
                QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(folder))

        self.main.run_task(lambda: [str(p) for p in steptest.export(log, res)], done,
                           busy=_("Esportazione delle prove a gradino…"))


# ------------------------------------------------------------- dialogo profilo


LOOP_SHORT = {"mc_rate": N_("Multicottero · rate"), "mc_att": N_("Multicottero · assetto"),
              "fw_rate": N_("Ala fissa · rate"), "fw_att": N_("Ala fissa · assetto")}


class ProfileDialog(QtWidgets.QDialog):
    """Soglie, pesi e obiettivi del profilo di valutazione (anche i profili con le definizioni della scheda)."""

    def __init__(self, profile, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Profilo di valutazione"))
        self.resize(900, 600)
        self.profile = json.loads(json.dumps(profile))
        intro = QtWidgets.QLabel(_(
            "Ogni metrica vale 100 punti alla soglia «ottimo», 60 a «accettabile» e 0 a «da rivedere» "
            "(interpolazione lineare). Il peso decide quanto conta nel punteggio dell'asse. Obiettivo del tempo di "
            "salita: «auto» lo ricava dai parametri del log (MC_AT_RISE_TIME, MC_ROLL_P, FW_R_TC…), oppure un valore "
            "in secondi. Nel profilo «Vespa hover» la soglia «accettabile» è il criterio della scheda di taratura e le "
            "grandezze sono misurate rispetto all'ampiezza comandata."))
        intro.setWordWrap(True)
        self.name = QtWidgets.QLineEdit()
        self.tabs = QtWidgets.QTabWidget()
        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                             QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        b_load = buttons.addButton(_("Carica…"), QtWidgets.QDialogButtonBox.ButtonRole.ActionRole)
        b_save = buttons.addButton(_("Salva come…"), QtWidgets.QDialogButtonBox.ButtonRole.ActionRole)
        b_def = buttons.addButton(_("PX4 standard"), QtWidgets.QDialogButtonBox.ButtonRole.ResetRole)
        b_vespa = buttons.addButton(_("Vespa hover"), QtWidgets.QDialogButtonBox.ButtonRole.ResetRole)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        b_load.clicked.connect(self._load)
        b_save.clicked.connect(self._save)
        b_def.clicked.connect(self._defaults)
        b_vespa.clicked.connect(self._vespa)
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(intro)
        form = QtWidgets.QFormLayout()
        form.addRow(_("Nome del profilo:"), self.name)
        lay.addLayout(form)
        lay.addWidget(self.tabs, 1)
        lay.addWidget(buttons)
        self._set(self.profile)

    @staticmethod
    def _metric_table(metrics):
        tbl = QtWidgets.QTableWidget(len(metrics), 5)
        tbl.setHorizontalHeaderLabels([_("Metrica"), _("Ottimo (100)"), _("Accettabile (60)"), _("Da rivedere (0)"),
                                       _("Peso")])
        tbl.verticalHeader().setVisible(False)
        for row, (mk, th) in enumerate(metrics.items()):
            unit = scoring.METRIC_INFO[mk][1]
            lab = QtWidgets.QTableWidgetItem(_(scoring.METRIC_INFO[mk][0]) + (f" [{unit}]" if unit else ""))
            lab.setFlags(lab.flags() & ~Qt.ItemFlag.ItemIsEditable)
            lab.setData(Qt.ItemDataRole.UserRole, mk)
            tbl.setItem(row, 0, lab)
            for col, key in enumerate(("good", "ok", "bad", "weight"), start=1):
                tbl.setItem(row, col, QtWidgets.QTableWidgetItem(f"{th[key]:g}"))
        tbl.horizontalHeader().setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Stretch)
        return tbl

    def _set(self, prof):
        """Ricostruisce le schede dal profilo (la struttura cambia tra PX4 standard e Vespa hover)."""
        self.profile = json.loads(json.dumps(prof))
        self.name.setText(_(prof.get("nome", "")))
        while self.tabs.count():
            w = self.tabs.widget(0)
            self.tabs.removeTab(0)
            w.deleteLater()
        self._tables, self._targets, self._exc = {}, {}, {}
        for loop, cfg in self.profile["loops"].items():
            w = QtWidgets.QWidget()
            lay = QtWidgets.QVBoxLayout(w)
            form = QtWidgets.QFormLayout()
            if cfg.get("definizioni") == "scheda":
                form.addRow(hint_label(_("Definizioni della scheda di taratura: gradino di {a} per {d}.").format(
                    a=", ".join(f"{_(scoring.AXIS_LABELS[a]).lower()} {scoring.step_spec(self.profile, loop, a)['amp']:g}"
                                for a in scoring.AXES),
                    d=", ".join(f"{scoring.step_spec(self.profile, loop, a)['dur']:g} s" for a in scoring.AXES))))
            for axis in scoring.AXES:
                le = QtWidgets.QLineEdit(str(cfg["rise_target_s"].get(axis, "auto")))
                form.addRow(_("Obiettivo tempo di salita, {asse} [s]:").format(asse=_(scoring.AXIS_LABELS[axis]).lower()),
                            le)
                self._targets[(loop, axis)] = le
            sp = QtWidgets.QDoubleSpinBox()
            sp.setDecimals(3)
            sp.setRange(0.0, 10.0)
            sp.setSingleStep(0.01)
            sp.setValue(float(cfg.get("min_excitation", 0.1)))
            form.addRow(_("Eccitazione minima (picco-picco in 1 s, rad o rad/s):"), sp)
            self._exc[loop] = sp
            lay.addLayout(form)
            tbl = self._metric_table(cfg["metrics"])
            lay.addWidget(tbl, 1)
            self._tables[(loop, None)] = tbl
            title = _(LOOP_SHORT.get(loop, loop))
            others = [a for a in scoring.AXES if a not in cfg.get("metrics_asse", {})]
            if cfg.get("metrics_asse"):
                title += " · " + "/".join(_(scoring.AXIS_LABELS[a]).lower() for a in others)
            self.tabs.addTab(w, title)
            for axis, metrics in cfg.get("metrics_asse", {}).items():
                w2 = QtWidgets.QWidget()
                l2 = QtWidgets.QVBoxLayout(w2)
                l2.addWidget(hint_label(_("Soglie solo per l'asse {asse}.").format(
                    asse=_(scoring.AXIS_LABELS[axis]).lower())))
                t2 = self._metric_table(metrics)
                l2.addWidget(t2, 1)
                self._tables[(loop, axis)] = t2
                self.tabs.addTab(w2, f"{_(LOOP_SHORT.get(loop, loop))} · {_(scoring.AXIS_LABELS[axis]).lower()}")

    @staticmethod
    def _read_table(tbl):
        metrics = {}
        for row in range(tbl.rowCount()):
            mk = tbl.item(row, 0).data(Qt.ItemDataRole.UserRole)
            label = _(scoring.METRIC_INFO[mk][0])
            vals = {}
            for col, key in enumerate(("good", "ok", "bad", "weight"), start=1):
                txt = tbl.item(row, col).text().replace(",", ".").strip()
                try:
                    vals[key] = float(txt)
                except ValueError:
                    raise ValueError(_("{metrica}: «{testo}» non è un numero").format(metrica=label, testo=txt)) from None
            if vals["good"] == vals["ok"] or vals["ok"] == vals["bad"]:
                raise ValueError(_("{metrica}: le tre soglie devono essere diverse").format(metrica=label))
            if (vals["good"] < vals["ok"]) != (vals["ok"] < vals["bad"]):
                raise ValueError(_("{metrica}: le soglie devono essere in ordine monotono").format(metrica=label))
            metrics[mk] = vals
        return metrics

    def _collect(self):
        prof = json.loads(json.dumps(self.profile))  # tiene definizioni, gradino, sezioni delle prove a gradino
        prof["nome"] = self.name.text().strip() or _("Profilo personalizzato")
        for (loop, axis), tbl in self._tables.items():
            metrics = self._read_table(tbl)
            if axis is None:
                prof["loops"][loop]["metrics"] = metrics
            else:
                prof["loops"][loop].setdefault("metrics_asse", {})[axis] = metrics
        for loop in prof["loops"]:
            targets = {}
            for axis in scoring.AXES:
                txt = self._targets[(loop, axis)].text().strip().replace(",", ".")
                if txt.lower() in ("", "auto"):
                    targets[axis] = "auto"
                else:
                    try:
                        targets[axis] = float(txt)
                    except ValueError:
                        raise ValueError(_("Obiettivo del tempo di salita non valido: «{testo}»").format(testo=txt)) \
                            from None
            prof["loops"][loop]["rise_target_s"] = targets
            prof["loops"][loop]["min_excitation"] = self._exc[loop].value()
        return prof

    def _accept(self):
        try:
            self.profile = self._collect()
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, _("Valore non valido"), str(exc))
            return
        self.accept()

    def _load(self):
        path, _f = QtWidgets.QFileDialog.getOpenFileName(self, _("Carica profilo"), "", _("Profilo JSON (*.json)"))
        if path:
            try:
                self._set(scoring.load_profile(path))
            except Exception as exc:  # noqa: BLE001
                QtWidgets.QMessageBox.warning(self, _("Profilo non valido"), str(exc))

    def _save(self):
        try:
            prof = self._collect()
        except ValueError as exc:
            QtWidgets.QMessageBox.warning(self, _("Valore non valido"), str(exc))
            return
        path, _f = QtWidgets.QFileDialog.getSaveFileName(self, _("Salva profilo"), "profilo_vespa.json",
                                                         _("Profilo JSON (*.json)"))
        if path:
            scoring.save_profile(prof, path)

    def _defaults(self):
        self._set(scoring.default_profile())

    def _vespa(self):
        try:
            self._set(scoring.vespa_hover_profile())
        except Exception as exc:  # noqa: BLE001
            QtWidgets.QMessageBox.warning(self, _("Profilo non valido"), str(exc))


# ------------------------------------------------------------ impostazioni


BACKGROUND_CHOICES = (("both", N_("Fasi VTOL e modi di volo")), ("phases", N_("Solo fasi VTOL")),
                      ("modes", N_("Solo modi di volo")), ("none", N_("Nessuno")))
ANGLE_CHOICES = (("deg", N_("Gradi (° e °/s)")), ("rad", N_("Radianti (rad e rad/s)")))


class SettingsDialog(QtWidgets.QDialog):
    """Impostazioni: generale, unità, grafici, schede visibili, esportazione, scheda di taratura."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle(_("Impostazioni"))
        self.resize(660, 540)
        self.tabs = QtWidgets.QTabWidget()

        # generale
        g = QtWidgets.QWidget()
        gf = QtWidgets.QFormLayout(g)
        self.language = QtWidgets.QComboBox()
        for code, name in i18n.SUPPORTED.items():
            self.language.addItem(name, code)
        gf.addRow(_("Lingua:"), self.language)
        gf.addRow("", hint_label(_("Il cambio di lingua si applica al riavvio dell'app.")))
        self.theme = QtWidgets.QComboBox()
        for key, label in (("light", N_("Chiaro")), ("dark", N_("Scuro")), ("system", N_("Come il sistema"))):
            self.theme.addItem(_(label), key)
        gf.addRow(_("Tema:"), self.theme)
        self.default_phase = QtWidgets.QComboBox()
        for key, label in (("auto", N_("Automatica (la fase più lunga)")), ("MC", N_("Multicottero")),
                           ("FW", N_("Ala fissa"))):
            self.default_phase.addItem(_(label), key)
        gf.addRow(_("Fase da analizzare all'apertura:"), self.default_phase)
        self.analyze_on_open = QtWidgets.QCheckBox(_("Esegui l'analisi PID appena si apre un log"))
        gf.addRow("", self.analyze_on_open)
        if sys.platform == "win32":
            b_short = QtWidgets.QPushButton(_("Crea scorciatoia sul desktop"))
            b_short.clicked.connect(self._shortcut)
            gf.addRow(_("Desktop:"), b_short)
        self.tabs.addTab(g, _("Generale"))

        # unità di misura
        u = QtWidgets.QWidget()
        uf = QtWidgets.QFormLayout(u)
        self.angle = QtWidgets.QComboBox()
        for key, label in ANGLE_CHOICES:
            self.angle.addItem(_(label), key)
        uf.addRow(_("Angoli e velocità angolari:"), self.angle)
        self.speed = QtWidgets.QComboBox()
        for key, label in (("m/s", N_("metri al secondo (m/s)")), ("km/h", N_("chilometri orari (km/h)")),
                           ("kn", N_("nodi (kn)"))):
            self.speed.addItem(_(label), key)
        uf.addRow(_("Velocità:"), self.speed)
        self.alt = QtWidgets.QComboBox()
        self.alt.addItem(_("metri (m)"), "m")
        self.alt.addItem(_("piedi (ft)"), "ft")
        uf.addRow(_("Quote e distanze:"), self.alt)
        uf.addRow("", hint_label(_("Le grandezze della valutazione PID restano nelle unità della scala di "
                                   "valutazione (%, s, dB, gradi di fase).")))
        self.tabs.addTab(u, _("Unità di misura"))

        # grafici
        p = QtWidgets.QWidget()
        pf = QtWidgets.QFormLayout(p)
        self.background = QtWidgets.QComboBox()
        for key, label in BACKGROUND_CHOICES:
            self.background.addItem(_(label), key)
        pf.addRow(_("Sfondo dei grafici:"), self.background)
        self.line_width = QtWidgets.QDoubleSpinBox()
        self.line_width.setRange(0.5, 3.0)
        self.line_width.setSingleStep(0.1)
        pf.addRow(_("Spessore delle linee (×):"), self.line_width)
        self.font_scale = QtWidgets.QDoubleSpinBox()
        self.font_scale.setRange(0.7, 1.8)
        self.font_scale.setSingleStep(0.1)
        pf.addRow(_("Dimensione del testo (×):"), self.font_scale)
        self.max_points = QtWidgets.QSpinBox()
        self.max_points.setRange(500, 20000)
        self.max_points.setSingleStep(500)
        pf.addRow(_("Punti disegnati per curva:"), self.max_points)
        pf.addRow("", hint_label(_("Più punti = più dettaglio ma grafici più lenti; con lo zoom il dettaglio "
                                   "aumenta comunque.")))
        self.legend_toggle = QtWidgets.QCheckBox(_("Clic sulla legenda per nascondere o mostrare una curva"))
        pf.addRow("", self.legend_toggle)
        self.wheel_zoom = QtWidgets.QCheckBox(_("Rotella per lo zoom e trascinamento per spostarsi"))
        pf.addRow("", self.wheel_zoom)
        self.tabs.addTab(p, _("Grafici"))

        # schede visibili
        s = QtWidgets.QWidget()
        sl = QtWidgets.QVBoxLayout(s)
        sl.addWidget(hint_label(_("Schede da mostrare nella finestra principale:")))
        self.tab_checks = {}
        grid = QtWidgets.QGridLayout()
        for i, key in enumerate(TAB_KEYS):
            cb = QtWidgets.QCheckBox(_(TAB_LABELS[key]))
            if key == "overview":
                cb.setEnabled(False)
            self.tab_checks[key] = cb
            grid.addWidget(cb, i // 2, i % 2)
        sl.addLayout(grid)
        sl.addStretch(1)
        self.tabs.addTab(s, _("Schede"))

        # esportazione
        e = QtWidgets.QWidget()
        ef = QtWidgets.QFormLayout(e)
        self.export_format = QtWidgets.QComboBox()
        self.export_format.addItem("PDF", "pdf")
        self.export_format.addItem(_("HTML (pagina web)"), "html")
        ef.addRow(_("Formato predefinito del report:"), self.export_format)
        self.export_frequency = QtWidgets.QCheckBox(_("Includi la risposta in frequenza"))
        ef.addRow("", self.export_frequency)
        self.export_parameters = QtWidgets.QCheckBox(_("Includi i parametri di valutazione in fondo al report"))
        ef.addRow("", self.export_parameters)
        self.tabs.addTab(e, _("Esportazione"))

        # scheda di taratura
        t = QtWidgets.QWidget()
        tl = QtWidgets.QFormLayout(t)
        self.responsible = QtWidgets.QLineEdit()
        self.verifier = QtWidgets.QLineEdit()
        tl.addRow(_("Responsabile:"), self.responsible)
        tl.addRow(_("Verificato da:"), self.verifier)
        tl.addRow("", hint_label(_("Nomi usati per precompilare la scheda di taratura.")))
        self.tabs.addTab(t, _("Scheda di taratura"))

        buttons = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok |
                                             QtWidgets.QDialogButtonBox.StandardButton.Cancel)
        b_def = buttons.addButton(_("Ripristina predefiniti"), QtWidgets.QDialogButtonBox.ButtonRole.ResetRole)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        b_def.clicked.connect(lambda: self._load({**config.DEFAULTS, "language": CFG.get("language", "it")}))
        lay = QtWidgets.QVBoxLayout(self)
        lay.addWidget(self.tabs, 1)
        lay.addWidget(buttons)
        self._load(CFG)

    @staticmethod
    def _select(combo, value):
        for i in range(combo.count()):
            if combo.itemData(i) == value:
                combo.setCurrentIndex(i)
                return

    def _load(self, values):
        self._select(self.language, values.get("language", "it"))
        self._select(self.theme, values.get("theme", "light"))
        self._select(self.default_phase, values.get("default_phase", "auto"))
        self.analyze_on_open.setChecked(bool(values.get("analyze_on_open", True)))
        self._select(self.angle, values.get("angle_unit", "deg"))
        self._select(self.speed, values.get("speed_unit", "m/s"))
        self._select(self.alt, values.get("alt_unit", "m"))
        self._select(self.background, values.get("background", "both"))
        self.line_width.setValue(float(values.get("line_width", 1.0)))
        self.font_scale.setValue(float(values.get("font_scale", 1.0)))
        self.max_points.setValue(int(values.get("max_points", 2500)))
        self.legend_toggle.setChecked(bool(values.get("legend_toggle", True)))
        self.wheel_zoom.setChecked(bool(values.get("wheel_zoom", True)))
        hidden = set(values.get("hidden_tabs", []))
        for key, cb in self.tab_checks.items():
            cb.setChecked(key not in hidden)
        self._select(self.export_format, values.get("export_format", "pdf"))
        self.export_frequency.setChecked(bool(values.get("export_frequency", True)))
        self.export_parameters.setChecked(bool(values.get("export_parameters", True)))
        self.responsible.setText(str(values.get("responsible", "")))
        self.verifier.setText(str(values.get("verifier", "")))

    def values(self):
        return {
            "language": self.language.currentData(), "theme": self.theme.currentData(),
            "default_phase": self.default_phase.currentData(), "analyze_on_open": self.analyze_on_open.isChecked(),
            "angle_unit": self.angle.currentData(), "speed_unit": self.speed.currentData(),
            "alt_unit": self.alt.currentData(), "background": self.background.currentData(),
            "line_width": round(float(self.line_width.value()), 2), "font_scale": round(float(self.font_scale.value()), 2),
            "max_points": int(self.max_points.value()), "legend_toggle": self.legend_toggle.isChecked(),
            "wheel_zoom": self.wheel_zoom.isChecked(),
            "hidden_tabs": [k for k, cb in self.tab_checks.items() if not cb.isChecked() and k != "overview"],
            "export_format": self.export_format.currentData(), "export_frequency": self.export_frequency.isChecked(),
            "export_parameters": self.export_parameters.isChecked(), "responsible": self.responsible.text().strip(),
            "verifier": self.verifier.text().strip(),
        }

    def _shortcut(self):
        path = desktop_shortcut_path()
        if path is None:
            QtWidgets.QMessageBox.warning(self, _("Desktop non disponibile"),
                                          _("Non è stato possibile individuare la cartella Desktop."))
            return
        try:
            _create_desktop_shortcut(path)
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            QtWidgets.QMessageBox.warning(self, _("Scorciatoia non creata"), str(exc))
        else:
            QtWidgets.QMessageBox.information(self, APP_NAME, _("Scorciatoia creata sul desktop."))


# ------------------------------------------------------------- finestra


def help_html():
    li = "".join
    return li([
        f"<h3>{_('Come leggere i punteggi')}</h3>",
        "<p>" + _("Per ogni asse l'app stima dai dati di volo la risposta al gradino dell'anello scelto (rate o "
                  "assetto) e la confronta con soglie fisse: sovraelongazione, tempo di salita rispetto a un "
                  "obiettivo, assestamento, errore a regime, picco di risonanza e, per il rate multicottero, il "
                  "margine di fase calcolato dal guadagno d'anello. Ogni metrica vale 100 punti alla soglia ottima, "
                  "60 a quella accettabile e 0 a quella da rivedere.") + "</p>",
        "<p>" + _("Affidabilità: alta, media o bassa a seconda di quanta eccitazione c'è nel volo, della frequenza "
                  "di log e della dispersione della stima (jackknife a blocchi). Gli assi ad affidabilità bassa non "
                  "entrano nel totale.") + "</p>",
        "<p>" + _("Per confrontare due tarature usa lo stesso profilo e manovre simili; aggiungi l'altro log con "
                  "«Aggiungi log di confronto…».") + "</p>",
        f"<h3>{_('Navigare nei grafici')}</h3><ul>",
        "<li>" + _("Rotella: zoom sul tempo attorno al mouse; Ctrl+rotella: zoom verticale; Maiusc+rotella: "
                   "scorrimento.") + "</li>",
        "<li>" + _("Trascinamento con il tasto sinistro: spostamento nel tempo; doppio clic: tutto il log.") + "</li>",
        "<li>" + _("Tastiera, dopo un clic sul grafico: frecce per scorrere, + e − per lo zoom, Home per tutto il "
                   "log, A per riadattare l'asse verticale.") + "</li>",
        "<li>" + _("Menu «Vai a»: porta tutti i grafici su una fase VTOL, un modo di volo o il tratto in volo.")
        + "</li>",
        "<li>" + _("Clic su una voce di legenda: nasconde o mostra quella curva.") + "</li>",
        "<li>" + _("◀ / ▶ (o Ctrl+B) nasconde il pannello laterale per allargare i grafici; F11 schermo intero.")
        + "</li></ul>",
        f"<h3>{_('Volo di prova consigliato')}</h3><ul>",
        "<li>" + _("Parametro SDLOG_PROFILE con il bit «High rate» (es. 17 = default + alta frequenza).") + "</li>",
        "<li>" + _("Per ogni asse almeno 20–30 s di impulsi brevi e netti sullo stick, alternati a pause, in "
                   "Stabilized o Acro.") + "</li>",
        "<li>" + _("Per stimare i margini di stabilità: autotune PX4 con MC_AT_APPLY = 0 (solo registrazione, i "
                   "guadagni non vengono cambiati), avviato in Position/Hold.") + "</li>",
        "<li>" + _("Non cambiare i guadagni durante il volo analizzato.") + "</li></ul>",
    ])


class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(APP_NAME)
        self.resize(1500, 950)
        self.settings = _settings()
        if (RESOURCES / "icona.png").exists():
            self.setWindowIcon(QtGui.QIcon(str(RESOURCES / "icona.png")))
        self.profile = self._load_profile()
        self.step_profile = self._load_step_profile()
        self.log: LogData | None = None
        self.comparisons: list[LogData] = []
        self.xrange = None
        self.pool = QtCore.QThreadPool.globalInstance()
        self._tasks = {}
        self._task_seq = 0
        self._built = set()

        self.tabs = QtWidgets.QTabWidget()
        self.tabs.setDocumentMode(True)
        self.tabs.setUsesScrollButtons(True)
        self.t_overview = OverviewTab(self)
        self.t_pid = PidTab(self)
        self.t_pid.show_profile()
        self.t_steps = StepTestTab(self)
        self.t_att = TimeTab(self, plots.build_attitude)
        self.t_rates = TimeTab(self, plots.build_rates)
        self.t_pos = TimeTab(self, plots.build_position)
        self.t_ctrl = TimeTab(self, plots.build_controls)
        self.t_power = TimeTab(self, plots.build_power)
        self.t_out = TimeTab(self, plots.build_outputs)
        self.t_rpm = TimeTab(self, plots.build_rpm)
        vib_views = [(N_("Vibrazioni nel tempo"), plots.build_vibration),
                     (N_("Densità spettrale di potenza nel tempo (come Flight Review)"), plots.build_psd_spectrograms)]
        vib_views += [((N_("Spettro: "), name), _spectrum_builder(name)) for name in plots.SPECTRUM_SIGNALS]
        self.t_vib = TimeTab(self, views=vib_views)
        self.t_sys = TimeTab(self, plots.build_system)
        self.t_flags = FlagsTab(self)
        self.t_params = ParamsTab()
        self.t_msgs = MessagesTab(self)
        self.t_explore = ExplorerTab(self)
        self.tab_widgets = {
            "overview": self.t_overview, "pid": self.t_pid, "steps": self.t_steps, "attitude": self.t_att,
            "rates": self.t_rates,
            "position": self.t_pos, "controls": self.t_ctrl, "power": self.t_power, "outputs": self.t_out,
            "rpm": self.t_rpm, "vibration": self.t_vib, "system": self.t_sys, "flags": self.t_flags,
            "params": self.t_params, "messages": self.t_msgs, "explore": self.t_explore,
        }
        self.time_tabs = [self.t_att, self.t_rates, self.t_pos, self.t_ctrl, self.t_power, self.t_out, self.t_rpm,
                          self.t_vib, self.t_sys, self.t_flags, self.t_explore, self.t_steps]
        self._rebuild_tabs()
        self.tabs.currentChanged.connect(self._tab_changed)
        self.setCentralWidget(self.tabs)
        self._welcome()

        self.progress = QtWidgets.QProgressBar()
        self.progress.setRange(0, 0)
        self.progress.setMaximumWidth(160)
        self.progress.setVisible(False)
        self.readout = QtWidgets.QLabel("")
        self.statusBar().addPermanentWidget(self.readout, 1)
        self.statusBar().addPermanentWidget(self.progress)
        self._build_menus()
        self.setAcceptDrops(True)

    def _rebuild_tabs(self):
        current = self.tabs.currentWidget()
        hidden = set(CFG.get("hidden_tabs", []))
        self.tabs.blockSignals(True)
        while self.tabs.count():
            self.tabs.removeTab(0)
        for key in TAB_KEYS:
            if key in hidden and key != "overview":
                continue
            self.tabs.addTab(self.tab_widgets[key], _(TAB_LABELS[key]))
        idx = self.tabs.indexOf(current) if current is not None else -1
        self.tabs.setCurrentIndex(idx if idx >= 0 else 0)
        self.tabs.blockSignals(False)

    # -- menu e barra degli strumenti
    def _build_menus(self):
        mb = self.menuBar()
        m_file = mb.addMenu(_("&File"))
        a_open = QtGui.QAction(_("Apri log…"), self)
        a_open.setShortcut(QtGui.QKeySequence(QtGui.QKeySequence.StandardKey.Open))
        a_open.triggered.connect(self.open_dialog)
        m_file.addAction(a_open)
        self.m_recent = m_file.addMenu(_("Apri recenti"))
        self._fill_recent()
        m_file.addSeparator()
        a_pdf = QtGui.QAction(_("Esporta PDF"), self)
        a_pdf.setShortcut(QtGui.QKeySequence("Ctrl+P"))
        a_pdf.setToolTip(_("Crea subito il report PDF accanto al log e lo apre (Ctrl+P)"))
        a_pdf.triggered.connect(self.export_pdf_quick)
        m_file.addAction(a_pdf)
        a_rep = QtGui.QAction(_("Esporta report…"), self)
        a_rep.setShortcut(QtGui.QKeySequence("Ctrl+E"))
        a_rep.setToolTip(_("Sceglie dove salvare il report, in PDF o HTML (Ctrl+E)"))
        a_rep.triggered.connect(self.export_report)
        m_file.addAction(a_rep)
        a_json = QtGui.QAction(_("Esporta risultati JSON…"), self)
        a_json.triggered.connect(self.export_json)
        m_file.addAction(a_json)
        a_img = QtGui.QAction(_("Salva grafico corrente…"), self)
        a_img.setShortcut(QtGui.QKeySequence("Ctrl+S"))
        a_img.triggered.connect(self.save_current_plot)
        m_file.addAction(a_img)
        m_file.addSeparator()
        a_set = QtGui.QAction(_("Impostazioni…"), self)
        a_set.setShortcut(QtGui.QKeySequence("Ctrl+,"))
        a_set.triggered.connect(self.edit_settings)
        m_file.addAction(a_set)
        m_file.addSeparator()
        a_quit = QtGui.QAction(_("Esci"), self)
        a_quit.setShortcut(QtGui.QKeySequence(QtGui.QKeySequence.StandardKey.Quit))
        a_quit.triggered.connect(self.close)
        m_file.addAction(a_quit)

        m_an = mb.addMenu(_("&Analisi"))
        a_prof = QtGui.QAction(_("Profilo di valutazione…"), self)
        a_prof.triggered.connect(self.edit_profile)
        m_an.addAction(a_prof)
        a_px4 = QtGui.QAction(_("Usa il profilo PX4 standard"), self)
        a_px4.triggered.connect(self.use_px4_profile)
        m_an.addAction(a_px4)
        a_vespa = QtGui.QAction(_("Usa il profilo Vespa hover (scheda di taratura)"), self)
        a_vespa.triggered.connect(self.use_vespa_profile)
        m_an.addAction(a_vespa)
        m_an.addSeparator()
        a_cmp = QtGui.QAction(_("Aggiungi log di confronto…"), self)
        a_cmp.triggered.connect(self.add_comparison)
        m_an.addAction(a_cmp)
        a_clr = QtGui.QAction(_("Rimuovi log di confronto"), self)
        a_clr.triggered.connect(self.clear_comparisons)
        m_an.addAction(a_clr)

        m_view = mb.addMenu(_("&Visualizza"))
        m_units = m_view.addMenu(_("Unità degli angoli"))
        g_units = QtGui.QActionGroup(self)
        self._unit_actions = {}
        for key, text in ANGLE_CHOICES:
            a = QtGui.QAction(_(text), self)
            a.setCheckable(True)
            a.setChecked(CFG["angle_unit"] == key)
            a.triggered.connect(lambda _c=False, k=key: self.set_display("angle_unit", k))
            g_units.addAction(a)
            m_units.addAction(a)
            self._unit_actions[key] = a
        m_bg = m_view.addMenu(_("Sfondo dei grafici"))
        g_bg = QtGui.QActionGroup(self)
        self._bg_actions = {}
        for key, text in BACKGROUND_CHOICES:
            a = QtGui.QAction(_(text), self)
            a.setCheckable(True)
            a.setChecked(CFG["background"] == key)
            a.triggered.connect(lambda _c=False, k=key: self.set_display("background", k))
            g_bg.addAction(a)
            m_bg.addAction(a)
            self._bg_actions[key] = a
        self._dark_action = QtGui.QAction(_("Tema scuro"), self)
        self._dark_action.setCheckable(True)
        self._dark_action.setChecked(theme.current() == "dark")
        self._dark_action.triggered.connect(lambda checked: self.set_display("theme", "dark" if checked else "light"))
        m_view.addAction(self._dark_action)
        m_view.addSeparator()
        a_side = QtGui.QAction(_("Nascondi/mostra pannello laterale"), self)
        a_side.setShortcut(QtGui.QKeySequence("Ctrl+B"))
        a_side.triggered.connect(self.toggle_side_panel)
        m_view.addAction(a_side)
        a_full = QtGui.QAction(_("Schermo intero"), self)
        a_full.setShortcut(QtGui.QKeySequence("F11"))
        a_full.triggered.connect(self.toggle_fullscreen)
        m_view.addAction(a_full)

        m_help = mb.addMenu(_("A&iuto"))
        a_help = QtGui.QAction(_("Guida rapida"), self)
        a_help.setShortcut(QtGui.QKeySequence("F1"))
        a_help.triggered.connect(lambda: self._message(_("Guida"), help_html()))
        m_help.addAction(a_help)
        a_about = QtGui.QAction(_("Informazioni"), self)
        a_about.triggered.connect(self.show_about)
        m_help.addAction(a_about)

        tb = self.addToolBar(_("Principale"))
        tb.setObjectName("MainBar")
        tb.setMovable(False)
        tb.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextOnly)
        for a in (a_open, a_pdf, a_rep, a_prof, a_set):
            tb.addAction(a)
        # loghi a destra nella barra
        spacer = QtWidgets.QWidget()
        spacer.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Preferred)
        tb.addWidget(spacer)
        for name, height, tip in (("logo_team.png", 30, N_("Team Zefiro — Meccanica del volo")),
                                  ("logo_polito.png", 30, "Politecnico di Torino")):
            path = RESOURCES / name
            if path.exists():
                lab = QtWidgets.QLabel()
                lab.setPixmap(QtGui.QPixmap(str(path)).scaledToHeight(height, Qt.TransformationMode.SmoothTransformation))
                lab.setToolTip(_(tip))
                lab.setContentsMargins(6, 0, 6, 0)
                if name == "logo_polito.png":
                    # sulla barra blu il logo del Politecnico (blu scuro) va su un fondo chiaro per restare leggibile
                    lab.setStyleSheet("background:#ffffff;border-radius:4px;padding:2px 6px;")
                tb.addWidget(lab)

    def show_about(self):
        box = QtWidgets.QMessageBox(self)
        box.setWindowTitle(_("Informazioni"))
        team = RESOURCES / "logo_team.png"
        if team.exists():
            box.setIconPixmap(QtGui.QPixmap(str(team)).scaledToHeight(72, Qt.TransformationMode.SmoothTransformation))
        polito = RESOURCES / "logo_polito.png"
        logo = f"<p><img src='{polito.as_uri()}' height='64'></p>" if polito.exists() else ""
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText(f"<h3>{APP_NAME} {__version__}</h3>"
                    f"<p>{_('Analisi dei log PX4 (.ulg) e valutazione oggettiva dei controllori.')}</p>"
                    f"<p>{_('Team Zefiro — reparto di Meccanica del volo')}<br>Politecnico di Torino</p>"
                    f"{logo}<p style='color:#868e96'>"
                    f"{_('Lettore ULog interno, grafici matplotlib, interfaccia PySide6.')}</p>")
        box.exec()

    def _message(self, title, text):
        box = QtWidgets.QMessageBox(self)
        box.setWindowTitle(title)
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText(text)
        box.exec()

    def _welcome(self):
        msg = _("Apri un file .ulg (menu File o trascinalo nella finestra)")
        for tab in self.time_tabs:
            tab.panel.clear_message(msg)
        self.t_overview.panel.clear_message(msg)

    # -- profilo e impostazioni
    def _load_profile(self):
        raw = self.settings.value("profilo")
        if raw:
            try:
                return scoring.profile_from_dict(json.loads(str(raw)))
            except Exception:  # noqa: BLE001 - profilo salvato illeggibile: si torna al predefinito
                pass
        return scoring.default_profile()

    def edit_profile(self):
        dlg = ProfileDialog(self.profile, self)
        if dlg.exec():
            self.set_profile(dlg.profile)

    def set_profile(self, profile):
        """Profilo di valutazione dell'Analisi PID (PX4 standard, Vespa hover o personalizzato)."""
        self.profile = profile
        self.settings.setValue("profilo", json.dumps(self.profile, ensure_ascii=False))
        self.statusBar().showMessage(_("Profilo «{nome}» attivo").format(nome=_(self.profile["nome"])), 5000)
        self.t_pid.show_profile()
        if self.log is not None:
            self.t_pid.run()

    def use_px4_profile(self):
        self.set_profile(scoring.default_profile())

    def use_vespa_profile(self):
        try:
            self.set_profile(scoring.vespa_hover_profile())
        except Exception as exc:  # noqa: BLE001
            QtWidgets.QMessageBox.warning(self, _("Profilo non valido"), str(exc))

    def _load_step_profile(self):
        raw = self.settings.value("profilo_gradini")
        if raw:
            try:
                prof = scoring.profile_from_dict(json.loads(str(raw)))
                if "gradini" in prof and steptest.definitions_ok(prof):
                    return prof
            except Exception:  # noqa: BLE001 - criteri salvati illeggibili: si torna a quelli forniti
                pass
        return steptest.step_profile(None)

    def set_step_profile(self, profile):
        """Criteri delle prove a gradino; None = quelli forniti con l'app (Vespa hover)."""
        if profile is None:
            self.settings.remove("profilo_gradini")
            self.step_profile = steptest.step_profile(None)
        else:
            self.step_profile = profile
            self.settings.setValue("profilo_gradini", json.dumps(profile, ensure_ascii=False))

    def edit_settings(self):
        dlg = SettingsDialog(self)
        if not dlg.exec():
            return
        new = dlg.values()
        old = dict(CFG)
        config.update(new)
        save_config(self.settings)
        if new["theme"] != old.get("theme"):
            app = QtWidgets.QApplication.instance()
            if app is not None:
                apply_theme(app, new["theme"])
            self._dark_action.setChecked(theme.current() == "dark")
            if not self.t_pid.results:
                self.t_pid._overall_idle()
        if new["hidden_tabs"] != old.get("hidden_tabs"):
            self._rebuild_tabs()
        for key, a in self._unit_actions.items():
            a.setChecked(CFG["angle_unit"] == key)
        for key, a in self._bg_actions.items():
            a.setChecked(CFG["background"] == key)
        visual = ("theme", "angle_unit", "speed_unit", "alt_unit", "background", "line_width", "font_scale",
                  "max_points", "legend_toggle")
        if any(new[k] != old.get(k) for k in visual):
            self._redraw_all()
        if new["language"] != old.get("language"):
            answer = QtWidgets.QMessageBox.question(
                self, APP_NAME, _("La nuova lingua si applica al riavvio. Riavviare ora?"))
            if answer == QtWidgets.QMessageBox.StandardButton.Yes:
                self.restart()

    def restart(self):
        args = [] if FROZEN else ["-m", "flight_analyzer"]
        if self.log is not None:
            args.append(str(self.log.path))
        QtCore.QProcess.startDetached(sys.executable, args)
        QtWidgets.QApplication.quit()

    # -- visualizzazione
    def set_display(self, key, value):
        """Cambia unità, sfondo o tema dal menu Visualizza e ridisegna i grafici."""
        if CFG.get(key) == value:
            return
        CFG[key] = value
        save_config(self.settings)
        if key == "theme":
            app = QtWidgets.QApplication.instance()
            if app is not None:
                apply_theme(app, value)
            if not self.t_pid.results:
                self.t_pid._overall_idle()
        self._redraw_all()

    def _redraw_all(self):
        if self.log is None:
            if not self.t_pid.results:
                self._welcome()
            return
        self._built = set()
        QtWidgets.QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            for tab in (self.tabs.currentWidget(), self.t_overview, self.t_params, self.t_msgs):
                self._refresh_tab(tab)
            if self.t_pid.results:
                self.t_pid._done(self.t_pid.results)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

    def toggle_side_panel(self):
        tab = self.tabs.currentWidget()
        if callable(type(tab).__dict__.get("toggle_side")):
            tab.toggle_side()

    def toggle_fullscreen(self):
        if self.isFullScreen():
            self.showNormal()
        else:
            self.showFullScreen()

    # -- lavori in background
    def run_task(self, fn, done, busy=None, on_fail=None):
        self._task_seq += 1
        tid = self._task_seq
        task = Task(tid, fn)
        self._tasks[tid] = (task, done, on_fail)
        self.progress.setVisible(True)
        self.statusBar().showMessage(busy or _("Elaborazione…"))
        task.signals.done.connect(self._task_done)
        task.signals.failed.connect(self._task_failed)
        self.pool.start(task)

    def _task_finish(self, tid):
        entry = self._tasks.pop(tid, None)
        if not self._tasks:
            self.progress.setVisible(False)
            self.statusBar().clearMessage()
        return entry

    @QtCore.Slot(int, object)
    def _task_done(self, tid, result):
        entry = self._task_finish(tid)
        if entry is not None:
            entry[1](result)

    @QtCore.Slot(int, str)
    def _task_failed(self, tid, tb):
        entry = self._task_finish(tid)
        if entry is not None and entry[2]:
            entry[2]()
        last = tb.strip().splitlines()[-1] if tb.strip() else _("errore sconosciuto")
        last = re.sub(r"^[\w.]*(Error|Exception): ", "", last)  # solo il messaggio, senza il nome della classe
        box = QtWidgets.QMessageBox(QtWidgets.QMessageBox.Icon.Critical, _("Errore"), last, parent=self)
        box.setDetailedText(tb)
        box.exec()

    # -- apertura
    def open_dialog(self):
        start = self.settings.value("ultima_cartella", "")
        path, _f = QtWidgets.QFileDialog.getOpenFileName(self, _("Apri log di volo"), str(start),
                                                         _("Log PX4 (*.ulg);;Tutti i file (*)"))
        if path:
            self.load(path)

    def load(self, path):
        self.settings.setValue("ultima_cartella", str(Path(path).parent))
        self.run_task(lambda: LogData(path), self._loaded, busy=_("Lettura di {nome}…").format(nome=Path(path).name))

    def _loaded(self, log):
        self.log = log
        self.xrange = None
        self._built = set()
        self.setWindowTitle(f"{APP_NAME} — {log.name}")
        self._add_recent(str(log.path))
        # fase da analizzare: quella scelta nelle impostazioni se presente nel log, altrimenti la più lunga
        mc, fw = log.phase_time("MC", log.airborne_known), log.phase_time("FW", log.airborne_known)
        pref = CFG.get("default_phase", "auto")
        if pref == "MC" and mc > 0:
            self.t_pid.phase.setCurrentIndex(0)
        elif pref == "FW" and fw > 0:
            self.t_pid.phase.setCurrentIndex(1)
        else:
            self.t_pid.phase.setCurrentIndex(0 if mc >= fw or fw == 0 else 1)
        QtWidgets.QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self._refresh_tab(self.tabs.currentWidget())
            for tab in (self.t_overview, self.t_params, self.t_msgs):
                self._refresh_tab(tab)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()
        if CFG.get("analyze_on_open", True):
            self.t_pid.run()
        if log.ulog.corrupt:
            self.statusBar().showMessage(_("Attenzione: il file contiene parti corrotte o troncate"), 8000)

    def _refresh_tab(self, tab):
        if self.log is None or tab is None or tab in self._built:
            return
        if tab is not self.t_pid and callable(type(tab).__dict__.get("refresh")):
            tab.refresh(self.log)
        self._built.add(tab)

    def _tab_changed(self, _i):
        tab = self.tabs.currentWidget()
        if self.log is None:
            return
        QtWidgets.QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self._refresh_tab(tab)
            panel = tab.__dict__.get("panel")
            if isinstance(panel, PlotPanel) and self.xrange is not None and panel.time_linked:
                panel.apply_xrange(*self.xrange)
        finally:
            QtWidgets.QApplication.restoreOverrideCursor()

    # -- asse dei tempi condiviso
    def on_xrange(self, lo, hi):
        self.xrange = (lo, hi)
        current = self.tabs.currentWidget()
        for tab in self.time_tabs:
            if tab in self._built and (tab is current or tab.isVisible()):
                tab.panel.apply_xrange(lo, hi)
        if self.t_pid.range.currentData() == "view":
            self.statusBar().showMessage(
                _("Intervallo per l'analisi PID: {a:.1f}–{b:.1f} s (premi Analizza)").format(a=lo, b=hi), 4000)

    def show_readout(self, text):
        self.readout.setText(text)

    # -- confronti
    def add_comparison(self):
        if self.log is None:
            return
        start = self.settings.value("ultima_cartella", "")
        paths, _f = QtWidgets.QFileDialog.getOpenFileNames(self, _("Log di confronto"), str(start),
                                                           _("Log PX4 (*.ulg)"))
        if not paths:
            return

        def done(logs):
            self.comparisons.extend(logs)
            self.t_pid.update_comparison_label()
            self.t_pid.run()

        self.run_task(lambda: [LogData(p) for p in paths], done, busy=_("Lettura dei log di confronto…"))

    def clear_comparisons(self):
        self.comparisons = []
        self.t_pid.update_comparison_label()
        if self.log is not None:
            self.t_pid.run()

    # -- esportazione
    def _export_job(self, path, fmt):
        log, prof, cmps = self.log, self.profile, list(self.comparisons)
        step_prof = self.step_profile
        done_steps = self.t_steps.result if self.t_steps._for_log is log and not self.t_steps.ignore_mode.isChecked() \
            else None

        def job():
            results = report.run_all(log, prof)
            comparisons = {}
            for other in cmps:
                for r in report.run_all(other, prof):
                    comparisons.setdefault(r.loop_key, []).append((other.name, r))
            steps = done_steps if done_steps is not None else steptest.detect(log, step_prof)
            report.export(log, results, path, prof, comparisons, fmt, steps)
            return str(path)

        return job

    def _offer_open(self, p):
        answer = QtWidgets.QMessageBox.question(self, _("Report pronto"),
                                                _("Report salvato in:\n{p}\n\nAprirlo ora?").format(p=p))
        if answer == QtWidgets.QMessageBox.StandardButton.Yes:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl.fromLocalFile(p))

    def export_pdf_quick(self):
        """Report PDF con un clic: accanto al log, con lo stesso nome (se la cartella non è scrivibile chiede dove)."""
        if self.log is None:
            return
        path = self.log.path.with_suffix(".report.pdf")
        if not os.access(path.parent, os.W_OK):
            chosen, _f = QtWidgets.QFileDialog.getSaveFileName(self, _("Esporta PDF"), path.name, _("Report PDF (*.pdf)"))
            if not chosen:
                return
            path = Path(chosen)
        self.run_task(self._export_job(path, "pdf"), self._offer_open, busy=_("Creazione del report PDF…"))

    def export_report(self):
        if self.log is None:
            return
        fmt = CFG.get("export_format", "pdf")
        filters = [_("Report PDF (*.pdf)"), _("Pagina HTML (*.html)")]
        if fmt == "html":
            filters.reverse()
        default = str(self.log.path.with_suffix(f".report.{fmt}"))
        path, chosen = QtWidgets.QFileDialog.getSaveFileName(self, _("Esporta report"), default, ";;".join(filters))
        if not path:
            return
        ext = Path(path).suffix.lower().lstrip(".")
        if ext not in ("pdf", "html", "htm"):
            ext = "pdf" if "pdf" in str(chosen).lower() else "html"
            path = str(Path(path).with_suffix("." + ext))
        self.run_task(self._export_job(path, "pdf" if ext == "pdf" else "html"), self._offer_open,
                      busy=_("Creazione del report…"))

    def export_json(self):
        if self.log is None:
            return
        path, _f = QtWidgets.QFileDialog.getSaveFileName(self, _("Esporta risultati"),
                                                         str(self.log.path.with_suffix(".json")), "JSON (*.json)")
        if not path:
            return
        log, prof = self.log, self.profile
        self.run_task(lambda: report.export_json(report.run_all(log, prof), path) or path,
                      lambda p: self.statusBar().showMessage(_("Risultati salvati in {p}").format(p=p), 6000),
                      busy=_("Esportazione…"))

    def save_current_plot(self):
        tab = self.tabs.currentWidget()
        panel = self.t_pid.current_panel() if tab is self.t_pid else tab.__dict__.get("panel")
        if isinstance(panel, PlotPanel):
            panel.save_image(self)

    # -- file recenti
    def _recent(self):
        raw = self.settings.value("recenti", [])
        if isinstance(raw, str):
            raw = [raw]
        return [p for p in (raw or []) if p]

    def _add_recent(self, path):
        items = [p for p in self._recent() if p != path]
        items.insert(0, path)
        self.settings.setValue("recenti", items[:8])
        self._fill_recent()

    def _fill_recent(self):
        self.m_recent.clear()
        items = self._recent()
        if not items:
            a = self.m_recent.addAction(_("(nessuno)"))
            a.setEnabled(False)
        for p in items:
            a = self.m_recent.addAction(p)
            a.triggered.connect(lambda _checked=False, p=p: self.load(p))

    # -- trascinamento
    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event):
        urls = [u.toLocalFile() for u in event.mimeData().urls()]
        ulgs = [u for u in urls if u.lower().endswith(".ulg")]
        if ulgs:
            self.load(ulgs[0])


# ------------------------------------------------------------------ avvio


def _choose_language_first_run(settings):
    """Al primo avvio, se l'installer non ha già scritto la lingua, la chiede (in entrambe le lingue)."""
    if settings.value(SETTING_KEYS["language"]):
        return
    dlg = QtWidgets.QDialog()
    dlg.setWindowTitle(APP_NAME)
    lay = QtWidgets.QVBoxLayout(dlg)
    lay.addWidget(QtWidgets.QLabel("Scegli la lingua dell'interfaccia\nChoose the interface language"))
    combo = QtWidgets.QComboBox()
    for code, name in i18n.SUPPORTED.items():
        combo.addItem(name, code)
    lay.addWidget(combo)
    ok = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.StandardButton.Ok)
    ok.accepted.connect(dlg.accept)
    lay.addWidget(ok)
    dlg.exec()
    CFG["language"] = combo.currentData() or "it"
    settings.setValue(SETTING_KEYS["language"], CFG["language"])


def _offer_shortcut(settings):
    """Propone la scorciatoia sul desktop (solo Windows; con l'installer la crea già l'installer)."""
    if sys.platform != "win32" or FROZEN:
        return
    if settings.value("desktop_shortcut_prompted", False, type=bool):
        return
    shortcut_path = desktop_shortcut_path()
    if shortcut_path is None:
        QtWidgets.QMessageBox.warning(None, _("Desktop non disponibile"),
                                      _("Non è stato possibile individuare la cartella Desktop."))
        return
    if shortcut_path.exists():
        settings.setValue("desktop_shortcut_prompted", True)
        return
    answer = QtWidgets.QMessageBox.question(
        None, APP_NAME, _("Vuoi creare una scorciatoia di Flight Analyzer sul desktop?"),
        QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No,
        QtWidgets.QMessageBox.StandardButton.Yes)
    if answer == QtWidgets.QMessageBox.StandardButton.Yes:
        try:
            _create_desktop_shortcut(shortcut_path)
        except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
            QtWidgets.QMessageBox.warning(
                None, _("Scorciatoia non creata"),
                _("Non è stato possibile creare la scorciatoia sul desktop.") + f"\n\n{exc}")
            return
    settings.setValue("desktop_shortcut_prompted", True)


def run(path=None):
    if sys.platform == "win32":
        # icona propria nella barra delle applicazioni (altrimenti Windows mostra quella di Python)
        try:
            import ctypes

            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("ZefiroMDV.FlightAnalyzer")
        except Exception:  # noqa: BLE001 - solo estetica
            pass
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORG)
    if (RESOURCES / "icona.png").exists():
        app.setWindowIcon(QtGui.QIcon(str(RESOURCES / "icona.png")))
    settings = _settings()
    load_config(settings)
    _choose_language_first_run(settings)
    i18n.set_language(CFG.get("language", "it"))
    apply_theme(app, CFG.get("theme", "light"))
    _offer_shortcut(settings)
    win = MainWindow()
    win.show()
    if path:
        QtCore.QTimer.singleShot(0, lambda: win.load(path))
    return app.exec()
