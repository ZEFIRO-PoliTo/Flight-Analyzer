"""Prove a gradino: misura diretta, gradino per gradino, delle prove di taratura in hover.

Complementare alla stima FIR di ``analysis``: la stima dà una risposta media, la scheda di taratura chiede che
ogni gradino rispetti i criteri nel caso peggiore. Qui ogni gradino viene trovato nel comando registrato e misurato
rispetto a quel comando, mai rispetto a tempi teorici.

Rilevamento
    Velocità angolare: vehicle_rates_setpoint, solo nei tratti in cui il setpoint è esterno (vehicle_control_mode con
    velocità angolare attiva e assetto spento: Acro, Offboard a velocità angolare). Assetto: vehicle_attitude_setpoint
    in Stabilized o Offboard d'assetto. Un gradino inizia quando |comando| supera la soglia e finisce quando torna
    sotto; A = mediana del comando sul tratto sopra il 90% del suo massimo, meno il valore prima del gradino.

Grandezze (definizioni della guida al tuning del team)
    ritardo        t(risposta al 50% di A) − t(comando al 50% di A); comando: timestamp, risposta: timestamp_sample
    sovraelong.    (picco − A)/A durante il gradino, in %
    assestamento   dal comando al 50% all'ultimo istante fuori dalla fascia ±10% di A (assetto: ±1°), finché dura il
                   gradino; «non assestato» se a fine gradino è ancora fuori
    errore         media di |comando − risposta| negli ultimi 0,2 s del gradino, in % di A (assetto: in gradi, da 1 s
                   dopo l'inizio alla fine)
    rimbalzi       uscite dalla fascia dopo il picco
    saturazione    % dei campioni di actuator_motors, dall'inizio a 0,5 s dopo la fine (senza i 50 ms dopo i cambi di
                   modo), con almeno un motore ≤ 0,02 o ≥ 0,98

Tutte le soglie stanno nel profilo (profili/vespa_hover.json, sezioni ``gradini``, ``tenuta`` e criteri ``ok`` degli
anelli mc_rate e mc_att).
"""

from __future__ import annotations

import csv
import math
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import __version__, dsp, modes, scoring
from .flags import raised_flags
from .i18n import N_, _, language
from .logdata import NAV_STATES, LogData, Series

DEG = 180.0 / np.pi
KINDS = {"rate": N_("Velocità angolare"), "att": N_("Assetto")}
KIND_SHORT = {"rate": N_("Vel. ang."), "att": N_("Assetto")}
LOOP_OF = {"rate": "mc_rate", "att": "mc_att"}
AXES_OF = {"rate": ("roll", "pitch", "yaw"), "att": ("roll", "pitch")}
AXIS_INDEX = {"roll": 0, "pitch": 1, "yaw": 2}
UNITS = {"rate": "°/s", "att": "°"}
TIME_CONVENTION = N_("comando: timestamp; risposta: timestamp_sample")

# grandezze per gradino: chiave -> (attributo, chiave della metrica nel profilo, etichetta breve, unità)
QUANTITIES = (
    ("delay", N_("Ritardo"), "s"),
    ("overshoot", N_("Sovraelongazione"), "%"),
    ("settling", N_("Assestamento"), "s"),
    ("end_error", N_("Errore"), None),
    ("bounces", N_("Rimbalzi"), ""),
    ("saturation", N_("Saturazione"), "%"),
)
PROFILE_KEY = {"delay": "delay", "overshoot": "overshoot_cmd", "settling": "settling_band", "bounces": "bounces",
               "saturation": "saturation"}


def error_key(kind):
    return "end_error_deg" if kind == "att" else "end_error"


def error_unit(kind):
    return "°" if kind == "att" else "%"


# ------------------------------------------------------------------- profilo


def step_profile(profile=None):
    """Il profilo con le sezioni ``gradini`` e ``tenuta``: quello dato se le ha, altrimenti «Vespa hover»."""
    if profile is not None and "gradini" in profile and definitions_ok(profile):
        return profile
    return _bundled()


def definitions_ok(profile):
    return all(scoring.definitions(profile, lp) == "scheda" for lp in LOOP_OF.values())


_BUNDLED = {}


def _bundled():
    if "p" not in _BUNDLED:
        _BUNDLED["p"] = scoring.vespa_hover_profile()
    return _BUNDLED["p"]


def _settings(profile, section):
    base = _bundled().get(section, {})
    out = dict(base)
    out.update(profile.get(section, {}) if profile else {})
    return out


# ------------------------------------------------------------------- misura


@dataclass
class Response:
    t_resp50: float | None
    delay: float | None
    peak: float | None  # in unità di A
    t_peak: float | None
    overshoot: float | None  # %
    settling: float | None  # s; None = non assestato
    end_error: float | None  # % di A (velocità angolare) o gradi (assetto)
    level_end: float | None  # risposta media nella finestra dell'errore / A
    bounces: int | None


def _interp_cross(t0, t1, e0, e1):
    """Istante in cui e passa per 0 tra (t0, e0) e (t1, e1)."""
    if e1 == e0:
        return t1
    return t0 + (t1 - t0) * e0 / (e0 - e1)


