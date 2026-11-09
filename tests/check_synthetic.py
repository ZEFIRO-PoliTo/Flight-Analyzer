"""Analizza un log sintetico e confronta con la verità del simulatore."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from flight_analyzer.logdata import LogData
from flight_analyzer import analysis

path = sys.argv[1]
t0 = time.time(); log = LogData(path); t1 = time.time()
truth = json.loads(Path(path + ".verita.json").read_text())
print(f"caricato in {t1-t0:.1f}s; durata {log.duration:.0f}s; fasi {[(round(a),round(b),p) for a,b,p in log.phases]}")
print("in volo:", [(round(a,1), round(b,1)) for a, b in log.airborne], "vtol", log.is_vtol)
fails = 0
for phase in ("MC", "FW"):
    for loop in ("rate", "att"):
        t2 = time.time(); res = analysis.analyze(log, phase, loop); dt = time.time() - t2
        print(f"\n### {res.title}: punteggio {None if res.score is None else round(res.score)} ({res.grade}) — {res.total_time:.0f}s usati, {dt:.1f}s di calcolo")
        for w in res.warnings: print("   !", w)
        for axis, ar in res.axes.items():
            tv = truth.get(f"{res.loop_key}.{axis}")
            if not ar.available:
                print(f"  {axis:5s}: non disponibile — {ar.reason}"); continue
            st, sp = ar.step, ar.spread
            c = ar.card
            def f(v, s=1e3): return "  —  " if v is None else f"{v*s:5.0f}"
            line = (f"  {axis:5s}: salita {f(st.rise_time)} (vera {f(tv['rise_time']) if tv else '?'}) ms | "
                    f"OS {st.overshoot:5.1f}±{(sp.get('overshoot') or 0):.1f} (vera {tv['overshoot'] if tv else float('nan'):5.1f}) | "
                    f"regime {st.final:.3f} (vero {tv['final'] if tv else float('nan'):.3f}) | punti {None if c.score is None else round(c.score)} {c.grade} aff. {c.confidence}")
            print(line)
            if ar.margins is not None:
                m = ar.margins
                print(f"         margini: {'PM %.0f±%.0f° fc %.1f Hz Ms %.2f' % (m.phase_margin_deg, m.pm_sd or 0, m.crossover_hz, m.ms) if m.valid else m.reason}")
            for d in c.diagnostics: print("         -", d)
            if tv and tv['overshoot'] is not None:
                if abs(st.overshoot - tv['overshoot']) > max(6, 3*(sp.get('overshoot') or 0)): fails += 1; print("         ** sovraelongazione fuori tolleranza")
print("\nfuori tolleranza:", fails)
