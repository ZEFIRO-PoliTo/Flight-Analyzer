"""Analisi dei controllori su un log: selezione dati, identificazione, metriche, punteggio."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from . import dsp, loopid, modes, scoring, steptest
from .i18n import N_, _
from .logdata import LogData, Series

PHASES = {"MC": N_("Multicottero"), "FW": N_("Ala fissa"), "ALL": N_("Tutto il volo")}
LOOPS = {"rate": N_("Velocità angolare (rate)"), "att": N_("Assetto")}
AXIS_INDEX = {"roll": 0, "pitch": 1, "yaw": 2}
EDGE_TRIM = 0.5  # s tolti a inizio/fine di ogni tratto (decollo, atterraggio, cambi di fase)


@dataclass
class AxisResult:
    axis: str
    loop_key: str
    available: bool
    reason: str = ""
    sources: dict = field(default_factory=dict)
    fs: float = 0.0
    used_time: float = 0.0
    target_rise: float | None = None
    target_note: str = ""
    est: loopid.LoopEstimate | None = None
    step: loopid.StepMetrics | None = None
    spread: dict = field(default_factory=dict)
    freq: loopid.FreqMetrics | None = None
    margins: loopid.Margins | None = None
    extras: dict = field(default_factory=dict)
    card: scoring.ScoreCard | None = None


@dataclass
class AnalysisResult:
    log_name: str
    phase: str
    loop: str
    loop_key: str
    intervals: list
    total_time: float
    axes: dict
    score: float | None
    grade: str
    warnings: list = field(default_factory=list)

    @property
    def title(self):
        return _(scoring.LOOP_LABELS.get(self.loop_key, self.loop_key))


def loop_key(phase, loop):
    prefix = "fw" if phase == "FW" else "mc"
    return f"{prefix}_{loop}"


# ------------------------------------------------------------------- sorgenti


def _rate_sources(log: LogData, axis: str, phase: str):
    i = AXIS_INDEX[axis]
    sp = [("vehicle_rates_setpoint", axis)]
    meas = [
        ("vehicle_angular_velocity", f"xyz[{i}]"),
        ("vehicle_attitude", ["rollspeed", "pitchspeed", "yawspeed"][i]),
        ("sensor_combined", f"gyro_rad[{i}]"),
    ]
    if phase == "FW":
        torque = [("vehicle_torque_setpoint_virtual_fw", f"xyz[{i}]")]
        if log.is_vtol:
            torque.append(("vehicle_torque_setpoint", f"xyz[{i}]", 1))
        torque += [("vehicle_torque_setpoint", f"xyz[{i}]", 0), ("actuator_controls_1", f"control[{i}]"),
                   ("actuator_controls_0", f"control[{i}]")]
    else:
        torque = [
            ("vehicle_torque_setpoint_virtual_mc", f"xyz[{i}]"),
            ("vehicle_torque_setpoint", f"xyz[{i}]", 0),
            ("actuator_controls_0", f"control[{i}]"),
        ]
    return sp, meas, torque


def _euler_series(log: LogData, topic: str, qfield: str, idx: int):
    e = log.attitude_euler(topic, qfield)
    return None if e is None else e[idx]


def _attitude_pair(log: LogData, axis: str):
    i = AXIS_INDEX[axis]
    sp = _euler_series(log, "vehicle_attitude_setpoint", "q_d", i)
    sp_name = "vehicle_attitude_setpoint.q_d"
    if sp is None:
        sp = log.series("vehicle_attitude_setpoint", f"{axis}_body")
        sp_name = f"vehicle_attitude_setpoint.{axis}_body"
    meas = _euler_series(log, "vehicle_attitude", "q", i)
    return sp, sp_name, meas, "vehicle_attitude.q"


# ------------------------------------------------------------------- supporto


def _segments_for(intervals, series_list, fs, methods, min_len):
    """Ricampiona le serie sugli intervalli; restituisce lista di dict uniformi."""
    segs = []
    names = list(series_list)
    for t0, t1 in intervals:
        lo = max([t0] + [series_list[n].t[0] for n in names])
        hi = min([t1] + [series_list[n].t[-1] for n in names])
        if hi - lo < min_len:
            continue
        grid = np.arange(lo, hi, 1.0 / fs)
        seg = {}
        for n in names:
            s = series_list[n]
            seg[n] = dsp.resample(s.t, s.y, grid, methods.get(n, "linear"))
        seg["t"] = grid
        segs.append(seg)
    return segs


def _trim(intervals, edge=EDGE_TRIM):
    return [(a + edge, b - edge) for a, b in intervals if b - a > 2 * edge]


def _wrap_align(sp: Series, meas: Series):
    """Allinea l'imbardata del setpoint a quella misurata (niente salti di 2π)."""
    y_m = np.unwrap(meas.y)
    sp_on_m = np.interp(sp.t, meas.t, y_m)
    diff = np.angle(np.exp(1j * (sp.y - sp_on_m)))
    return Series(sp.t, sp_on_m + diff), Series(meas.t, y_m)


def _fraction(series: Series | None, intervals, predicate):
    if series is None or len(series) == 0:
        return None
    mask = dsp.mask_from_intervals(series.t, intervals)
    if np.count_nonzero(mask) < 10:
        return None
    return float(np.count_nonzero(predicate(series.y[mask])) / np.count_nonzero(mask) * 100.0)


def _noise_rms(segs, fs, key="u", f_lo=30.0):
    if fs / 2 < f_lo * 1.5:
        return None
    acc = dsp.SpectralAccumulator(1)
    nper = min(dsp.next_pow2(int(fs)), 1024)
    for s in segs:
        if s.get(key) is not None and len(s[key]) >= nper:
            acc.add([s[key]], fs, nper)
    got = acc.get()
    if got is None:
        return None
    f, auto, _c, _n = got
    return dsp.band_rms(f, auto[0], f_lo, 0.9 * fs / 2)