def measure_response(t, u, amp, t0, t_end, band, cmd=None, err_last=None, err_from=None, err_abs=False,
                     debounce=2):
    """Grandezze di un gradino già riportato a «partenza da 0, verso positivo».

    ``t``, ``u``: istanti e risposta (stesse unità di ``amp`` > 0, valore prima del gradino tolto e segno
    raddrizzato); ``t0``: istante del comando al 50%; ``t_end``: fine del gradino; ``band``: semiampiezza della
    fascia (stesse unità); ``cmd``: comando sugli istanti ``t`` (None = gradino ideale di ampiezza ``amp`` da t0).
    Errore: media di |comando − risposta| negli ultimi ``err_last`` s (in % di amp) oppure da ``err_from`` s dopo
    t0 alla fine (``err_abs``: nelle unità della risposta). Usata sia per i gradini misurati sia per la risposta
    stimata (FIR), così le definizioni sono le stesse.
    """
    t = np.asarray(t, float)
    u = np.asarray(u, float)
    c = np.full_like(u, amp) if cmd is None else np.asarray(cmd, float)
    # il gradino dura da t0 a t_end escluso: all'istante t_end il comando è già tornato al valore di partenza
    sel = (t >= t0 - 1e-9) & (t < t_end - 1e-9)
    ts, us = t[sel], u[sel]
    if ts.size < 3 or amp <= 0:
        return None
    # risposta al 50% (interpolazione lineare: la risposta è un segnale fisico campionato)
    t50 = None
    above = np.flatnonzero(us >= 0.5 * amp)
    if above.size:
        j = int(above[0])
        if j == 0:
            prev = np.flatnonzero(t < ts[0])
            if prev.size and u[prev[-1]] < 0.5 * amp:
                k = prev[-1]
                t50 = _interp_cross(t[k], ts[0], u[k] - 0.5 * amp, us[0] - 0.5 * amp)
            else:
                t50 = float(ts[0])
        else:
            t50 = _interp_cross(ts[j - 1], ts[j], us[j - 1] - 0.5 * amp, us[j] - 0.5 * amp)
    delay = None if t50 is None else float(t50 - t0)
    kpk = int(np.argmax(us))
    peak = float(us[kpk])
    overshoot = (peak - amp) / amp * 100.0
    # assestamento
    err = np.abs(us - amp) - band
    out = err > 0
    if out[-1]:
        settling = None
    elif not np.any(out):
        settling = 0.0
    else:
        j = int(np.flatnonzero(out)[-1])
        settling = float(_interp_cross(ts[j], ts[j + 1], err[j], err[j + 1]) - t0)
    # rimbalzi: uscite dalla fascia che iniziano dopo il picco (almeno ``debounce`` campioni, o fino alla fine)
    bounces = 0
    o = out[kpk:]
    i = 1
    while i < len(o):
        if o[i] and not o[i - 1]:
            k = i
            while k < len(o) and o[k]:
                k += 1
            if k - i >= debounce or k == len(o):
                bounces += 1
            i = k
        else:
            i += 1
    # errore a fine gradino
    end_error = level = None
    if err_from is not None:
        w = (t >= t0 + err_from - 1e-9) & (t < t_end - 1e-9)
    else:
        w = (t >= t_end - (err_last or 0.2) - 1e-9) & (t < t_end - 1e-9)
    if np.count_nonzero(w) >= 2:
        e = float(np.mean(np.abs(c[w] - u[w])))
        end_error = e if err_abs else e / amp * 100.0
        level = float(np.mean(u[w]) / amp)
    return Response(None if t50 is None else float(t50), delay, peak / amp, float(ts[kpk]), float(overshoot),
                    settling, end_error, level, int(bounces))


# ------------------------------------------------------------------- risultati


@dataclass
class StepResult:
    n: int
    kind: str  # "rate" | "att"
    axis: str
    sign: int
    t_start: float
    t_end: float
    amplitude: float  # |A| [°/s o °]
    baseline: float
    mode: str
    valid: bool = True
    reasons: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    t_cmd50: float | None = None
    resp: Response | None = None
    saturation: float | None = None
    sat_detail: dict = field(default_factory=dict)
    sat_window: tuple = (0.0, 0.0)
    start: dict = field(default_factory=dict)

    @property
    def duration(self):
        return self.t_end - self.t_start

    @property
    def sign_label(self):
        return "+" if self.sign > 0 else "−"

    def value(self, key):
        """Valore della grandezza (None = non disponibile; assestamento non avvenuto = inf)."""
        if key == "saturation":
            return self.saturation
        if self.resp is None:
            return None
        if key == "settling":
            return math.inf if self.resp.settling is None else self.resp.settling
        return getattr(self.resp, key)

    def sat_text(self):
        return modes.describe_saturation(self.sat_detail, _("al minimo"), _("al massimo"))


@dataclass
class DirectionSummary:
    sign: int
    n_valid: int
    n_total: int
    median: dict
    worst: dict
    passed: dict  # chiave -> True/False/None


@dataclass
class AxisSummary:
    kind: str
    axis: str
    limits: dict  # chiave -> limite «ok» del profilo
    directions: dict  # segno -> DirectionSummary
    tuned: bool | None  # True = tarato, False = no, None = non si può dire
    messages: list = field(default_factory=list)

    @property
    def n_valid(self):
        return sum(d.n_valid for d in self.directions.values())


@dataclass
class HoldResult:
    t0: float
    t1: float
    mode: str
    short: bool
    values: dict  # chiave -> valore
    passed: dict  # chiave -> bool
    notes: list = field(default_factory=list)

    @property
    def ok(self):
        return all(v for v in self.passed.values() if v is not None)


