"""Costruzione dei grafici (matplotlib, indipendente dalla finestra).

Ogni funzione ``build_*`` riempie una Figure già creata. ``TimeFigure`` gestisce
i grafici temporali impilati: asse x condiviso, decimazione min/max che si
aggiorna con lo zoom, sfondo con fasi VTOL e modi di volo, reticolo con lettura
dei valori e metodi di navigazione (zoom, spostamento) usati dall'interfaccia.

I testi passano per _() (italiano/inglese), i colori per theme, le unità per
config.CFG.
"""

from __future__ import annotations

import numpy as np
from matplotlib.figure import Figure
from matplotlib.legend import Legend
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Patch

from . import config, dsp, loopid, theme
from .config import CFG, DEG, alt_scale, angle_scale, speed_scale
from .flags import SEVERITY_LABELS, raised_flags
from .i18n import N_, _, language
from .logdata import NAV_STATES, PHASE_LABELS, LogData

DISPLAY = CFG  # compatibilità con il codice precedente

PALETTE = {"setpoint": "#e8590c", "measured": "#1c7ed6", "truth": "#2b8a3e", "extra": "#7048e8", "muted": "#868e96"}
SERIES_COLORS = ["#1c7ed6", "#e8590c", "#2b8a3e", "#7048e8", "#f08c00", "#0c8599", "#c2255c", "#5c940d",
                 "#364fc7", "#a61e4d", "#087f5b", "#862e9c"]
MODE_COLORS = {
    0: "#fff3bf", 1: "#d3f9d8", 2: "#d0ebff", 3: "#e5dbff", 4: "#ffe3e3", 5: "#ffd8a8", 6: "#c5f6fa",
    8: "#e9fac8", 10: "#ffc9c9", 12: "#f1f3f5", 13: "#ff8787", 14: "#d0bfff", 15: "#fff9db", 17: "#c3fae8",
    18: "#ffdeeb", 19: "#e7f5ff", 20: "#ffe8cc", 21: "#f3d9fa", 22: "#c3fae8",
}
PHASE_COLORS = {"MC": "#4dabf7", "FW": "#69db7c", "TRANS": "#ffa94d", "ALTRO": "#ced4da"}
MODE_STRIP_COLORS = {
    0: "#ffe066", 1: "#8ce99a", 2: "#74c0fc", 3: "#b197fc", 4: "#ffa8a8", 5: "#ffc078", 6: "#66d9e8",
    8: "#c0eb75", 10: "#ff8787", 12: "#ced4da", 13: "#fa5252", 14: "#9775fa", 15: "#ffd43b", 17: "#63e6be",
    18: "#faa2c1", 19: "#a5d8ff", 20: "#ffc078", 21: "#e599f7", 22: "#63e6be",
}
SEVERITY_COLORS = {3: "#e03131", 2: "#f08c00", 1: "#868e96"}
AXIS_NAMES = (N_("Rollio"), N_("Beccheggio"), N_("Imbardata"))


def angle_unit_label(rate=False):
    _k, u = angle_scale()
    return f"[{u}/s]" if rate else f"[{u}]"


# ------------------------------------------------------------- legenda cliccabile


def enable_legend_toggle(fig):
    """Rende cliccabili le voci di legenda: un clic nasconde/mostra la curva corrispondente."""
    mapping = {}
    if CFG.get("legend_toggle", True):
        for leg in fig.findobj(Legend):
            ax = leg.axes
            if ax is None:
                continue
            artists = {}
            for a in list(ax.lines) + list(ax.collections) + list(ax.patches):
                lab = a.get_label()
                if lab and not lab.startswith("_"):
                    artists.setdefault(lab, []).append(a)
            handles = getattr(leg, "legend_handles", None) or getattr(leg, "legendHandles", [])
            for h, txt in zip(handles, leg.get_texts()):
                origs = artists.get(txt.get_text())
                if not origs:
                    continue
                for a in (h, txt):
                    if a is None:
                        continue
                    a.set_picker(True)
                    mapping[a] = (origs, h, txt)
    fig._fa_legend_map = mapping


def toggle_from_pick(fig, artist):
    """Gestisce il clic su una voce di legenda; restituisce True se ha cambiato qualcosa."""
    entry = getattr(fig, "_fa_legend_map", {}).get(artist)
    if entry is None:
        return False
    origs, h, txt = entry
    visible = not origs[0].get_visible()
    for o in origs:
        o.set_visible(visible)
    if h is not None:
        h.set_alpha(1.0 if visible else 0.2)
    txt.set_alpha(1.0 if visible else 0.35)
    return True


# ------------------------------------------------------------------- stile


def _layout(fig):
    """tight_layout solo se la figura non ha già un motore di impaginazione (GUI: constrained)."""
    if fig.get_layout_engine() is None:
        fig.tight_layout()


def style_axes(ax):
    ax.grid(True, color=theme.tok("grid"), linewidth=0.6)
    ax.tick_params(labelsize=config.font(8))
    ax.set_facecolor(theme.tok("ax_bg"))
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)


def _title(ax, text):
    ax.set_title(text, fontsize=config.font(9), loc="left", fontweight="bold", color=theme.tok("text"))


def _no_data(fig, text):
    fig.clear()
    ax = fig.add_subplot(111)
    ax.text(0.5, 0.5, text, ha="center", va="center", fontsize=config.font(11), color=theme.tok("text_muted"),
            wrap=True, transform=ax.transAxes)
    ax.set_axis_off()
    return None


# ------------------------------------------------------------------- TimeFigure


class TimeFigure:
    """Grafici temporali impilati con asse dei tempi condiviso."""

    def __init__(self, fig: Figure, nrows: int, log: LogData | None = None, height_ratios=None):
        self.fig = fig
        fig.clear()
        self.axes = list(np.atleast_1d(fig.subplots(nrows, 1, sharex=True, squeeze=False,
                                                     gridspec_kw={"height_ratios": height_ratios} if height_ratios else None
                                                     ).flatten()))
        self.log = log
        self._lines = []  # (line, t, y)
        self._cursor = []
        self._busy = False
        self._context = []
        self._strip = False
        self.max_points = int(CFG.get("max_points", 2500) or 2500)
        for ax in self.axes:
            style_axes(ax)
        self.axes[-1].set_xlabel(_("Tempo dall'inizio del log [s]"), fontsize=config.font(8))
        self.axes[0].callbacks.connect("xlim_changed", self._on_xlim)

    def plot(self, ax_index, t, y, label=None, color=None, lw=1.0, ls="-", alpha=1.0, step=False):
        if t is None or y is None or len(t) == 0:
            return None
        ax = self.axes[ax_index]
        t = np.asarray(t, float)
        y = np.asarray(y, float)
        td, yd = dsp.minmax_decimate(t, y, self.max_points)
        kw = {"drawstyle": "steps-post"} if step else {}
        (line,) = ax.plot(td, yd, label=label, color=color, lw=config.lw(lw), ls=ls, alpha=alpha, **kw)
        self._lines.append((line, t, y))
        return line

    def plot_series(self, ax_index, series, scale=1.0, **kw):
        if series is None:
            return None
        return self.plot(ax_index, series.t, series.y * scale, **kw)

    def set_ylabel(self, ax_index, text):
        self.axes[ax_index].set_ylabel(text, fontsize=config.font(8))

    def title(self, ax_index, text):
        _title(self.axes[ax_index], text)

    def has_data(self, ax_index=None):
        axes = self.axes if ax_index is None else [self.axes[ax_index]]
        return any(line.axes in axes for line, _t, _y in self._lines)

    def legends(self):
        # sotto la striscia dei modi, se c'è, per non coprirne i nomi
        kw = {"bbox_to_anchor": (1.0, 0.92)} if self._strip else {}
        for ax in self.axes:
            if ax.get_legend_handles_labels()[0]:
                ax.legend(loc="upper right", fontsize=config.font(7), framealpha=0.85, ncol=3, **kw)

    def shade_modes(self, use_phases=None):
        """Sfondo secondo CFG["background"]: fasi VTOL (colore) e modi di volo (striscia in alto)."""
        self._context = []
        if self.log is None:
            return
        mode = CFG.get("background", "both")
        if mode == "none":
            return
        phases_present = list(dict.fromkeys(p for _, _, p in self.log.phases))
        multi_phase = self.log.is_vtol or len(phases_present) > 1
        show_phases = multi_phase and mode in ("both", "phases")
        show_modes = mode in ("both", "modes") or not multi_phase
        strip = show_phases and show_modes
        self._strip = strip
        pa, ma = theme.tok("phase_alpha"), theme.tok("mode_alpha")
        for ax in self.axes:
            if show_phases:
                for a, b, p in self.log.phases:
                    ax.axvspan(a, b, color=PHASE_COLORS.get(p, "#e9ecef"), alpha=pa, lw=0, zorder=0)
            if show_modes:
                for a, b, v in self.log.modes:
                    if strip:
                        ax.axvspan(a, b, ymin=0.93, ymax=1.0, color=MODE_STRIP_COLORS.get(v, "#ced4da"), lw=0,
                                   alpha=0.95, zorder=0.5)
                    else:
                        ax.axvspan(a, b, color=MODE_COLORS.get(v, "#f1f3f5"), alpha=ma, lw=0, zorder=0)
        if strip:
            total = max(self.log.duration, 1.0)
            for a, b, v in self.log.modes:
                if (b - a) / total > 0.05:
                    self.axes[0].text((a + b) / 2, 0.965, NAV_STATES.get(v, f"{_('modo')} {v}"),
                                      fontsize=config.font(6.5), ha="center", va="center",
                                      color="#1b2430", transform=self.axes[0].get_xaxis_transform(),
                                      clip_on=True, zorder=6)
        if show_phases:
            self._context += [Patch(color=PHASE_COLORS.get(p, "#e9ecef"), alpha=0.5, label=_(PHASE_LABELS.get(p, p)))
                              for p in phases_present]
        if show_modes and not strip:
            modes = list(dict.fromkeys(v for _, _, v in self.log.modes))
            if len(modes) <= 8:
                self._context += [Patch(color=MODE_COLORS.get(v, "#eee"), label=NAV_STATES.get(v, f"{_('Modo')} {v}"))
                                  for v in modes]

    def finish(self, xlim=None):
        self.legends()
        if self._context:
            ax0 = self.axes[0]
            first = ax0.get_legend()
            if first is not None:
                ax0.add_artist(first)
            ax0.legend(handles=self._context, loc="upper left", fontsize=config.font(7), framealpha=0.85,
                       ncol=len(self._context), bbox_to_anchor=(0.0, 0.92))
        if xlim is not None:
            self.axes[0].set_xlim(*xlim)
        elif self.log is not None:
            self.axes[0].set_xlim(0, max(1.0, self.log.duration))
        self.fig.align_ylabels(self.axes)
        _layout(self.fig)

    # -- decimazione dinamica
    def _on_xlim(self, ax):
        if self._busy:
            return
        lo, hi = ax.get_xlim()
        for line, t, y in self._lines:
            i0 = max(0, int(np.searchsorted(t, lo)) - 1)
            i1 = min(len(t), int(np.searchsorted(t, hi)) + 1)
            if i1 - i0 < 2:
                continue
            td, yd = dsp.minmax_decimate(t[i0:i1], y[i0:i1], self.max_points)
            line.set_data(td, yd)

    def autoscale_y(self, reset_user=False):
        """Riadatta l'asse y ai dati visibili (dopo uno zoom orizzontale).

        Gli assi con scala fissa (spettrogrammi, flag) non cambiano; quelli su cui l'utente ha fatto lo zoom
        verticale restano com'erano finché non si chiede «Adatta Y» (``reset_user=True``).
        """
        lo, hi = self.axes[0].get_xlim()
        for ax in self.axes:
            if reset_user:
                ax._fa_user_y = False
            if getattr(ax, "_fa_fixed_y", False) or getattr(ax, "_fa_user_y", False):
                continue
            vals = []
            for line, t, y in self._lines:
                if line.axes is ax and line.get_visible():
                    sel = (t >= lo) & (t <= hi)
                    if np.any(sel):
                        v = y[sel]
                        v = v[np.isfinite(v)]
                        if v.size:
                            vals.append((v.min(), v.max()))
            if vals:
                a = min(v[0] for v in vals)
                b = max(v[1] for v in vals)
                pad = 0.05 * (b - a) if b > a else 1.0
                top = b + pad
                if self._strip:  # spazio per la striscia dei modi
                    top = b + pad + 0.08 * (top - (a - pad))
                ax.set_ylim(a - pad, top)

    # -- navigazione
    def limits(self):
        lo, hi = 0.0, 1.0
        if self.log is not None:
            hi = max(1.0, self.log.duration)
        elif self._lines:
            lo = min(t[0] for _l, t, _y in self._lines)
            hi = max(t[-1] for _l, t, _y in self._lines)
        return lo, hi

    def set_xrange(self, lo, hi):
        full_lo, full_hi = self.limits()
        span = max(hi - lo, 0.05)
        span = min(span, (full_hi - full_lo) * 1.05 + 1.0)
        lo = max(full_lo - 0.02 * (full_hi - full_lo), lo)
        hi = lo + span
        if hi > full_hi + 0.02 * (full_hi - full_lo):
            hi = full_hi + 0.02 * (full_hi - full_lo)
            lo = hi - span
        self.axes[0].set_xlim(lo, hi)

    def zoom_x(self, factor, center=None):
        lo, hi = self.axes[0].get_xlim()
        c = (lo + hi) / 2 if center is None else center
        self.set_xrange(c - (c - lo) * factor, c + (hi - c) * factor)

    def pan_x(self, fraction):
        lo, hi = self.axes[0].get_xlim()
        d = (hi - lo) * fraction
        self.set_xrange(lo + d, hi + d)

    def full(self):
        lo, hi = self.limits()
        self.axes[0].set_xlim(lo, hi)

    # -- reticolo e lettura valori
    def readout(self, x):
        """Testo con i valori di tutte le curve al tempo x (per la barra di stato), raggruppati per grafico."""
        parts = [f"t = {x:.3f} s"]
        for i, ax in enumerate(self.axes):
            vals = []
            for line, t, y in self._lines:
                lab = line.get_label()
                if line.axes is not ax or not lab or lab.startswith("_") or not line.get_visible():
                    continue
                k = int(np.clip(np.searchsorted(t, x), 0, len(t) - 1))
                if abs(t[k] - x) > 1.0:
                    continue
                vals.append(f"{lab} {y[k]:.4g}")
            if vals:
                title = ax.get_title(loc="left").split("—")[-1].strip() or f"{_('grafico')} {i + 1}"
                parts.append(f"{title}: " + ", ".join(vals))
        if self.log is not None:
            for a, b, v in self.log.modes:
                if a <= x <= b:
                    parts.append(f"{_('modo')} {NAV_STATES.get(v, v)}")
                    break
            for a, b, p in self.log.phases:
                if a <= x <= b:
                    parts.append(_(PHASE_LABELS.get(p, p)))
                    break
        return "   |   ".join(parts)

    def set_cursor(self, x):
        if not self._cursor:
            self._cursor = [ax.axvline(x, color=theme.tok("ref_line"), lw=0.8, ls="--", zorder=5, animated=True)
                            for ax in self.axes]
        for c in self._cursor:
            c.set_xdata([x, x])
            c.set_visible(True)

    def draw_cursor(self):
        """Disegna solo il cursore (da usare con il blitting dopo restore_region)."""
        for ax, c in zip(self.axes, self._cursor):
            if c.get_visible():
                ax.draw_artist(c)

    def hide_cursor(self):
        for c in self._cursor:
            c.set_visible(False)