def _oscillation(segs, fs):
    """Picco stretto nello spettro dell'errore di tracking, rispetto al fondo locale."""
    acc = dsp.SpectralAccumulator(1)
    nper = min(dsp.next_pow2(int(2 * fs)), 2048)
    for s in segs:
        e = s["r"] - s["y"]
        if len(e) >= nper:
            acc.add([e], fs, nper)
    got = acc.get()
    if got is None:
        return None
    f, auto, _c, _n = got
    p = np.maximum(auto[0], 1e-20)
    df = f[1] - f[0]
    total = dsp.band_rms(f, p, 0.2, 0.9 * fs / 2)
    best = None
    for k in np.flatnonzero((f >= 4.0) & (f <= min(0.8 * fs / 2, 150.0))):
        if k == 0 or k >= len(p) - 1 or p[k] < p[k - 1] or p[k] < p[k + 1]:
            continue
        local = (f >= f[k] / 1.5) & (f <= f[k] * 1.5) & (np.abs(f - f[k]) > 2.5 * df)
        if np.count_nonzero(local) < 4:
            continue
        prom = 10 * np.log10(p[k] / np.median(p[local]))
        if best is None or prom > best[1]:
            best = (k, prom)
    if best is None:
        return None
    k, prom = best
    rms = dsp.band_rms(f, p, f[k] - 2 * df, f[k] + 2 * df)
    return {"freq": float(f[k]), "prominence_db": float(prom), "rms": rms,
            "fraction": float(rms / total) if total and total > 0 else 0.0}


AUTOTUNE_ACTIVE = {2, 3, 5, 6, 8, 9, 13}


def _exogenous_intervals(log):
    """Tratti in cui il setpoint di rate è già esterno all'anello d'assetto.

    vehicle_control_mode con velocità angolare attiva e assetto spento (Acro e Offboard a velocità angolare; se il
    topic manca, Acro), più l'eccitazione dell'autotune.
    """
    out = list(modes.rate_external_intervals(log))
    s = log.series("autotune_attitude_control_status", "state")
    if s is not None:
        out += dsp.intervals_where(s.t, np.isin(s.y.astype(int), list(AUTOTUNE_ACTIVE)), log.duration)
    return dsp.merge_close(out, 0.0)


def _pick_integrator(log, intervals, field_name):
    best, best_sd = None, -1.0
    for inst in log.instances("rate_ctrl_status"):
        s = log.series("rate_ctrl_status", field_name, inst)
        if s is None:
            continue
        mask = dsp.mask_from_intervals(s.t, intervals)
        if np.count_nonzero(mask) < 10:
            continue
        sd = float(np.std(s.y[mask]))
        if sd > best_sd:
            best, best_sd = s, sd
    return best


# --------------------------------------------------------------------- analisi


def analyze(log: LogData, phase="MC", loop="rate", time_range=None, profile=None) -> AnalysisResult:
    profile = profile or scoring.default_profile()
    key = loop_key(phase, loop)
    warnings = []
    phase_total = dsp.total_length(log.phase_intervals(phase)) if phase != "ALL" else log.duration
    phase_iv = log.phase_intervals(phase if phase != "ALL" else "ALL")
    if log.airborne_known:
        intervals = dsp.intersect(phase_iv, log.airborne)
    else:
        intervals = phase_iv
        warnings.append(_("Il log non permette di distinguere volo e terra: analizzato tutto il tratto selezionato."))
    if time_range is not None:
        intervals = dsp.intersect(intervals, [tuple(time_range)])
    if loop == "att":
        # senza flag_control_attitude_enabled il setpoint d'assetto non viene pubblicato (Offboard a velocità
        # angolare, Acro): il valore rimasto fermo non è un dato
        att_iv = modes.attitude_setpoint_intervals(log)
        if att_iv is not None:
            intervals = dsp.intersect(intervals, att_iv)
    intervals = _trim(intervals)
    total = dsp.total_length(intervals)
    if phase == "ALL" and len({p for _, _, p in log.phases}) > 1:
        warnings.append(
            _("Il log contiene più fasi (multicottero/ala fissa): analizzarle insieme mescola controllori diversi.")
        )
    axes = {}
    for axis in scoring.AXES:
        if phase_total <= 0:
            ar = AxisResult(axis, key, False, reason=_("il log non contiene volo in modalità {fase}").format(
                fase=_(PHASES[phase]).lower()))
        elif total <= 0:
            ar = AxisResult(axis, key, False, reason=_("nessun tratto in volo nella fase e nell'intervallo scelti"))
        else:
            ar = _analyze_axis(log, axis, phase, loop, key, intervals, profile)
        if ar.card is None:
            ar.card = scoring.build_scorecard(key, {}, {}, {}, profile)
            ar.card.confidence = "—"
        axes[axis] = ar
    reliable = {a: r.card for a, r in axes.items() if r.card is not None and r.card.confidence in ("alta", "media")}
    indicative = not reliable
    cards = reliable or {a: r.card for a, r in axes.items()}
    score = scoring.combine_axes(cards)
    if indicative and score is not None:
        warnings.append(_("Tutti gli assi hanno affidabilità bassa: il punteggio complessivo è solo indicativo."))
    elif len(reliable) < sum(1 for r in axes.values() if r.available):
        warnings.append(_("Gli assi con affidabilità bassa sono esclusi dal punteggio complessivo."))
    if 0 < total < 5:
        warnings.append(_("Solo {t:.1f} s di volo utile nella fase scelta.").format(t=total))
    return AnalysisResult(log.name, phase, loop, key, intervals, total, axes, score, scoring.grade(score), warnings)


