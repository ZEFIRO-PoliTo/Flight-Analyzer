"""Tratti di volo per tipo di comando, transitori ai cambi di modo, saturazione degli attuatori.

Funzioni condivise dalla stima FIR (analysis) e dalle prove a gradino (steptest):

* quali tratti hanno il setpoint di velocità angolare «esterno» (Acro, Offboard a velocità
  angolare): lo dicono i flag di ``vehicle_control_mode`` (velocità angolare attiva, assetto spento);
* dove esiste davvero un setpoint d'assetto (``flag_control_attitude_enabled``);
* i cambi di modo (``nav_state`` e flag di controllo) e i 50 ms che li seguono, in cui PX4 pubblica
  setpoint fuori scala per un ciclo e i motori possono saturare: vanno tolti da stima, saturazione,
  eccitazione e gradini;
* la saturazione misurata sulle uscite (``actuator_motors`` a piena frequenza, servi dei tilt usati per
  il controllo), invece di ``control_allocator_status`` che è registrato solo a 5 Hz.
"""

from __future__ import annotations

import numpy as np

from . import dsp
from .logdata import LogData

TRANSIENT_S = 0.05  # s esclusi dopo ogni cambio di modo
NAV_ACRO, NAV_OFFBOARD, NAV_STAB = 10, 14, 15
SAT_LOW, SAT_HIGH = 0.02, 0.98


# ------------------------------------------------------------------ modo di controllo


def control_modes(log: LogData):
    """[(t0, t1, frozenset(flag attivi))] da vehicle_control_mode (flag senza il prefisso), o None."""
    key = "_control_modes"
    if key in log._cache:
        return log._cache[key]
    d = log.dataset("vehicle_control_mode")
    out = None
    if d is not None and len(d):
        names = [f for f in d.data if f.startswith("flag_control_")]
        if names:
            t = log._time(d, False)
            order = np.argsort(t, kind="stable")
            t = t[order]
            bits = np.array([d.data[n][order].astype(int) != 0 for n in names]).T
            codes = bits @ (1 << np.arange(len(names), dtype=np.int64))
            out = []
            for a, b, code in dsp.step_intervals(t, codes, log.duration):
                flags = frozenset(n[len("flag_control_"):] for i, n in enumerate(names) if int(code) >> i & 1)
                out.append((a, b, flags))
            if out:
                out[0] = (0.0, out[0][1], out[0][2])
    log._cache[key] = out
    return out


def control_intervals(log: LogData, require=(), forbid=()):
    """Intervalli con i flag ``require`` attivi e ``forbid`` spenti (es. "rates_enabled"); None se manca il topic."""
    cm = control_modes(log)
    if cm is None:
        return None
    req, forb = set(require), set(forbid)
    out = [(a, b) for a, b, fl in cm if req <= fl and not (forb & fl) and b > a]
    return dsp.merge_close(out, 0.0)


def _nav_intervals(log: LogData, states):
    return dsp.merge_close([(a, b) for a, b, v in log.modes if v in states and b > a], 0.0)


def rate_external_intervals(log: LogData):
    """Tratti con il setpoint di velocità angolare esterno all'anello d'assetto.

    vehicle_control_mode con velocità angolare attiva e assetto spento (Acro e Offboard a velocità
    angolare); se il topic manca, i tratti in Acro (nav_state 10).
    """
    iv = control_intervals(log, require=("rates_enabled",), forbid=("attitude_enabled",))
    return _nav_intervals(log, {NAV_ACRO}) if iv is None else iv


def attitude_setpoint_intervals(log: LogData):
    """Tratti in cui esiste un setpoint d'assetto (flag_control_attitude_enabled); None se il topic manca."""
    return control_intervals(log, require=("attitude_enabled",))


def attitude_step_intervals(log: LogData):
    """Tratti in cui il setpoint d'assetto viene dal pilota o dallo script: Stabilized, Offboard d'assetto."""
    stab = _nav_intervals(log, {NAV_STAB})
    offb = _nav_intervals(log, {NAV_OFFBOARD})
    att = control_intervals(log, require=("attitude_enabled",), forbid=("velocity_enabled", "position_enabled"))
    if att is not None:
        offb = dsp.intersect(offb, att)
    return dsp.merge_close(sorted(stab + offb), 0.0)


