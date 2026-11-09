"""Scala di valutazione oggettiva dei controllori.

Ogni metrica viene convertita in punti con tre soglie: ``good`` (100 punti),
``ok`` (60 punti) e ``bad`` (0 punti), interpolando linearmente. Il punteggio
dell'asse è la media pesata delle metriche disponibili; le metriche che il log
non permette di calcolare vengono escluse e il loro peso ridistribuito (e
l'affidabilità scende). Tutte le soglie stanno nel profilo, modificabile e
salvabile in JSON, così due log valutati con lo stesso profilo sono
confrontabili.

Riferimenti delle soglie predefinite (dettagli nel README):
* sovraelongazione: sistema del 2° ordine, 5% ≈ smorzamento 0,69, 15% ≈ 0,52,
  35% ≈ 0,32;
* tempo di salita: obiettivo PX4 ``MC_AT_RISE_TIME`` (0,14 s di default) per
  l'anello di rate multicottero, 2,2/P per gli anelli d'assetto (risposta
  ideale del 1° ordine imposta dal guadagno d'assetto);
* margine di fase: 50° buono, 35° minimo usuale, 20° insufficiente;
* le soglie su rumore, saturazione e integratore sono euristiche.
"""

from __future__ import annotations

import copy
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

from .i18n import N_, _

LOOP_LABELS = {
    "mc_rate": N_("Multicottero — anello di velocità angolare (rate)"),
    "mc_att": N_("Multicottero — anello di assetto"),
    "fw_rate": N_("Ala fissa — anello di velocità angolare (rate)"),
    "fw_att": N_("Ala fissa — anello di assetto"),
}
AXES = ("roll", "pitch", "yaw")
AXIS_LABELS = {"roll": N_("Rollio"), "pitch": N_("Beccheggio"), "yaw": N_("Imbardata")}
AXIS_WEIGHTS = {"roll": 0.4, "pitch": 0.4, "yaw": 0.2}

METRIC_INFO = {
    # chiave: (etichetta, unità, formato)
    # definizioni «px4» (profilo PX4 standard): rispetto al valore finale della risposta stimata
    "overshoot": (N_("Sovraelongazione"), "%", "{:.1f}"),
    "rise_ratio": (N_("Tempo di salita / obiettivo"), "×", "{:.2f}"),
    "settling_ratio": (N_("Tempo di assestamento (5%) / obiettivo di salita"), "×", "{:.2f}"),
    "ss_error": (N_("Errore del livello a fine finestra"), "%", "{:.1f}"),
    "phase_margin": (N_("Margine di fase"), "°", "{:.0f}"),
    "resonance": (N_("Picco di risonanza in anello chiuso"), "dB", "{:.1f}"),
    "noise": (N_("Rumore sul comando (> 30 Hz, RMS)"), "", "{:.3f}"),
    "saturation": (N_("Tempo con motori al limite (≤ 0,02 o ≥ 0,98)"), "%", "{:.1f}"),
    "integrator": (N_("Tempo con integratore oltre l'80% del limite"), "%", "{:.1f}"),
    # definizioni «scheda» (scheda di taratura): rispetto all'ampiezza comandata
    "delay": (N_("Ritardo (comando al 50% → risposta al 50%)"), "s", "{:.3f}"),
    "overshoot_cmd": (N_("Sovraelongazione rispetto al comando"), "%", "{:.1f}"),
    "settling_band": (N_("Assestamento nella fascia"), "s", "{:.3f}"),
    "end_error": (N_("Errore a fine gradino"), "%", "{:.1f}"),
    "end_error_deg": (N_("Errore dopo 1 s"), "°", "{:.2f}"),
    "bounces": (N_("Rimbalzi dopo il picco"), "", "{:.0f}"),
}
SCHEDA_METRICS = ("delay", "overshoot_cmd", "settling_band", "end_error", "end_error_deg", "bounces", "saturation")


def _m(good, ok, bad, weight):
    return {"good": good, "ok": ok, "bad": bad, "weight": weight}