@dataclass
class StepTestResult:
    log_name: str
    version: str
    profile_name: str
    ignore_mode: bool
    steps: list
    summary: dict  # (kind, axis) -> AxisSummary
    holds: list
    warnings: list
    params: list  # [(nome, valore)]
    excluded: list  # finestre escluse dopo i cambi di modo
    fir: dict = field(default_factory=dict)  # (kind, axis) -> dict con gli indicatori FIR

    def valid_steps(self, kind=None, axis=None, sign=None):
        return [s for s in self.steps if s.valid and (kind is None or s.kind == kind)
                and (axis is None or s.axis == axis) and (sign is None or s.sign == sign)]

    def has_steps(self):
        return bool(self.steps)


# ------------------------------------------------------------------- dati


def _cmd_series(log: LogData, kind, axis):
    if kind == "rate":
        s = log.series("vehicle_rates_setpoint", axis)
        return None if s is None else Series(s.t, s.y * DEG)
    e = log.attitude_euler("vehicle_attitude_setpoint", "q_d")
    if e is None:
        s = log.series("vehicle_attitude_setpoint", f"{axis}_body")
        return None if s is None else Series(s.t, s.y * DEG)
    s = e[AXIS_INDEX[axis]]
    return Series(s.t, s.y * DEG)


def _resp_series(log: LogData, kind, axis):
    if kind == "rate":
        s = log.series("vehicle_angular_velocity", f"xyz[{AXIS_INDEX[axis]}]", use_sample=True)
        return None if s is None else Series(s.t, s.y * DEG)
    e = log.attitude_euler("vehicle_attitude", "q", use_sample=True)
    if e is None:
        return None
    s = e[AXIS_INDEX[axis]]
    return Series(s.t, s.y * DEG)


def _mean_at(s: Series | None, t0, t1):
    if s is None or len(s) == 0:
        return None
    sel = (s.t >= t0) & (s.t <= t1)
    if np.count_nonzero(sel):
        return float(np.mean(s.y[sel]))
    return float(np.interp(t1, s.t, s.y))


def _runs(mask):
    """[(i0, i1)] indici (inclusi) delle sequenze True."""
    if mask.size == 0:
        return []
    d = np.diff(np.concatenate(([0], mask.astype(int), [0])))
    starts = np.flatnonzero(d == 1)
    ends = np.flatnonzero(d == -1) - 1
    return list(zip(starts, ends))


def _inside(t, intervals):
    return any(a <= t < b for a, b in intervals)


def _fmt(v, nd=2):
    txt = f"{v:.{nd}f}"
    return txt.replace(".", ",") if language() == "it" else txt


# ------------------------------------------------------------------- rilevamento


def flight_parameters(log: LogData):  # noqa: D401
    """Parametri del controllore da mettere in testa alla scheda e al report."""
    names = []
    for pref in ("MC_ROLLRATE", "MC_PITCHRATE", "MC_YAWRATE"):
        names += [f"{pref}_{x}" for x in ("P", "I", "D", "K", "FF")]
    names += ["MC_ROLL_P", "MC_PITCH_P", "MC_YAW_P"]
    return [(n, log.params[n]) for n in names if n in log.params]


def detect(log: LogData, profile=None, ignore_mode=False, threshold=None, time_range=None, with_fir=False):
    """Trova e misura i gradini del log; restituisce uno StepTestResult.

    ``ignore_mode``: cerca i gradini in tutto il volo in multicottero (per i log dell'autotune, con gradini
    iniettati in Hold) con la soglia ``threshold`` (°/s per la velocità angolare; per l'assetto la soglia del
    profilo scalata nello stesso rapporto). ``with_fir``: aggiunge gli indicatori della stima FIR per gli stessi
    assi (più lento).
    """
    profile = step_profile(profile)
    g = _settings(profile, "gradini")
    excl_s = float(g.get("esclusione_cambio_modo_s", modes.TRANSIENT_S))
    excluded = modes.transient_windows(log, excl_s)
    changes = modes.change_times(log)
    base = log.phase_intervals("MC")
    if log.airborne_known:
        base = dsp.intersect(base, log.airborne)
    if time_range is not None:
        base = dsp.intersect(base, [tuple(time_range)])
    try:
        flags = [f for f in raised_flags(log, include_info=False) if f.severity >= 2]
    except Exception:  # noqa: BLE001 - i flag sono solo informativi
        flags = []
    vel = (log.series("vehicle_local_position", "vx"), log.series("vehicle_local_position", "vy"))
    att_meas = log.attitude_euler("vehicle_attitude", "q", use_sample=True)
    rates_meas = [log.series("vehicle_angular_velocity", f"xyz[{i}]", use_sample=True) for i in range(3)]
    outputs = modes.actuator_outputs(log, "MC")

    steps = []
    for kind in ("rate", "att"):
        if ignore_mode:
            eligible = base
            thr = float(threshold if threshold is not None else g.get("soglia_ignora_modo_dps", 10.0))
            if kind == "att":
                ratio = thr / float(g.get("soglia_rate_dps", 20.0))
                thr = float(g.get("soglia_assetto_deg", 3.0)) * ratio
        else:
            eligible = dsp.intersect(modes.rate_external_intervals(log) if kind == "rate"
                                     else modes.attitude_step_intervals(log), base)
            thr = float(g.get("soglia_rate_dps", 20.0) if kind == "rate" else g.get("soglia_assetto_deg", 3.0))
        if not eligible:
            continue
        cmds = {a: _cmd_series(log, kind, a) for a in ("roll", "pitch", "yaw")}
        for axis in AXES_OF[kind]:
            cmd = cmds[axis]
            if cmd is None or len(cmd) < 3:
                continue
            resp = _resp_series(log, kind, axis)
            cand = _find_runs(cmd, base, eligible, thr, g)
            if not cand:
                continue
            durations = [b - a for a, b, _s in cand if b - a >= float(g.get("durata_min_s", 0.2))]
            med = float(np.median(durations)) if durations else None
            for t_start, t_end, sign in cand:
                st = _measure_step(log, kind, axis, sign, t_start, t_end, cmd, resp, cmds, profile, g, med,
                                   excluded, changes, flags, vel, att_meas, rates_meas, outputs)
                steps.append(st)
    steps.sort(key=lambda s: s.t_start)
    for i, s in enumerate(steps, 1):
        s.n = i
    summary = summarize(steps, profile)
    holds = hold_quality(log, profile, excluded)
    warnings = _warnings(log, steps, summary, g)
    res = StepTestResult(log.name, __version__, _(profile.get("nome", "")), ignore_mode, steps, summary, holds,
                         warnings, flight_parameters(log), excluded)
    if with_fir:
        res.fir = fir_indicators(log, res, profile)
    return res


