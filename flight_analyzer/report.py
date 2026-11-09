"""Report del volo in HTML (pagina unica con grafici SVG) o PDF, ed esportazione JSON.

Entrambi i formati hanno lo stesso contenuto: riepilogo, punteggi, dettaglio per
asse con diagnosi, grafici e, in fondo, i parametri di valutazione usati (soglie,
pesi, obiettivi), così il report è leggibile anche da chi non ha il profilo.
I grafici dei report sono sempre in tema chiaro.
"""

from __future__ import annotations

import base64
import datetime as _dt
import html
import io
import json
import math
from pathlib import Path

from matplotlib.figure import Figure

from . import __version__, analysis, config, plots, scoring, steptest, theme
from .i18n import _, language
from .logdata import LogData

RESOURCES = Path(__file__).resolve().parent / "resources"

CSS = """
body{font-family:-apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:#1b2430;margin:0;background:#f4f6f9}
main{max-width:1180px;margin:0 auto;padding:24px 20px 60px;background:#fff}
h1{font-size:22px;margin:0 0 4px;color:#004183} h2{font-size:18px;margin:34px 0 10px;border-bottom:3px solid #ffc400;
padding-bottom:6px;color:#004183} h3{font-size:15px;margin:22px 0 8px}
.sub{color:#6b7785;font-size:13px;margin-bottom:18px}
.head{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap}
.logos{display:flex;align-items:center;gap:18px}.logos img{height:46px;width:auto}
table{border-collapse:collapse;width:100%;font-size:13px;margin:6px 0 12px}
th,td{border-bottom:1px solid #e3e8ee;padding:5px 8px;text-align:left;vertical-align:top}
th{background:#eef2f7;font-weight:600}
td.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.kv td:first-child{color:#495057;width:38%}
.badge{display:inline-block;padding:2px 8px;border-radius:10px;font-weight:600;font-size:12px;color:#fff}
.g-ok{background:#2b8a3e}.g-good{background:#5c940d}.g-warn{background:#e67700}.g-bad{background:#c92a2a}.g-na{background:#adb5bd}
.conf-bassa{color:#c92a2a;font-weight:600}.conf-media{color:#e67700}.conf-alta{color:#2b8a3e}
.diag{margin:4px 0 0 18px;padding:0;font-size:13px} .diag li{margin:3px 0}
.warn{background:#fff4e6;border-left:4px solid #ff922b;padding:8px 12px;font-size:13px;margin:8px 0}
.info{background:#eef2f7;border-left:4px solid #004183;padding:8px 12px;font-size:13px;margin:8px 0}
.note{color:#495057;font-size:13px;line-height:1.5}
svg{max-width:100%;height:auto}
@media print{body{background:#fff} main{padding:0}}
"""

GRADE_CLASS = {"Ottimo": "ok", "Buono": "good", "Accettabile": "warn", "Da rivedere": "bad", "Non valutabile": "na"}
GRADE_HEX = {"Ottimo": "#2b8a3e", "Buono": "#5c940d", "Accettabile": "#e67700", "Da rivedere": "#c92a2a",
             "Non valutabile": "#adb5bd"}


# ------------------------------------------------------------------ analisi


def run_all(log: LogData, profile=None, time_range=None):
    """Analizza tutte le combinazioni fase/anello presenti nel log."""
    out = []
    for phase in ("MC", "FW"):
        if log.phase_time(phase, airborne_only=log.airborne_known) <= 0:
            continue
        for loop in ("rate", "att"):
            out.append(analysis.analyze(log, phase, loop, time_range, profile))
    return out


def _fig(builder, *args, size=(13, 4.2), **kw):
    with theme.matplotlib_theme("light"):
        fig = Figure(figsize=size, dpi=100)
        builder(fig, *args, **kw)
    return fig


def _svg(builder, *args, size=(13, 4.2), **kw):
    fig = _fig(builder, *args, size=size, **kw)
    buf = io.StringIO()
    fig.savefig(buf, format="svg", bbox_inches="tight", facecolor="white")
    txt = buf.getvalue()
    return txt[txt.find("<svg"):]


def _png(builder, *args, size=(13, 4.2), dpi=150, **kw):
    fig = _fig(builder, *args, size=size, **kw)
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight", facecolor="white")
    return buf.getvalue()


def _fmt_score(s):
    return "—" if s is None else f"{s:.0f}"


def _th(t):
    good, ok, bad = t
    return f"{good:g} / {ok:g} / {bad:g}"


def _conf(c):
    return _(scoring.CONFIDENCE.get(c, c))


# ------------------------------------------------------------- parametri di valutazione


def _now():
    """Data e ora nel formato della lingua (giorno/mese in italiano, ISO in inglese per non confondere)."""
    fmt = "%d/%m/%Y %H:%M" if language() == "it" else "%Y-%m-%d %H:%M"
    return _dt.datetime.now().strftime(fmt)