def flight_segments(log: LogData):
    """Tratti per il menu «Vai a»: fasi VTOL e modi di volo, (etichetta, inizio, fine)."""
    out = [(_("Tutto il log"), 0.0, max(1.0, log.duration))]
    for a, b in log.airborne:
        out.append((_("In volo") + f"  {a:.0f}–{b:.0f} s", a, b))
    multi = log.is_vtol or len({p for _a, _b, p in log.phases}) > 1
    if multi:
        for a, b, p in log.phases:
            if b - a >= 1.0:
                out.append((f"{_(PHASE_LABELS.get(p, p))}  {a:.0f}–{b:.0f} s", a, b))
    for a, b, v in log.modes:
        if b - a >= 1.0:
            out.append((f"{_('Modo')} {NAV_STATES.get(v, v)}  {a:.0f}–{b:.0f} s", a, b))
    return out


# ----------------------------------------------------------------- sorgenti dati


def _first(log, cands, use_sample=False):
    s, _n = log.first_series(cands, use_sample)
    return s


def _gt_euler(log):
    return log.attitude_euler("vehicle_attitude_groundtruth", "q") if log.has("vehicle_attitude_groundtruth") else None


def _nonzero(s, eps=1e-6):
    return s is not None and len(s) > 0 and np.any(np.isfinite(s.y)) and np.nanmax(np.abs(s.y)) > eps


def _is_sitl(log):
    hw = str(log.info.get("ver_hw", "")).upper()
    return "SITL" in hw


# ---------------------------------------------------------------- schede tempo


def build_attitude(fig, log: LogData):
    tf = TimeFigure(fig, 3, log)
    tf.shade_modes()
    k, _u = angle_scale()
    est = log.attitude_euler("vehicle_attitude", "q")
    sp = log.attitude_euler("vehicle_attitude_setpoint", "q_d")
    gt = _gt_euler(log)
    for i, name in enumerate(AXIS_NAMES):
        tf.title(i, f"{_('Assetto')} — {_(name)}")
        if sp is not None:
            tf.plot_series(i, sp[i], k, label=_("setpoint"), color=PALETTE["setpoint"], lw=0.9, step=True)
        else:
            s = log.series("vehicle_attitude_setpoint", ["roll_body", "pitch_body", "yaw_body"][i])
            tf.plot_series(i, s, k, label=_("setpoint"), color=PALETTE["setpoint"], lw=0.9)
        if est is not None:
            tf.plot_series(i, est[i], k, label=_("stimato"), color=PALETTE["measured"])
        if gt is not None:
            tf.plot_series(i, gt[i], k, label=_("ground truth"), color=PALETTE["truth"], lw=0.8, ls="--")
        tf.set_ylabel(i, angle_unit_label())
    tf.finish()
    return tf


def build_rates(fig, log: LogData):
    tf = TimeFigure(fig, 3, log)
    tf.shade_modes()
    k, _u = angle_scale()
    for i, (name, ax) in enumerate(zip(AXIS_NAMES, ("roll", "pitch", "yaw"))):
        tf.title(i, f"{_('Velocità angolare')} — {_(name)}")
        tf.plot_series(i, log.series("vehicle_rates_setpoint", ax), k, label=_("setpoint"), color=PALETTE["setpoint"],
                       lw=0.9, step=True)
        meas = _first(log, [("vehicle_angular_velocity", f"xyz[{i}]"),
                            ("vehicle_attitude", ["rollspeed", "pitchspeed", "yawspeed"][i])], use_sample=True)
        tf.plot_series(i, meas, k, label=_("misurata (filtrata)"), color=PALETTE["measured"])
        gt = _first(log, [("vehicle_angular_velocity_groundtruth", f"xyz[{i}]")])
        tf.plot_series(i, gt, k, label=_("ground truth"), color=PALETTE["truth"], lw=0.8, ls="--")
        tf.set_ylabel(i, angle_unit_label(rate=True))
    tf.finish()
    return tf


def build_position(fig, log: LogData):
    has_air = log.has("airspeed_validated")
    tf = TimeFigure(fig, 4 if has_air else 3, log)
    tf.shade_modes()
    ks, us = speed_scale()
    ka, ua = alt_scale()
    tf.title(0, _("Posizione locale (NED)"))
    tf.title(1, _("Velocità locale (NED)"))
    tf.title(2, _("Quota"))
    for i, (c, col) in enumerate(zip("xyz", SERIES_COLORS)):
        if c != "z":
            tf.plot_series(0, log.series("vehicle_local_position", c), ka, label=c, color=col)
            sp = _first(log, [("trajectory_setpoint", f"position[{i}]"), ("vehicle_local_position_setpoint", c)])
            tf.plot_series(0, sp, ka, label=f"{c} setpoint", color=col, lw=0.8, ls="--")
        v = log.series("vehicle_local_position", "v" + c)
        tf.plot_series(1, v, ks, label="v" + c, color=col)
        vsp = _first(log, [("trajectory_setpoint", f"velocity[{i}]"), ("vehicle_local_position_setpoint", "v" + c)])
        tf.plot_series(1, vsp, ks, label=f"v{c} setpoint", color=col, lw=0.8, ls="--")
    z = log.series("vehicle_local_position", "z")
    tf.plot_series(2, z, -ka, label=_("quota stimata (-z)"), color=PALETTE["measured"])
    zsp = _first(log, [("trajectory_setpoint", "position[2]"), ("vehicle_local_position_setpoint", "z")])
    tf.plot_series(2, zsp, -ka, label=_("setpoint"), color=PALETTE["setpoint"], lw=0.8, ls="--")
    gt = log.series("vehicle_local_position_groundtruth", "z")
    tf.plot_series(2, gt, -ka, label=_("ground truth"), color=PALETTE["truth"], lw=0.8, ls="--")
    tf.set_ylabel(0, f"[{ua}]")
    tf.set_ylabel(1, f"[{us}]")
    tf.set_ylabel(2, f"[{ua}]")
    if has_air:
        tf.title(3, _("Velocità all'aria"))
        tf.plot_series(3, log.series("airspeed_validated", "indicated_airspeed_m_s"), ks, label="IAS",
                       color=SERIES_COLORS[0])
        tf.plot_series(3, log.series("airspeed_validated", "true_airspeed_m_s"), ks, label="TAS", color=SERIES_COLORS[1])
        tf.plot_series(3, _first(log, [("tecs_status", "true_airspeed_sp"), ("tecs_status", "airspeed_sp")]), ks,
                       label=_("setpoint TECS"), color=PALETTE["setpoint"], lw=0.8, ls="--")
        tf.set_ylabel(3, f"[{us}]")
    tf.finish()
    return tf


