"""Verifica delle prove a gradino (steptest) e delle correzioni della 1.2.0 su segnali e log sintetici.

Uso: python tests/check_steptest.py [CARTELLA_DI_LAVORO]

1. Sistema del secondo ordine con ritardo: smorzamento e pulsazione noti, verità calcolata su una griglia fine
   (1 µs); il segnale viene campionato a 250 Hz con rumore e il comando ogni 24 ms, come nei log.
2. Tre tarature del rate controller PX4 1.17 (tests/simulate.py) in un log sintetico con gradini in Offboard: le
   grandezze di ogni gradino valido devono coincidere con quelle della simulazione senza rumore e il ritardo della
   stima FIR (profilo Vespa hover) deve stare entro il 10% del tempo al 50% della risposta vera (true_step).
3. Gradino con saturazione forzata (3 campioni), gradino troncato, partenza inclinata e in scivolata, doppietto
   interrotto da un passaggio in Hold: motivi giusti.
4. Log senza gradini; PX4 senza la correzione dell'allocatore; SDLOG_PROFILE = 131 con motori a 10 Hz: avvisi.
5. Punti 1 e 4: tratti esterni da vehicle_control_mode, assetto escluso in Offboard a velocità angolare, 50 ms dopo
   ogni cambio di modo esclusi; punto 5: niente «ridurre FF» con FF = 0.
"""

from __future__ import annotations

import math
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import make_step_log  # noqa: E402

from flight_analyzer import analysis, dsp, modes, scoring, steptest  # noqa: E402
from flight_analyzer.logdata import LogData  # noqa: E402
from flight_analyzer.__main__ import _console_utf8  # noqa: E402

FAILS = []


def check(cond, msg):
    print(("  ok: " if cond else "  ERRORE: ") + msg)
    if not cond:
        FAILS.append(msg)


# ----------------------------------------------------------------- 1. secondo ordine


def second_order(t, zeta, wn, tau):
    """Risposta al gradino unitario di wn²/(s² + 2ζwn s + wn²) con ritardo puro tau."""
    tt = np.maximum(t - tau, 0.0)
    wd = wn * math.sqrt(1 - zeta ** 2)
    phi = math.acos(zeta)
    y = 1 - np.exp(-zeta * wn * tt) / math.sqrt(1 - zeta ** 2) * np.sin(wd * tt + phi)
    return np.where(t >= tau, y, 0.0)


def dense_truth(zeta, wn, tau, dur, band=0.1):
    """Grandezze calcolate a mano su una griglia di 1 µs (indipendenti da steptest)."""
    t = np.arange(0, dur, 1e-6)
    y = second_order(t, zeta, wn, tau)
    t50 = t[np.flatnonzero(y >= 0.5)[0]]
    k = int(np.argmax(y))
    out = np.abs(y - 1) > band
    settling = None if out[-1] else float(t[np.flatnonzero(out)[-1] + 1])
    o = out[k:]
    bounces = int(np.count_nonzero(o[1:] & ~o[:-1]))
    w = t >= dur - 0.2
    err = float(np.mean(np.abs(1 - y[w])) * 100)
    return {"delay": float(t50), "overshoot": float((y[k] - 1) * 100), "settling": settling, "end_error": err,
            "bounces": bounces}


def test_second_order():
    print("1. sistema del secondo ordine (verità su griglia di 1 µs)")
    rng = np.random.default_rng(1)
    A = 45.0
    for zeta, wn, tau, dur in ((0.7, 25.0, 0.020, 0.5), (0.45, 30.0, 0.030, 0.5), (0.25, 22.0, 0.010, 0.8)):
        tr = dense_truth(zeta, wn, tau, dur)
        t0 = 10.0
        phase = rng.uniform(0, 0.004)
        t = np.arange(9.5, t0 + dur + 0.5, 0.004) + phase  # risposta a 250 Hz, fase qualunque
        u = A * second_order(t - t0, zeta, wn, tau) + 0.05 * rng.standard_normal(len(t))
        cmd = np.where((t >= t0) & (t < t0 + dur), A, 0.0)
        r = steptest.measure_response(t, u, A, t0, t0 + dur, 0.1 * A, cmd=cmd, err_last=0.2)
        lab = f"ζ={zeta}, ωn={wn}, ritardo {tau * 1000:.0f} ms"
        check(abs(r.delay - tr["delay"]) < 0.002, f"{lab}: ritardo {r.delay * 1000:.1f} ms (vero {tr['delay'] * 1000:.1f})")
        check(abs(r.overshoot - tr["overshoot"]) < 0.6,
              f"{lab}: sovraelongazione {r.overshoot:.2f}% (vera {tr['overshoot']:.2f}%)")
        if tr["settling"] is None:
            check(r.settling is None, f"{lab}: non assestato (vero: non assestato)")
        else:
            check(r.settling is not None and abs(r.settling - tr["settling"]) < 0.004,
                  f"{lab}: assestamento {r.settling} s (vero {tr['settling']:.4f} s)")
        check(abs(r.end_error - tr["end_error"]) < 0.4, f"{lab}: errore {r.end_error:.2f}% (vero {tr['end_error']:.2f}%)")
        check(r.bounces == tr["bounces"], f"{lab}: rimbalzi {r.bounces} (veri {tr['bounces']})")


