"""Punto di ingresso.

    python -m flight_analyzer                      apre l'applicazione
    python -m flight_analyzer volo.ulg             apre l'applicazione con un log
    python -m flight_analyzer report volo.ulg [-o report.pdf|.html] [--formato pdf|html] [--json risultati.json]
                                             [--lingua it|en]
    python -m flight_analyzer punteggio a.ulg b.ulg [--fase MC|FW] [--anello rate|att] [--lingua it|en]
    python -m flight_analyzer gradini a.ulg [b.ulg ...] [--ignora-modo] [--soglia 10] [--profilo-gradini f.json]
                                             [--lingua it|en] [--senza-png-gradini]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _profile(path):
    from . import scoring

    return scoring.load_profile(path) if path else scoring.default_profile()


def _language(code):
    from . import i18n

    i18n.set_language(code or "it")


def cmd_report(args):
    import matplotlib

    matplotlib.use("Agg")
    from . import report
    from .logdata import LogData

    _language(args.lingua)

    log = LogData(args.log)
    prof = _profile(args.profilo)
    tr = (args.da, args.a) if args.da is not None and args.a is not None else None
    results = report.run_all(log, prof, tr)
    comparisons = {}
    for other in args.confronta or []:
        olog = LogData(other)
        for r in report.run_all(olog, prof, None):
            comparisons.setdefault(r.loop_key, []).append((olog.name, r))
    fmt = args.formato
    if fmt is None:
        fmt = "html" if args.output and Path(args.output).suffix.lower() in (".html", ".htm") else "pdf"
    out = Path(args.output or Path(args.log).with_suffix(f".report.{fmt}"))
    report.export(log, results, out, prof, comparisons, fmt)
    print(f"Report scritto in {out}")
    if args.json:
        report.export_json(results, args.json)
        print(f"Risultati JSON scritti in {args.json}")


def cmd_score(args):
    import matplotlib

    matplotlib.use("Agg")
    from . import analysis, scoring
    from .i18n import _
    from .logdata import LogData

    _language(args.lingua)
    prof = _profile(args.profilo)
    key = analysis.loop_key(args.fase, args.anello)
    print(f"{_(scoring.LOOP_LABELS[key])} — {_('profilo di valutazione')}: {_(prof['nome'])}")
    head = f"{'log':34s} {_('Totale'):>7s}  " + "  ".join(f"{_(scoring.AXIS_LABELS[a]):>16s}" for a in scoring.AXES)
    print(head)
    print("-" * len(head))
    for path in args.log:
        log = LogData(path)
        r = analysis.analyze(log, args.fase, args.anello, None, prof)
        cells = []
        for a in scoring.AXES:
            ar = r.axes[a]
            if not ar.available:
                cells.append(f"{'—':>16s}")
            else:
                sc = "—" if ar.card.score is None else f"{ar.card.score:.0f}"
                conf = _(scoring.CONFIDENCE.get(ar.card.confidence, ar.card.confidence))
                cells.append(f"{sc + ' (' + conf + ')':>16s}")
        tot = "—" if r.score is None else f"{r.score:.0f}"
        print(f"{log.name[:34]:34s} {tot:>7s}  " + "  ".join(cells))
        if args.dettagli:
            for a in scoring.AXES:
                ar = r.axes[a]
                if ar.available:
                    for it in ar.card.items:
                        pts = _("n.d.") if it.points is None else f"{it.points:.0f}"
                        print(f"      {a:5s} {it.label:52s} {it.display():>20s}  {_('Punti')} {pts:>4s}")
                    for d in ar.card.diagnostics:
                        print(f"      {a:5s} → {d}")


def cmd_steps(args):
    """Prove a gradino: PNG e CSV per ogni log e tabella di confronto tra i log."""
    import matplotlib

    matplotlib.use("Agg")
    from . import scoring, steptest
    from .i18n import _
    from .logdata import LogData

    _language(args.lingua)
    prof = steptest.step_profile(scoring.load_profile(args.profilo_gradini) if args.profilo_gradini else None)
    rows = []
    for path in args.log:
        log = LogData(path)
        res = steptest.detect(log, prof, args.ignora_modo, args.soglia)
        files = steptest.export(log, res, per_step=not args.senza_png_gradini)
        n_ok = len(res.valid_steps())
        print(f"{log.name}: {_('{n} gradini trovati, {v} validi').format(n=len(res.steps), v=n_ok)}")
        for f in files[:2]:
            print(f"   {f}")
        if len(files) > 2:
            print("   " + _("{n} PNG dei singoli gradini in {cartella}").format(n=len(files) - 2,
                                                                          cartella=Path(files[2]).parent))
        for w in res.warnings:
            print(f"   ⚠ {w}")
        gains = {k: v for k, v in res.params}
        for (kind, axis), sm in res.summary.items():
            pname = (scoring.RATE_PARAM_PREFIX[axis] + "_P") if kind == "rate" else scoring.MC_ATT_PARAM[axis]
            worst = {}
            for key, _lab, _u in steptest.QUANTITIES:
                vals = [d.worst.get(key) for d in sm.directions.values() if d.worst.get(key) is not None]
                worst[key] = max(vals) if vals else None
            rows.append((log.name, f"{_(steptest.KIND_SHORT[kind])} {_(scoring.AXIS_LABELS[axis]).lower()}",
                         pname, gains.get(pname), sm, worst))
    if not rows:
        print(_("Nessun gradino trovato nei log."))
        return 0
    print()
    head = (f"{'log':30s} {_('asse'):18s} {'P':>8s} {_('validi +/−'):>10s} {_('ritardo'):>8s} {_('sovr.%'):>7s} "
            f"{_('assest.'):>8s} {_('errore'):>7s} {_('rimb.'):>5s} {_('sat.%'):>6s}  {_('esito')}")
    print(_("Confronto tra i log (caso peggiore dei gradini validi, entrambi i versi)"))
    print(head)
    print("-" * len(head))
    for name, ax, _pname, pval, sm, w in rows:
        def f(v, nd):
            if v is None:
                return "—"
            if v == float("inf"):
                return _("n.ass.")
            return f"{v:.{nd}f}"

        nv = "/".join(str(sm.directions[s].n_valid) for s in (1, -1) if s in sm.directions)
        verdict = {None: "—", True: _("tarato"), False: _("non tarato")}[sm.tuned]
        print(f"{name[:30]:30s} {ax[:18]:18s} {f(pval, 3):>8s} {nv:>10s} {f(w['delay'], 3):>8s} "
              f"{f(w['overshoot'], 1):>7s} {f(w['settling'], 3):>8s} {f(w['end_error'], 1):>7s} "
              f"{f(w['bounces'], 0):>5s} {f(w['saturation'], 1):>6s}  {verdict}")
    return 0


def _console_utf8():
    """Su Windows l'uscita rediretta (file, pipe, CI) usa cp1252, che non ha °, −, ζ…: si passa a UTF-8."""
    for stream in (sys.stdout, sys.stderr):
        enc = (getattr(stream, "encoding", None) or "").lower().replace("-", "")
        if stream is not None and hasattr(stream, "reconfigure") and enc != "utf8":
            try:
                stream.reconfigure(encoding="utf-8", errors="replace")
            except (ValueError, OSError):
                pass


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in ("report", "punteggio", "gradini"):
        _console_utf8()
        ap = argparse.ArgumentParser(prog="flight_analyzer")
        sub = ap.add_subparsers(dest="cmd")
        rp = sub.add_parser("report", help="crea il report in PDF (predefinito) o HTML")
        rp.add_argument("log")
        rp.add_argument("-o", "--output", help="file di uscita (.pdf o .html)")
        rp.add_argument("--formato", choices=["pdf", "html"], help="formato del report (predefinito: dall'estensione, "
                                                                  "altrimenti PDF)")
        rp.add_argument("--lingua", choices=["it", "en"], default="it", help="lingua del report")
        rp.add_argument("--json")
        rp.add_argument("--profilo", help="profilo di valutazione JSON")
        rp.add_argument("--confronta", nargs="*", help="altri log da sovrapporre")
        rp.add_argument("--da", type=float, help="inizio intervallo [s]")
        rp.add_argument("--a", type=float, help="fine intervallo [s]")
        sp = sub.add_parser("punteggio", help="tabella dei punteggi di uno o più log")
        sp.add_argument("log", nargs="+")
        sp.add_argument("--fase", default="MC", choices=["MC", "FW", "ALL"])
        sp.add_argument("--anello", default="rate", choices=["rate", "att"])
        sp.add_argument("--profilo")
        sp.add_argument("--dettagli", action="store_true")
        sp.add_argument("--lingua", choices=["it", "en"], default="it")
        gp = sub.add_parser("gradini", help="prove a gradino: PNG e CSV per ogni log e tabella di confronto")
        gp.add_argument("log", nargs="+")
        gp.add_argument("--ignora-modo", action="store_true", help="cerca i gradini in tutto il volo in multicottero "
                                                                    "(log dell'autotune)")
        gp.add_argument("--soglia", type=float, help="soglia in °/s con --ignora-modo (predefinita dal profilo)")
        gp.add_argument("--profilo-gradini", help="profilo JSON con i criteri (predefinito profili/vespa_hover.json)")
        gp.add_argument("--senza-png-gradini", action="store_true", help="non scrivere un PNG per ogni gradino")
        gp.add_argument("--lingua", choices=["it", "en"], default="it")
        args = ap.parse_args(argv)
        if args.cmd == "gradini":
            return cmd_steps(args)
        return cmd_report(args) if args.cmd == "report" else cmd_score(args)
    from .gui import run

    return run(argv[0] if argv else None)


if __name__ == "__main__":
    sys.exit(main())