def _find_runs(cmd: Series, base, eligible, thr, g):
    """Tratti con |comando| sopra soglia, dello stesso segno, che iniziano in un tratto ammesso."""
    out = []
    spike = float(g.get("durata_picco_s", 0.05))
    inside = dsp.mask_from_intervals(cmd.t, base)
    for sign in (1, -1):
        above = (sign * cmd.y > thr) & inside
        for i0, i1 in _runs(above):
            t_start = float(cmd.t[i0])
            t_end = float(cmd.t[i1 + 1]) if i1 + 1 < len(cmd.t) else float(cmd.t[i1])
            iv = next(((a, b) for a, b in eligible if a <= t_start < b), None)
            if iv is None:
                continue  # comandi prodotti da Hold/Position: non sono gradini
            # un gradino interrotto da un cambio di modo finisce lì: dopo, il comando è dell'altro modo
            t_end = min(t_end, iv[1])
            if t_end - t_start < spike:
                continue  # picco di un ciclo (cambio di modo): non è un gradino
            out.append((t_start, t_end, sign))
    return sorted(out)


def _measure_step(log, kind, axis, sign, t_start, t_end, cmd, resp, cmds, profile, g, med, excluded, changes,
                  flags, vel, att_meas, rates_meas, outputs):
    unit = UNITS[kind]
    pre = float(g.get("valore_prima_s", 0.3))
    sel_pre = (cmd.t >= t_start - pre) & (cmd.t < t_start)
    baseline = float(np.median(cmd.y[sel_pre])) if np.any(sel_pre) else 0.0
    sel = (cmd.t >= t_start) & (cmd.t < t_end)
    dev = sign * (cmd.y[sel] - baseline)
    amp = float(np.median(dev[dev >= 0.9 * dev.max()])) if dev.size else 0.0
    st = StepResult(0, kind, axis, sign, t_start, t_end, amp, baseline, modes.mode_name_at(log, t_start))
    k50 = np.flatnonzero(dev >= 0.5 * amp)
    st.t_cmd50 = float(cmd.t[sel][k50[0]]) if k50.size else t_start

    # --- motivi di scarto
    if st.duration < float(g.get("durata_min_s", 0.2)):
        st.reasons.append(_("troppo corto ({d} s)").format(d=_fmt(st.duration)))
    t_lo = t_start - float(g.get("modo_stabile_prima_s", 0.4))
    hits = [c for c in changes if t_lo <= c <= t_end]
    if hits:
        c = hits[-1]
        st.reasons.append(_("cambio di modo a {t} s ({da} → {a})").format(
            t=_fmt(c), da=modes.mode_name_at(log, c - 1e-3), a=modes.mode_name_at(log, c + 1e-3)))
    frac = float(g.get("troncato_frazione_mediana", 0.9))
    if med and st.duration < frac * med and st.duration >= float(g.get("durata_min_s", 0.2)):
        st.reasons.append(_("troncato: {d} s contro la mediana di {m} s").format(d=_fmt(st.duration), m=_fmt(med)))
    w0, w1 = t_start - float(g.get("partenza_finestra_s", 0.1)), t_start
    roll = _mean_at(att_meas[0], w0, w1) if att_meas else None
    pitch = _mean_at(att_meas[1], w0, w1) if att_meas else None
    rate = _mean_at(rates_meas[AXIS_INDEX[axis]], w0, w1)
    vx, vy = (_mean_at(v, w0, w1) for v in vel)
    st.start = {"roll": None if roll is None else roll * DEG, "pitch": None if pitch is None else pitch * DEG,
                "rate": None if rate is None else rate * DEG,
                "vxy": None if vx is None or vy is None else float(math.hypot(vx, vy))}
    why = []
    tilt_max = float(g.get("partenza_max_inclinazione_deg", 2.0))
    for key, lab in (("roll", _("rollio")), ("pitch", _("beccheggio"))):
        v = st.start[key]
        if v is not None and abs(v) > tilt_max:
            why.append(f"{lab} {_fmt(v, 1)}°")
    v = st.start["rate"]
    if v is not None and abs(v) > float(g.get("partenza_max_rate_dps", 5.0)):
        why.append(_("velocità angolare {v} °/s").format(v=_fmt(v, 1)))
    v = st.start["vxy"]
    if v is not None and v > float(g.get("partenza_max_vel_orizz_ms", 0.5)):
        why.append(_("velocità orizzontale {v} m/s").format(v=_fmt(v, 1)))
    if why:
        st.reasons.append(_("partenza non ferma: {cosa}").format(cosa=", ".join(why)))
    tol = float(g.get("altri_assi_max_dps", 3.0) if kind == "rate" else g.get("altri_assi_max_deg", 1.0))
    for other in AXES_OF[kind] if kind == "att" else ("roll", "pitch", "yaw"):
        if other == axis or cmds.get(other) is None:
            continue
        oc = cmds[other]
        sp = (oc.t >= t_start - pre) & (oc.t < t_start)
        ob = float(np.median(oc.y[sp])) if np.any(sp) else 0.0
        so = (oc.t >= t_start) & (oc.t < t_end)
        if np.any(so):
            dev_o = float(np.max(np.abs(oc.y[so] - ob)))
            if dev_o > tol:
                st.reasons.append(_("comando anche su {asse} ({v} {u})").format(
                    asse=_(scoring.AXIS_LABELS[other]).lower(), v=_fmt(dev_o, 1), u=unit))
    post = float(g.get("saturazione_dopo_s", 0.5))
    for f in flags:
        for a, b in f.intervals:
            if a <= t_end and b >= t_start:
                st.reasons.append(_("flag «{f}» attivo durante il gradino ({t} s)").format(f=f.label(), t=_fmt(a)))
                break
            if t_end < a <= t_end + post:
                st.notes.append(_("flag «{f}» a {t} s, dopo la fine del gradino").format(f=f.label(), t=_fmt(a)))
                break

    # --- risposta
    if resp is None or len(resp) < 3:
        st.reasons.append(_("risposta non registrata"))
    else:
        w = (resp.t >= t_start - pre) & (resp.t <= t_end + post)
        tt = resp.t[w]
        u = sign * (resp.y[w] - baseline)
        c = sign * (dsp.resample(cmd.t, cmd.y, tt, "zoh") - baseline)
        spec = scoring.step_spec(profile, LOOP_OF[kind], axis)
        band = spec["band"] if spec["absolute_band"] else amp * spec["band_pct"] / 100.0
        st.resp = measure_response(tt, u, amp, st.t_cmd50, t_end, band, cmd=c, err_last=spec["err_last"],
                                   err_from=spec["err_from"], err_abs=kind == "att",
                                   debounce=int(g.get("rimbalzi_min_campioni", 2)))
        if st.resp is None:
            st.reasons.append(_("risposta non registrata"))

    # --- saturazione dei motori (i 50 ms dopo ogni cambio di modo sono esclusi)
    sat_end = t_end + post
    nxt = [c for c in changes if t_end < c < sat_end]
    if nxt:
        st.notes.append(_("la finestra della saturazione comprende il cambio di modo a {t} s ({da} → {a})").format(
            t=_fmt(nxt[0]), da=modes.mode_name_at(log, nxt[0] - 1e-3), a=modes.mode_name_at(log, nxt[0] + 1e-3)))
    st.sat_window = (t_start, sat_end)
    sat = modes.saturation(log, [(t_start, sat_end)], excluded, "MC", outputs)
    if sat is not None:
        st.saturation = sat["percent"]
        st.sat_detail = sat["detail"]
    st.valid = not st.reasons
    return st