def evaluation_parameters(profile):
    """Contenuto della sezione «Parametri di valutazione» (uguale per HTML e PDF)."""
    sections = []

    def metric_rows(metrics):
        rows = []
        for mk, th in metrics.items():
            label, unit, _fmt = scoring.METRIC_INFO[mk]
            rows.append((_(label) + (f" [{unit}]" if unit else ""), f"{th['good']:g}", f"{th['ok']:g}",
                         f"{th['bad']:g}", f"{th['weight']:g}"))
        return rows

    for loop, cfg in profile["loops"].items():
        targets = ", ".join(f"{_(scoring.AXIS_LABELS[a]).lower()}: "
                            + (_("automatico") if cfg["rise_target_s"].get(a, "auto") == "auto"
                               else f"{float(cfg['rise_target_s'][a]):g} s") for a in scoring.AXES)
        overrides = cfg.get("metrics_asse", {})
        title = _(scoring.LOOP_LABELS[loop])
        if overrides:
            title += " — " + "/".join(_(scoring.AXIS_LABELS[a]).lower() for a in scoring.AXES if a not in overrides)
        sec = {"title": title, "rows": metric_rows(cfg["metrics"]), "targets": targets,
               "excitation": float(cfg.get("min_excitation", 0.1))}
        if cfg.get("definizioni") == "scheda":
            unit = "°/s" if loop.endswith("rate") else "°"
            specs = [scoring.step_spec(profile, loop, a) for a in scoring.AXES]
            sec["targets"] = _("gradino della scheda: {g}; fascia {f}").format(
                g=", ".join(f"{_(scoring.AXIS_LABELS[a]).lower()} {sp['amp']:g} {unit} × {sp['dur']:g} s"
                            for a, sp in zip(scoring.AXES, specs)),
                f=(f"±{specs[0]['band']:g}°" if specs[0]["absolute_band"] else f"±{specs[0]['band_pct']:g}%"))
        sections.append(sec)
        for axis, metrics in overrides.items():
            sections.append({"title": f"{_(scoring.LOOP_LABELS[loop])} — {_(scoring.AXIS_LABELS[axis]).lower()}",
                             "rows": metric_rows(metrics), "targets": sec["targets"],
                             "excitation": sec["excitation"]})
    general = [
        _("Punti per metrica: 100 alla soglia «ottimo», 60 alla soglia «accettabile», 0 alla soglia «da rivedere», "
          "con interpolazione lineare; oltre l'ultima soglia 0 punti."),
        _("Punteggio dell'asse: media pesata dei punti delle metriche disponibili; serve almeno metà del peso "
          "totale, altrimenti l'asse è «non valutabile»."),
        _("Punteggio dell'anello: rollio 0,4, beccheggio 0,4, imbardata 0,2; gli assi con affidabilità bassa sono "
          "esclusi."),
        _("Giudizio: ottimo ≥ 85, buono ≥ 70, accettabile ≥ 55, altrimenti da rivedere."),
        _("Obiettivo del tempo di salita automatico: MC_AT_RISE_TIME per il rate multicottero (doppio per "
          "l'imbardata), 2,2/MC_ROLL_P (o PITCH/YAW) per l'assetto multicottero, 2,2·FW_R_TC per l'assetto ad ala "
          "fissa e 2,2·FW_R_TC/4 per il rate ad ala fissa."),
        _("Affidabilità alta con almeno 20 s di manovre utili, media tra 8 e 20 s, bassa sotto 8 s; scende anche "
          "con meno di 8 campioni nel tempo di salita, con stime disperse (sovraelongazione ± oltre 5 punti) o con "
          "guadagni cambiati in volo. Nei voli di prove a gradino (Acro, Offboard) contano invece i gradini validi: "
          "alta con almeno 3 per verso, media con almeno 3 in tutto, altrimenti bassa."),
        _("Saturazione: quota dei campioni di actuator_motors (piena frequenza) con almeno un motore ≤ 0,02 o "
          "≥ 0,98, più i tilt usati per il controllo; i 50 ms dopo ogni cambio di modo sono esclusi."),
    ]
    if any(cfg.get("definizioni") == "scheda" for cfg in profile["loops"].values()):
        general.append(_("Definizioni della scheda di taratura (anelli marcati «gradino della scheda»): grandezze "
                         "della risposta stimata calcolate per un gradino dell'ampiezza e della durata indicate, "
                         "rispetto all'ampiezza comandata: ritardo dal comando al 50% alla risposta al 50%, "
                         "sovraelongazione (picco − A)/A, assestamento nella fascia, errore medio negli ultimi 0,2 s "
                         "(assetto: dopo 1 s, in gradi), rimbalzi fuori dalla fascia dopo il picco. La soglia da 60 "
                         "punti è il criterio della scheda."))
    return {"name": _(profile.get("nome", "")), "sections": sections, "general": general}


# --------------------------------------------------------------------- HTML


def _logos_html():
    imgs = []
    for name, alt in (("logo_team.png", "Team Zefiro"), ("logo_polito.png", "Politecnico di Torino")):
        f = RESOURCES / name
        if f.exists():
            data = base64.b64encode(f.read_bytes()).decode("ascii")
            imgs.append(f"<img src='data:image/png;base64,{data}' alt='{alt}'>")
    return f"<div class='logos'>{''.join(imgs)}</div>" if imgs else ""


def _badge(grade):
    return f'<span class="badge g-{GRADE_CLASS.get(grade, "na")}">{html.escape(_(grade))}</span>'