def _analyze_axis(log, axis, phase, loop, key, intervals, profile):
    res = AxisResult(axis, key, False)
    params = log.params
    res.extras["_params"] = params
    target, tnote = scoring.rise_target(key, axis, params, profile)
    res.target_rise, res.target_note = target, tnote
    show = float(np.clip(5.0 * target, 0.5, 3.0))
    scheda = scoring.definitions(profile, key) == "scheda"
    spec = scoring.step_spec(profile, key, axis) if scheda else None
    if spec is not None:
        show = float(min(3.0, max(show, spec["dur"] + 0.1)))  # la finestra deve coprire il gradino nominale
    taps = float(np.clip(2.0 * show, 1.0, 4.0))
    min_exc = float(profile["loops"][key].get("min_excitation", 0.1))

    z = None
    if key == "fw_att" and axis == "yaw":
        res.reason = _("in ala fissa l'imbardata non ha un anello d'assetto (coordinazione di virata)")
        res.card = scoring.build_scorecard(key, {}, {}, {}, profile)
        res.card.confidence = "—"
        return res
    if loop == "rate":
        sp_c, meas_c, torque_c = _rate_sources(log, axis, phase)
        sp, sp_name = log.first_series(sp_c)
        meas, meas_name = log.first_series(meas_c, use_sample=True)
        u, u_name = log.first_series(torque_c, use_sample=True)
        cap = 500.0
        if not (phase == "FW" and axis == "yaw"):
            z, _zn, _m, _mn = _attitude_pair(log, axis)
            if z is not None and axis == "yaw":
                z = Series(z.t, np.unwrap(z.y))
    else:
        sp, sp_name, meas, meas_name = _attitude_pair(log, axis)
        u = u_name = None
        cap = 100.0
        if sp is not None and meas is not None and axis == "yaw":
            sp, meas = _wrap_align(sp, meas)
    if sp is None or meas is None:
        res.reason = _("setpoint o misura non presenti nel log")
        res.card = scoring.build_scorecard(key, {}, {}, {}, profile)
        res.card.confidence = "—"
        return res
    res.sources = {_("setpoint"): sp_name, _("misura"): meas_name}
    if u is not None:
        res.sources[_("comando")] = u_name
    fs_sp, fs_m = dsp.median_rate(sp.t), dsp.median_rate(meas.t)
    fs = float(min(cap, max(fs_sp, fs_m)))
    if fs < 10:
        res.reason = _("frequenza di log troppo bassa")
        res.card = scoring.build_scorecard(key, {}, {}, {}, profile)
        return res
    res.fs = fs
    series = {"r": sp, "y": meas}
    methods = {"r": "zoh", "y": "linear", "u": "zoh"}
    if u is not None:
        series["u"] = u
    if z is not None and len(z) > 10:
        series["z"] = z
        methods["z"] = "zoh"
    segs = _segments_for(intervals, series, fs, methods, 3 * taps)
    if "z" in series:
        exo = _exogenous_intervals(log)
        for s in segs:
            if exo:
                m = dsp.mask_from_intervals(s["t"], exo)
                s["z"] = np.where(m, s["r"], s["z"])
        res.sources[_("strumento")] = _("setpoint d'assetto (anello esterno)")
    # 50 ms dopo ogni cambio di modo: setpoint fuori scala per un ciclo e motori saturi. Quei campioni escono
    # dalle equazioni (il tratto non viene spezzato) e nel setpoint il picco viene sostituito dall'interpolazione.
    excluded = modes.transient_windows(log)
    res.extras["excluded"] = excluded
    n_excl = 0
    for s in segs:
        m = dsp.mask_from_intervals(s["t"], excluded) if excluded else np.zeros(len(s["t"]), bool)
        s["w"] = ~m
        n_excl += int(np.count_nonzero(m))
        modes.fill_excluded(s, m, ("r", "z"))
    res.extras["excluded_samples"] = n_excl
    res.used_time = float(sum(np.count_nonzero(s["w"]) for s in segs) / fs)
    if not segs:
        res.reason = _("nessun tratto di volo abbastanza lungo (servono almeno {s:.0f} s continui) nella fase scelta"
                       ).format(s=3 * taps)
        res.card = scoring.build_scorecard(key, {}, {}, {}, profile)
        res.card.confidence = "bassa"
        return res
    est = loopid.estimate_loop(segs, fs, taps_s=taps, resp_len=show, min_excitation=min_exc,
                               f_max=80.0 if loop == "rate" else 20.0)
    if est is None:
        res.reason = _("stima non riuscita")
        res.card = scoring.build_scorecard(key, {}, {}, {}, profile)
        return res
    res.available = True
    res.est = est
    res.step, res.spread = loopid.step_metrics_spread(est)
    res.freq = loopid.freq_metrics(est)
    if spec is not None:
        res.extras["cmd"], res.extras["cmd_spread"] = cmd_metrics(est, spec)
        res.extras["spec"] = spec

    # gradini misurati direttamente (per l'affidabilità e per la saturazione con il profilo della scheda)
    kind = "rate" if loop == "rate" else "att"
    if phase in ("MC", "ALL") and axis in steptest.AXES_OF[kind]:
        res.extras["steps"] = _steps_for(log, kind, axis, intervals, profile)

    # margini (solo rate multicottero: modello del controllore PX4 noto)
    if key == "mc_rate" and u is not None:
        pref = scoring.RATE_PARAM_PREFIX[axis]
        kp, ki, kd = (params.get(f"{pref}_{x}") for x in ("P", "I", "D"))
        kk = params.get(f"{pref}_K", 1.0)
        if None not in (kp, ki, kd):
            ctrl = lambda f, kp=kp, ki=ki, kd=kd, kk=kk: loopid.mc_rate_controller(
                f, kp, ki, kd, kk, params.get("IMU_DGYRO_CUTOFF", 20.0)
            )
            res.margins = loopid.loop_margins(est, ctrl)
        else:
            res.margins = loopid.Margins(False, _("guadagni del rate controller non presenti nei parametri"))
        changed = {k for _, k, _ in log.param_changes if k.startswith(pref) or k == "IMU_DGYRO_CUTOFF"}
        if changed:
            res.extras["param_changed"] = sorted(changed)

    # grandezze aggiuntive
    sat_iv, sat_where = intervals, "all"
    st = res.extras.get("steps")
    if spec is not None and st and st["windows"]:
        sat_iv, sat_where = st["windows"], "steps"
    if loop == "rate" or spec is not None:
        # saturazione dalle uscite a piena frequenza (actuator_motors, tilt usati per il controllo), non da
        # control_allocator_status (registrato a 5 Hz)
        sat = modes.saturation(log, sat_iv, excluded, phase if phase != "ALL" else "ALL")
        res.extras["saturation"] = None if sat is None else sat["percent"]
        res.extras["saturation_detail"] = None if sat is None else sat["detail"]
        res.extras["saturation_where"] = sat_where
    if loop == "rate":
        res.extras["noise"] = _noise_rms(segs, fs) if u is not None else None
        ifield = f"{axis}speed_integ"
        integ = _pick_integrator(log, intervals, ifield)
        if phase == "FW":
            lim = params.get({"roll": "FW_RR_IMAX", "pitch": "FW_PR_IMAX", "yaw": "FW_YR_IMAX"}[axis])
        else:
            lim = params.get({"roll": "MC_RR_INT_LIM", "pitch": "MC_PR_INT_LIM", "yaw": "MC_YR_INT_LIM"}[axis])
        if integ is not None and lim:
            res.extras["integrator"] = _fraction(integ, intervals, lambda y: np.abs(y) >= 0.8 * float(lim))
            res.extras["integrator_series"] = integ
            res.extras["integrator_limit"] = float(lim)
    res.extras["oscillation"] = _oscillation(segs, fs)
    res.extras["segments"] = segs

    _score(res, key, profile)
    return res