def change_times(log: LogData):
    """Istanti dei cambi di nav_state e dei flag di vehicle_control_mode (il primo stato non conta)."""
    times = [a for a, _b, _v in log.modes[1:]]
    cm = control_modes(log)
    if cm:
        times += [a for a, _b, _f in cm[1:]]
    return sorted(set(round(t, 6) for t in times))


def transient_windows(log: LogData, after=TRANSIENT_S):
    """[(t, t + after)] dopo ogni cambio di modo."""
    if not after or after <= 0:
        return []
    return dsp.merge_close([(t, t + after) for t in change_times(log)], 0.0)


def mode_name_at(log: LogData, t):
    from .logdata import NAV_STATES

    for a, b, v in log.modes:
        if a <= t < b:
            return NAV_STATES.get(v, str(v))
    return "—"


# ------------------------------------------------------------------ uscite e saturazione


def actuator_outputs(log: LogData, phase="MC"):
    """Uscite da controllare per la saturazione: [(etichetta, Series, tipo)] con tipo "motor" o "servo".

    Motori: actuator_motors.control[i] con valori finiti (0..1). Servi: in multicottero solo i tilt usati per
    il controllo (CA_SV_TLx_CT ≠ 0), in ala fissa le superfici di controllo; i tilt fermi a fine corsa in hover
    non sono una saturazione.
    """
    out = []
    for i in range(16 if phase in ("MC", "ALL") else 0):  # in ala fissa i motori di sostentamento sono spenti
        s = log.series("actuator_motors", f"control[{i}]")
        if s is None:
            if not log.has("actuator_motors", f"control[{i}]"):
                break
            continue
        out.append((f"M{i + 1}", s, "motor"))
    params = log.params
    n_cs = int(params.get("CA_SV_CS_COUNT", 0) or 0)
    servos = []
    if phase in ("MC", "ALL"):
        for k in range(int(params.get("CA_SV_TL_COUNT", 0) or 0)):
            if int(params.get(f"CA_SV_TL{k}_CT", 0) or 0) != 0:
                servos.append(n_cs + k)
    if phase in ("FW", "ALL"):
        servos += list(range(n_cs))
    for idx in sorted(set(servos)):
        s = log.series("actuator_servos", f"control[{idx}]")
        if s is not None:
            out.append((f"S{idx + 1}", s, "servo"))
    return out


def _limits(kind, y):
    if kind == "motor":
        return y <= SAT_LOW, y >= SAT_HIGH
    return y <= -SAT_HIGH, y >= SAT_HIGH


def saturation(log: LogData, intervals, exclude=(), phase="MC", outputs=None):
    """Quota di campioni con almeno un'uscita al limite, negli ``intervals`` meno ``exclude``.

    Restituisce None se non ci sono uscite, altrimenti dict(percent, samples, detail) con
    detail = {etichetta: (percentuale al minimo, percentuale al massimo)}. I campioni sono quelli di
    actuator_motors (piena frequenza); i servi vengono portati sugli stessi istanti.
    """
    if phase == "ALL" and outputs is None:
        # ogni tratto con le uscite della sua fase
        parts = [saturation(log, dsp.intersect(intervals, log.phase_intervals(ph)), exclude, ph) for ph in ("MC", "FW")]
        parts = [p for p in parts if p is not None]
        if not parts:
            return None
        n = sum(p["samples"] for p in parts)
        cnt = sum(p["count"] for p in parts)
        detail = {}
        for p in parts:
            for k, (lo, hi) in p["detail"].items():
                a, b = detail.get(k, (0.0, 0.0))
                detail[k] = (a + lo * p["samples"] / n, b + hi * p["samples"] / n)
        return {"percent": cnt / n * 100, "samples": n, "detail": detail, "count": cnt}
    outputs = actuator_outputs(log, phase) if outputs is None else outputs
    if not outputs or not intervals:
        return None
    base = next((s for _n, s, k in outputs if k == "motor"), outputs[0][1])
    mask = dsp.mask_from_intervals(base.t, intervals)
    if exclude:
        mask &= ~dsp.mask_from_intervals(base.t, exclude)
    n = int(np.count_nonzero(mask))
    if n == 0:
        return None
    t = base.t[mask]
    any_sat = np.zeros(n, bool)
    detail = {}
    for name, s, kind in outputs:
        y = s.y[mask] if s is base else dsp.resample(s.t, s.y, t, "zoh")
        lo, hi = _limits(kind, y)
        any_sat |= lo | hi
        if np.any(lo) or np.any(hi):
            detail[name] = (float(np.count_nonzero(lo) / n * 100), float(np.count_nonzero(hi) / n * 100))
    return {"percent": float(np.count_nonzero(any_sat) / n * 100), "samples": n, "detail": detail,
            "count": int(np.count_nonzero(any_sat))}