def build_html(log: LogData, results, profile=None, comparisons=None, steps=None):
    """``comparisons``: dict loop_key -> [(etichetta, AnalysisResult)] per sovrapporre altri log;
    ``steps``: StepTestResult delle prove a gradino (None = calcolato qui con i criteri forniti con l'app)."""
    profile = profile or scoring.default_profile()
    comparisons = comparisons or {}
    sec_steps = step_section(_steps_for_report(log, steps))
    now = _now()
    e = html.escape
    parts = [f"<!doctype html><html lang='{language()}'><head><meta charset='utf-8'>"
             "<meta name='viewport' content='width=device-width, initial-scale=1'>"
             f"<title>{e(_('Analisi del volo'))} {e(log.name)}</title><style>{CSS}</style></head><body><main>"]
    parts.append(f"<div class='head'><h1>{e(_('Analisi del volo'))} — {e(log.name)}</h1>{_logos_html()}</div>")
    parts.append(f"<div class='sub'>{e(_('Generato il {data} con Flight Analyzer {ver}').format(data=now, ver=__version__))}"
                 f" · {e(_('profilo di valutazione'))}: {e(_(profile.get('nome', '')))}</div>")

    parts.append(f"<h2>{e(_('Riepilogo del volo'))}</h2><table class='kv'>")
    for k, v in log.summary().items():
        parts.append(f"<tr><td>{e(k)}</td><td>{e(str(v))}</td></tr>")
    parts.append("</table>")
    parts.append(_svg(plots.build_overview, log, size=(13, 6)))

    parts.append(f"<h2>{e(_('Valutazione dei controllori'))}</h2>")
    if not results:
        parts.append(f"<p class='note'>{e(_('Il log non contiene tratti di volo analizzabili.'))}</p>")
    else:
        parts.append(f"<table><tr><th>{e(_('Anello'))}</th><th>{e(_('Punteggio'))}</th><th>{e(_('Giudizio'))}</th>"
                     + "".join(f"<th>{e(_(scoring.AXIS_LABELS[a]))}</th>" for a in scoring.AXES)
                     + f"<th>{e(_('Tempo usato'))}</th></tr>")
        for r in results:
            cells = []
            for a in scoring.AXES:
                ar = r.axes[a]
                c = ar.card
                if not ar.available:
                    cells.append("<td>—</td>")
                else:
                    cells.append(f"<td class='num'>{_fmt_score(c.score)} <span class='conf-{c.confidence}'>"
                                 f"({e(_conf(c.confidence))})</span></td>")
            parts.append(f"<tr><td>{e(r.title)}</td><td class='num'><b>{_fmt_score(r.score)}</b></td>"
                         f"<td>{_badge(r.grade)}</td>{''.join(cells)}<td class='num'>{r.total_time:.0f} s</td></tr>")
        parts.append("</table>")
        parts.append(f"<p class='note'>{e(_('Punteggio 0–100: ottimo ≥ 85, buono ≥ 70, accettabile ≥ 55. Tra parentesi l’affidabilità della stima; gli assi ad affidabilità bassa non entrano nel punteggio complessivo.'))}</p>")

    for r in results:
        if not any(ar.available for ar in r.axes.values()):
            continue
        parts.append(f"<h2>{e(r.title)}</h2>")
        for w in r.warnings:
            parts.append(f"<div class='warn'>{e(w)}</div>")
        comp = comparisons.get(r.loop_key, [])
        labels = [log.name] + [lab for lab, _r in comp]
        parts.append(_svg(plots.build_step_responses, [r] + [c for _l, c in comp], labels))
        for axis in scoring.AXES:
            ar = r.axes[axis]
            score = "" if ar.card.score is None else f"{ar.card.score:.0f}/100"
            parts.append(f"<h3>{e(_(scoring.AXIS_LABELS[axis]))} — {_badge(ar.card.grade)} {score} "
                         f"<span class='conf-{ar.card.confidence}'>{e(_('affidabilità'))} "
                         f"{e(_conf(ar.card.confidence))}</span></h3>")
            if not ar.available:
                parts.append(f"<p class='note'>{e(ar.reason)}</p>")
                continue
            parts.append(f"<table><tr><th>{e(_('Metrica'))}</th><th>{e(_('Valore'))}</th><th>{e(_('Punti'))}</th>"
                         f"<th>{e(_('Soglie 100 / 60 / 0'))}</th><th>{e(_('Peso'))}</th><th>{e(_('Note'))}</th></tr>")
            for it in ar.card.items:
                pts = _("n.d.") if it.points is None else f"{it.points:.0f}"
                parts.append(f"<tr><td>{e(it.label)}</td><td class='num'>{e(it.display())}</td>"
                             f"<td class='num'>{pts}</td><td class='num'>{_th(it.thresholds)}</td>"
                             f"<td class='num'>{it.weight:g}</td><td>{e(it.note)}</td></tr>")
            parts.append("</table>")
            if ar.card.confidence_reasons:
                parts.append(f"<p class='note'>{e(_('Affidabilità'))}: " + e("; ".join(ar.card.confidence_reasons)) + "</p>")
            parts.append("<ul class='diag'>" + "".join(f"<li>{e(d)}</li>" for d in ar.card.diagnostics) + "</ul>")
            src = ", ".join(f"{k}: {v}" for k, v in ar.sources.items())
            parts.append(f"<p class='note'>{e(_('Segnali'))}: {e(src)} · {ar.fs:.0f} Hz · "
                         f"{e(_('{s:.0f} s analizzati').format(s=ar.used_time))}</p>")
            if r.loop_key == "mc_rate" and ar.est is not None and config.CFG.get("export_frequency", True):
                others = [c.axes[axis] for _l, c in comp]
                parts.append(_svg(plots.build_frequency, ar, others, labels, size=(13, 3.8)))
        if r.loop_key == "mc_rate" and config.CFG.get("export_frequency", True):
            parts.append(f"<div class='info'>{e(_(plots.T_EXPLANATION))}</div>")

    if sec_steps is not None:
        res_steps = _steps_for_report(log, steps)
        parts.append(f"<h2>{e(_('Prove a gradino'))}</h2>")
        parts.append(f"<p class='note'>{e(_('Criteri'))}: <b>{e(sec_steps['profile'])}</b> · "
                     f"{e(_('Parametri del volo'))}: {e(sec_steps['params'])}</p>")
        for w in sec_steps["warnings"]:
            parts.append(f"<div class='warn'>{e(w)}</div>")
        if res_steps is not None and res_steps.steps:
            parts.append(_svg(plots.build_step_summary, log, res_steps, size=(13, 4.2), header=False, table=False))
        if len(sec_steps["summary"]) > 1:
            parts.append(f"<h3>{e(_('Riepilogo per asse e verso (mediana / caso peggiore dei gradini validi)'))}</h3>")
            parts.append("<table>")
            for i, row in enumerate(sec_steps["summary"]):
                v = sec_steps["verdicts"][i]
                tag = "th" if i == 0 else "td"
                style = " style='background:#f1f3f5'" if v == "limit" else ""
                color = {True: "#2b8a3e", False: "#c92a2a"}.get(v) if v != "limit" else None
                cells = []
                for j, c in enumerate(row):
                    st_c = f" style='color:{color};font-weight:600'" if (color and j == len(row) - 1) else ""
                    cells.append(f"<{tag}{st_c}{' class=num' if 2 < j < len(row) - 1 and i else ''}>{e(c)}</{tag}>")
                parts.append(f"<tr{style}>{''.join(cells)}</tr>")
            parts.append("</table>")
        if len(sec_steps["steps"]) > 1:
            parts.append(f"<h3>{e(_('Gradini trovati'))}</h3><table>")
            for i, row in enumerate(sec_steps["steps"]):
                tag = "th" if i == 0 else "td"
                parts.append("<tr>" + "".join(f"<{tag}>{e(c)}</{tag}>" for c in row) + "</tr>")
            parts.append("</table>")
        for h in sec_steps["holds"]:
            col = "#2b8a3e" if h["ok"] else "#c92a2a"
            parts.append(f"<h3 style='color:{col}'>{e(_('Tenuta'))} — {e(h['title'])}</h3>")
            for n in h["notes"]:
                parts.append(f"<p class='note'>{e(n)}</p>")
            parts.append("<table class='kv'>" + "".join(
                f"<tr><td>{e(lab)}</td><td style='color:{'#2b8a3e' if ok else '#c92a2a' if ok is False else 'inherit'}'>"
                f"{e(txt)}</td></tr>" for lab, txt, ok in h["items"]) + "</table>")
        parts.append(f"<p class='note'>{e(_('Convenzione dei tempi'))}: {e(sec_steps['convention'])}</p>")

    parts.append(f"<h2>{e(_('Metodo'))}</h2><div class='note'>")
    for title, text in method_paragraphs():
        parts.append(f"<p><b>{e(title)}.</b> {e(text)}</p>")
    parts.append("</div>")
    if config.CFG.get("export_parameters", True):
        ev = evaluation_parameters(profile)
        parts.append(f"<h2>{e(_('Parametri di valutazione'))}</h2>")
        parts.append(f"<p class='note'>{e(_('Profilo'))}: <b>{e(ev['name'])}</b></p>")
        for sec in ev["sections"]:
            parts.append(f"<h3>{e(sec['title'])}</h3>")
            parts.append(f"<table><tr><th>{e(_('Metrica'))}</th><th>{e(_('100 punti'))}</th><th>{e(_('60 punti'))}</th>"
                         f"<th>{e(_('0 punti'))}</th><th>{e(_('Peso'))}</th></tr>")
            for row in sec["rows"]:
                parts.append("<tr>" + "".join(f"<td{' class=num' if i else ''}>{e(c)}</td>" for i, c in enumerate(row))
                             + "</tr>")
            parts.append("</table>")
            parts.append(f"<p class='note'>{e(_('Obiettivo del tempo di salita'))}: {e(sec['targets'])} · "
                         f"{e(_('eccitazione minima'))}: {sec['excitation']:g}</p>")
        parts.append("<ul class='diag'>" + "".join(f"<li>{e(g)}</li>" for g in ev["general"]) + "</ul>")
    parts.append("</main></body></html>")
    return "\n".join(parts)