# ------------------------------------------------------------ comandi e spinta


def _controls_instance(log, inst):
    """Coppia e spinta di un'istanza (allocazione dinamica) o di actuator_controls_N (log vecchi)."""
    torque = [log.series("vehicle_torque_setpoint", f"xyz[{k}]", inst) for k in range(3)]
    if any(_nonzero(s) for s in torque):
        thr = [log.series("vehicle_thrust_setpoint", f"xyz[{k}]", inst) for k in range(3)]
        return torque, thr, False
    old = [log.series(f"actuator_controls_{inst}", f"control[{k}]") for k in range(4)]
    if any(_nonzero(s) for s in old):
        return old[:3], [None, None, old[3]], True
    return None, None, False


def build_controls(fig, log: LogData):
    """Come «Actuator Controls» e «Actuator Controls 1» di Flight Review, più la spinta totale."""
    inst0 = _controls_instance(log, 0)
    inst1 = _controls_instance(log, 1)
    if inst0[0] is None and inst1[0] is None:
        return _no_data(fig, _("Il log non contiene coppia e spinta richieste (vehicle_torque_setpoint)."))
    rows = []
    if inst0[0] is not None:
        rows.append(0)
    if inst1[0] is not None:
        rows.append(1)
    rows.append("norm")
    tf = TimeFigure(fig, len(rows), log)
    tf.shade_modes()
    for i, row in enumerate(rows):
        if row == "norm":
            tf.title(i, _("Spinta totale richiesta (norma del vettore, 1 = spinta massima)"))
            tf.set_ylabel(i, "[0…1]")
            for inst, ls in ((0, "-"), (1, "--")):
                comps = [log.series("vehicle_thrust_setpoint", f"xyz[{k}]", inst) for k in range(3)]
                if all(c is not None for c in comps) and any(_nonzero(c) for c in comps):
                    n = min(len(c) for c in comps)
                    norm = np.sqrt(sum(c.y[:n] ** 2 for c in comps))
                    lab = _("spinta") + (" [1]" if inst else "")
                    tf.plot(i, comps[0].t[:n], norm, label=lab, color=SERIES_COLORS[3 if inst == 0 else 4], ls=ls)
            continue
        torque, thr, old = (inst0 if row == 0 else inst1)
        if row == 0:
            tf.title(i, _("Comandi — istanza multicottero [0]: coppia e spinta normalizzate (±1 = massimo)"))
        else:
            tf.title(i, _("Comandi — istanza ala fissa [1] (VTOL in ala fissa)"))
        tf.set_ylabel(i, "[−1…1]")
        for k, name in enumerate((N_("rollio"), N_("beccheggio"), N_("imbardata"))):
            tf.plot_series(i, torque[k], label=_(name), color=SERIES_COLORS[k], lw=0.8)
        if old:
            tf.plot_series(i, thr[2], label=_("spinta"), color=SERIES_COLORS[3], lw=0.9)
        else:
            if thr[2] is not None and _nonzero(thr[2]):
                tf.plot_series(i, thr[2], -1.0, label=_("spinta verso l'alto (−z)"), color=SERIES_COLORS[3], lw=0.9)
            if thr[0] is not None and _nonzero(thr[0]):
                tf.plot_series(i, thr[0], label=_("spinta in avanti (x)"), color=SERIES_COLORS[4], lw=0.9)
    tf.finish()
    return tf


# ------------------------------------------------------------------ potenza


def _esc(log, field, i):
    return log.series("esc_status", f"esc[{i}].{field}")


def _esc_count(log):
    s = log.series("esc_status", "esc_count")
    if s is None:
        return 0
    return int(np.nanmax(s.y)) if len(s) else 0


def build_power(fig, log: LogData):
    """Come «Power» di Flight Review (batteria) più potenza elettrica e potenza ai motori."""
    v = log.series("battery_status", "voltage_v") or log.series("battery_status", "voltage_filtered_v")
    a = log.series("battery_status", "current_a")
    n_esc = _esc_count(log)
    esc_power = [s for s in (_esc(log, "esc_power", i) for i in range(n_esc)) if _nonzero(s)]
    esc_vi = []
    for i in range(n_esc):
        ev, ec = _esc(log, "esc_voltage", i), _esc(log, "esc_current", i)
        if _nonzero(ev) and _nonzero(ec) and len(ev) == len(ec):
            esc_vi.append((i, ev.t, ev.y * ec.y))
    motors = [(k, s) for k, s in _channels(log, "actuator_motors", "control", 12)]
    if v is None and a is None and not esc_power and not motors:
        return _no_data(fig, _("Il log non contiene dati di potenza (battery_status, esc_status, actuator_motors)."))
    rows = []
    if v is not None or a is not None:
        rows += ["battery", "electric"]
    rows.append("motors")
    sysp = log.series("system_power", "voltage5v_v")
    if _nonzero(sysp, 1e-4):
        rows.append("rails")
    tf = TimeFigure(fig, len(rows), log)
    tf.shade_modes()
    sitl = _is_sitl(log)
    for i, row in enumerate(rows):
        if row == "battery":
            tf.title(i, _("Batteria (come «Power» di Flight Review)"))
            tf.plot_series(i, v, label=_("tensione [V]"), color=SERIES_COLORS[0])
            tf.plot_series(i, a, label=_("corrente [A]"), color=SERIES_COLORS[1])
            mah = log.series("battery_status", "discharged_mah")
            if _nonzero(mah):
                tf.plot_series(i, mah, 0.01, label=_("consumo [mAh/100]"), color=SERIES_COLORS[2])
            rem = log.series("battery_status", "remaining")
            if _nonzero(rem):
                tf.plot_series(i, rem, 10.0, label=_("carica residua [0 = vuota, 10 = piena]"), color=SERIES_COLORS[3])
            ocv = log.series("battery_status", "ocv_estimate")
            if _nonzero(ocv):
                tf.plot_series(i, ocv, label=_("stima tensione a vuoto [V]"), color=SERIES_COLORS[4], lw=0.8)
            tf.set_ylabel(i, _("valori misti"))
        elif row == "electric":
            title = _("Potenza elettrica = tensione × corrente [W]")
            if sitl and esc_vi:
                title += " — " + _("in SITL le correnti degli ESC sono simulate da PX4, non misurate")
            tf.title(i, title)
            if v is not None and a is not None:
                n = min(len(v), len(a))
                tf.plot(i, v.t[:n], v.y[:n] * np.maximum(a.y[:n], 0), label=_("batteria"), color=SERIES_COLORS[0])
            for k, t, p in esc_vi:
                tf.plot(i, t, p, label=f"ESC {k + 1}", color=SERIES_COLORS[(k + 1) % 12], lw=0.8)
            tf.set_ylabel(i, "[W]")
        elif row == "motors":
            if esc_power:
                tf.title(i, _("Potenza applicata dagli ESC [%] (esc_power)"))
                for k in range(n_esc):
                    s = _esc(log, "esc_power", k)
                    if _nonzero(s):
                        tf.plot_series(i, s, label=f"ESC {k + 1}", color=SERIES_COLORS[k % 12], lw=0.8)
            else:
                tf.title(i, _("Potenza ai motori: comando di ogni motore in % del massimo (actuator_motors)"))
                for k, s in motors:
                    tf.plot_series(i, s, 100.0, label=f"{_('Motore')} {k + 1}", color=SERIES_COLORS[k % 12], lw=0.8)
            tf.set_ylabel(i, "[%]")
        elif row == "rails":
            tf.title(i, _("Alimentazioni di bordo"))
            tf.plot_series(i, sysp, label="5 V", color=SERIES_COLORS[6])
            s33 = log.series("system_power", "sensors3v3[0]")
            if _nonzero(s33, 1e-4):
                tf.plot_series(i, s33, label="3.3 V", color=SERIES_COLORS[5])
            tf.set_ylabel(i, "[V]")
    tf.finish()
    return tf


# --------------------------------------------------------- uscite motori e servi


def _channels(log, topic, field, n, instance=0):
    out = []
    for k in range(n):
        s = log.series(topic, f"{field}[{k}]", instance)
        if s is not None and np.any(np.isfinite(s.y)) and np.nanmax(np.abs(np.nan_to_num(s.y))) > 0:
            out.append((k, s))
    return out


SURFACE_TYPES = {1: N_("alettone sx"), 2: N_("alettone dx"), 3: N_("equilibratore"), 4: N_("timone"),
                 5: N_("elevone sx"), 6: N_("elevone dx"), 7: N_("coda a V sx"), 8: N_("coda a V dx"),
                 9: N_("flap sx"), 10: N_("flap dx"), 11: N_("aerofreno"), 12: N_("personalizzata"),
                 13: N_("coda ad A sx"), 14: N_("coda ad A dx"), 15: N_("alettone canale unico"),
                 16: N_("ruotino"), 17: N_("spoiler sx"), 18: N_("spoiler dx")}


def servo_layout(log: LogData):
    """Nomi dei canali di actuator_servos dai parametri CA_SV_* (superfici prima, poi tilt, come in PX4)."""
    p = log.params
    n_cs = int(p.get("CA_SV_CS_COUNT", 0) or 0)
    n_tl = int(p.get("CA_SV_TL_COUNT", 0) or 0)
    names, tilts = {}, {}
    for i in range(n_cs):
        t = int(p.get(f"CA_SV_CS{i}_TYPE", 0) or 0)
        names[i] = _(SURFACE_TYPES[t]) if t in SURFACE_TYPES else f"{_('superficie')} {i}"
    for j in range(n_tl):
        k = n_cs + j
        names[k] = f"tilt {j}"
        lo, hi = p.get(f"CA_SV_TL{j}_MINA"), p.get(f"CA_SV_TL{j}_MAXA")
        if lo is not None and hi is not None and hi != lo:
            tilts[k] = (float(lo), float(hi))
    return names, tilts


def _outputs_instances(log):
    out = []
    names = {0: "Main", 1: "AUX", 2: "EXTRA"}
    for inst in log.instances("actuator_outputs"):
        chans = []
        for k in range(16):
            s = log.series("actuator_outputs", f"output[{k}]", inst)
            if s is not None and len(s) and not np.all(s.y == s.y[0]):
                chans.append((k, s))
        if chans:
            out.append((inst, names.get(inst, str(inst)), chans))
    return out