# ------------------------------------------------------------------- riepilogo


def limits_for(profile, kind, axis):
    th = scoring.loop_metrics(profile, LOOP_OF[kind], axis)
    out = {}
    for key, _lab, _u in QUANTITIES:
        pk = error_key(kind) if key == "end_error" else PROFILE_KEY[key]
        out[key] = th[pk]["ok"] if pk in th else None
    return out


def direction_verdict(d: DirectionSummary):
    """True se il caso peggiore del verso rispetta tutti i criteri, False se no, None senza gradini validi."""
    if d.n_valid == 0:
        return None
    vals = [p for p in d.passed.values() if p is not None]
    return all(vals) if vals else None


def summarize(steps, profile):
    out = {}
    g = _settings(profile, "gradini")
    need = int(g.get("min_validi_per_verso", 3))
    for kind in ("rate", "att"):
        for axis in AXES_OF[kind]:
            mine = [s for s in steps if s.kind == kind and s.axis == axis]
            if not mine:
                continue
            lim = limits_for(profile, kind, axis)
            dirs = {}
            msgs = []
            for sign in (1, -1):
                tot = [s for s in mine if s.sign == sign]
                val = [s for s in tot if s.valid]
                med, worst, passed = {}, {}, {}
                for key, _lab, _u in QUANTITIES:
                    vals = [s.value(key) for s in val]
                    vals = [v for v in vals if v is not None]
                    if not vals:
                        med[key] = worst[key] = passed[key] = None
                        continue
                    med[key] = float(np.median(vals))
                    worst[key] = float(np.max(vals))
                    passed[key] = None if lim[key] is None else bool(worst[key] <= lim[key] + 1e-9)
                dirs[sign] = DirectionSummary(sign, len(val), len(tot), med, worst, passed)
                if len(val) < need:
                    msgs.append(_("verso {s}: {n} gradini validi su {t} (ne servono almeno {k})").format(
                        s="+" if sign > 0 else "−", n=len(val), t=len(tot), k=need))
            both = all(dirs[s].n_valid > 0 for s in (1, -1))
            all_pass = all(p is not False for d in dirs.values() for p in d.passed.values())
            if not both:
                tuned = None if all_pass else False
            else:
                tuned = all_pass and all(p is not None for d in dirs.values() for k, p in d.passed.items()
                                         if lim[k] is not None)
            out[(kind, axis)] = AxisSummary(kind, axis, lim, dirs, tuned, msgs)
    return out