# ----------------------------------------------------------------- 2. simulatore


TUNINGS = {"lenta": dict(kp=0.15, ki=0.20, kd=0.003), "Vespa prova 0": dict(kp=0.26, ki=0.30, kd=0.004),
           "vivace": dict(kp=0.45, ki=0.45, kd=0.007)}


def test_simulator(work):
    print("2. tre tarature del rate controller PX4 1.17 (log sintetici con gradini in Offboard)")
    vespa = scoring.vespa_hover_profile()
    for name, g in TUNINGS.items():
        path = work / f"gradini_{name.replace(' ', '_')}.ulg"
        meta = make_step_log.build(path, gains=g)
        log = LogData(path)
        res = steptest.detect(log)
        truth = meta["gradini"]
        check(len(res.steps) == len(truth), f"{name}: {len(res.steps)} gradini trovati su {len(truth)}")
        worst = {"delay": 0.0, "overshoot": 0.0, "end_error": 0.0, "settling": 0.0}
        for st, tr in zip(res.steps, truth):
            if not (st.valid and tr["valid"]):
                continue
            r = st.resp
            worst["delay"] = max(worst["delay"], abs(r.delay - tr["delay"]))
            worst["overshoot"] = max(worst["overshoot"], abs(r.overshoot - tr["overshoot"]))
            worst["end_error"] = max(worst["end_error"], abs(r.end_error - tr["end_error"]))
            if (r.settling is None) != (tr["settling"] is None):
                worst["settling"] = math.inf
            elif r.settling is not None:
                worst["settling"] = max(worst["settling"], abs(r.settling - tr["settling"]))
        check(worst["delay"] < 0.003, f"{name}: ritardo entro {worst['delay'] * 1000:.1f} ms dalla simulazione")
        check(worst["overshoot"] < 2.0, f"{name}: sovraelongazione entro {worst['overshoot']:.2f} punti")
        check(worst["end_error"] < 1.5, f"{name}: errore a fine gradino entro {worst['end_error']:.2f} punti")
        check(worst["settling"] < 0.015, f"{name}: assestamento entro {worst['settling'] * 1000:.1f} ms "
                                         "(o non assestato in entrambi)")
        r = analysis.analyze(log, "MC", "rate", None, vespa)
        d = r.axes["roll"].extras["cmd"]["delay"]
        t50 = meta["t50_vero"]
        check(abs(d - t50) / t50 < 0.10, f"{name}: ritardo della stima FIR {d * 1000:.0f} ms, vero {t50 * 1000:.0f} ms "
                                        f"({(d - t50) / t50 * 100:+.0f}%)")
        if name == "Vespa prova 0":
            check_reasons(res, truth, log)
            check_fixes(log, r)


def check_reasons(res, truth, log):
    print("3. scarti e saturazione (taratura della prova 0)")
    words = {"troncato": "troncato", "partenza non ferma": "partenza non ferma", "cambio di modo": "cambio di modo"}
    for st, tr in zip(res.steps, truth):
        if tr["valid"]:
            check(st.valid, f"gradino a {st.t_start:.2f} s valido")
        else:
            want = words[tr["reason"]]
            check(not st.valid and any(want in r for r in st.reasons),
                  f"gradino a {st.t_start:.2f} s scartato per «{want}»: {'; '.join(st.reasons)}")
    sat = [s for s, tr in zip(res.steps, truth) if tr.get("sat")][0]
    n = int(round((sat.sat_window[1] - sat.sat_window[0]) * 250))
    check(sat.saturation is not None and abs(sat.saturation - 3 / n * 100) < 0.3 and "M2" in sat.sat_detail,
          f"saturazione di 3 campioni trovata: {sat.saturation:.2f}% ({sat.sat_text()})")
    others = [s.saturation for s, tr in zip(res.steps, truth) if tr["valid"] and not tr.get("sat")]
    check(max(others) == 0.0, "nessuna saturazione negli altri gradini (picchi dei cambi di modo esclusi)")
    sm = res.summary[("rate", "roll")]
    check(sm.directions[1].n_valid >= 3 and sm.directions[-1].n_valid >= 3, "almeno 3 gradini validi per verso")
    check(sm.tuned is False, "esito «non tarato» (ritardo e sovraelongazione oltre i criteri)")
    check(len(res.holds) >= 1 and res.holds[-1].ok and not res.holds[-1].short, "tenuta di 40 s in Hold nei criteri")