def build_outputs(fig, log: LogData):
    """Come «Motor Outputs», «Servo Outputs» e «Actuator Outputs» di Flight Review, più l'angolo dei tilt."""
    motors = _channels(log, "actuator_motors", "control", 12)
    servos = _channels(log, "actuator_servos", "control", 8)
    names, tilts = servo_layout(log)
    outs = _outputs_instances(log)
    rows = []
    if motors:
        rows.append(("motors", None))
    if servos:
        rows.append(("servos", None))
        if tilts:
            rows.append(("tilt", None))
    for o in outs:
        rows.append(("outputs", o))
    if not rows:
        return _no_data(fig, _("Il log non contiene uscite di motori o servi."))
    tf = TimeFigure(fig, len(rows), log)
    tf.shade_modes()
    for i, (row, extra) in enumerate(rows):
        if row == "motors":
            tf.title(i, _("Uscite motori (actuator_motors) — comando 0…1, 1 = spinta massima del motore"))
            tf.set_ylabel(i, "[0…1]")
            for k, s in motors:
                tf.plot_series(i, s, label=f"{_('Motore')} {k + 1}", color=SERIES_COLORS[k % 12], lw=0.8)
            for lim in (0.0, 1.0):
                tf.axes[i].axhline(lim, color="#c92a2a", lw=0.6, ls=":")
        elif row == "servos":
            tf.title(i, _("Uscite servi (actuator_servos) — comando −1…1, ±1 = fine corsa"))
            tf.set_ylabel(i, "[−1…1]")
            for k, s in servos:
                tf.plot_series(i, s, label=f"{_('Servo')} {k + 1} {names.get(k, '')}".strip(),
                               color=SERIES_COLORS[k % 12], lw=0.8)
        elif row == "tilt":
            tf.title(i, _("Angolo dei tilt — da CA_SV_TL*_MINA/MAXA, 0° = rotore verso l'alto"))
            tf.set_ylabel(i, "[°]")
            for k, (lo, hi) in tilts.items():
                s = log.series("actuator_servos", f"control[{k}]")
                if s is not None:
                    ang = lo + (np.clip(s.y, -1, 1) + 1.0) / 2.0 * (hi - lo)
                    tf.plot(i, s.t, ang, label=f"{_('Servo')} {k + 1} {names[k]}", color=SERIES_COLORS[k % 12], lw=0.9)
        elif row == "outputs":
            inst, name, chans = extra
            tf.title(i, _("Uscite ({name}) — valore inviato all'uscita (PWM in µs o valore del simulatore)").format(
                name=name))
            tf.set_ylabel(i, _("uscita"))
            for k, s in chans:
                tf.plot_series(i, s, label=f"{_('Uscita')} {k + 1}", color=SERIES_COLORS[k % 12], lw=0.8)
    tf.finish()
    return tf


# ------------------------------------------------------------------ giri motore


def build_rpm(fig, log: LogData):
    """Come «Motor RPM» di Flight Review (esc_status), più il topic rpm e le temperature degli ESC."""
    n_esc = _esc_count(log)
    rpm = [(i, _esc(log, "esc_rpm", i)) for i in range(n_esc)]
    rpm = [(i, s) for i, s in rpm if _nonzero(s, 0.001)]
    rpm_topic = [(inst, log.series("rpm", "rpm_estimate", inst)) for inst in log.instances("rpm")]
    rpm_topic = [(i, s) for i, s in rpm_topic if _nonzero(s)]
    temps = [(i, _esc(log, "esc_temperature", i)) for i in range(n_esc)]
    temps = [(i, s) for i, s in temps if _nonzero(s, 0.001)]
    if not rpm and not rpm_topic:
        return _no_data(fig, _("Il log non contiene giri motore (esc_status o rpm).\n"
                               "Servono ESC con telemetria (DShot, UAVCAN) o un sensore di giri."))
    rows = ["rpm"] + (["temp"] if temps else [])
    tf = TimeFigure(fig, len(rows), log)
    tf.shade_modes()
    title = _("Giri motore (esc_status)")
    if _is_sitl(log) and rpm:
        title += " — " + _("in SITL Gazebo Classic PX4 li calcola dal comando (comando × 6000), non sono misurati")
    tf.title(0, title)
    for i, s in rpm:
        tf.plot_series(0, s, label=f"ESC {i + 1}", color=SERIES_COLORS[i % 12], lw=0.8)
    for inst, s in rpm_topic:
        tf.plot_series(0, s, label=f"{_('sensore di giri')} [{inst}]", color=SERIES_COLORS[(8 + inst) % 12], lw=0.9,
                       ls="--")
    tf.set_ylabel(0, "[rpm]")
    if temps:
        tf.title(1, _("Temperatura degli ESC"))
        for i, s in temps:
            tf.plot_series(1, s, label=f"ESC {i + 1}", color=SERIES_COLORS[i % 12], lw=0.8)
        tf.set_ylabel(1, "[°C]")
    tf.finish()
    return tf


# ------------------------------------------------------------------ vibrazioni


def build_vibration(fig, log: LogData):
    tf = TimeFigure(fig, 3, log)
    tf.shade_modes()
    tf.title(0, _("Accelerazione grezza (sensor_combined)"))
    for k, lab in enumerate("xyz"):
        tf.plot_series(0, log.series("sensor_combined", f"accelerometer_m_s2[{k}]"), label=lab, color=SERIES_COLORS[k],
                       lw=0.6)
    tf.set_ylabel(0, "[m/s²]")
    tf.title(1, _("Metrica di vibrazione dell'accelerometro (verde < 0,5 g, arancio < 1 g, rosso oltre)"))
    ax = tf.axes[1]
    for lo, hi, col in ((0, 4.905, "#40c057"), (4.905, 9.81, "#fd7e14"), (9.81, 1e3, "#fa5252")):
        ax.axhspan(lo, hi, color=col, alpha=0.10, lw=0, zorder=0)
    for inst in log.instances("vehicle_imu_status"):
        tf.plot_series(1, log.series("vehicle_imu_status", "accel_vibration_metric", inst), label=f"accel [{inst}]",
                       color=SERIES_COLORS[inst % 12])
    tf.set_ylabel(1, "[m/s²]")
    tf.title(2, _("Metrica di vibrazione del giroscopio"))
    for inst in log.instances("vehicle_imu_status"):
        tf.plot_series(2, log.series("vehicle_imu_status", "gyro_vibration_metric", inst), label=f"gyro [{inst}]",
                       color=SERIES_COLORS[inst % 12])
    tf.set_ylabel(2, "[rad/s]")
    tf.finish()
    vals = [y for line, _t, y in tf._lines if line.axes is ax]
    top = max([float(np.nanmax(v)) for v in vals if len(v)] + [12.0])
    ax.set_ylim(0, top * 1.1)
    return tf


PSD_SIGNALS = {
    # chiave: (sorgenti candidate (topic, campo), titolo); si usa la prima presente nel log
    "accel": ([("sensor_combined", "accelerometer_m_s2[{k}]")], N_("Densità spettrale dell'accelerazione")),
    "gyro": ([("vehicle_angular_velocity", "xyz[{k}]"), ("sensor_combined", "gyro_rad[{k}]")],
             N_("Densità spettrale della velocità angolare")),
    # in PX4 recenti l'accelerazione angolare è in vehicle_angular_velocity.xyz_derivative (come in Flight Review)
    "angacc": ([("vehicle_angular_velocity", "xyz_derivative[{k}]"), ("vehicle_angular_acceleration", "xyz[{k}]")],
               N_("Densità spettrale dell'accelerazione angolare")),
}


def build_psd_spectrograms(fig, log: LogData):
    """Spettrogrammi come in Flight Review: somma delle PSD dei tre assi, finestra di Hann di 256 campioni."""
    rows = []
    for key, (sources, title) in PSD_SIGNALS.items():
        for topic, field in sources:
            comps = [log.series(topic, field.format(k=k)) for k in range(3)]
            if any(c is None or len(c) < 512 for c in comps):
                continue
            fs = dsp.median_rate(comps[0].t)
            if fs < 100:  # stessa soglia di Flight Review
                continue
            rows.append((key, title, comps, fs))
            break
    if not rows:
        return _no_data(fig, _("Spettrogrammi non disponibili: servono accelerometro o giroscopio registrati ad "
                               "almeno 100 Hz (SDLOG_PROFILE con alta frequenza)."))
    tf = TimeFigure(fig, len(rows), log)
    for i, (key, title, comps, fs) in enumerate(rows):
        n = min(len(c) for c in comps)
        t = comps[0].t[:n]
        grid = np.arange(t[0], t[-1], 1.0 / fs)
        total = None
        for c in comps:
            yy = np.interp(grid, c.t[:n], c.y[:n])
            sg = dsp.spectrogram(yy, fs, nperseg=256, overlap=0.5)
            if sg is None:
                total = None
                break
            tt, ff, S = sg
            total = S if total is None else total + S
        ax = tf.axes[i]
        if total is not None:
            img = ax.pcolormesh(tt + grid[0], ff, 10 * np.log10(total + 1e-20), shading="auto", cmap="viridis",
                                rasterized=True)
            cb = fig.colorbar(img, ax=ax, pad=0.01)
            cb.set_label("dB", fontsize=config.font(8))
            cb.ax.tick_params(labelsize=config.font(7))
            ax._fa_fixed_y = True
            ax.set_ylim(0, fs / 2)
        tf.title(i, f"{_(title)} — {_('somma dei tre assi')} ({fs:.0f} Hz)")
        tf.set_ylabel(i, "[Hz]")
    tf.finish()
    return tf


SPECTRUM_SIGNALS = {
    N_("Giroscopio (velocità angolare filtrata)"): [("vehicle_angular_velocity", "xyz[{k}]")],
    N_("Giroscopio grezzo (sensor_combined)"): [("sensor_combined", "gyro_rad[{k}]")],
    N_("Accelerometro (sensor_combined)"): [("sensor_combined", "accelerometer_m_s2[{k}]")],
    N_("Coppia richiesta (vehicle_torque_setpoint)"): [("vehicle_torque_setpoint", "xyz[{k}]")],
}
FILTER_MARKS = {"vehicle_angular_velocity": ["IMU_GYRO_CUTOFF", "IMU_GYRO_NF0_FRQ", "IMU_GYRO_NF1_FRQ"],
                "vehicle_torque_setpoint": ["IMU_DGYRO_CUTOFF", "IMU_GYRO_CUTOFF"],
                "sensor_combined": ["IMU_GYRO_CUTOFF"]}