DEFAULT_PROFILE = {
    "nome": N_("PX4 standard (predefinito)"),
    "loops": {
        "mc_rate": {
            "rise_target_s": {"roll": "auto", "pitch": "auto", "yaw": "auto"},
            "min_excitation": 0.2,
            "metrics": {
                "overshoot": _m(5, 15, 35, 25),
                "rise_ratio": _m(1.0, 1.5, 3.0, 15),
                "settling_ratio": _m(2.5, 4.0, 6.0, 15),
                "ss_error": _m(3, 10, 25, 10),
                "phase_margin": _m(50, 35, 20, 15),
                "resonance": _m(1.0, 3.0, 6.0, 5),
                "noise": _m(0.01, 0.03, 0.08, 5),
                "saturation": _m(0.5, 3, 10, 5),
                "integrator": _m(1, 5, 20, 5),
            },
        },
        "mc_att": {
            "rise_target_s": {"roll": "auto", "pitch": "auto", "yaw": "auto"},
            "min_excitation": 0.05,
            "metrics": {
                "overshoot": _m(5, 15, 30, 30),
                "rise_ratio": _m(1.2, 1.6, 3.0, 25),
                "settling_ratio": _m(1.8, 3.0, 5.0, 20),
                "ss_error": _m(3, 10, 25, 15),
                "resonance": _m(1.0, 3.0, 6.0, 10),
            },
        },
        "fw_rate": {
            "rise_target_s": {"roll": "auto", "pitch": "auto", "yaw": "auto"},
            "min_excitation": 0.1,
            "metrics": {
                "overshoot": _m(5, 15, 35, 25),
                "rise_ratio": _m(1.0, 1.5, 3.0, 20),
                "settling_ratio": _m(2.5, 4.0, 6.0, 15),
                "ss_error": _m(5, 15, 30, 15),
                "resonance": _m(1.0, 3.0, 6.0, 10),
                "noise": _m(0.01, 0.03, 0.08, 5),
                "saturation": _m(0.5, 3, 10, 5),
                "integrator": _m(1, 5, 20, 5),
            },
        },
        "fw_att": {
            "rise_target_s": {"roll": "auto", "pitch": "auto", "yaw": "auto"},
            "min_excitation": 0.05,
            "metrics": {
                "overshoot": _m(5, 15, 30, 30),
                "rise_ratio": _m(1.2, 1.6, 3.0, 25),
                "settling_ratio": _m(1.8, 3.0, 5.0, 20),
                "ss_error": _m(5, 15, 30, 15),
                "resonance": _m(1.0, 3.0, 6.0, 10),
            },
        },
    },
}


def default_profile():
    return copy.deepcopy(DEFAULT_PROFILE)


def bundled_profile_path(name):
    """Percorso di un profilo fornito con l'app (cartella profili/), anche nell'eseguibile PyInstaller."""
    roots = [Path(__file__).resolve().parents[1] / "profili"]
    if getattr(sys, "_MEIPASS", None):
        roots.insert(0, Path(sys._MEIPASS) / "profili")
    for root in roots:
        f = root / name
        if f.exists():
            return f
    raise FileNotFoundError(_("profilo {nome} non trovato nella cartella profili").format(nome=name))


def vespa_hover_profile():
    """Profilo «Vespa hover»: criteri della scheda di taratura (profili/vespa_hover.json)."""
    return load_profile(bundled_profile_path("vespa_hover.json"))


def load_profile(path):
    return profile_from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


def _metric_set(src):
    out = {}
    for mk, mv in (src or {}).items():
        if mk in METRIC_INFO:
            out[mk] = {k: float(mv[k]) for k in ("good", "ok", "bad", "weight")}
    return out