def step_section(res):
    """Contenuto della sezione «Prove a gradino» (uguale per HTML e PDF), o None se non ci sono gradini né tenuta."""
    if res is None or (not res.steps and not res.holds):
        return None
    num = plots._num
    head = [_("Asse"), _("Verso"), _("Validi")] + [_(lab) for _k, lab, _u in steptest.QUANTITIES] + [_("Esito")]
    rows, verdicts = [head], [None]
    for (kind, axis), sm in res.summary.items():
        for i, (sign, d) in enumerate(sm.directions.items()):
            cells = [f"{_(steptest.KIND_SHORT[kind])} {_(scoring.AXIS_LABELS[axis]).lower()}",
                     "+" if sign > 0 else "−", f"{d.n_valid}/{d.n_total}"]
            for qk, _lab, _u in steptest.QUANTITIES:
                m, w = d.median.get(qk), d.worst.get(qk)
                cells.append("—" if w is None else f"{num(m, qk)} / {num(w, qk)}")
            v = steptest.direction_verdict(d)
            txt = {None: "—", True: _("entro i criteri"), False: _("fuori criterio")}[v]
            if i == 0:
                txt += " · " + {None: _("asse: non valutabile"), True: _("asse: TARATO"),
                                False: _("asse: NON TARATO")}[sm.tuned]
            cells.append(txt)
            rows.append(cells)
            verdicts.append(v)
        lim = [f"{_('criterio')}", "", ""] + [("≤ " + num(sm.limits[qk], qk)) if sm.limits.get(qk) is not None
                                             else "—" for qk, _l, _u in steptest.QUANTITIES] + [""]
        rows.append(lim)
        verdicts.append("limit")
    steps = [[_("#"), _("Asse"), _("Verso"), _("Inizio [s]"), _("Durata [s]"), _("Ritardo [s]"), _("Sovraelong. [%]"),
              _("Assest. [s]"), _("Errore"), _("Saturaz. [%]"), _("Esito / motivo")]]
    for st in res.steps:
        r = st.resp
        steps.append([str(st.n), f"{_(steptest.KIND_SHORT[st.kind])} {_(scoring.AXIS_LABELS[st.axis]).lower()}",
                      st.sign_label, num(st.t_start, nd=2), num(st.duration, nd=3),
                      "—" if r is None or r.delay is None else num(r.delay, nd=3),
                      "—" if r is None else num(r.overshoot, nd=1),
                      "—" if r is None else (_("non assestato") if r.settling is None else num(r.settling, nd=3)),
                      "—" if r is None or r.end_error is None else f"{num(r.end_error, nd=1)} {steptest.error_unit(st.kind)}",
                      "—" if st.saturation is None else num(st.saturation, nd=1),
                      _("valido") if st.valid else "; ".join(st.reasons)])
    holds = []
    for h in res.holds:
        items = []
        for key, label, unit, _lim in steptest.HOLD_ITEMS:
            val = h.values.get(key)
            if val is None:
                continue
            if isinstance(val, tuple):
                txt = (f"{num(val[0], nd=3)} ± {num(val[1], nd=3)}" if key == "hover"
                       else f"{num(val[0], nd=2)} – {num(val[1], nd=2)}")
            else:
                txt = f"{num(val, nd=2)} {unit}".strip()
            items.append((_(label), txt, h.passed.get(key)))
        holds.append({"title": f"{h.mode} {num(h.t0, nd=1)}–{num(h.t1, nd=1)} s: "
                               + (_("entro i criteri") if h.ok else _("fuori criterio")),
                      "ok": h.ok, "notes": h.notes, "items": items})
    params = "   ".join(f"{k} = {_g(v)}" for k, v in res.params)
    return {"params": params, "warnings": res.warnings, "summary": rows, "verdicts": verdicts, "steps": steps,
            "holds": holds, "profile": res.profile_name, "convention": _(steptest.TIME_CONVENTION)}