def _score(res: AxisResult, key, profile):
    st, sp = res.step, res.spread
    tgt = res.target_rise or 1.0
    values, spreads, notes = {}, {}, {}
    if scoring.definitions(profile, key) == "scheda":
        _score_scheda(res, key, profile, values, spreads, notes)
    elif st is not None:
        values["overshoot"] = st.overshoot
        spreads["overshoot"] = sp.get("overshoot")
        if st.rise_time is not None:
            values["rise_ratio"] = st.rise_time / tgt
            spreads["rise_ratio"] = sp["rise_time"] / tgt if sp.get("rise_time") is not None else None
            notes["rise_ratio"] = _("t salita {tr:.0f} ms, obiettivo {tg:.0f} ms ({nota})").format(
                tr=st.rise_time * 1000, tg=tgt * 1000, nota=res.target_note)
        else:
            values["rise_ratio"] = float("inf")
        if st.settling_time is not None:
            values["settling_ratio"] = st.settling_time / tgt
            spreads["settling_ratio"] = sp["settling_time"] / tgt if sp.get("settling_time") is not None else None
            notes["settling_ratio"] = _("t assestamento {ts:.0f} ms").format(ts=st.settling_time * 1000)
        else:
            values["settling_ratio"] = float("inf")
            notes["settling_ratio"] = _("non assestato entro la finestra di risposta")
        values["ss_error"] = st.ss_error
        spreads["ss_error"] = sp.get("ss_error")
        notes["ss_error"] = _("livello a fine finestra {v:.3f}").format(v=st.final)
    fm = res.freq
    if fm is not None and fm.resonance_db is not None and fm.f_valid_max >= 2.0:
        values["resonance"] = max(0.0, fm.resonance_db)
        notes["resonance"] = _("a {f:.1f} Hz").format(f=fm.resonance_f)
    mg = res.margins
    if mg is not None and mg.valid:
        values["phase_margin"] = mg.phase_margin_deg
        spreads["phase_margin"] = mg.pm_sd
        notes["phase_margin"] = _("attraversamento a {f:.1f} Hz").format(f=mg.crossover_hz)
    elif mg is not None:
        notes["phase_margin"] = mg.reason
    for k in ("noise", "saturation", "integrator"):
        if res.extras.get(k) is not None:
            values[k] = res.extras[k]
    if res.extras.get("noise") is None:
        notes["noise"] = _("serve il comando di coppia registrato ad almeno 90 Hz")
    if res.extras.get("saturation") is not None:
        det = modes.describe_saturation(res.extras.get("saturation_detail") or {}, _("al minimo"), _("al massimo"))
        where = (_("nelle finestre dei gradini validi") if res.extras.get("saturation_where") == "steps"
                 else _("su tutto il tratto analizzato"))
        notes["saturation"] = where + (f" — {det}" if det else "")
    card = scoring.build_scorecard(key, values, spreads, notes, profile, res.axis)
    card.confidence, card.confidence_reasons = _confidence(res, profile)
    card.diagnostics = diagnostics(res, card, profile)
    if card.confidence == "bassa" and card.diagnostics:
        card.diagnostics.insert(0, _("Stima poco affidabile: le indicazioni che seguono vanno confermate con le "
                                     "prove a gradino."))
    res.card = card