def build_spectrum(fig, log: LogData, signal_name, intervals=None):
    """Densità spettrale (Welch) per asse, con le frequenze dei filtri PX4, e spettrogramma dell'asse z."""
    fig.clear()
    gs = fig.add_gridspec(2, 1, height_ratios=[1, 1.2])
    ax_psd = fig.add_subplot(gs[0])
    ax_sg = fig.add_subplot(gs[1])
    style_axes(ax_psd)
    cands = SPECTRUM_SIGNALS[signal_name]
    topic, field = cands[0]
    intervals = intervals if intervals is not None else (log.airborne or [(0, log.duration)])
    fs_used = None
    last = None
    for k, lab in enumerate("xyz"):
        s = log.series(topic, field.format(k=k))
        if s is None:
            continue
        fs = dsp.median_rate(s.t)
        if fs < 20:
            continue
        acc = dsp.SpectralAccumulator(1)
        nper = min(dsp.next_pow2(int(fs)), 2048)
        for a, b in intervals:
            sel = (s.t >= a) & (s.t <= b)
            if np.count_nonzero(sel) > nper:
                grid = np.arange(s.t[sel][0], s.t[sel][-1], 1 / fs)
                acc.add([np.interp(grid, s.t[sel], s.y[sel])], fs, nper)
        got = acc.get()
        if got is None:
            continue
        f, auto, _x, _y = got
        ax_psd.semilogy(f[1:], auto[0][1:], color=SERIES_COLORS[k], lw=config.lw(0.9), label=lab)
        fs_used = fs
        last = s
    _title(ax_psd, f"{_('Densità spettrale di potenza')} — {_(signal_name)} ({_('solo in volo')})")
    ax_psd.set_xlabel(_("Frequenza [Hz]"), fontsize=config.font(8))
    ax_psd.set_ylabel(_("PSD [unità²/Hz]"), fontsize=config.font(8))
    if fs_used is None:
        ax_psd.text(0.5, 0.5, _("Segnale non presente o registrato a frequenza troppo bassa"), ha="center",
                    va="center", transform=ax_psd.transAxes)
        ax_sg.set_axis_off()
        _layout(fig)
        return
    for j, pname in enumerate(FILTER_MARKS.get(topic, [])):
        fv = log.params.get(pname)
        if fv and 0 < float(fv) < fs_used / 2:
            ax_psd.axvline(float(fv), color=SERIES_COLORS[6 + j], lw=0.9, ls="--", label=f"{pname} = {float(fv):g} Hz")
    ax_psd.axvline(fs_used / 2, color=theme.tok("text_muted"), lw=0.7, ls=":")
    if ax_psd.get_legend_handles_labels()[0]:
        ax_psd.legend(fontsize=config.font(7))
    grid = np.arange(last.t[0], last.t[-1], 1 / fs_used)
    yy = np.interp(grid, last.t, last.y)
    nper = min(512, dsp.next_pow2(int(fs_used / 2)))
    sg = dsp.spectrogram(yy, fs_used, nperseg=nper, overlap=0.5)
    if sg is not None:
        tt, ff, S = sg
        img = ax_sg.pcolormesh(tt + grid[0], ff, 10 * np.log10(S + 1e-20), shading="auto", cmap="viridis",
                               rasterized=True)
        cb = fig.colorbar(img, ax=ax_sg, pad=0.01)
        cb.set_label("dB", fontsize=config.font(8))
        cb.ax.tick_params(labelsize=config.font(7))
    _title(ax_sg, _("Spettrogramma (asse z)"))
    ax_sg.set_xlabel(_("Tempo dall'inizio del log [s]"), fontsize=config.font(8))
    ax_sg.set_ylabel(_("Frequenza [Hz]"), fontsize=config.font(8))
    ax_sg.tick_params(labelsize=config.font(8))
    _layout(fig)


# ------------------------------------------------------------------ sistema


def build_system(fig, log: LogData):
    tf = TimeFigure(fig, 2, log)
    tf.shade_modes()
    tf.title(0, _("Carico CPU e RAM"))
    tf.plot_series(0, log.series("cpuload", "load"), 100.0, label="CPU", color=SERIES_COLORS[2])
    tf.plot_series(0, log.series("cpuload", "ram_usage"), 100.0, label="RAM", color=SERIES_COLORS[3])
    tf.set_ylabel(0, "[%]")
    tf.title(1, _("Comandi del pilota (manual_control_setpoint)"))
    for k, f in enumerate(("roll", "pitch", "yaw", "throttle")):
        tf.plot_series(1, _first(log, [("manual_control_setpoint", f), ("manual_control_setpoint", "xyzr"[k])]),
                       label=f, color=SERIES_COLORS[k], lw=0.8)
    tf.set_ylabel(1, "[−1…1]")
    tf.finish()
    return tf


# ------------------------------------------------------------------ flag


def build_flags(fig, log: LogData, flags=None, include_info=True):
    """Diagramma a barre dei flag attivi nel tempo, colorati per gravità."""
    flags = raised_flags(log, include_info) if flags is None else flags
    if not flags:
        return _no_data(fig, _("Nessun flag sollevato in questo volo.") if log.has("failsafe_flags") or
                        log.has("estimator_status_flags") else
                        _("Il log non contiene i topic dei flag (failsafe_flags, estimator_status_flags)."))
    tf = TimeFigure(fig, 1, log)
    tf.shade_modes()
    ax = tf.axes[0]
    n = len(flags)
    for row, f in enumerate(flags):
        y = n - 1 - row
        ax.broken_barh([(a, max(b - a, log.duration * 0.002)) for a, b in f.intervals], (y - 0.35, 0.7),
                       facecolors=SEVERITY_COLORS.get(f.severity, "#868e96"), alpha=0.9, zorder=3)
    ax.set_yticks(range(n))
    ax.set_yticklabels([f.label() for f in reversed(flags)], fontsize=config.font(7))
    ax.set_ylim(-0.7, n - 0.3 + (0.9 if tf._strip else 0.0))
    ax._fa_fixed_y = True
    ax.grid(True, axis="x")
    _title(ax, _("Flag sollevati nel tempo"))
    handles = [Patch(color=SEVERITY_COLORS[s], label=_(SEVERITY_LABELS[s])) for s in (3, 2, 1)
               if any(f.severity == s for f in flags)]
    tf.finish()
    ax.legend(handles=handles + tf._context, loc="lower right", fontsize=config.font(7), framealpha=0.85,
              ncol=len(handles) + len(tf._context))
    return tf


# ------------------------------------------------------------------ panoramica


def _shade_context(ax, log: LogData):
    """Stesso sfondo dei grafici temporali (fasi VTOL + striscia dei modi) per un asse singolo."""
    fake = TimeFigure.__new__(TimeFigure)
    fake.axes = [ax]
    fake.log = log
    fake._context = []
    fake._strip = False
    TimeFigure.shade_modes(fake)
    return fake._context


def build_overview(fig, log: LogData):
    """Traccia con profilo di missione, quota con fasi e modi, velocità."""
    fig.clear()
    ka, ua = alt_scale()
    ks, us = speed_scale()
    gs = fig.add_gridspec(2, 2, width_ratios=[1, 1.6], height_ratios=[1, 1])
    ax_tr = fig.add_subplot(gs[:, 0])
    ax_alt = fig.add_subplot(gs[0, 1])
    ax_sp = fig.add_subplot(gs[1, 1], sharex=ax_alt)
    for ax in (ax_tr, ax_alt, ax_sp):
        style_axes(ax)
    x = log.series("vehicle_local_position", "x")
    y = log.series("vehicle_local_position", "y")
    mission = log.mission()
    if x is not None and y is not None and len(x) == len(y):
        phases_seen = []
        for a, b, p in log.phases:
            sel = (x.t >= a) & (x.t <= b)
            if np.any(sel):
                ax_tr.plot(y.y[sel], x.y[sel], color=PHASE_COLORS.get(p, "#999"), lw=config.lw(1.6), zorder=3,
                           label=_(PHASE_LABELS.get(p, p)) if p not in phases_seen else "_")
                phases_seen.append(p)
        _draw_mission(ax_tr, mission)
        ax_tr.plot(y.y[0], x.y[0], "o", color="#2b8a3e", ms=7, label=_("inizio"), zorder=5)
        ax_tr.plot(y.y[-1], x.y[-1], "s", color="#c92a2a", ms=7, label=_("fine"), zorder=5)
        ax_tr.set_aspect("equal", adjustable="datalim")
        ax_tr.set_xlabel(_("Est [m]"), fontsize=config.font(8))
        ax_tr.set_ylabel(_("Nord [m]"), fontsize=config.font(8))
        ax_tr.legend(fontsize=config.font(7), loc="best", framealpha=0.85)
    else:
        ax_tr.text(0.5, 0.5, _("Posizione locale non registrata"), ha="center", va="center", transform=ax_tr.transAxes)
    _title(ax_tr, _("Traccia (vista dall'alto) e profilo di missione"))

    context = _shade_context(ax_alt, log)
    z = log.series("vehicle_local_position", "z")
    if z is not None:
        td, yd = dsp.minmax_decimate(z.t, -z.y * ka, 3000)
        ax_alt.plot(td, yd, color=PALETTE["measured"], lw=config.lw(1.1), label=_("quota (-z)"))
    sp = mission.get("setpoints")
    if sp is not None and sp["alt"] is not None:
        ax_alt.plot(sp["t"], sp["alt"] * ka, color=theme.tok("ref_line"), lw=0.9, ls="--", drawstyle="steps-post",
                    label=_("quota del waypoint attivo"))
    for it in mission["items"]:
        if np.isfinite(it["alt"]):
            ax_alt.plot(it["t"], it["alt"] * ka, "o", color=theme.tok("ref_line"), ms=3.5)
    _title(ax_alt, _("Quota, fasi VTOL (sfondo) e modi di volo (striscia in alto)"))
    ax_alt.set_ylabel(f"[{ua}]", fontsize=config.font(8))
    if ax_alt.get_legend_handles_labels()[0]:
        lines = ax_alt.legend(fontsize=config.font(7), loc="upper right", framealpha=0.85, bbox_to_anchor=(1.0, 0.92))
        if context:
            ax_alt.add_artist(lines)
    if context:
        ax_alt.legend(handles=context, fontsize=config.font(7), loc="upper left", framealpha=0.85, ncol=len(context),
                      bbox_to_anchor=(0.0, 0.92))

    _shade_context(ax_sp, log)
    vx = log.series("vehicle_local_position", "vx")
    vy = log.series("vehicle_local_position", "vy")
    ias = log.series("airspeed_validated", "indicated_airspeed_m_s")
    if vx is not None and vy is not None and len(vx) == len(vy):
        td, yd = dsp.minmax_decimate(vx.t, np.hypot(vx.y, vy.y) * ks, 3000)
        ax_sp.plot(td, yd, color=SERIES_COLORS[0], lw=config.lw(1.0), label=_("velocità al suolo"))
    if ias is not None:
        td, yd = dsp.minmax_decimate(ias.t, ias.y * ks, 3000)
        ax_sp.plot(td, yd, color=SERIES_COLORS[1], lw=config.lw(1.0), label=_("velocità all'aria (IAS)"))
    for a, b in log.airborne:
        ax_sp.axvline(a, color="#2b8a3e", lw=0.8, ls=":")
        ax_sp.axvline(b, color="#c92a2a", lw=0.8, ls=":")
    _title(ax_sp, _("Velocità"))
    ax_sp.set_ylabel(f"[{us}]", fontsize=config.font(8))
    ax_sp.set_xlabel(_("Tempo dall'inizio del log [s]"), fontsize=config.font(8))
    if ax_sp.get_legend_handles_labels()[0]:
        ax_sp.legend(fontsize=config.font(7), loc="upper right", framealpha=0.85, bbox_to_anchor=(1.0, 0.92))
    ax_alt.set_xlim(0, max(1.0, log.duration))
    _layout(fig)


MISSION_MARKERS = {22: "^", 84: "^", 21: "v", 85: "v", 20: "v", 3000: "D", 17: "o", 18: "o", 19: "o", 31: "o"}