def _g(v):
    """Valore di un parametro nel formato della lingua (0,26 in italiano)."""
    txt = f"{v:g}" if isinstance(v, float) else str(v)
    return txt.replace(".", ",") if language() == "it" else txt


def _steps_for_report(log, steps):
    if steps is not None:
        return steps
    try:
        return steptest.detect(log)
    except Exception:  # noqa: BLE001 - la sezione è facoltativa
        return None


def method_paragraphs():
    return [
        (_("Identificazione"), _(
            "Per ogni asse si stima ai minimi quadrati la risposta impulsiva (FIR) dal setpoint alla misura usando "
            "tutti i tratti in volo della fase scelta; la risposta al gradino è la sua somma cumulativa. Quando il "
            "setpoint di velocità angolare è prodotto dall'anello d'assetto (modi Stabilized, Position, Hold, Mission) "
            "si usano le variabili strumentali, con il setpoint d'assetto come riferimento esterno: così la reazione "
            "del controllore alle raffiche non falsa la stima. Dove il setpoint di velocità angolare è già esterno "
            "(vehicle_control_mode con velocità angolare attiva e assetto spento: Acro e Offboard a velocità angolare) "
            "si usa il setpoint stesso; per l'anello d'assetto si escludono i tratti senza setpoint d'assetto. I 50 ms "
            "dopo ogni cambio di modo escono dalle equazioni. L'incertezza (banda ±2σ e valori ±) viene da un "
            "jackknife a blocchi di dati.")),
        (_("Prove a gradino"), _(
            "Ogni gradino del comando registrato viene misurato direttamente: ritardo dal comando al 50% alla "
            "risposta al 50% (comando: timestamp; risposta: timestamp_sample), sovraelongazione (picco − A)/A, "
            "assestamento nella fascia ±10% di A (assetto ±1°), errore medio negli ultimi 0,2 s (assetto: dopo 1 s), "
            "rimbalzi dopo il picco, saturazione dei motori fino a 0,5 s dopo la fine. Si scartano i gradini con un "
            "cambio di modo da 0,4 s prima dell'inizio alla fine, quelli troncati (sotto il 90% della durata mediana), "
            "quelli che partono inclinati, in rotazione o in movimento e quelli con comandi sugli altri assi.")),
        (_("Robustezza"), _(
            "Per l'anello di rate multicottero, dal rapporto tra le risposte setpoint→misura e setpoint→comando si "
            "ottiene l'impianto P(f); con il controllore PX4 ricostruito dai parametri (P, I, D, K, IMU_DGYRO_CUTOFF) "
            "si calcolano il guadagno d'anello L = C·P, il margine di fase, il margine di guadagno e il picco di "
            "sensitività Ms. Serve eccitazione fino a circa due volte la frequenza di attraversamento.")),
    ]