def profile_from_dict(data):
    """Unisce un profilo (anche parziale) a quello predefinito.

    Un anello con ``"definizioni": "scheda"`` usa solo le metriche scritte nel file (definizioni della scheda di
    taratura: rispetto all'ampiezza comandata) e può avere soglie diverse per asse in ``metrics_asse``. Le sezioni
    ``gradini`` e ``tenuta`` (prove a gradino) vengono copiate così come sono.
    """
    prof = default_profile()
    prof["nome"] = data.get("nome", prof["nome"])
    if data.get("nota"):
        prof["nota"] = data["nota"]
    for loop, cfg in data.get("loops", {}).items():
        if loop not in prof["loops"]:
            continue
        base = prof["loops"][loop]
        for k in ("rise_target_s", "min_excitation"):
            if k in cfg:
                base[k] = cfg[k]
        if cfg.get("definizioni") == "scheda":
            base["definizioni"] = "scheda"
            base["gradino"] = copy.deepcopy(cfg.get("gradino", {}))
            base["metrics"] = _metric_set(cfg.get("metrics"))
            base["metrics_asse"] = {a: _metric_set(m) for a, m in cfg.get("metrics_asse", {}).items() if a in AXES}
            continue
        for mk, mv in cfg.get("metrics", {}).items():
            if mk in base["metrics"]:
                base["metrics"][mk].update({k: float(v) for k, v in mv.items() if k in ("good", "ok", "bad", "weight")})
            elif mk in METRIC_INFO:
                base["metrics"][mk] = {k: float(mv[k]) for k in ("good", "ok", "bad", "weight")}
    for sec in ("gradini", "tenuta"):
        if isinstance(data.get(sec), dict):
            prof[sec] = copy.deepcopy(data[sec])
    return prof


def definitions(profile, loop):
    """«scheda» se l'anello usa le definizioni della scheda di taratura, altrimenti «px4»."""
    return profile["loops"].get(loop, {}).get("definizioni", "px4")


def loop_metrics(profile, loop, axis=None):
    """Soglie delle metriche dell'anello, con quelle specifiche dell'asse se il profilo le ha."""
    cfg = profile["loops"][loop]
    if axis is not None and axis in cfg.get("metrics_asse", {}):
        return cfg["metrics_asse"][axis]
    return cfg["metrics"]


def step_spec(profile, loop, axis):
    """Gradino nominale della scheda per l'anello e l'asse: ampiezza, durata, fascia, finestra dell'errore."""
    g = profile["loops"].get(loop, {}).get("gradino", {})
    amp = float(g.get("ampiezza", {}).get(axis, 45.0 if loop == "mc_rate" else 10.0))
    dur = float(g.get("durata_s", {}).get(axis, 0.5 if loop == "mc_rate" else 1.5))
    if "fascia_assoluta" in g:
        band = float(g["fascia_assoluta"])
    else:
        band = amp * float(g.get("fascia_pct", 10.0)) / 100.0
    return {"amp": amp, "dur": dur, "band": band, "band_pct": float(g.get("fascia_pct", 10.0)),
            "err_last": g.get("errore_ultimi_s"), "err_from": g.get("errore_da_s"),
            "absolute_band": "fascia_assoluta" in g}