# ------------------------------------------------------------------- tenuta


def hold_quality(log: LogData, profile, excluded=()):
    """Tenuta in Hold/Position: tratti senza comandi, assetto, posizione, integratori, motori, spinta di hover."""
    h = _settings(profile, "tenuta")
    base = log.phase_intervals("MC")
    if log.airborne_known:
        base = dsp.intersect(base, log.airborne)
    # tratti in cui al velivolo si chiede di stare fermo (velocità del trajectory_setpoint quasi nulla):
    # un Hold con un riposizionamento o una salita non è una prova di tenuta
    still = _still_intervals(log, float(h.get("vel_setpoint_max_ms", 0.3)))
    segs = []
    skip = float(h.get("scarta_inizio_s", 1.0))
    min_full = float(h.get("durata_min_s", 30.0))
    min_ind = float(h.get("durata_min_indicativa_s", 5.0))
    for a, b, v in log.modes:
        if v not in (2, 4):
            continue
        pieces = dsp.intersect([(a, b)], base)
        if still is not None:
            pieces = dsp.intersect(pieces, still)
        for lo, hi in pieces:
            lo += skip
            if hi - lo >= min_ind:
                segs.append((lo, hi, NAV_STATES.get(v, str(v))))
    if not segs:
        return []
    att = log.attitude_euler("vehicle_attitude", "q", use_sample=True)
    asp = log.attitude_euler("vehicle_attitude_setpoint", "q_d")
    pos = [log.series("vehicle_local_position", c) for c in ("x", "y", "z")]
    integ = [_pick_integrator(log, segs, f"{ax}speed_integ") for ax in ("roll", "pitch")]
    motors = [s for _n, s, k in modes.actuator_outputs(log, "MC") if k == "motor"]
    hover = log.series("hover_thrust_estimate", "hover_thrust")
    sticks = [log.series("manual_control_setpoint", f) for f in ("roll", "pitch", "yaw")]
    out = []
    for lo, hi, name in segs:
        vals, passed, notes = {}, {}, []
        if att is not None and asp is not None:
            for i, ax in enumerate(("roll", "pitch")):
                m = att[i].slice(lo, hi)
                if len(m) < 10:
                    continue
                spv = dsp.resample(asp[i].t, asp[i].y, m.t, "zoh")
                e = (spv - m.y) * DEG
                vals[f"{ax}_rms"] = float(np.sqrt(np.mean(e ** 2)))
                vals[f"{ax}_peak"] = float(np.max(np.abs(e)))
                vals[f"{ax}_range"] = (float(np.min(m.y) * DEG), float(np.max(m.y) * DEG))
                passed[f"{ax}_rms"] = vals[f"{ax}_rms"] <= float(h.get("assetto_rms_deg", 1.0))
                passed[f"{ax}_peak"] = vals[f"{ax}_peak"] <= float(h.get("assetto_picco_deg", 3.0))
        if all(p is not None for p in pos):
            xs, ys, zs = (p.slice(lo, hi) for p in pos)
            if len(xs) > 10 and len(xs) == len(ys):
                dh = np.hypot(xs.y - xs.y.mean(), ys.y - ys.y.mean())
                vals["pos_h"] = float(dh.max())
                passed["pos_h"] = vals["pos_h"] <= float(h.get("posizione_orizz_m", 0.5))
            if len(zs) > 10:
                vals["pos_v"] = float(np.max(np.abs(zs.y - zs.y.mean())))
                passed["pos_v"] = vals["pos_v"] <= float(h.get("posizione_vert_m", 0.3))
        for ax, s in zip(("roll", "pitch"), integ):
            if s is not None:
                m = s.slice(lo, hi)
                if len(m):
                    vals[f"{ax}_integ"] = float(np.max(np.abs(m.y)))
                    passed[f"{ax}_integ"] = vals[f"{ax}_integ"] <= float(h.get("integratori_max", 0.15))
        if motors:
            lo_m, hi_m = math.inf, -math.inf
            for s in motors:
                m = s.slice(lo, hi)
                if len(m):
                    lo_m, hi_m = min(lo_m, float(m.y.min())), max(hi_m, float(m.y.max()))
            if math.isfinite(lo_m):
                vals["motors"] = (lo_m, hi_m)
                passed["motors"] = lo_m >= float(h.get("motori_min", 0.05)) and hi_m <= float(h.get("motori_max", 0.95))
        if hover is not None:
            m = hover.slice(lo, hi)
            if len(m) >= 3:
                vals["hover"] = (float(m.y.mean()), float(m.y.std()))
        moved = 0.0
        for s in sticks:
            if s is not None:
                m = s.slice(lo, hi)
                if len(m):
                    moved = max(moved, float(np.mean(np.abs(m.y) > float(h.get("stick_max", 0.1)))))
        if moved > 0.01:
            notes.append(_("stick mossi per il {p:.0f}% del tratto").format(p=moved * 100))
        short = hi - lo < min_full
        if short:
            notes.append(_("tratto di {d:.0f} s, più corto dei {m:.0f} s richiesti: valori indicativi").format(
                d=hi - lo, m=min_full))
        out.append(HoldResult(lo, hi, name, short, vals, passed, notes))
    return out