def cmd_metrics(est: loopid.LoopEstimate, spec):
    """Grandezze della scheda sulla risposta stimata: gradino unitario = ampiezza comandata, comando al 50% a t = 0.

    Stesse definizioni (e stessa funzione) dei gradini misurati: steptest.measure_response.
    """
    amp, dur, band = spec["amp"], spec["dur"], spec["band"]
    band = band if spec["absolute_band"] else amp * spec["band_pct"] / 100.0
    kw = dict(err_last=spec["err_last"], err_from=spec["err_from"], err_abs=spec["absolute_band"])

    # il setpoint è portato sulla griglia con un mantenimento (zoh): i suoi fronti vi compaiono in media mezzo
    # campione dopo l'istante vero, quindi la risposta stimata va spostata di mezzo campione in avanti
    t = est.t + 0.5 / est.fs

    def one(step):
        r = steptest.measure_response(t, step * amp, amp, 0.0, dur, band, **kw)
        if r is None:
            return None
        return {"delay": r.delay, "overshoot": r.overshoot,
                "settling": math.inf if r.settling is None else r.settling, "end_error": r.end_error,
                "bounces": float(r.bounces), "level_end": r.level_end}

    main = one(est.step) or {}
    reps = [one(s) for s in est.step_reps] if est.step_reps.shape[0] >= 3 else []
    spread = {}
    for k in main:
        vals = [r.get(k) for r in reps if r is not None]
        if len(vals) < 3 or any(v is None or not math.isfinite(v) for v in vals):
            spread[k] = None
            continue
        v = np.array(vals, float)
        n = len(v)
        spread[k] = float(np.sqrt((n - 1) / n * np.sum((v - v.mean()) ** 2)))
    return main, spread


def _score_scheda(res, key, profile, values, spreads, notes):
    cm, sd = res.extras.get("cmd") or {}, res.extras.get("cmd_spread") or {}
    spec = res.extras.get("spec") or scoring.step_spec(profile, key, res.axis)
    unit = "°/s" if key == "mc_rate" else "°"
    if not cm:
        return
    values["delay"], spreads["delay"] = cm.get("delay"), sd.get("delay")
    values["overshoot_cmd"], spreads["overshoot_cmd"] = cm.get("overshoot"), sd.get("overshoot")
    values["settling_band"], spreads["settling_band"] = cm.get("settling"), sd.get("settling")
    ek = "end_error_deg" if spec["absolute_band"] else "end_error"
    values[ek], spreads[ek] = cm.get("end_error"), sd.get("end_error")
    values["bounces"], spreads["bounces"] = cm.get("bounces"), sd.get("bounces")
    band_txt = (f"±{spec['band']:g}°" if spec["absolute_band"] else f"±{spec['band_pct']:g}%")
    ref = _("gradino stimato di {a:g} {u} per {d:g} s").format(a=spec["amp"], u=unit, d=spec["dur"])
    notes["delay"] = ref
    notes["overshoot_cmd"] = ref
    if cm.get("settling") is not None and not math.isfinite(cm["settling"]):
        notes["settling_band"] = _("non assestato entro la fine del gradino (fascia {f})").format(f=band_txt)
    else:
        notes["settling_band"] = _("fascia {f} del comando").format(f=band_txt)
    if cm.get("level_end") is not None:
        notes[ek] = _("livello a fine gradino {v:.0f}% del comando").format(v=cm["level_end"] * 100)
    mg = res.margins
    if mg is not None and mg.valid:
        values["phase_margin"] = mg.phase_margin_deg
        spreads["phase_margin"] = mg.pm_sd
        notes["phase_margin"] = _("attraversamento a {f:.1f} Hz").format(f=mg.crossover_hz)
    elif mg is not None:
        notes["phase_margin"] = mg.reason
    if res.extras.get("saturation") is not None:
        values["saturation"] = res.extras["saturation"]


def _steps_for(log, kind, axis, intervals, profile):
    """Gradini validi di quest'asse dentro gli intervalli analizzati: conteggi per verso e finestre."""
    key = ("_steps_cache", id(profile) if "gradini" in profile else 0)
    if key not in log._cache:
        try:
            log._cache[key] = steptest.detect(log, steptest.step_profile(profile))
        except Exception:  # noqa: BLE001 - senza gradini l'analisi FIR resta valida
            log._cache[key] = None
    res = log._cache[key]
    out = {"pos": 0, "neg": 0, "windows": [], "amp": None, "unit": steptest.UNITS[kind]}
    # volo di prove a gradino: tratti con il comando dato da script o stick per l'asse (Acro, Offboard)
    if kind == "rate":
        ext = modes.rate_external_intervals(log)
    else:  # lo Stabilized è anche volo normale: conta solo l'Offboard d'assetto
        offb = [(a, b) for a, b, v in log.modes if v == modes.NAV_OFFBOARD]
        ext = dsp.intersect(modes.attitude_step_intervals(log), offb)
    out["step_flight"] = dsp.total_length(dsp.intersect(ext, intervals)) > 0
    if res is None:
        return out
    prof = steptest.step_profile(profile)
    out["amp"] = scoring.step_spec(prof, steptest.LOOP_OF[kind], axis)["amp"]
    out["need"] = int(steptest._settings(prof, "gradini").get("min_validi_per_verso", 3))
    for s in res.valid_steps(kind, axis):
        if not any(a <= s.t_start and s.t_end <= b for a, b in intervals):
            continue
        out["pos" if s.sign > 0 else "neg"] += 1
        out["windows"].append(s.sat_window)
    out["windows"] = dsp.merge_close(sorted(out["windows"]), 0.0)
    return out


def _what_to_fly(st):
    """«3 doppietti a 45 °/s» per l'asse (ampiezza dal profilo della scheda)."""
    if not st or st.get("amp") is None:
        return ""
    return _("volare {n} doppietti a {a:g} {u}, partendo in piano e da fermo").format(
        n=st.get("need", 3), a=st["amp"], u=st["unit"])