def describe_saturation(detail, low_word, high_word):
    """«M4 al minimo 41%» per l'uscita più saturata (testi tradotti passati dal chiamante)."""
    if not detail:
        return ""
    parts = []
    for name, (lo, hi) in sorted(detail.items(), key=lambda kv: -max(kv[1])):
        if lo >= hi:
            parts.append(f"{name} {low_word} {lo:.0f}%")
        else:
            parts.append(f"{name} {high_word} {hi:.0f}%")
    return ", ".join(parts[:3])


def fill_excluded(seg, mask, keys=("r", "z")):
    """Interpola linearmente ``keys`` sui campioni esclusi (mask True): i picchi dei cambi di modo spariscono."""
    if not np.any(mask):
        return
    t = seg["t"]
    good = ~mask
    if np.count_nonzero(good) < 2:
        return
    for k in keys:
        v = seg.get(k)
        if v is None:
            continue
        seg[k] = np.where(mask, np.interp(t, t[good], v[good]), v)


# ------------------------------------------------------------------ avvisi sul log


def allocator_fix_warning(log: LogData, min_time=20.0, min_fraction=0.9):
    """Avviso «PX4 senza la correzione dell'allocatore del tiltrotor», oppure None.

    Scatta se in hover (multicottero in volo, almeno ``min_time`` s) control_allocator_status dice
    torque_setpoint_achieved falso per almeno il 90% del tempo: con l'allocatore del tiltrotor non corretto la coppia
    non viene mai data per raggiunta e le misure del log non valgono. Se anche gli integratori di rate_ctrl_status
    restano fermi, lo dice.
    """
    from .i18n import _

    key = "_alloc_warning"
    if key in log._cache:
        return log._cache[key]
    iv = log.phase_intervals("MC")
    if log.airborne_known:
        iv = dsp.intersect(iv, log.airborne)
    out = None
    inst = log.instances("control_allocator_status")
    if dsp.total_length(iv) >= min_time and inst:
        s = log.series("control_allocator_status", "torque_setpoint_achieved", inst[0])
        if s is not None and len(s) >= 10:
            grid = np.arange(iv[0][0], iv[-1][1], 0.05)
            grid = grid[dsp.mask_from_intervals(grid, iv)]
            if grid.size:
                false_frac = float(np.mean(dsp.resample(s.t, s.y, grid, "zoh") < 0.5))
                if false_frac >= min_fraction:
                    frozen = []
                    for ax in ("roll", "pitch"):
                        it = log.series("rate_ctrl_status", f"{ax}speed_integ")
                        if it is not None:
                            m = dsp.mask_from_intervals(it.t, iv)
                            if np.count_nonzero(m) > 10 and float(np.std(it.y[m])) < 1e-4:
                                frozen.append(ax)
                    out = _("Possibile PX4 senza la correzione dell'allocatore del tiltrotor: in hover "
                            "torque_setpoint_achieved è falso per il {p:.0f}% del tempo").format(p=false_frac * 100)
                    if frozen:
                        out += _(" e gli integratori di rate_ctrl_status sono fermi")
                    out += _(". Le misure di questo log non valgono.")
    log._cache[key] = out
    return out


def log_rate_warning(log: LogData, min_hz=100.0):
    """Avviso «SDLOG_PROFILE senza alta frequenza» (bit 16 assente o motori registrati sotto 100 Hz), o None."""
    from .i18n import _

    prof = log.params.get("SDLOG_PROFILE")
    hz = log.rate("actuator_motors") if log.has("actuator_motors") else None
    bad_bit = prof is not None and not int(prof) & 16
    bad_rate = hz is not None and 0 < hz < min_hz
    if not (bad_bit or bad_rate):
        return None
    parts = []
    if prof is not None:
        parts.append(f"SDLOG_PROFILE = {int(prof)}")
    if hz:
        parts.append(_("motori registrati a {f:.0f} Hz").format(f=hz))
    return _("SDLOG_PROFILE senza alta frequenza ({cosa}): ritardi e saturazione dei gradini sono imprecisi. "
             "Usare SDLOG_PROFILE = 17 (predefinito + alta frequenza).").format(cosa=", ".join(parts))