# ---------------------------------------------------------------------- PDF


def _register_fonts():
    """DejaVu Sans (incluso in matplotlib) per avere °, ±, ≥, →, σ nel PDF."""
    from matplotlib import get_data_path
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    base = Path(get_data_path()) / "fonts" / "ttf"
    try:
        pdfmetrics.getFont("DejaVu")
    except KeyError:
        pdfmetrics.registerFont(TTFont("DejaVu", str(base / "DejaVuSans.ttf")))
        pdfmetrics.registerFont(TTFont("DejaVu-Bold", str(base / "DejaVuSans-Bold.ttf")))
        from reportlab.lib.fonts import addMapping

        addMapping("DejaVu", 0, 0, "DejaVu")
        addMapping("DejaVu", 1, 0, "DejaVu-Bold")
    return "DejaVu", "DejaVu-Bold"


def build_pdf(log: LogData, results, path, profile=None, comparisons=None, steps=None):
    """Report PDF (A4) con lo stesso contenuto del report HTML."""
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import (Image, KeepTogether, PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table,
                                    TableStyle)

    profile = profile or scoring.default_profile()
    comparisons = comparisons or {}
    font, bold = _register_fonts()
    blue = colors.HexColor(theme.ZEFIRO_BLUE)
    st = {
        "h1": ParagraphStyle("h1", fontName=bold, fontSize=17, leading=21, textColor=blue, spaceAfter=2),
        "h2": ParagraphStyle("h2", fontName=bold, fontSize=13, leading=16, textColor=blue, spaceBefore=12,
                             spaceAfter=6, keepWithNext=1),
        "h3": ParagraphStyle("h3", fontName=bold, fontSize=10.5, leading=13, spaceBefore=8, spaceAfter=4,
                             keepWithNext=1),
        "p": ParagraphStyle("p", fontName=font, fontSize=8.5, leading=11.5, alignment=TA_LEFT),
        "small": ParagraphStyle("small", fontName=font, fontSize=7.5, leading=10, textColor=colors.HexColor("#495057")),
        "cell": ParagraphStyle("cell", fontName=font, fontSize=7.5, leading=9.5),
        "cellb": ParagraphStyle("cellb", fontName=bold, fontSize=7.5, leading=9.5),
        "warn": ParagraphStyle("warn", fontName=font, fontSize=8, leading=10.5, backColor=colors.HexColor("#fff4e6"),
                               borderPadding=4, spaceBefore=3, spaceAfter=5),
        "info": ParagraphStyle("info", fontName=font, fontSize=8, leading=10.5, backColor=colors.HexColor("#eef2f7"),
                               borderPadding=4, spaceBefore=3, spaceAfter=5),
    }
    e = html.escape
    page_w, page_h = A4
    margin = 14 * mm
    width = page_w - 2 * margin

    def P(text, style="p"):
        return Paragraph(e(str(text)), st[style])

    def table(rows, widths, header=True, num_cols=()):
        data = [[Paragraph(e(str(c)), st["cellb" if (header and r == 0) else "cell"]) for c in row]
                for r, row in enumerate(rows)]
        t = Table(data, colWidths=widths, repeatRows=1 if header else 0)
        style = [("VALIGN", (0, 0), (-1, -1), "TOP"), ("LINEBELOW", (0, 0), (-1, -1), 0.3, colors.HexColor("#d5dbe3")),
                 ("TOPPADDING", (0, 0), (-1, -1), 2), ("BOTTOMPADDING", (0, 0), (-1, -1), 2)]
        if header:
            style.append(("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#eef2f7")))
        for c in num_cols:
            style.append(("ALIGN", (c, 0), (c, -1), "RIGHT"))
        t.setStyle(TableStyle(style))
        return t

    def image(png_bytes, max_h=None):
        from reportlab.lib.utils import ImageReader

        ir = ImageReader(io.BytesIO(png_bytes))
        iw, ih = ir.getSize()
        w = width
        h = w * ih / iw
        if max_h and h > max_h:
            h = max_h
            w = h * iw / ih
        return Image(io.BytesIO(png_bytes), width=w, height=h)

    story = []
    logos = []
    for name, h in (("logo_team.png", 13 * mm), ("logo_polito.png", 13 * mm)):
        f = RESOURCES / name
        if f.exists():
            from reportlab.lib.utils import ImageReader

            iw, ih = ImageReader(str(f)).getSize()
            logos.append(Image(str(f), width=h * iw / ih, height=h))
    title = [P(f"{_('Analisi del volo')} — {log.name}", "h1"),
             P(_("Generato il {data} con Flight Analyzer {ver}").format(
                 data=_now(), ver=__version__)
               + f" · {_('profilo di valutazione')}: {_(profile.get('nome', ''))}", "small")]
    head = Table([[title, logos]], colWidths=[width - 62 * mm, 62 * mm])
    head.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "MIDDLE"), ("ALIGN", (1, 0), (1, 0), "RIGHT")]))
    story += [head, Spacer(1, 4 * mm)]

    story.append(P(_("Riepilogo del volo"), "h2"))
    rows = [[k, v] for k, v in log.summary().items()]
    story.append(table(rows, [width * 0.42, width * 0.58], header=False))
    story.append(Spacer(1, 3 * mm))
    story.append(image(_png(plots.build_overview, log, size=(13, 6)), max_h=110 * mm))

    story.append(P(_("Valutazione dei controllori"), "h2"))
    if not results:
        story.append(P(_("Il log non contiene tratti di volo analizzabili.")))
    else:
        rows = [[_("Anello"), _("Punteggio"), _("Giudizio")] + [_(scoring.AXIS_LABELS[a]) for a in scoring.AXES]
                + [_("Tempo usato")]]
        for r in results:
            cells = []
            for a in scoring.AXES:
                ar = r.axes[a]
                cells.append("—" if not ar.available else f"{_fmt_score(ar.card.score)} ({_conf(ar.card.confidence)})")
            rows.append([r.title, _fmt_score(r.score), _(r.grade)] + cells + [f"{r.total_time:.0f} s"])
        t = table(rows, [width * 0.27, width * 0.11, width * 0.13] + [width * 0.13] * 3 + [width * 0.10],
                  num_cols=(1, 3, 4, 5, 6))
        extra = []
        for i, r in enumerate(results, start=1):
            extra.append(("TEXTCOLOR", (2, i), (2, i), colors.HexColor(GRADE_HEX.get(r.grade, "#adb5bd"))))
        t.setStyle(TableStyle(extra))
        story.append(t)
        story.append(P(_("Punteggio 0–100: ottimo ≥ 85, buono ≥ 70, accettabile ≥ 55. Tra parentesi l’affidabilità "
                         "della stima; gli assi ad affidabilità bassa non entrano nel punteggio complessivo."), "small"))

    for r in results:
        if not any(ar.available for ar in r.axes.values()):
            continue
        story.append(PageBreak())
        story.append(P(r.title, "h2"))
        for w in r.warnings:
            story.append(P("⚠ " + w, "warn"))
        comp = comparisons.get(r.loop_key, [])
        labels = [log.name] + [lab for lab, _r in comp]
        story.append(image(_png(plots.build_step_responses, [r] + [c for _l, c in comp], labels), max_h=70 * mm))
        for axis in scoring.AXES:
            ar = r.axes[axis]
            score = "" if ar.card.score is None else f" {ar.card.score:.0f}/100"
            block = [P(f"{_(scoring.AXIS_LABELS[axis])} — {_(ar.card.grade)}{score} · {_('affidabilità')} "
                       f"{_conf(ar.card.confidence)}", "h3")]
            if not ar.available:
                block.append(P(ar.reason, "small"))
                story.append(KeepTogether(block))
                continue
            rows = [[_("Metrica"), _("Valore"), _("Punti"), _("Soglie 100 / 60 / 0"), _("Peso"), _("Note")]]
            for it in ar.card.items:
                rows.append([it.label, it.display(), _("n.d.") if it.points is None else f"{it.points:.0f}",
                             _th(it.thresholds), f"{it.weight:g}", it.note])
            block.append(table(rows, [width * 0.26, width * 0.14, width * 0.07, width * 0.14, width * 0.07,
                                      width * 0.32], num_cols=(1, 2, 3, 4)))
            if ar.card.confidence_reasons:
                block.append(P(f"{_('Affidabilità')}: " + "; ".join(ar.card.confidence_reasons), "small"))
            for d in ar.card.diagnostics:
                block.append(P("• " + d))
            src = ", ".join(f"{k}: {v}" for k, v in ar.sources.items())
            block.append(P(f"{_('Segnali')}: {src} · {ar.fs:.0f} Hz · " + _("{s:.0f} s analizzati").format(
                s=ar.used_time), "small"))
            story.append(KeepTogether(block))
            if r.loop_key == "mc_rate" and ar.est is not None and config.CFG.get("export_frequency", True):
                others = [c.axes[axis] for _l, c in comp]
                story.append(image(_png(plots.build_frequency, ar, others, labels, size=(13, 3.8)), max_h=62 * mm))
        if r.loop_key == "mc_rate" and config.CFG.get("export_frequency", True):
            story.append(P(_(plots.T_EXPLANATION), "info"))

    res_steps = _steps_for_report(log, steps)
    sec_steps = step_section(res_steps)
    if sec_steps is not None:
        story.append(PageBreak())
        story.append(P(_("Prove a gradino"), "h2"))
        story.append(P(f"{_('Criteri')}: {sec_steps['profile']} · {_('Parametri del volo')}: {sec_steps['params']}",
                       "small"))
        for w in sec_steps["warnings"]:
            story.append(P("⚠ " + w, "warn"))
        if res_steps.steps:
            story.append(image(_png(plots.build_step_summary, log, res_steps, size=(13, 4.2), header=False,
                                    table=False), max_h=70 * mm))
        if len(sec_steps["summary"]) > 1:
            ncol = len(sec_steps["summary"][0])
            widths = [width * 0.14, width * 0.07, width * 0.07] + [width * 0.09] * 6 + [width * 0.18]
            t = table(sec_steps["summary"], widths[:ncol], num_cols=tuple(range(3, ncol - 1)))
            extra = []
            for i, v in enumerate(sec_steps["verdicts"]):
                if v == "limit":
                    extra.append(("BACKGROUND", (0, i), (-1, i), colors.HexColor("#f1f3f5")))
                elif v is not None:
                    extra.append(("TEXTCOLOR", (-1, i), (-1, i), colors.HexColor("#2b8a3e" if v else "#c92a2a")))
            t.setStyle(TableStyle(extra))
            story.append(KeepTogether([P(_("Riepilogo per asse e verso (mediana / caso peggiore dei gradini validi)"),
                                         "h3"), t]))
        if len(sec_steps["steps"]) > 1:
            widths = [0.04, 0.13, 0.06, 0.08, 0.08, 0.08, 0.10, 0.10, 0.08, 0.08, 0.17]
            story.append(P(_("Gradini trovati"), "h3"))
            story.append(table(sec_steps["steps"], [width * w for w in widths], num_cols=tuple(range(3, 10))))
        for h in sec_steps["holds"]:
            block = [P(f"{_('Tenuta')} — {h['title']}", "h3")]
            for n in h["notes"]:
                block.append(P(n, "small"))
            block.append(table([[lab, txt] for lab, txt, _ok in h["items"]], [width * 0.5, width * 0.5],
                               header=False))
            story.append(KeepTogether(block))
        story.append(P(f"{_('Convenzione dei tempi')}: {sec_steps['convention']}", "small"))

    story.append(PageBreak())
    story.append(P(_("Metodo"), "h2"))
    for title_txt, text in method_paragraphs():
        story.append(Paragraph(f"<b>{e(title_txt)}.</b> {e(text)}", st["p"]))
        story.append(Spacer(1, 2 * mm))
    if config.CFG.get("export_parameters", True):
        ev = evaluation_parameters(profile)
        story.append(P(_("Parametri di valutazione"), "h2"))
        story.append(P(f"{_('Profilo')}: {ev['name']}"))
        for sec in ev["sections"]:
            block = [P(sec["title"], "h3")]
            rows = [[_("Metrica"), _("100 punti"), _("60 punti"), _("0 punti"), _("Peso")]] + [list(r) for r in sec["rows"]]
            block.append(table(rows, [width * 0.52, width * 0.12, width * 0.12, width * 0.12, width * 0.12],
                               num_cols=(1, 2, 3, 4)))
            block.append(P(f"{_('Obiettivo del tempo di salita')}: {sec['targets']} · {_('eccitazione minima')}: "
                           f"{sec['excitation']:g}", "small"))
            story.append(KeepTogether(block))
        story.append(Spacer(1, 2 * mm))
        for g in ev["general"]:
            story.append(P("• " + g))

    footer = f"Flight Analyzer {__version__} — {log.name}"

    def on_page(canvas, doc):
        canvas.saveState()
        canvas.setFont(font, 7)
        canvas.setFillColor(colors.HexColor("#6b7785"))
        canvas.drawString(margin, 8 * mm, footer)
        canvas.drawRightString(page_w - margin, 8 * mm, _("Pagina {n}").format(n=doc.page))
        canvas.setStrokeColor(colors.HexColor(theme.ZEFIRO_YELLOW))
        canvas.setLineWidth(1.2)
        canvas.line(margin, page_h - 9 * mm, page_w - margin, page_h - 9 * mm)
        canvas.restoreState()

    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=margin, rightMargin=margin, topMargin=13 * mm,
                            bottomMargin=14 * mm, title=f"{_('Analisi del volo')} {log.name}",
                            author="Flight Analyzer — Team Zefiro")
    doc.build(story, onFirstPage=on_page, onLaterPages=on_page)
    return path