def _confidence(res: AxisResult, profile=None):
    levels = {"alta": 2, "media": 1, "bassa": 0}
    worst = 2
    why = []
    est = res.est
    st = res.extras.get("steps")
    n_pos, n_neg = (st["pos"], st["neg"]) if st else (0, 0)
    need = st.get("need", 3) if st else 3
    # livello dai gradini validi: con le prove a gradino contano i gradini, non i secondi di manovre, così non si
    # spinge a dare tanti gradini piccoli fuori dai criteri della scheda
    if n_pos >= need and n_neg >= need:
        lev_steps, why_steps = 2, None
    else:
        lev_steps = 1 if n_pos + n_neg >= need else 0
        why_steps = _("{p} gradini validi nel verso + e {n} nel verso − (ne servono {k} per verso): {cosa}").format(
            p=n_pos, n=n_neg, k=need, cosa=_what_to_fly(st))
    # livello dalla quantità di manovre (voli senza prove a gradino)
    if est.excited_time >= 20:
        lev_exc, why_exc = 2, None
    elif est.excited_time >= 8:
        lev_exc = 1
        why_exc = _("eccitazione limitata: {s:.0f} s di manovre utili (consigliati ≥ 20 s)").format(s=est.excited_time)
    else:
        lev_exc = 0
        why_exc = _("eccitazione scarsa: {s:.0f} s di manovre utili (consigliati ≥ 20 s)").format(s=est.excited_time)
    if st and st.get("step_flight"):
        # volo di prove a gradino (Acro / Offboard): vale solo il conteggio dei gradini validi
        worst = lev_steps
        if why_steps:
            why.append(why_steps)
    elif n_pos + n_neg > 0 and lev_steps >= lev_exc:
        worst = lev_steps
        if why_steps:
            why.append(why_steps)
    else:
        worst = lev_exc
        if why_exc:
            hint = _what_to_fly(st)
            why.append(why_exc + (_(", oppure {cosa}").format(cosa=hint) if hint else ""))
    if est.n_blocks < 3:
        worst = 0
        why.append(_("dati troppo brevi per stimare l'incertezza"))
    if res.step is not None and res.step.rise_time:
        spr = res.step.rise_time * res.fs
        if spr < 4:
            worst = 0
            why.append(_("frequenza di log bassa ({f:.0f} Hz): meno di 4 campioni nel tempo di salita").format(f=res.fs))
        elif spr < 8:
            worst = min(worst, 1)
            why.append(_("frequenza di log modesta ({f:.0f} Hz): abilitare il profilo di log ad alta frequenza").format(
                f=res.fs))
    ov_sd = (res.extras.get("cmd_spread") or {}).get("overshoot") if res.extras.get("cmd") else res.spread.get(
        "overshoot")
    if ov_sd is not None:
        if ov_sd > 10:
            worst = 0
            why.append(_("stima dispersa (sovraelongazione ± {s:.0f} punti)").format(s=ov_sd))
        elif ov_sd > 5:
            worst = min(worst, 1)
            why.append(_("stima moderatamente dispersa (sovraelongazione ± {s:.0f} punti)").format(s=ov_sd))
    if res.card is not None and res.card.coverage < 0.8:
        worst = min(worst, 1)
    if res.extras.get("param_changed"):
        worst = min(worst, 1)
        why.append(_("guadagni modificati durante il volo: il risultato mescola tarature diverse"))
    name = {v: k for k, v in levels.items()}[worst]
    return name, why


# ------------------------------------------------------------------ diagnosi


def _pnames(key, axis):
    if key == "mc_rate":
        p = scoring.RATE_PARAM_PREFIX[axis]
        return {"P": f"{p}_P", "I": f"{p}_I", "D": f"{p}_D", "FF": f"{p}_FF", "LIM": {"roll": "MC_RR_INT_LIM", "pitch": "MC_PR_INT_LIM", "yaw": "MC_YR_INT_LIM"}[axis]}
    if key == "fw_rate":
        p = scoring.FW_RATE_PREFIX[axis]
        return {"P": f"{p}_P", "I": f"{p}_I", "D": f"{p}_D", "FF": f"{p}_FF", "LIM": f"{p}_IMAX"}
    if key == "mc_att":
        return {"P": scoring.MC_ATT_PARAM[axis]}
    return {"TC": scoring.FW_TC_PARAM[axis]}


def _level_high_action(res, n):
    """Risposta che a fine finestra supera il comando: FF solo se è davvero usato, altrimenti la coda dell'integratore."""
    ff = float(paramsafe(res, n["FF"]) or 0.0) if "FF" in n else 0.0
    if "FF" in n and ff > 0:
        return _("ridurre {ff} (ora {v:g})").format(ff=n["FF"], v=ff)
    if "I" in n:
        return _("con {ff} = 0 è la coda dell'integratore, cioè una risposta lenta che carica l'integratore: aumentare "
                 "{p} oppure ridurre {i}").format(ff=n.get("FF", "FF"), p=n["P"], i=n["I"])
    return _("verificare l'integratore dell'anello di rate")