def _draw_mission(ax, mission):
    """Percorso pianificato, waypoint numerati, cerchi di loiter e setpoint di posizione."""
    mark = theme.tok("track_mark")
    sp = mission.get("setpoints")
    if sp is not None and len(sp["north"]):
        ax.plot(sp["east"], sp["north"], ".", color="#868e96", ms=2.5, alpha=0.6, zorder=2,
                label=_("setpoint di posizione"))
    items = mission["items"]
    if not items:
        return
    e = [it["east"] for it in items]
    n = [it["north"] for it in items]
    ax.plot(e, n, color=mark, lw=1.0, ls="--", zorder=4, label=_("percorso pianificato"))
    labelled = set()
    kinds = {"^": N_("decollo"), "v": N_("atterraggio"), "D": N_("transizione")}
    for it in items:
        mk = MISSION_MARKERS.get(it["cmd"], "o")
        kind = kinds.get(mk, N_("waypoint"))
        ax.plot(it["east"], it["north"], mk, ms=7, mfc=theme.tok("surface"), mec=mark, mew=1.3, zorder=5,
                label=_(kind) if kind not in labelled else "_")
        labelled.add(kind)
        ax.annotate(str(it["seq"]), (it["east"], it["north"]), xytext=(5, 5), textcoords="offset points",
                    fontsize=config.font(7), color=theme.tok("text"), zorder=6)
        if it["cmd"] in (17, 18, 19, 31) and it["loiter_radius"] > 0:
            ax.add_patch(Circle((it["east"], it["north"]), it["loiter_radius"], fill=False, ec=mark,
                                lw=0.8, ls=":", zorder=4))


# --------------------------------------------------------------------- PID

COMPARE_STYLES = [("--", 0.95), (":", 0.95), ("-.", 0.95), ((0, (5, 1)), 0.9)]


def build_step_responses(fig, results, labels=None, show_band=True):
    """Risposte al gradino stimate per i tre assi; ``results`` = [AnalysisResult, ...] (il primo è il log attivo)."""
    fig.clear()
    axs = fig.subplots(1, 3, sharey=True)
    labels = labels or [r.log_name for r in results]
    main = results[0]
    for j, axis in enumerate(("roll", "pitch", "yaw")):
        ax = axs[j]
        style_axes(ax)
        ar = main.axes[axis]
        spec = ar.extras.get("spec") if ar.extras else None
        ax.axhline(1.0, color=theme.tok("ref_line"), lw=0.8)
        if spec is not None:  # profilo della scheda: fascia ±10% (assetto ±1°) del comando
            bandr = spec["band"] / spec["amp"] if spec["absolute_band"] else spec["band_pct"] / 100.0
            ax.axhspan(1 - bandr, 1 + bandr, color=theme.tok("band"), lw=0, zorder=0)
        else:
            ax.axhspan(0.95, 1.05, color=theme.tok("band"), lw=0, zorder=0)
        title = _(AXIS_NAMES[j])
        if ar.available and ar.est is not None:
            shift = 0.5 / ar.est.fs if spec is not None else 0.0
            t_ms = (ar.est.t + shift) * 1000
            if show_band:
                ax.fill_between(t_ms, ar.est.step_lo, ar.est.step_hi, color=PALETTE["measured"], alpha=0.18, lw=0,
                                label=_("incertezza (±2σ)"))
            ax.plot(t_ms, ar.est.step, color=PALETTE["measured"], lw=config.lw(1.8), label=labels[0])
            if spec is not None:
                lim = next((it.thresholds[1] for it in ar.card.items if it.key == "delay"), None)
                if lim is not None:
                    ax.plot([lim * 1000], [0.5], "|", color=PALETTE["setpoint"], ms=14, mew=2,
                            label=_("criterio del ritardo"))
                ax.axvline(spec["dur"] * 1000, color=theme.tok("text_muted"), lw=0.8, ls="--",
                           label=_("fine del gradino della scheda"))
            elif ar.target_rise:
                ax.axvline(ar.target_rise * 1000, color=PALETTE["setpoint"], lw=0.9, ls=":",
                           label=_("obiettivo t salita"))
            sc = ar.card.score
            title += f" — {round(sc)}/100 ({_(ar.card.grade).lower()})" if sc is not None else f" — {_('non valutabile')}"
        else:
            ax.text(0.5, 0.5, ar.reason or _("non disponibile"), ha="center", va="center", transform=ax.transAxes,
                    fontsize=config.font(8), wrap=True)
        for k, other in enumerate(results[1:]):
            oa = other.axes.get(axis)
            if oa is None or not oa.available or oa.est is None:
                continue
            ls, al = COMPARE_STYLES[k % len(COMPARE_STYLES)]
            ax.plot(oa.est.t * 1000, oa.est.step, color=SERIES_COLORS[(k + 1) % 12], lw=config.lw(1.4), ls=ls,
                    alpha=al, label=labels[k + 1])
        _title(ax, title)
        ax.set_xlabel(_("Tempo [ms]"), fontsize=config.font(8))
        if j == 0:
            ax.set_ylabel(_("Risposta al gradino unitario"), fontsize=config.font(8))
        if ax.get_legend_handles_labels()[0]:
            ax.legend(fontsize=config.font(7), loc="lower right")
    lo = min(0.0, *(ax.get_ylim()[0] for ax in axs))
    hi = max(1.6, *(ax.get_ylim()[1] for ax in axs))
    axs[0].set_ylim(max(lo, -0.6), min(hi, 2.5))  # una banda d'incertezza enorme non schiaccia le altre curve
    fig.suptitle(main.title, fontsize=config.font(10), fontweight="bold", x=0.01, ha="left", color=theme.tok("text"))
    _layout(fig)


T_EXPLANATION = N_(
    "Anello chiuso |T|: per ogni frequenza indica quanta parte di una variazione del setpoint arriva sulla misura. "
    "0 dB (|T| = 1) significa che l'asse segue il comando perfettamente; −3 dB segna la banda passante, cioè fino "
    "a che frequenza il drone segue i comandi; un picco sopra 0 dB indica poco smorzamento (sovraelongazione, "
    "oscillazioni). La fase dice con quanto ritardo segue: −90° alla frequenza f equivalgono a un ritardo di 1/(4f). "
    "Il guadagno d'anello L = C·P (terzo grafico) è invece l'anello aperto, da cui si ricavano margini e sensitività."
)


def build_frequency(fig, ar, others=None, labels=None):
    """Bode della risposta setpoint->misura e, se disponibile, sensitività e guadagno d'anello."""
    fig.clear()
    has_l = ar is not None and ar.margins is not None and ar.margins.f is not None
    axs = fig.subplots(1, 3 if has_l else 2)
    for ax in axs:
        style_axes(ax)
    if ar is None or not ar.available or ar.est is None:
        for ax in axs:
            ax.set_axis_off()
        axs[0].text(0.5, 0.5, _("Risposta in frequenza non disponibile"), ha="center", va="center",
                    transform=axs[0].transAxes)
        _layout(fig)
        return
    est = ar.est
    k0, k1 = loopid._valid_band(est)
    valid_end = est.f[min(len(est.f) - 1, max(k1 - 1, 0))] if k1 > k0 else 0.0
    f_show = max(1.6 * valid_end, min(10.0, est.f[-1]))
    vis = est.f <= f_show
    rel = est.rel_uncertainty()
    good = (rel <= 0.2) & vis
    mag = 20 * np.log10(np.maximum(np.abs(est.T), 1e-6))
    ph = np.degrees(np.unwrap(np.angle(est.T)))
    labels = labels or []
    main_mag = np.where(good, mag, np.nan)
    axs[0].semilogx(est.f[vis], main_mag[vis], color=PALETTE["measured"], lw=config.lw(1.6),
                    label=labels[0] if labels else _("stima"))
    bad = vis & ~good
    if np.any(bad):
        axs[0].semilogx(est.f[bad], mag[bad], ".", color=PALETTE["muted"], ms=3, label=_("stima incerta (>20%)"))
    axs[1].semilogx(est.f[vis], np.where(good, ph, np.nan)[vis], color=PALETTE["measured"], lw=config.lw(1.6))
    if np.any(bad):
        axs[1].semilogx(est.f[bad], ph[bad], ".", color=PALETTE["muted"], ms=3)
    for k, oa in enumerate(others or []):
        if oa is None or not oa.available or oa.est is None:
            continue
        ls, _al = COMPARE_STYLES[k % len(COMPARE_STYLES)]
        ov = oa.est.f <= f_show
        axs[0].semilogx(oa.est.f[ov], 20 * np.log10(np.maximum(np.abs(oa.est.T[ov]), 1e-6)),
                        color=SERIES_COLORS[(k + 1) % 12], ls=ls, lw=config.lw(1.2),
                        label=labels[k + 1] if len(labels) > k + 1 else f"{_('confronto')} {k + 1}")
        axs[1].semilogx(oa.est.f[ov], np.degrees(np.unwrap(np.angle(oa.est.T[ov]))),
                        color=SERIES_COLORS[(k + 1) % 12], ls=ls, lw=config.lw(1.2))
    axs[0].axhline(-3, color=PALETTE["setpoint"], lw=0.8, ls=":", label=_("−3 dB (banda passante)"))
    axs[0].axhline(0, color=theme.tok("ref_line"), lw=0.6)
    fm = ar.freq
    if fm is not None and fm.bandwidth:
        axs[0].axvline(fm.bandwidth, color=PALETTE["setpoint"], lw=0.8, ls=":")
    _title(axs[0], _("Anello chiuso |T| = misura / setpoint"))
    axs[0].set_ylabel("[dB]", fontsize=config.font(8))
    _title(axs[1], _("Fase di T (ritardo della risposta)"))
    axs[1].set_ylabel("[°]", fontsize=config.font(8))
    for ax in axs[:2]:
        ax.set_xlabel(_("Frequenza [Hz]"), fontsize=config.font(8))
    axs[0].relim()
    axs[0].autoscale_view()
    lo, hi = axs[0].get_ylim()
    axs[0].set_ylim(max(-30.0, lo), min(20.0, max(4.0, hi)))
    axs[0].legend(fontsize=config.font(7), loc="lower left")
    if has_l:
        m = ar.margins
        ax = axs[2]
        lmag = 20 * np.log10(np.abs(m.L))
        smag = -20 * np.log10(np.abs(1 + m.L))
        ax.semilogx(m.f, lmag, color=SERIES_COLORS[3], lw=config.lw(1.4), label=_("|L| guadagno d'anello"))
        ax.semilogx(m.f, smag, color=SERIES_COLORS[1], lw=config.lw(1.4), label=_("|S| sensitività"))
        ax.axhline(0, color=theme.tok("ref_line"), lw=0.6)
        ax.axhline(20 * np.log10(2.0), color="#e03131", lw=0.7, ls=":", label="Ms = 2 (6 dB)")
        if m.valid:
            ax.axvline(m.crossover_hz, color=SERIES_COLORS[3], lw=0.8, ls=":")
            txt = (f"PM {m.phase_margin_deg:.0f}°" + (f" ± {m.pm_sd:.0f}" if m.pm_sd else "")
                   + f" {_('a')} {m.crossover_hz:.1f} Hz")
            txt += f"\nMs {m.ms:.2f}" + (f" ± {m.ms_sd:.2f}" if m.ms_sd else "")
            if m.gain_margin_db is not None:
                txt += f"\nGM {m.gain_margin_db:.1f} dB"
            ax.text(0.03, 0.04, txt, transform=ax.transAxes, fontsize=config.font(8), va="bottom",
                    bbox={"boxstyle": "round", "fc": theme.tok("surface"), "ec": theme.tok("border")})
        else:
            ax.text(0.03, 0.04, _("Margini non validi:") + "\n" + m.reason, transform=ax.transAxes,
                    fontsize=config.font(7), va="bottom", wrap=True)
        _title(ax, _("Robustezza (L = C·P stimato)"))
        ax.set_xlabel(_("Frequenza [Hz]"), fontsize=config.font(8))
        ax.set_ylabel("[dB]", fontsize=config.font(8))
        ax.legend(fontsize=config.font(7), loc="upper right")
        ax.set_ylim(-30, 30)
    _layout(fig)