def check_fixes(log, r):
    print("5. correzioni dei punti 1, 4 e 5")
    offb = [(a, b) for a, b, v in log.modes if v == 14]
    ext = modes.rate_external_intervals(log)
    check(len(ext) == len(offb) and all(abs(a - c) < 0.01 and abs(b - d) < 0.01 for (a, b), (c, d) in zip(ext, offb)),
          "tratti esterni = Offboard a velocità angolare (da vehicle_control_mode)")
    att = modes.attitude_setpoint_intervals(log)
    check(dsp.total_length(dsp.intersect(att, offb)) == 0, "assetto escluso dove non c'è setpoint d'assetto")
    ra = analysis.analyze(log, "MC", "att", None)
    check(dsp.total_length(dsp.intersect(ra.intervals, offb)) == 0, "l'analisi d'assetto non usa i tratti in Offboard")
    tw = modes.transient_windows(log)
    check(len(tw) == len(modes.change_times(log)) and all(abs((b - a) - 0.05) < 1e-9 for a, b in tw),
          f"{len(tw)} finestre di 50 ms dopo i cambi di modo")
    check(r.axes["roll"].extras["excluded_samples"] > 0, "campioni esclusi dalle equazioni della stima")
    rp = analysis.analyze(log, "MC", "rate", None)  # profilo PX4 standard
    diag = " ".join(rp.axes["roll"].card.diagnostics)
    check("ridurre MC_ROLLRATE_FF" not in diag, "nessun «ridurre MC_ROLLRATE_FF» con FF = 0")
    check("a regime" not in diag, "«livello a fine finestra», non «a regime»")


# ----------------------------------------------------------------- 4. log particolari


def test_special_logs(work):
    print("4. log senza gradini, senza correzione dell'allocatore, con SDLOG_PROFILE = 131")
    p = work / "senza_gradini.ulg"
    make_step_log.build(p, with_steps=False)
    res = steptest.detect(LogData(p))
    check(not res.steps and any("Nessun gradino" in w for w in res.warnings), "log senza gradini: avviso")
    check(len(res.holds) >= 1, "log senza gradini: tenuta valutata")
    p = work / "senza_correzione.ulg"
    make_step_log.build(p, alloc_fix=False)
    log = LogData(p)
    res = steptest.detect(log)
    check(any("correzione dell'allocatore" in w for w in res.warnings), "avviso «PX4 senza la correzione dell'allocatore»")
    summ = log.summary()
    check(any(str(v).startswith("⚠") and "torque_setpoint_achieved" in str(v) for v in summ.values()),
          "stessa riga con ⚠ nel riepilogo del volo")
    p = work / "sdlog131.ulg"
    make_step_log.build(p, sdlog131=True)
    res = steptest.detect(LogData(p))
    check(any("SDLOG_PROFILE senza alta frequenza" in w for w in res.warnings), "avviso SDLOG_PROFILE = 131 / motori a 10 Hz")
    p = work / "gradini.ulg"
    make_step_log.build(p)
    log = LogData(p)
    res = steptest.detect(log, ignore_mode=True, threshold=10.0)
    check(res.ignore_mode and len(res.steps) >= 11, f"«ignora il modo»: {len(res.steps)} gradini con soglia 10 °/s")
    res = steptest.detect(log)
    files = steptest.export(log, res, work)
    csv_text = files[1].read_text(encoding="utf-8-sig")
    lines = csv_text.splitlines()
    check(len(lines) == 1 + len(res.steps) + 3 * 2, f"CSV: {len(res.steps)} righe dei gradini più il riepilogo")
    check(lines[1].startswith("1.2.0;") and "timestamp_sample" in lines[1], "CSV con versione e convenzione dei tempi")
    check(files[0].stat().st_size > 20_000 and len(files) == 2 + len(res.steps), "PNG riassuntivo e un PNG per gradino")


def main():
    _console_utf8()  # su Windows (CI, pipe) la console è cp1252: niente ζ, −, °
    work = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(tempfile.mkdtemp(prefix="gradini_"))
    work.mkdir(parents=True, exist_ok=True)
    test_second_order()
    test_simulator(work)
    test_special_logs(work)
    print()
    if FAILS:
        print(f"{len(FAILS)} CONTROLLI FALLITI")
        return 1
    print("TUTTO OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