def _still_intervals(log: LogData, vmax):
    """Tratti con la velocità richiesta (trajectory_setpoint) sotto ``vmax``; None se il topic manca."""
    d = log.dataset("trajectory_setpoint")
    if d is None or "velocity[0]" not in d.data:
        return None
    t = log._time(d, False)
    v = np.zeros(len(t))
    for i in range(3):
        y = d.data[f"velocity[{i}]"].astype(float)
        v += np.where(np.isfinite(y), y, 0.0) ** 2
    order = np.argsort(t, kind="stable")
    return dsp.intervals_where(t[order], np.sqrt(v[order]) < vmax, log.duration)


def _pick_integrator(log, intervals, field_name):
    best, best_sd = None, -1.0
    iv = [(a, b) for a, b, *_r in intervals]
    for inst in log.instances("rate_ctrl_status"):
        s = log.series("rate_ctrl_status", field_name, inst)
        if s is None:
            continue
        mask = dsp.mask_from_intervals(s.t, iv)
        if np.count_nonzero(mask) < 10:
            continue
        sd = float(np.std(s.y[mask]))
        if sd > best_sd:
            best, best_sd = s, sd
    return best


HOLD_ITEMS = (
    ("roll_rms", N_("Errore di rollio RMS"), "°", "assetto_rms_deg"),
    ("roll_peak", N_("Errore di rollio di picco"), "°", "assetto_picco_deg"),
    ("pitch_rms", N_("Errore di beccheggio RMS"), "°", "assetto_rms_deg"),
    ("pitch_peak", N_("Errore di beccheggio di picco"), "°", "assetto_picco_deg"),
    ("pos_h", N_("Scostamento orizzontale dalla media"), "m", "posizione_orizz_m"),
    ("pos_v", N_("Scostamento verticale dalla media"), "m", "posizione_vert_m"),
    ("roll_integ", N_("Integratore di rollio (max |valore|)"), "", "integratori_max"),
    ("pitch_integ", N_("Integratore di beccheggio (max |valore|)"), "", "integratori_max"),
    ("motors", N_("Motori (min – max)"), "", None),
    ("hover", N_("Spinta di hover stimata (media ± dev. std)"), "", None),
)


# ------------------------------------------------------------------- avvisi


def _warnings(log: LogData, steps, summary, g):
    out = []
    w = modes.allocator_fix_warning(log)
    if w:
        out.append(w)
    w = modes.log_rate_warning(log)
    if w:
        out.append(w)
    gains = [(t, k, v) for t, k, v in log.param_changes
             if k.startswith(("MC_ROLLRATE", "MC_PITCHRATE", "MC_YAWRATE")) or k in ("MC_ROLL_P", "MC_PITCH_P",
                                                                                      "MC_YAW_P")]
    if gains:
        names = ", ".join(sorted({k for _t, k, _v in gains}))
        out.append(_("Parametri del controllore cambiati durante il volo ({nomi}): la prova non vale, serve un log "
                     "per ogni configurazione.").format(nomi=names))
    if not steps:
        out.append(_("Nessun gradino trovato: i gradini di velocità angolare si cercano in Acro e in Offboard a "
                     "velocità angolare, quelli d'assetto in Stabilized e in Offboard d'assetto (per i log "
                     "dell'autotune usare «Ignora il modo»)."))
    for (kind, axis), sm in summary.items():
        for m in sm.messages:
            out.append(f"{_(KINDS[kind])} {_(scoring.AXIS_LABELS[axis]).lower()}: {m}")
    return out


# ------------------------------------------------------------------- FIR affiancato


def fir_indicators(log: LogData, res: StepTestResult, profile):
    """Indicatori della stima FIR (definizioni della scheda) per gli assi con gradini, e confronto."""
    from . import analysis

    out = {}
    for kind in ("rate", "att"):
        axes = [a for a in AXES_OF[kind] if (kind, a) in res.summary]
        if not axes:
            continue
        try:
            r = analysis.analyze(log, "MC", kind, None, profile)
        except Exception as exc:  # noqa: BLE001 - la scheda resta valida anche senza FIR
            for a in axes:
                out[(kind, a)] = {"error": str(exc)}
            continue
        for a in axes:
            ar = r.axes[a]
            if not ar.available or ar.extras.get("cmd") is None:
                out[(kind, a)] = {"error": ar.reason or _("stima non disponibile")}
                continue
            cm, sd = ar.extras["cmd"], ar.extras.get("cmd_spread", {})
            item = {"values": cm, "spread": sd, "score": ar.card.score, "confidence": ar.card.confidence,
                    "warnings": []}
            sm = res.summary[(kind, a)]
            for key in ("delay", "overshoot", "settling"):
                meds = [d.median[key] for d in sm.directions.values() if d.median.get(key) is not None]
                fv, fs = cm.get(key), sd.get(key)
                if not meds or fv is None or not math.isfinite(fv) or fs is None:
                    continue
                m = float(np.median(meds))
                if not math.isfinite(m):
                    continue
                if abs(fv - m) > max(2 * fs, 1e-6):
                    lab = dict((k, l) for k, l, _u in QUANTITIES)[key]
                    item["warnings"].append(_("{g}: stima FIR {f} contro mediana dei gradini {m} (oltre ±2σ = {s})"
                                              ).format(g=_(lab), f=_fmt(fv, 3), m=_fmt(m, 3), s=_fmt(2 * fs, 3)))
            out[(kind, a)] = item
    return out