def build_analysis_timeline(fig, log: LogData, result, axis):
    """Setpoint e misura dell'asse con i tratti usati evidenziati (per scegliere l'intervallo)."""
    tf = TimeFigure(fig, 2, log, height_ratios=[2.2, 1])
    ar = result.axes[axis]
    for a, b, p in log.phases:
        for ax in tf.axes:
            ax.axvspan(a, b, color=PHASE_COLORS.get(p, "#eee"), alpha=theme.tok("phase_alpha") * 0.8, lw=0, zorder=0)
    for a, b in result.intervals:
        tf.axes[0].axvspan(a, b, color=theme.tok("accent"), alpha=0.25, lw=0, zorder=0)
    excluded = ar.extras.get("excluded", []) if ar.extras else []
    for a, b in excluded:  # 50 ms dopo ogni cambio di modo: fuori dalla stima
        for ax in tf.axes:
            ax.axvspan(a, b, color=EXCLUDED_COLOR, alpha=0.6, lw=0, zorder=0.5)
    scale, _u = angle_scale()
    unit = angle_unit_label(rate=result.loop == "rate")
    segs = ar.extras.get("segments", [])
    for seg in segs:
        tf.plot(0, seg["t"], seg["r"] * scale, color=PALETTE["setpoint"], lw=0.8)
        tf.plot(0, seg["t"], seg["y"] * scale, color=PALETTE["measured"], lw=0.8)
        if "u" in seg:
            tf.plot(1, seg["t"], seg["u"], color=SERIES_COLORS[3], lw=0.6)
    tf.axes[0].plot([], [], color=PALETTE["setpoint"], label=_("setpoint"))
    tf.axes[0].plot([], [], color=PALETTE["measured"], label=_("misura"))
    tf.axes[0].plot([], [], color=theme.tok("accent"), lw=6, alpha=0.6, label=_("tratti analizzati"))
    if excluded:
        tf.axes[0].plot([], [], color=EXCLUDED_COLOR, lw=6, alpha=0.6, label=_("escluso (50 ms dopo un cambio di modo)"))
    idx = ("roll", "pitch", "yaw").index(axis)
    tf.title(0, f"{_('Dati usati')} — {_(AXIS_NAMES[idx])}")
    tf.set_ylabel(0, unit)
    has_u = bool(segs) and "u" in segs[0]
    tf.title(1, _("Comando di coppia") if has_u else "")
    integ = ar.extras.get("integrator_series")
    if integ is not None and not has_u:
        tf.plot_series(1, integ, color=SERIES_COLORS[4], label=_("integratore"))
    tf.finish()
    return tf


# ----------------------------------------------------------------- esplorazione


def build_explorer(fig, log: LogData, selections):
    """selections: lista di (topic, istanza, campo). Un pannello per topic."""
    groups = {}
    for topic, inst, field in selections:
        groups.setdefault((topic, inst), []).append(field)
    if not groups:
        return _no_data(fig, _("Seleziona uno o più campi nell'elenco a sinistra"))
    tf = TimeFigure(fig, len(groups), log)
    tf.shade_modes()
    for i, ((topic, inst), fields) in enumerate(groups.items()):
        tf.title(i, topic + (f" [{inst}]" if inst else ""))
        for k, field in enumerate(fields):
            tf.plot_series(i, log.series(topic, field, inst), label=field, color=SERIES_COLORS[k % 12], lw=0.9)
    tf.finish()
    return tf


BUILDERS = {
    "attitude": build_attitude, "rates": build_rates, "position": build_position, "controls": build_controls,
    "power": build_power, "outputs": build_outputs, "rpm": build_rpm, "system": build_system,
}


# ----------------------------------------------------------------- prove a gradino

VALID_COLOR, REJECT_COLOR, EXCLUDED_COLOR = "#2b8a3e", "#c92a2a", "#e03131"


def _step_series(log: LogData, step):
    from . import steptest

    return steptest._cmd_series(log, step.kind, step.axis), steptest._resp_series(log, step.kind, step.axis)


def _shade_excluded(ax, windows, lo, hi, label=True):
    first = label
    for a, b in windows:
        if b < lo or a > hi:
            continue
        ax.axvspan(a, b, color=EXCLUDED_COLOR, alpha=0.18, lw=0, hatch="///", zorder=0.4,
                   label=_("escluso (50 ms dopo un cambio di modo)") if first else None)
        first = False


def build_step_detail(fig, log: LogData, res, step):
    """Un gradino: comando, risposta, fascia, punti del 50%, picco; sotto i motori con i limiti di saturazione."""
    from . import modes, scoring, steptest

    fig.clear()
    axs = fig.subplots(2, 1, sharex=True, gridspec_kw={"height_ratios": [2.3, 1]})
    for ax in axs:
        style_axes(ax)
    cmd, resp = _step_series(log, step)
    t0 = step.t_cmd50 if step.t_cmd50 is not None else step.t_start
    lo, hi = step.t_start - 0.3, max(step.sat_window[1], step.t_end + 0.5)
    unit = steptest.UNITS[step.kind]
    ax = axs[0]
    a_lvl = step.baseline + step.sign * step.amplitude
    spec = scoring.step_spec(steptest.step_profile(None), steptest.LOOP_OF[step.kind], step.axis)
    band = spec["band"] if spec["absolute_band"] else step.amplitude * spec["band_pct"] / 100.0
    ax.axhspan(a_lvl - band, a_lvl + band, xmin=0, xmax=1, color=theme.tok("band"), lw=0, zorder=0.2,
               label=_("fascia ±{b} {u}").format(b=_num(band, nd=1), u=unit))
    ax.axhline(a_lvl, color=theme.tok("ref_line"), lw=0.7, ls="--")
    if cmd is not None:
        c = cmd.slice(lo, hi)
        ax.step(c.t, c.y, where="post", color=PALETTE["setpoint"], lw=config.lw(1.4), label=_("comando"))
    if resp is not None:
        r = resp.slice(lo, hi)
        ax.plot(r.t, r.y, color=PALETTE["measured"], lw=config.lw(1.4), label=_("risposta"))
    rr = step.resp
    half = step.baseline + step.sign * 0.5 * step.amplitude
    ax.plot([t0], [half], "o", color=PALETTE["setpoint"], ms=6, zorder=5, label=_("comando al 50%"))
    if rr is not None and rr.t_resp50 is not None:
        ax.plot([rr.t_resp50], [half], "o", color=PALETTE["measured"], ms=6, zorder=5, label=_("risposta al 50%"))
        ax.annotate("", xy=(rr.t_resp50, half), xytext=(t0, half),
                    arrowprops={"arrowstyle": "<->", "color": theme.tok("text"), "lw": 0.8})
    if rr is not None and rr.t_peak is not None:
        pk = step.baseline + step.sign * rr.peak * step.amplitude
        ax.plot([rr.t_peak], [pk], "v" if step.sign > 0 else "^", color="#7048e8", ms=7, zorder=5, label=_("picco"))
    if rr is not None and rr.settling is not None:
        ax.axvline(t0 + rr.settling, color=VALID_COLOR, lw=0.9, ls=":", label=_("assestato"))
    ax.axvline(step.t_end, color=theme.tok("text_muted"), lw=0.8, ls="--", label=_("fine del gradino"))
    for c_t in modes.change_times(log):
        if lo <= c_t <= hi:
            ax.axvline(c_t, color=REJECT_COLOR, lw=0.9, ls="-.")
            ax.text(c_t, 0.98, " " + modes.mode_name_at(log, c_t + 1e-3), transform=ax.get_xaxis_transform(),
                    fontsize=config.font(7), color=REJECT_COLOR, va="top")
    for a in axs:
        _shade_excluded(a, res.excluded, lo, hi, label=a is ax)
    ax.set_ylabel(f"{_(steptest.KINDS[step.kind])} [{unit}]", fontsize=config.font(8))
    vals = []
    if rr is not None:
        if rr.delay is not None:
            vals.append(_("ritardo {v} s").format(v=_num(rr.delay, nd=3)))
        vals.append(_("sovraelong. {v}%").format(v=_num(rr.overshoot, nd=1)))
        vals.append(_("assestamento {v}").format(
            v=_("non assestato") if rr.settling is None else _num(rr.settling, nd=3) + " s"))
        if rr.end_error is not None:
            vals.append(_("errore {v} {u}").format(v=_num(rr.end_error, nd=1), u=steptest.error_unit(step.kind)))
        vals.append(_("rimbalzi {v}").format(v=rr.bounces))
    if step.saturation is not None:
        vals.append(_("saturazione {v}%").format(v=_num(step.saturation, nd=1)))
    ax.text(0.01, 0.03, " · ".join(vals), transform=ax.transAxes, fontsize=config.font(7.5), va="bottom",
            bbox={"boxstyle": "round", "fc": theme.tok("surface"), "ec": theme.tok("border"), "alpha": 0.9})
    status = _("VALIDO") if step.valid else _("SCARTATO") + ": " + "; ".join(step.reasons)
    _title(ax, f"#{step.n} {_(steptest.KINDS[step.kind])} — {_(scoring.AXIS_LABELS[step.axis]).lower()} "
               f"{step.sign_label} · {step.mode} · {_num(step.t_start, nd=2)} s · {status}")
    ax.title.set_color(VALID_COLOR if step.valid else REJECT_COLOR)
    ax.legend(fontsize=config.font(7), loc="best", ncol=2, framealpha=0.85)
    # motori
    ax = axs[1]
    outs = modes.actuator_outputs(log, "MC")
    for k, (name, s, kind) in enumerate(outs):
        m = s.slice(lo, hi)
        ax.plot(m.t, m.y, lw=config.lw(1.0), color=SERIES_COLORS[k % len(SERIES_COLORS)], label=name)
    ax.axhline(modes.SAT_LOW, color=REJECT_COLOR, lw=0.7, ls=":")
    ax.axhline(modes.SAT_HIGH, color=REJECT_COLOR, lw=0.7, ls=":")
    ax.axvspan(*step.sat_window, color=theme.tok("accent"), alpha=0.08, lw=0, zorder=0.1,
               label=_("finestra della saturazione"))
    ax.set_ylim(-0.05, 1.05)
    ax.set_ylabel(_("Motori [0–1]"), fontsize=config.font(8))
    ax.set_xlabel(_("Tempo dall'inizio del log [s]"), fontsize=config.font(8))
    txt = step.sat_text()
    _title(ax, _("Uscite dei motori") + (f" — {txt}" if txt else ""))
    ax.legend(fontsize=config.font(7), loc="upper right", ncol=6, framealpha=0.85)
    axs[0].set_xlim(lo, hi)
    _layout(fig)