def export(log: LogData, results, path, profile=None, comparisons=None, fmt=None, steps=None):
    """Scrive il report nel formato indicato (o dedotto dall'estensione)."""
    path = Path(path)
    fmt = (fmt or path.suffix.lstrip(".") or "html").lower()
    if fmt == "pdf":
        build_pdf(log, results, path, profile, comparisons, steps)
    else:
        path.write_text(build_html(log, results, profile, comparisons, steps), encoding="utf-8")
    return path


# --------------------------------------------------------------------- JSON


def _clean(v):
    if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
        return None
    return v


def result_to_dict(r):
    out = {"log": r.log_name, "fase": r.phase, "anello": r.loop_key, "punteggio": _clean(r.score), "giudizio": r.grade,
           "tempo_analizzato_s": r.total_time, "avvisi": r.warnings, "assi": {}}
    for axis, ar in r.axes.items():
        d = {"disponibile": ar.available, "motivo": ar.reason, "punteggio": _clean(ar.card.score) if ar.card else None,
             "giudizio": ar.card.grade if ar.card else None, "affidabilita": ar.card.confidence if ar.card else None,
             "metriche": {}, "diagnosi": ar.card.diagnostics if ar.card else [], "segnali": ar.sources,
             "frequenza_hz": ar.fs}
        if ar.card:
            for it in ar.card.items:
                d["metriche"][it.key] = {"valore": _clean(it.value), "incertezza": _clean(it.spread), "punti": it.points,
                                         "soglie": it.thresholds, "peso": it.weight, "nota": it.note}
        if ar.step is not None:
            d["risposta"] = {k: _clean(v) for k, v in ar.step.__dict__.items()}
        if ar.margins is not None and ar.margins.valid:
            m = ar.margins
            d["margini"] = {"crossover_hz": m.crossover_hz, "margine_fase_deg": m.phase_margin_deg, "pm_sd": m.pm_sd,
                            "margine_guadagno_db": m.gain_margin_db, "ms": m.ms, "ms_sd": m.ms_sd}
        out["assi"][axis] = d
    return out


def export_json(results, path):
    with open(path, "w", encoding="utf-8") as fh:
        json.dump([result_to_dict(r) for r in results], fh, indent=2, ensure_ascii=False)