# ------------------------------------------------------------------- esportazione


def _csv_num(v, nd=3):
    if v is None:
        return ""
    if isinstance(v, float) and math.isinf(v):
        return _("non assestato")
    txt = f"{v:.{nd}f}" if isinstance(v, float) else str(v)
    return txt.replace(".", ",") if language() == "it" else txt


def write_csv(res: StepTestResult, path):
    """CSV: una riga per gradino più le righe di riepilogo (italiano: separatore «;» e virgola decimale)."""
    sep = ";" if language() == "it" else ","
    head = [_("versione"), _("log"), _("riga"), _("n"), _("tipo"), _("asse"), _("verso"), _("modo"), _("inizio [s]"),
            _("fine [s]"), _("durata [s]"), _("ampiezza A"), _("unità"), _("comando al 50% [s]"),
            _("ritardo [s]"), _("sovraelongazione [%]"), _("assestamento [s]"), _("errore"), _("unità errore"),
            _("rimbalzi"), _("saturazione [%]"), _("motori saturi"), _("valido"), _("motivo dello scarto"),
            _("note"), _("convenzione dei tempi")]
    rows = []
    conv = _(TIME_CONVENTION)
    for s in res.steps:
        r = s.resp
        rows.append([res.version, res.log_name, _("gradino"), s.n, _(KINDS[s.kind]), _(scoring.AXIS_LABELS[s.axis]),
                     s.sign_label, s.mode, _csv_num(s.t_start), _csv_num(s.t_end), _csv_num(s.duration),
                     _csv_num(s.amplitude * s.sign, 1), UNITS[s.kind], _csv_num(s.t_cmd50),
                     _csv_num(None if r is None else r.delay), _csv_num(None if r is None else r.overshoot, 1),
                     _csv_num(s.value("settling")), _csv_num(None if r is None else r.end_error, 2),
                     error_unit(s.kind), "" if r is None else r.bounces, _csv_num(s.saturation, 1), s.sat_text(),
                     _("sì") if s.valid else _("no"), "; ".join(s.reasons), "; ".join(s.notes), conv])
    for (kind, axis), sm in res.summary.items():
        for sign, d in sm.directions.items():
            for what, data in ((_("mediana"), d.median), (_("caso peggiore"), d.worst)):
                rows.append([res.version, res.log_name, f"{_('riepilogo')} — {what}", d.n_valid, _(KINDS[kind]),
                             _(scoring.AXIS_LABELS[axis]), "+" if sign > 0 else "−", "", "", "", "", "",
                             UNITS[kind], "", _csv_num(data.get("delay")), _csv_num(data.get("overshoot"), 1),
                             _csv_num(data.get("settling")), _csv_num(data.get("end_error"), 2), error_unit(kind),
                             _csv_num(data.get("bounces"), 0), _csv_num(data.get("saturation"), 1), "",
                             "", "", "", conv])
            rows.append([res.version, res.log_name, _("riepilogo — esito"), d.n_valid, _(KINDS[kind]),
                         _(scoring.AXIS_LABELS[axis]), "+" if sign > 0 else "−", "", "", "", "", "", UNITS[kind], ""]
                        + [_verdict_word(d.passed.get(k)) for k in ("delay", "overshoot", "settling", "end_error")]
                        + [""] + [_verdict_word(d.passed.get("bounces")), _verdict_word(d.passed.get("saturation")),
                                  "", _verdict_word(sm.tuned, tuned=True), "", "", conv])
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        w = csv.writer(fh, delimiter=sep)
        w.writerow(head)
        w.writerows(rows)
    return path


def _verdict_word(v, tuned=False):
    if v is None:
        return "—"
    if tuned:
        return _("tarato") if v else _("non tarato")
    return _("ok") if v else _("fuori")


def output_paths(log_path, folder=None):
    log_path = Path(log_path)
    folder = Path(folder) if folder else log_path.parent
    stem = log_path.stem + "_riepilogo"
    return folder / f"{stem}.png", folder / f"{stem}.csv", folder / f"{log_path.stem}_gradini"


def export(log: LogData, res: StepTestResult, folder=None, per_step=True):
    """Scrive PNG riassuntivo, CSV e un PNG per gradino; restituisce i percorsi scritti."""
    from matplotlib.figure import Figure

    from . import plots, theme

    png, csv_path, step_dir = output_paths(log.path, folder)
    written = []
    with theme.matplotlib_theme("light"):
        fig = Figure(figsize=(14, 9.5), dpi=100)
        plots.build_step_summary(fig, log, res)
        fig.savefig(png, dpi=130, facecolor="white")
        written.append(png)
        if per_step and res.steps:
            step_dir.mkdir(parents=True, exist_ok=True)
            for s in res.steps:
                fig = Figure(figsize=(10, 6.5), dpi=100)
                plots.build_step_detail(fig, log, res, s)
                name = f"{s.n:02d}_{s.kind}_{s.axis}_{'pos' if s.sign > 0 else 'neg'}" + ("" if s.valid else "_scartato")
                f = step_dir / f"{name}.png"
                fig.savefig(f, dpi=110, facecolor="white")
                written.append(f)
    write_csv(res, csv_path)
    written.insert(1, csv_path)
    return written