def build_step_overview(fig, log: LogData, res, kind="rate", axis="roll"):
    """Tutto il volo per un asse: comando, risposta, gradini trovati (verde validi, rosso scartati), zone escluse."""
    from . import scoring, steptest

    tf = TimeFigure(fig, 1, log)
    cmd, resp = steptest._cmd_series(log, kind, axis), steptest._resp_series(log, kind, axis)
    unit = steptest.UNITS[kind]
    tf.plot_series(0, cmd, color=PALETTE["setpoint"], label=_("comando"), lw=0.9)
    tf.plot_series(0, resp, color=PALETTE["measured"], label=_("risposta"), lw=0.9)
    tf.shade_modes()
    ax = tf.axes[0]
    for s in res.steps:
        if s.kind != kind or s.axis != axis:
            continue
        col = VALID_COLOR if s.valid else REJECT_COLOR
        ax.axvspan(s.t_start, s.t_end, color=col, alpha=0.25, lw=0, zorder=0.6)
        ax.text(s.t_start, 0.04, f"#{s.n}", transform=ax.get_xaxis_transform(), fontsize=config.font(7), color=col)
    for a, b in res.excluded:
        ax.axvspan(a, b, color=EXCLUDED_COLOR, alpha=0.5, lw=0, zorder=0.7)
    ax.plot([], [], color=VALID_COLOR, lw=6, alpha=0.4, label=_("gradino valido"))
    ax.plot([], [], color=REJECT_COLOR, lw=6, alpha=0.4, label=_("gradino scartato"))
    tf.title(0, f"{_(steptest.KINDS[kind])} — {_(scoring.AXIS_LABELS[axis]).lower()}")
    tf.set_ylabel(0, f"[{unit}]")
    tf.finish()
    return tf


def build_step_summary(fig, log: LogData, res, header=True, table=True):
    """PNG riassuntivo: gradini validi sovrapposti per asse e verso, tabella con mediana, caso peggiore ed esito.

    Con ``header=False`` e ``table=False`` restano solo i grafici (per il report, che ha già le tabelle).
    """
    from . import scoring, steptest

    fig.clear()
    keys = list(res.summary)
    n = max(1, len(keys))
    n_rows = sum(len(sm.directions) for sm in res.summary.values()) + 2
    ratios = ([0.5] if header else []) + [2.2] + ([0.16 * n_rows + 0.25] if table else [])
    gs = fig.add_gridspec(len(ratios), n, height_ratios=ratios, hspace=0.38, wspace=0.22,
                          left=0.05, right=0.98, top=0.97, bottom=0.03 if table else 0.12)
    row_plot = 1 if header else 0
    if header:
        head = fig.add_subplot(gs[0, :])
        head.set_axis_off()
        params = "   ".join(f"{k} = {_num(v, nd=4).rstrip('0').rstrip(',.')}" if isinstance(v, float) else f"{k} = {v}"
                            for k, v in res.params)
        lines = [f"{_('Prove a gradino')} — {res.log_name} · Flight Analyzer {res.version} · {_('criteri')}: "
                 f"{res.profile_name}", params]
        lines += [f"⚠ {w}" for w in res.warnings[:3]]
        labels = {k: _(lab) for k, lab, _u, _l in steptest.HOLD_ITEMS}
        for h in res.holds[:2]:
            bad = [labels.get(k, k).lower() for k, ok in h.passed.items() if ok is False]
            lines.append(f"{_('Tenuta')} {h.mode} {_num(h.t0, nd=1)}–{_num(h.t1, nd=1)} s: "
                         + (_("entro i criteri") if h.ok else _("fuori criterio") + f" ({'; '.join(bad)})"))
        head.text(0.0, 1.0, "\n".join(lines), va="top", ha="left", fontsize=config.font(8), wrap=True,
                  color=theme.tok("text"), transform=head.transAxes)
    if not keys:
        if res.holds:  # senza gradini resta la tenuta: assetto nei tratti fermi
            holds = res.holds[:2]
            sub = gs[row_plot:, :].subgridspec(1, len(holds), wspace=0.15)
            for j, h in enumerate(holds):
                _draw_hold(fig.add_subplot(sub[0, j]), log, h)
            return
        ax = fig.add_subplot(gs[row_plot:, :])
        ax.set_axis_off()
        ax.text(0.5, 0.5, _("Nessun gradino trovato nel log."), ha="center", va="center", fontsize=config.font(12))
        return
    for j, key in enumerate(keys):
        kind, axis = key
        ax = fig.add_subplot(gs[row_plot, j])
        style_axes(ax)
        for s in res.steps:
            if s.kind != kind or s.axis != axis or not s.valid:
                continue
            _cmd, resp = _step_series(log, s)
            if resp is None:
                continue
            r = resp.slice(s.t_start - 0.2, s.t_end + 0.3)
            ax.plot(r.t - s.t_cmd50, s.sign * (r.y - s.baseline) / s.amplitude,
                    color=PALETTE["measured"] if s.sign > 0 else SERIES_COLORS[1], lw=config.lw(1.0), alpha=0.85)
        spec = scoring.step_spec(steptest.step_profile(None), steptest.LOOP_OF[kind], axis)
        bandr = spec["band"] / spec["amp"] if spec["absolute_band"] else spec["band_pct"] / 100.0
        ax.axhspan(1 - bandr, 1 + bandr, color=theme.tok("band"), lw=0, zorder=0)
        ax.axhline(1.0, color=theme.tok("ref_line"), lw=0.7)
        ax.axhline(0.5, color=theme.tok("ref_line"), lw=0.5, ls=":")
        ax.axvline(0, color=PALETTE["setpoint"], lw=0.8, ls=":")
        ax.plot([], [], color=PALETTE["measured"], label=_("verso +"))
        ax.plot([], [], color=SERIES_COLORS[1], label=_("verso −"))
        ax.legend(fontsize=config.font(7), loc="lower right")
        _title(ax, f"{_(steptest.KINDS[kind])} — {_(scoring.AXIS_LABELS[axis]).lower()}")
        ax.set_xlabel(_("Tempo dal comando al 50% [s]"), fontsize=config.font(8))
        if j == 0:
            ax.set_ylabel(_("Risposta / A"), fontsize=config.font(8))
    if not table:
        return
    tab = fig.add_subplot(gs[row_plot + 1, :])
    tab.set_axis_off()
    cols = [_("Asse"), _("Verso"), _("Validi")] + [_(lab) for _k, lab, _u in steptest.QUANTITIES] + [
        _("Verso"), _("Asse")]
    rows, colors = [], []
    for key in keys:
        sm = res.summary[key]
        kind, axis = key
        for i, (sign, d) in enumerate(sm.directions.items()):
            row = [f"{_(steptest.KIND_SHORT[kind])} {_(scoring.AXIS_LABELS[axis]).lower()}",
                   "+" if sign > 0 else "−", f"{d.n_valid}/{d.n_total}"]
            rc = ["white"] * 3
            for qk, _lab, _u in steptest.QUANTITIES:
                w, m = d.worst.get(qk), d.median.get(qk)
                row.append("—" if w is None else f"{_num(m, qk)} / {_num(w, qk)}")
                p = d.passed.get(qk)
                rc.append("white" if p is None else ("#d3f9d8" if p else "#ffe3e3"))
            ok_dir = steptest.direction_verdict(d)
            row.append({None: "—", True: _("entro i criteri"), False: _("fuori criterio")}[ok_dir])
            rc.append("white" if ok_dir is None else ("#d3f9d8" if ok_dir else "#ffe3e3"))
            tuned = sm.tuned
            row.append(("—" if tuned is None else (_("tarato") if tuned else _("non tarato"))) if i == 0 else "")
            rc.append("white" if tuned is None or i else ("#b2f2bb" if tuned else "#ffc9c9"))
            rows.append(row)
            colors.append(rc)
    lim_row = [_("criterio"), "", ""] + [
        "≤ " + _num(res.summary[keys[0]].limits.get(qk), qk) if res.summary[keys[0]].limits.get(qk) is not None
        else "—" for qk, _l, _u in steptest.QUANTITIES] + ["", ""]
    t = tab.table(cellText=rows + [lim_row], colLabels=cols, cellColours=colors + [["#f1f3f5"] * len(cols)],
                  loc="upper center", cellLoc="center")
    t.auto_set_font_size(False)
    t.set_fontsize(config.font(7.5))
    t.scale(1, 1.25)
    tab.text(0.0, 0.0, _("Celle: mediana / caso peggiore dei gradini validi; verde = entro il criterio. "
                           "Tempi: {conv}.").format(conv=_(steptest.TIME_CONVENTION)),
             transform=tab.transAxes, fontsize=config.font(7), va="top", color=theme.tok("text_muted"))


def _draw_hold(ax, log: LogData, h):
    """Tenuta: rollio e beccheggio misurati con i setpoint e la fascia del picco ammesso."""
    from . import steptest

    style_axes(ax)
    att = log.attitude_euler("vehicle_attitude", "q", use_sample=True)
    asp = log.attitude_euler("vehicle_attitude_setpoint", "q_d")
    lim = float(steptest._settings(steptest.step_profile(None), "tenuta").get("assetto_picco_deg", 3.0))
    for i, (lab, col) in enumerate(((_("rollio"), PALETTE["measured"]), (_("beccheggio"), SERIES_COLORS[2]))):
        if att is not None:
            m = att[i].slice(h.t0, h.t1)
            ax.plot(m.t, m.y * DEG, color=col, lw=config.lw(1.0), label=lab)
        if asp is not None:
            m = asp[i].slice(h.t0, h.t1)
            ax.plot(m.t, m.y * DEG, color=col, lw=config.lw(0.8), ls=":", label=f"{lab} — {_('setpoint')}")
    ax.axhspan(-lim, lim, color=theme.tok("band"), lw=0, zorder=0)
    ax.set_xlim(h.t0, h.t1)
    ax.set_ylabel("[°]", fontsize=config.font(8))
    ax.set_xlabel(_("Tempo dall'inizio del log [s]"), fontsize=config.font(8))
    _title(ax, f"{_('Tenuta')} {h.mode} — " + (_("entro i criteri") if h.ok else _("fuori criterio")))
    ax.title.set_color(VALID_COLOR if h.ok else REJECT_COLOR)
    ax.legend(fontsize=config.font(7), loc="upper right", ncol=2)


def _num(v, key=None, nd=None):
    """Numero nel formato della lingua (virgola decimale in italiano); assestamento non avvenuto = «n. ass.»."""
    if v is None:
        return "—"
    if isinstance(v, float) and not np.isfinite(v):
        return _("n. ass.")
    if nd is None:
        nd = {"delay": 3, "settling": 3, "overshoot": 1, "end_error": 1, "bounces": 0, "saturation": 1}.get(key, 2)
    txt = f"{v:.{nd}f}"
    return txt.replace(".", ",") if language() == "it" else txt