def diagnostics(res: AxisResult, card, profile):
    """Indicazioni testuali derivate dalle metriche (possibili azioni, non prescrizioni)."""
    key = res.loop_key
    if scoring.definitions(profile, key) == "scheda":
        return _diagnostics_scheda(res, card, profile)
    th = scoring.loop_metrics(profile, key, res.axis)
    items = {i.key: i for i in card.items}
    n = _pnames(key, res.axis)
    out = []
    st = res.step
    if st is None:
        return [res.reason] if res.reason else []

    def bad(k, level="ok"):
        it = items.get(k)
        if it is None or it.value is None:
            return False
        good, ok, worst = it.thresholds
        v = it.value
        lim = ok if level == "ok" else good
        return v < lim if good > worst else v > lim

    pm = res.margins.phase_margin_deg if (res.margins and res.margins.valid) else None
    ov = st.overshoot
    if bad("overshoot"):
        if key == "mc_rate":
            d_used = float(paramsafe(res, n["D"]) or 0.0) > 0
            if pm is not None and pm < th.get("phase_margin", {"ok": 35})["ok"]:
                txt = _("Sovraelongazione {ov:.0f}% con margine di fase di {pm:.0f}°: anello poco smorzato. "
                        "Possibili azioni: ridurre {p} del 10–20%").format(ov=ov, pm=pm, p=n["P"])
                if d_used:
                    txt += _(" oppure aumentare {d}").format(d=n["D"])
                out.append(txt + ".")
            elif d_used:
                out.append(_("Sovraelongazione {ov:.0f}%: possibili azioni: aumentare {d} o ridurre {p}.").format(
                    ov=ov, d=n["D"], p=n["P"]))
            else:
                out.append(_("Sovraelongazione {ov:.0f}%: possibili azioni: ridurre {p}.").format(ov=ov, p=n["P"]))
        elif key == "fw_rate":
            if float(paramsafe(res, n["FF"]) or 0.0) > 0:
                out.append(_("Sovraelongazione {ov:.0f}%: ridurre {ff} (se la risposta anticipa) o {p}.").format(
                    ov=ov, ff=n["FF"], p=n["P"]))
            else:
                out.append(_("Sovraelongazione {ov:.0f}%: possibili azioni: ridurre {p}.").format(ov=ov, p=n["P"]))
        elif key == "mc_att":
            out.append(_("Sovraelongazione dell'assetto {ov:.0f}%: ridurre {p} o verificare prima l'anello di rate."
                         ).format(ov=ov, p=n["P"]))
        else:
            out.append(_("Sovraelongazione dell'assetto {ov:.0f}%: aumentare {tc} per una risposta più morbida "
                         "o verificare l'anello di rate.").format(ov=ov, tc=n["TC"]))
    if bad("rise_ratio") and not bad("overshoot", "good"):
        tr = f"{st.rise_time * 1000:.0f} ms" if st.rise_time else _("n.d.")
        what = {"mc_rate": _("aumentare {p}").format(p=n.get("P")),
                "fw_rate": _("aumentare {ff} o {p}").format(ff=n.get("FF"), p=n.get("P")),
                "mc_att": _("aumentare {p}").format(p=n.get("P")),
                "fw_att": _("ridurre {tc}").format(tc=n.get("TC"))}[key]
        out.append(_("Risposta lenta (salita {tr} contro obiettivo {tg:.0f} ms): {azione}.").format(
            tr=tr, tg=res.target_rise * 1000, azione=what))
    if bad("ss_error"):
        if st.final < 1:
            what = {"mc_rate": _("aumentare {i}").format(i=n.get("I")),
                    "fw_rate": _("aumentare {ff} o {i}").format(ff=n.get("FF"), i=n.get("I")),
                    "mc_att": _("verificare l'integratore dell'anello di rate"),
                    "fw_att": _("verificare FF/I dell'anello di rate")}[key]
            out.append(_("Il livello a fine finestra si ferma al {v:.0f}% del comando: {azione}.").format(
                v=st.final * 100, azione=what))
        else:
            out.append(_("Il livello a fine finestra supera il comando ({v:.0f}%): {azione}.").format(
                v=st.final * 100, azione=_level_high_action(res, n)))
    if bad("settling_ratio") and not bad("overshoot"):
        if "I" in n:
            out.append(_("Assestamento lento con poca sovraelongazione: tipico di un integratore lento, valutare {i} "
                         "più alto.").format(i=n["I"]))
        else:
            out.append(_("Assestamento lento con poca sovraelongazione: tipico di un integratore lento."))
    if bad("resonance"):
        fm = res.freq
        out.append(_("Picco di risonanza in anello chiuso di {db:.1f} dB a {f:.1f} Hz: smorzamento insufficiente.").format(
            db=fm.resonance_db, f=fm.resonance_f))
    if bad("saturation"):
        out.append(_("Motori al limite per il {v:.1f}% del tempo: il controllore chiede più coppia di quella "
                     "disponibile (manovre troppo aggressive o margine di spinta ridotto).").format(
            v=res.extras["saturation"]))
    _common_tail(res, key, items, out, pm, bad)
    if not out:
        out.append(_("Nessun problema rilevato su questo asse."))
    return out


def _common_tail(res, key, items, out, pm, bad):
    """Indicazioni comuni ai due tipi di profilo (margini, rumore, integratore, oscillazione, cambi di parametri)."""
    n = _pnames(key, res.axis)
    if bad("phase_margin"):
        out.append(_("Margine di fase {pm:.0f}° sotto il minimo consigliato: rischio di oscillazioni con raffiche o "
                     "variazioni di massa.").format(pm=pm))
    if bad("noise"):
        out.append(_("Rumore elevato sul comando di coppia sopra 30 Hz: ridurre {d} o IMU_DGYRO_CUTOFF, "
                     "controllare vibrazioni e filtri notch.").format(d=n["D"]) if "D" in n else
                   _("Rumore elevato sul comando di coppia sopra 30 Hz: ridurre IMU_DGYRO_CUTOFF, controllare "
                     "vibrazioni e filtri notch."))
    if bad("integrator"):
        out.append(_("Integratore oltre l'80% del limite per il {v:.1f}% del tempo: possibile sbilanciamento "
                     "(baricentro, eliche, trim) o limite {lim} troppo basso.").format(
            v=res.extras["integrator"], lim=n.get("LIM", "")))
    osc = res.extras.get("oscillation")
    if osc and osc["prominence_db"] >= 10 and osc["fraction"] >= 0.15:
        out.append(_("Picco stretto nell'errore di tracking a {f:.1f} Hz ({db:.0f} dB sopra il fondo): possibile "
                     "oscillazione o vibrazione strutturale.").format(f=osc["freq"], db=osc["prominence_db"]))
    if res.margins is not None and not res.margins.valid and key == "mc_rate":
        out.append(_("Margini di stabilità non stimabili: {motivo}. Per stimarli servono impulsi brevi e netti sullo "
                     "stick o l'eccitazione dell'autotune con MC_AT_APPLY = 0.").format(motivo=res.margins.reason))
    if res.extras.get("param_changed"):
        out.append(_("Parametri del controllore cambiati durante il volo ({nomi}): restringere l'analisi a un "
                     "intervallo con una sola taratura.").format(nomi=", ".join(res.extras["param_changed"])))


