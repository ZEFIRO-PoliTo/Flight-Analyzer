"""Regressione sui log veri del Vespa: stampa i valori da confrontare con le misure fatte a parte.

Uso: python tests/regressione_vespa.py LOG.ulg [LOG2.ulg ...]

I log vengono riconosciuti dal nome; per ognuno si confrontano i valori con quelli attesi (tolleranza ±0,01 s e
±1 punto, salvo dove scritto) e si stampa OK / DIVERSO. Per un log non in elenco si stampano solo i valori.

    2026-11-07_rollrate_P0307.ulg   rollio, P 0,307, I 0,196, D 0,0054
        stima FIR (profilo Vespa hover): tempo al 50% circa 0,15 s (nella 1.1.0: 0,196 s)
        prove a gradino: 2 gradini positivi validi, ritardo 0,15–0,16 s, sovraelongazione 7–8%,
        assestamento 0,27–0,28 s, errore 4–5%; scartati tutti i negativi e un positivo per partenza non ferma
        (inclinati di 5–29°, in scivolata fino a 8,7 m/s), un positivo da 0,40 s perché troncato
    27-10-2026_prova5.ulg           deve comparire l'avviso «PX4 senza la correzione dell'allocatore»
    2026-11-04_rollio_prova0.ulg    5 gradini di rollio a 77,4 / 84,6 / 86,7 / 93,8 / 96,1 s; ritardo 0,156–0,172 s;
                                    sovraelongazione 1,7–14%; errore 2,9–7,5%; nessun rimbalzo; 2 gradini su 5 non
                                    assestati; saturazione 0% nei positivi; tenuta in Hold nei criteri; nessun
                                    consiglio su MC_ROLLRATE_FF (che vale 0)
    vespa_caduta.ulg                nessun gradino; tenuta in Hold fuori criterio
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import matplotlib  # noqa: E402

matplotlib.use("Agg")

from flight_analyzer import analysis, scoring, steptest  # noqa: E402
from flight_analyzer.logdata import LogData  # noqa: E402

RESULTS = []


def verdict(ok, text):
    RESULTS.append(ok)
    print(f"   [{'OK' if ok else 'DIVERSO'}] {text}")


def within(v, lo, hi, tol=0.0):
    return v is not None and lo - tol <= v <= hi + tol


def common(path):
    log = LogData(path)
    res = steptest.detect(log)
    fir = analysis.analyze(log, "MC", "rate", None, scoring.vespa_hover_profile())
    print(f"\n=== {log.name} — PX4 {log.ulog.version_string() or '?'}")
    print("   parametri: " + ", ".join(f"{k} {v:g}" if isinstance(v, float) else f"{k} {v}" for k, v in res.params
                                      if k.startswith("MC_ROLL")))
    for w in res.warnings:
        print(f"   ⚠ {w}")
    print(f"   {len(res.steps)} gradini, {len(res.valid_steps())} validi")
    for s in res.steps:
        r = s.resp
        vals = "—" if r is None else (
            f"ritardo {r.delay if r.delay is None else round(r.delay, 3)} s · sovr. {r.overshoot:.1f}% · assest. "
            f"{'non assestato' if r.settling is None else f'{r.settling:.3f} s'} · errore "
            f"{'—' if r.end_error is None else f'{r.end_error:.1f}'} · rimbalzi {r.bounces}")
        sat = "—" if s.saturation is None else f"{s.saturation:.1f}% {s.sat_text()}"
        state = "valido" if s.valid else "SCARTATO: " + "; ".join(s.reasons)
        print(f"   #{s.n} {s.kind}/{s.axis} {s.sign_label} {s.t_start:.2f} s ({s.duration:.3f} s): {vals} · sat. {sat} · "
              f"{state}")
    for h in res.holds:
        print(f"   tenuta {h.mode} {h.t0:.1f}–{h.t1:.1f} s: {'nei criteri' if h.ok else 'FUORI criterio'}"
              f" · rollio {h.values.get('roll_range')} · errore rollio picco {h.values.get('roll_peak')}")
    ar = fir.axes["roll"]
    cm = ar.extras.get("cmd") or {}
    print(f"   stima FIR rollio (Vespa hover): ritardo {cm.get('delay')} · sovr. {cm.get('overshoot')} · affidabilità "
          f"{ar.card.confidence}")
    return log, res, fir


def p0307(path):
    _log, res, fir = common(path)
    d = fir.axes["roll"].extras.get("cmd", {}).get("delay")
    verdict(within(d, 0.14, 0.16), f"tempo al 50% della stima FIR {d} s (atteso circa 0,15)")
    pos = res.valid_steps("rate", "roll", 1)
    verdict(len(pos) == 2, f"{len(pos)} gradini positivi validi (attesi 2)")
    for s in pos:
        r = s.resp
        verdict(within(r.delay, 0.15, 0.16, 0.01), f"#{s.n} ritardo {r.delay:.3f} s (atteso 0,15–0,16)")
        verdict(within(r.overshoot, 7, 8, 1), f"#{s.n} sovraelongazione {r.overshoot:.1f}% (attesa 7–8%)")
        verdict(r.settling is not None and within(r.settling, 0.27, 0.28, 0.01),
                f"#{s.n} assestamento {r.settling} s (atteso 0,27–0,28)")
        verdict(within(r.end_error, 4, 5, 1), f"#{s.n} errore {r.end_error:.1f}% (atteso 4–5%)")
    neg = [s for s in res.steps if s.kind == "rate" and s.axis == "roll" and s.sign < 0]
    verdict(neg and all(not s.valid and any("partenza non ferma" in r for r in s.reasons) for s in neg),
            "tutti i negativi scartati per partenza non ferma")
    bad_pos = [s for s in res.steps if s.kind == "rate" and s.axis == "roll" and s.sign > 0 and not s.valid]
    verdict(any(any("partenza non ferma" in r for r in s.reasons) for s in bad_pos), "un positivo per partenza non ferma")
    verdict(any(any("troncato" in r for r in s.reasons) and abs(s.duration - 0.40) < 0.03 for s in bad_pos),
            "un positivo da 0,40 s troncato")


def prova5(path):
    log, res, _fir = common(path)
    verdict(any("correzione dell'allocatore" in w for w in res.warnings), "avviso «PX4 senza la correzione dell'allocatore»")
    verdict(any(str(v).startswith("⚠") and "allocatore" in str(v) for v in log.summary().values()),
            "stesso avviso nel riepilogo del volo")


def prova0(path):
    """Valori di riferimento della replica indipendente (±0,01 s, ±2 punti)."""
    log, res, _fir = common(path)
    roll = [s for s in res.steps if s.kind == "rate" and s.axis == "roll"]
    starts = [round(s.t_start, 1) for s in roll]
    verdict(starts == [77.4, 84.6, 86.7, 93.8, 96.1], f"gradini a {starts} s")
    pos = [s for s in roll if s.valid]
    verdict([round(s.t_start, 1) for s in pos] == [77.4, 84.6, 93.8], "validi i 3 positivi a 77,4 / 84,6 / 93,8 s")
    ref = {"delay": (0.172, 0.164, 0.172), "overshoot": (12.9, 14.0, 10.1), "settling": (None, None, 0.48),
           "end_error": (7.5, 7.3, 5.9), "saturation": (2.4, 0.0, 0.0)}
    if len(pos) == 3:
        for i, s in enumerate(pos):
            r = s.resp
            verdict(within(r.delay, ref["delay"][i], ref["delay"][i], 0.01), f"#{s.n} ritardo {r.delay:.3f} s (rif. {ref['delay'][i]})")
            verdict(within(r.overshoot, ref["overshoot"][i], ref["overshoot"][i], 2),
                    f"#{s.n} sovraelongazione {r.overshoot:.1f}% (rif. {ref['overshoot'][i]})")
            rs = ref["settling"][i]
            verdict((r.settling is None) if rs is None else within(r.settling, rs, rs, 0.01),
                    f"#{s.n} assestamento {r.settling} (rif. {'non assestato' if rs is None else rs})")
            verdict(within(r.end_error, ref["end_error"][i], ref["end_error"][i], 2),
                    f"#{s.n} errore {r.end_error:.1f}% (rif. {ref['end_error'][i]})")
            verdict(r.bounces == 0, f"#{s.n} rimbalzi {r.bounces} (rif. 0)")
            verdict(within(s.saturation, ref["saturation"][i], ref["saturation"][i], 2),
                    f"#{s.n} saturazione {s.saturation:.1f}% (rif. {ref['saturation'][i]})")
    neg = [s for s in roll if s.sign < 0]
    verdict(all(not s.valid and any("partenza non ferma" in r for r in s.reasons) for s in neg),
            "negativi a 86,7 e 96,1 s scartati per partenza non ferma (inclinati 20–22°, 5–6 m/s)")
    verdict(any(abs(t - 97.332) < 0.01 for a, b in res.excluded for t in (a,)), "passaggio in Hold a 97,33 s escluso")
    verdict(res.holds and res.holds[0].ok, "tenuta in Hold nei criteri (primo tratto fermo)")
    rp = analysis.analyze(log, "MC", "rate", None)  # profilo PX4 standard, definizioni rispetto al livello finale
    st = rp.axes["roll"].step
    verdict(within(st.delay, 0.172, 0.172, 0.01), f"stima FIR t50 {st.delay:.3f} s (rif. 0,172 con i punti 1 e 4)")
    verdict(within(st.final, 1.09, 1.09, 0.02), f"livello a fine finestra {st.final:.3f} (rif. 1,09)")
    cm = _fir.axes["roll"].extras["cmd"]
    verdict(within(cm["overshoot"], 11, 11, 2), f"sovraelongazione della stima rispetto al comando {cm['overshoot']:.1f}% "
                                                "(rif. 11%, picco 1,11)")
    diag = " ".join(rp.axes["roll"].card.diagnostics)
    verdict("ridurre MC_ROLLRATE_FF" not in diag, "nessun consiglio di ridurre MC_ROLLRATE_FF (vale 0)")


def caduta(path):
    log, res, _fir = common(path)
    # non regressione del punto 1: l'Acro era già esterno e lo resta
    from flight_analyzer import modes
    acro = [(round(a, 3), round(b, 3)) for a, b, v in log.modes if v == 10]
    ext = [(round(a, 3), round(b, 3)) for a, b in modes.rate_external_intervals(log)]
    verdict(ext == acro, f"tratti esterni da vehicle_control_mode = Acro {acro}")
    verdict(not res.steps, "nessun gradino contato nelle rotazioni senza comandi")
    verdict(res.holds and not res.holds[0].ok, "tenuta in Hold fuori criterio")


KNOWN = (("P0307", p0307), ("prova5", prova5), ("prova0", prova0), ("caduta", caduta))


def main(argv):
    if not argv:
        print(__doc__)
        return 2
    for path in argv:
        fn = next((f for key, f in KNOWN if key in Path(path).name), None)
        if fn is None:
            common(path)
        else:
            fn(path)
    print()
    print(f"{sum(RESULTS)} su {len(RESULTS)} confronti come atteso" if RESULTS else "nessun confronto con valori attesi")
    return 0 if all(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