def save_profile(profile, path):
    Path(path).write_text(json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8")


# ----------------------------------------------------------------- obiettivi auto

RATE_PARAM_PREFIX = {"roll": "MC_ROLLRATE", "pitch": "MC_PITCHRATE", "yaw": "MC_YAWRATE"}
FW_RATE_PREFIX = {"roll": "FW_RR", "pitch": "FW_PR", "yaw": "FW_YR"}
MC_ATT_PARAM = {"roll": "MC_ROLL_P", "pitch": "MC_PITCH_P", "yaw": "MC_YAW_P"}
FW_TC_PARAM = {"roll": "FW_R_TC", "pitch": "FW_P_TC", "yaw": "FW_R_TC"}
MC_ATT_DEFAULT = {"roll": 6.5, "pitch": 6.5, "yaw": 2.8}


def rise_target(loop, axis, params, profile):
    """Obiettivo di tempo di salita [s] e descrizione di come è stato ottenuto."""
    cfg = profile["loops"][loop]["rise_target_s"].get(axis, "auto")
    if cfg != "auto":
        return float(cfg), _("impostato nel profilo")
    if loop == "mc_rate":
        base = float(params.get("MC_AT_RISE_TIME", 0.14))
        src = "MC_AT_RISE_TIME" if "MC_AT_RISE_TIME" in params else _("MC_AT_RISE_TIME predefinito")
        if axis == "yaw":
            return 2.0 * base, _("2 × {src} (imbardata più lenta)").format(src=src)
        return base, src
    if loop == "mc_att":
        p = float(params.get(MC_ATT_PARAM[axis], MC_ATT_DEFAULT[axis]))
        p = p if p > 0.1 else MC_ATT_DEFAULT[axis]
        return 2.2 / p, _("2,2 / {par} (risposta ideale del 1° ordine)").format(par=MC_ATT_PARAM[axis])
    tc = float(params.get(FW_TC_PARAM[axis], 0.4))
    tc = tc if tc > 0.05 else 0.4
    if loop == "fw_att":
        if axis == "yaw":
            return 2.2 * tc * 2, _("2 × 2,2 × {par} (euristica)").format(par=FW_TC_PARAM[axis])
        return 2.2 * tc, _("2,2 × {par} (risposta ideale del 1° ordine)").format(par=FW_TC_PARAM[axis])
    return 2.2 * tc / 4.0, _("2,2 × {par} / 4 (anello interno 4 volte più veloce)").format(par=FW_TC_PARAM[axis])


# ----------------------------------------------------------------------- punti


def metric_points(value, good, ok, bad):
    """Punti 0-100 con soglie a 100/60/0; funziona sia per "più basso è meglio" sia il contrario."""
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if math.isinf(value):
        value = 1e9 if value > 0 else -1e9
    higher_better = good > bad
    if higher_better:
        value, good, ok, bad = -value, -good, -ok, -bad
    if value <= good:
        return 100.0
    if value <= ok:
        return 100.0 - 40.0 * (value - good) / (ok - good)
    if value <= bad:
        return 60.0 - 60.0 * (value - ok) / (bad - ok)
    return 0.0


GRADES = (N_("Ottimo"), N_("Buono"), N_("Accettabile"), N_("Da rivedere"), N_("Non valutabile"))
CONFIDENCE = {"alta": N_("alta"), "media": N_("media"), "bassa": N_("bassa"), "—": "—"}


def grade(score):
    """Giudizio (chiave in italiano: tradurre con _() quando si mostra)."""
    if score is None:
        return "Non valutabile"
    if score >= 85:
        return "Ottimo"
    if score >= 70:
        return "Buono"
    if score >= 55:
        return "Accettabile"
    return "Da rivedere"


@dataclass
class ScoreItem:
    key: str
    label: str
    value: float | None
    spread: float | None
    unit: str
    fmt: str
    weight: float
    thresholds: tuple
    points: float | None
    note: str = ""

    def display(self):
        if self.value is None:
            return "—"
        if isinstance(self.value, float) and math.isinf(self.value):
            return _("non assestato") if self.key == "settling_band" else _("oltre la finestra")
        txt = self.fmt.format(self.value)
        if self.spread is not None:
            txt += " ± " + self.fmt.format(self.spread)
        return f"{txt} {self.unit}".strip()


@dataclass
class ScoreCard:
    items: list
    score: float | None
    coverage: float
    grade: str
    confidence: str
    confidence_reasons: list = field(default_factory=list)
    diagnostics: list = field(default_factory=list)


def build_scorecard(loop, values, spreads, notes, profile, axis=None):
    """values/spreads: dict metrica -> valore (None se non disponibile)."""
    cfg = loop_metrics(profile, loop, axis)
    items = []
    tot_w = 0.0
    got_w = 0.0
    acc = 0.0
    for key, th in cfg.items():
        label, unit, fmt = METRIC_INFO[key]
        label = _(label)
        val = values.get(key)
        pts = metric_points(val, th["good"], th["ok"], th["bad"])
        w = float(th["weight"])
        tot_w += w
        if pts is not None and w > 0:
            got_w += w
            acc += w * pts
        items.append(
            ScoreItem(key, label, val, spreads.get(key), unit, fmt, w, (th["good"], th["ok"], th["bad"]), pts,
                      notes.get(key, ""))
        )
    coverage = got_w / tot_w if tot_w else 0.0
    score = acc / got_w if got_w and coverage >= 0.5 else None
    return ScoreCard(items, score, coverage, grade(score), "—")


def combine_axes(cards: dict):
    """Punteggio complessivo della fase (pesi rollio 0,4, beccheggio 0,4, imbardata 0,2)."""
    acc = wsum = 0.0
    for axis, card in cards.items():
        if card is not None and card.score is not None:
            acc += AXIS_WEIGHTS[axis] * card.score
            wsum += AXIS_WEIGHTS[axis]
    if wsum < 0.5:
        return None
    return acc / wsum