def _diagnostics_scheda(res: AxisResult, card, profile):
    """Indicazioni con le definizioni della scheda di taratura (soglia «ok» = criterio della scheda)."""
    key = res.loop_key
    items = {i.key: i for i in card.items}
    n = _pnames(key, res.axis)
    cm = res.extras.get("cmd") or {}
    out = []
    if not cm:
        return [res.reason] if res.reason else []

    def over(k):
        it = items.get(k)
        return it is not None and it.value is not None and it.value > it.thresholds[1] + 1e-12

    def lim(k):
        return items[k].thresholds[1]

    def bad(k):
        it = items.get(k)
        if it is None or it.value is None:
            return False
        good, ok, worst = it.thresholds
        return it.value < ok if good > worst else it.value > ok

    rate = key == "mc_rate"
    d_used = float(paramsafe(res, n.get("D", "")) or 0.0) > 0 if rate else False
    ov, dl, lvl = cm.get("overshoot"), cm.get("delay"), cm.get("level_end")
    if over("overshoot_cmd"):
        if rate:
            txt = _("Sovraelongazione {ov:.0f}% rispetto al comando (criterio ≤ {c:g}%): ridurre {p}").format(
                ov=ov, c=lim("overshoot_cmd"), p=n["P"])
            out.append(txt + (_(" oppure aumentare {d}").format(d=n["D"]) if d_used else "") + ".")
        else:
            out.append(_("Sovraelongazione dell'assetto {ov:.0f}% (criterio ≤ {c:g}%): ridurre {p} o verificare prima "
                         "l'anello di rate.").format(ov=ov, c=lim("overshoot_cmd"), p=n["P"]))
    if over("delay"):
        txt = _("Ritardo {d:.0f} ms (criterio ≤ {c:.0f} ms): aumentare {p}").format(
            d=dl * 1000, c=lim("delay") * 1000, p=n["P"])
        if over("overshoot_cmd"):
            txt += _(", ma la sovraelongazione è già oltre il criterio: prima ridurla")
        out.append(txt + ".")
    ek = "end_error_deg" if "end_error_deg" in items else "end_error"
    level_action = None
    if lvl is not None and (over(ek) or over("settling_band")):
        if lvl < 1:
            level_action = (_("aumentare {i}").format(i=n["I"]) if "I" in n
                            else _("verificare l'integratore dell'anello di rate"))
            what = _("la risposta a fine gradino è al {v:.0f}% del comando: {azione}").format(
                v=lvl * 100, azione=level_action)
        else:
            level_action = _level_high_action(res, n)
            what = _("la risposta a fine gradino è al {v:.0f}% del comando: {azione}").format(
                v=lvl * 100, azione=level_action)
        if over(ek):
            unit = "°" if ek == "end_error_deg" else "%"
            out.append(_("Errore a fine gradino {e:.1f} {u} (criterio ≤ {c:g} {u}): {cosa}.").format(
                e=cm["end_error"], u=unit, c=lim(ek), cosa=what))
    if over("settling_band"):
        st = cm.get("settling")
        head = (_("Non assestato entro la fine del gradino") if st is None or not math.isfinite(st)
                else _("Assestamento {t:.0f} ms (criterio ≤ {c:.0f} ms)").format(t=st * 1000,
                                                                                  c=lim("settling_band") * 1000))
        if over("bounces") or over("overshoot_cmd"):
            out.append(head + _(": oscillazione poco smorzata (vedi sovraelongazione e rimbalzi)."))
        elif level_action is not None and not over(ek):
            out.append(head + ": " + level_action + ".")
        elif level_action is None:
            out.append(head + ".")
        else:
            out.append(head + _(": stessa causa dell'errore a fine gradino."))
    if over("bounces"):
        out.append(_("{b:.0f} rimbalzi fuori dalla fascia dopo il picco (criterio ≤ {c:g}): anello poco smorzato, "
                     "ridurre {p}{d}.").format(b=cm["bounces"], c=lim("bounces"), p=n["P"],
                                              d=_(" o aumentare {d}").format(d=n["D"]) if d_used else ""))
    if over("saturation"):
        out.append(_("Motori al limite per il {v:.1f}% del tempo (criterio ≤ {c:g}%): il controllore chiede più "
                     "coppia di quella disponibile; con i motori al minimo controllare baricentro e margine di "
                     "spinta.").format(v=res.extras["saturation"], c=lim("saturation")))
    pm = res.margins.phase_margin_deg if (res.margins and res.margins.valid) else None
    _common_tail(res, key, items, out, pm, bad)
    if not out:
        out.append(_("Tutte le grandezze della risposta stimata rispettano i criteri della scheda."))
    return out


def paramsafe(res, name):
    return res.extras.get("_params", {}).get(name, 0.0)
