"""Identificazione di un anello chiuso dai dati di volo.

Metodo: risposta impulsiva finita (FIR) stimata ai minimi quadrati dal
setpoint alla misura, su tutti i dati della fase scelta, con una piccola
regolarizzazione. La risposta al gradino è la somma cumulativa della risposta
impulsiva; la risposta in frequenza è la sua trasformata.

Perché non le finestre da 1 s di Flight Review/PID-Analyzer: nella validazione
su simulatore (tests/validate_loopid.py) la finestratura corta "spalma" la
coda lenta dell'integratore e sovrastima la sovraelongazione (es. 10% stimato
contro 1% vero); il FIR ai minimi quadrati non ha questo errore.

L'incertezza si ottiene con un jackknife a blocchi: i dati vengono divisi in
blocchi contigui, la stima viene ripetuta escludendone uno alla volta e la
dispersione dà l'intervallo di confidenza di ogni metrica.

Se è disponibile anche il comando di coppia u, si stima allo stesso modo la
risposta setpoint -> comando; il rapporto tra le due dà l'impianto P(f)
(valido anche in anello chiuso, perché il setpoint fa da riferimento esterno)
e, con il controllore noto dai parametri, il guadagno d'anello L = C·P.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from .i18n import _

# --------------------------------------------------------------- minimi quadrati


def _normal_equations(r, outputs, m, z=None, drop=None):
    """Equazioni normali esatte (metodo della covarianza) per un FIR di m prese.

    Con ``z`` (strumento) restituisce le equazioni delle variabili strumentali
    A[i,j] = Σ z[k-i] r[k-j], b[i] = Σ y[k] z[k-i]; senza, i minimi quadrati
    (z = r). Usa solo i campioni con m-1 campioni di storia. Costo O(n·m).
    ``drop``: campioni (True) le cui equazioni vanno tolte, per esempio i 50 ms dopo un cambio di modo:
    il tratto non viene spezzato, si sottraggono solo quelle righe.
    """
    n = len(r)
    rows = n - m + 1
    sym = z is None
    z = r if sym else z
    zt, rt = z[m - 1 :], r[m - 1 :]
    row0 = np.array([np.dot(zt, r[m - 1 - d : n - d]) for d in range(m)])  # A[0, d]
    col0 = row0 if sym else np.array([np.dot(z[m - 1 - d : n - d], rt) for d in range(m)])  # A[d, 0]
    a = np.empty((m, m))
    for d in range(m):
        cnt = m - d
        p = np.arange(cnt - 1)
        i = np.arange(cnt)
        # diagonale superiore A[i, i+d]
        add = z[m - 2 - p] * r[m - 2 - p - d] - z[n - 1 - p] * r[n - 1 - p - d]
        a[i, i + d] = row0[d] + np.concatenate(([0.0], np.cumsum(add)))
        if sym:
            a[i + d, i] = a[i, i + d]
        elif d > 0:
            # diagonale inferiore A[i+d, i]
            add = z[m - 2 - p - d] * r[m - 2 - p] - z[n - 1 - p - d] * r[n - 1 - p]
            a[i + d, i] = col0[d] + np.concatenate(([0.0], np.cumsum(add)))
    bs = []
    for y in outputs:
        yt = y[m - 1 :]
        bs.append(np.array([np.dot(yt, z[m - 1 - i : n - i]) for i in range(m)]))
    if drop is not None:
        k = np.flatnonzero(np.asarray(drop, bool))
        k = k[k >= m - 1]
        if k.size:
            idx = k[:, None] - np.arange(m)[None, :]
            zk, rk = z[idx], r[idx]
            a = a - zk.T @ rk
            bs = [b - zk.T @ y[k] for b, y in zip(bs, outputs)]
            rows -= int(k.size)
    return a, bs, rows


def _solve(a, b, lam, iv=False):
    if iv:
        ata = a.T @ a
        reg = (lam * np.linalg.norm(a) / np.sqrt(len(a))) ** 2 + 1e-30
        return np.linalg.solve(ata + reg * np.eye(len(a)), a.T @ b)
    reg = lam * max(np.trace(a) / len(a), 1e-12)
    return np.linalg.solve(a + reg * np.eye(len(a)), b)


@dataclass
class LoopEstimate:
    fs: float
    taps_s: float
    t: np.ndarray  # tempi della risposta al gradino mostrata [s]
    step: np.ndarray  # risposta al gradino stimata (setpoint -> misura)
    step_lo: np.ndarray  # banda di confidenza (jackknife, ~95%)
    step_hi: np.ndarray
    step_reps: np.ndarray  # repliche jackknife della risposta al gradino
    n_blocks: int
    samples: int  # campioni usati nella stima
    excited_time: float  # secondi con eccitazione del setpoint sufficiente
    f: np.ndarray  # frequenze [Hz]
    T: np.ndarray  # risposta in frequenza setpoint -> misura
    T_reps: np.ndarray  # repliche jackknife (n_blocks x len(f))
    P: np.ndarray | None = None  # impianto comando -> misura
    P_reps: np.ndarray | None = None
    notes: list = field(default_factory=list)

    def rel_uncertainty(self):
        """Incertezza relativa di |T| per frequenza (jackknife)."""
        return _jk_std(np.abs(self.T_reps)) / np.maximum(np.abs(self.T), 1e-9)


def _jk_std(reps):
    k = reps.shape[0]
    if k < 2:
        return np.zeros(reps.shape[1:])
    mean = reps.mean(axis=0)
    return np.sqrt((k - 1) / k * np.sum(np.abs(reps - mean) ** 2, axis=0))


def _freq_response(h, fs, f):
    k = np.arange(len(h))
    return np.exp(-2j * np.pi * np.outer(f, k) / fs) @ h


def estimate_loop(
    segments,
    fs,
    taps_s=1.0,
    resp_len=0.5,
    min_excitation=0.1,
    f_max=None,
    lam=1e-3,
    n_blocks=8,
):
    """Stima la risposta setpoint->misura (e setpoint->comando se ``u`` presente).

    ``segments``: lista di dict con array uniformi ``r``, ``y`` e opzionali ``u``
    (comando) e ``z`` (strumento: un segnale esterno correlato con il setpoint
    ma non con i disturbi, es. il setpoint d'assetto del pilota quando il
    setpoint di rate viene dall'anello d'assetto).
    ``min_excitation``: escursione picco-picco del setpoint (in 1 s) oltre la
    quale un tratto conta come "eccitato" (serve per l'affidabilità).
    Un segmento può avere ``w`` (bool, False = campione escluso): quelle
    equazioni vengono tolte senza spezzare il segmento.
    """
    m = int(round(taps_s * fs))
    show = int(round(resp_len * fs))
    if m < 8 or show < 4:
        return None
    has_u = bool(segments) and all(seg.get("u") is not None for seg in segments)
    min_len = 3 * m

    # blocchi contigui per il jackknife
    blocks = []
    total = sum(len(s["r"]) for s in segments if len(s["r"]) >= min_len)
    if total == 0:
        return None
    target = max(min_len, total // n_blocks)
    for seg in segments:
        n = len(seg["r"])
        if n < min_len:
            continue
        k = max(1, int(round(n / target)))
        edges = np.linspace(0, n, k + 1).astype(int)
        for a0, a1 in zip(edges[:-1], edges[1:]):
            if a1 - a0 >= min_len:
                blocks.append({key: (np.asarray(v[a0:a1], bool) if key == "w" else np.asarray(v[a0:a1], float))
                               for key, v in seg.items() if v is not None})
    if not blocks:
        return None

    # eccitazione: tratti di 1 s con escursione del setpoint sufficiente
    win = max(2, int(fs))
    excited = 0.0
    for blk in blocks:
        r = blk["r"]
        cnt = len(r) // win
        if cnt:
            rr = r[: cnt * win].reshape(cnt, win)
            exc = rr.max(axis=1) - rr.min(axis=1) >= min_excitation
            if blk.get("w") is not None:  # le finestre con campioni esclusi contano solo se restano piene
                exc &= blk["w"][: cnt * win].reshape(cnt, win).mean(axis=1) > 0.9
            excited += np.count_nonzero(exc)

    iv = any(blk.get("z") is not None for blk in blocks)
    A, By, Bu, rows = [], [], [], 0
    for blk in blocks:
        r = blk["r"]
        r0 = r  # niente rimozione della media: il guadagno statico è un'informazione
        outs = [blk["y"]] + ([blk["u"]] if has_u else [])
        z = blk.get("z")
        ok = np.isfinite(r0)
        for o in outs + ([z] if z is not None else []):
            ok &= np.isfinite(o)
        if not np.all(ok):
            r0 = np.where(ok, r0, 0.0)
            outs = [np.where(ok, o, 0.0) for o in outs]
            z = None if z is None else np.where(ok, z, 0.0)
        w = blk.get("w")
        a, bs, nrow = _normal_equations(r0, outs, m, z=z, drop=None if w is None else ~np.asarray(w, bool))
        A.append(a)
        By.append(bs[0])
        Bu.append(bs[1] if has_u else None)
        rows += nrow
    A_tot = np.sum(A, axis=0)
    By_tot = np.sum(By, axis=0)
    h_y = _solve(A_tot, By_tot, lam, iv)
    h_u = _solve(A_tot, np.sum(Bu, axis=0), lam, iv) if has_u else None

    nyq = 0.5 * fs
    f_hi = min(f_max or 0.8 * nyq, 0.8 * nyq)
    df = min(0.25, f_hi / 200)
    f = np.arange(df, f_hi + 1e-9, df)
    T = _freq_response(h_y, fs, f)
    P = None
    if has_u:
        Tu = _freq_response(h_u, fs, f)
        with np.errstate(divide="ignore", invalid="ignore"):
            P = T / Tu

    # jackknife
    nb = len(blocks)
    step_reps, T_reps, P_reps = [], [], []
    if nb >= 3:
        for i in range(nb):
            Ai = A_tot - A[i]
            hy = _solve(Ai, By_tot - By[i], lam, iv)
            step_reps.append(np.cumsum(hy)[:show])
            Ti = _freq_response(hy, fs, f)
            T_reps.append(Ti)
            if has_u:
                hu = _solve(Ai, np.sum(Bu, axis=0) - Bu[i], lam, iv)
                with np.errstate(divide="ignore", invalid="ignore"):
                    P_reps.append(Ti / _freq_response(hu, fs, f))
    step = np.cumsum(h_y)[:show]
    notes = [_("stima a variabili strumentali (setpoint dell'anello esterno come riferimento)")] if iv else []
    if step_reps:
        step_reps = np.array(step_reps)
        sd = _jk_std(step_reps)
        lo, hi = step - 2 * sd, step + 2 * sd
        T_reps = np.array(T_reps)
        P_reps = np.array(P_reps) if has_u else None
    else:
        step_reps = step[None, :]
        lo = hi = step.copy()
        T_reps = T[None, :]
        P_reps = P[None, :] if has_u else None
        notes.append(_("dati insufficienti per stimare l'incertezza (servono almeno 3 blocchi)"))
    return LoopEstimate(
        fs=fs,
        taps_s=taps_s,
        t=np.arange(show) / fs,
        step=step,
        step_lo=lo,
        step_hi=hi,
        step_reps=step_reps,
        n_blocks=nb,
        samples=rows,
        excited_time=float(excited),
        f=f,
        T=T,
        T_reps=T_reps,
        P=P,
        P_reps=P_reps,
        notes=notes,
    )


# --------------------------------------------------------------------- metriche


@dataclass
class StepMetrics:
    final: float  # livello a regime (media dell'ultimo 30% della finestra)
    rise_time: float | None  # 10-90% del valore finale [s]
    delay: float | None  # tempo al 50% [s]
    overshoot: float  # sovraelongazione relativa al valore finale [%]
    peak_time: float | None
    settling_time: float | None  # banda 5% [s]; None = non assestata nella finestra
    ss_error: float  # |1 - finale| [%]


def _cross_time(t, y, level):
    above = np.flatnonzero(y >= level)
    if above.size == 0:
        return None
    k = above[0]
    if k == 0:
        return float(t[0])
    y0, y1 = y[k - 1], y[k]
    frac = 0.0 if y1 == y0 else (level - y0) / (y1 - y0)
    return float(t[k - 1] + frac * (t[k] - t[k - 1]))


def step_metrics(t, s) -> StepMetrics:
    t = np.asarray(t)
    s = np.asarray(s)
    tail = s[int(len(s) * 0.7) :]
    final = float(np.mean(tail))
    ss_error = abs(1.0 - final) * 100.0
    if final <= 0.05:
        return StepMetrics(final, None, None, 0.0, None, None, ss_error)
    t10 = _cross_time(t, s, 0.1 * final)
    t90 = _cross_time(t, s, 0.9 * final)
    t50 = _cross_time(t, s, 0.5 * final)
    rise = (t90 - t10) if (t10 is not None and t90 is not None) else None
    k_peak = int(np.argmax(s))
    overshoot = max(0.0, (float(s[k_peak]) - final) / final * 100.0)
    outside = np.flatnonzero(np.abs(s - final) > 0.05 * abs(final))
    if outside.size == 0:
        settling = float(t[0])
    elif outside[-1] >= len(s) - max(2, len(s) // 20):
        settling = None
    else:
        settling = float(t[outside[-1] + 1])
    return StepMetrics(final, rise, t50, overshoot, float(t[k_peak]), settling, ss_error)


def step_metrics_spread(est: LoopEstimate):
    """Metriche della stima e loro deviazione standard jackknife."""
    main = step_metrics(est.t, est.step)
    reps = [step_metrics(est.t, s) for s in est.step_reps]
    k = len(reps)

    def sd(attr):
        vals = [getattr(r, attr) for r in reps]
        if k < 2 or any(v is None for v in vals):
            return None
        vals = np.array(vals, float)
        return float(np.sqrt((k - 1) / k * np.sum((vals - vals.mean()) ** 2)))

    spread = {a: sd(a) for a in ("rise_time", "overshoot", "settling_time", "ss_error", "final", "delay")}
    return main, spread


@dataclass
class FreqMetrics:
    f_valid_max: float  # fino a dove la stima è affidabile (incertezza < 20%)
    bandwidth: float | None  # -3 dB di |T| [Hz]
    bandwidth_lower_bound: bool  # True se |T| non scende sotto -3 dB nella banda valida
    resonance_db: float | None  # picco di |T| [dB]
    resonance_f: float | None
    delay_ms: float | None  # ritardo equivalente dalla fase a bassa frequenza


def _valid_band(est: LoopEstimate, max_rel=0.2):
    """Tratto contiguo di frequenze affidabili che parte dalle basse frequenze."""
    rel = est.rel_uncertainty()
    ok = (rel <= max_rel) & np.isfinite(est.T)
    start = np.flatnonzero(ok & (est.f <= 2.0))
    if start.size == 0:
        return 0, 0
    k0 = int(start[0])
    bad = np.flatnonzero(~ok[k0:])
    return k0, (k0 + int(bad[0])) if bad.size else len(ok)


def freq_metrics(est: LoopEstimate) -> FreqMetrics:
    k0, kmax = _valid_band(est)
    if kmax - k0 < 4:
        return FreqMetrics(0.0, None, False, None, None, None)
    fv, Tv = est.f[k0:kmax], est.T[k0:kmax]
    mag = np.abs(Tv)
    below = np.flatnonzero(mag < 1 / np.sqrt(2))
    if below.size:
        kb = below[0]
        if kb == 0:
            bw = float(fv[0])
        else:
            m0, m1 = 20 * np.log10(mag[kb - 1]), 20 * np.log10(mag[kb])
            frac = (-3.0103 - m0) / (m1 - m0) if m1 != m0 else 0.0
            bw = float(fv[kb - 1] + frac * (fv[kb] - fv[kb - 1]))
        lb = False
        search = slice(0, kb + 1)
    else:
        bw, lb = float(fv[-1]), True
        search = slice(0, len(fv))
    kpk = int(np.argmax(mag[search]))
    res_db = float(20 * np.log10(mag[kpk])) if mag[kpk] > 0 else None
    phase = np.unwrap(np.angle(Tv))
    lowsel = (fv >= 0.5) & (fv <= min(4.0, 0.5 * bw))
    delay = None
    if np.count_nonzero(lowsel) >= 3:
        slope = np.polyfit(2 * np.pi * fv[lowsel], phase[lowsel], 1)[0]
        delay = float(-slope * 1000.0)
    return FreqMetrics(float(fv[-1]), bw, lb, res_db, float(fv[kpk]), delay)


@dataclass
class Margins:
    valid: bool
    reason: str
    f_band: tuple = (0.0, 0.0)
    crossover_hz: float | None = None
    phase_margin_deg: float | None = None
    gain_margin_db: float | None = None
    ms: float | None = None  # picco della funzione di sensitività |1/(1+L)|
    ms_f: float | None = None
    pm_sd: float | None = None
    ms_sd: float | None = None
    partial: bool = False
    f: np.ndarray | None = None
    L: np.ndarray | None = None


def mc_rate_controller(f, kp, ki, kd, k=1.0, dgyro_cutoff=20.0):
    """C_fb(f) del rate controller multicottero PX4 (v1.14+) visto dal giroscopio filtrato.

    coppia = K*(P*e + I*int(e) - D*accel) + FF*sp, dove accel è la derivata
    del giroscopio già filtrato, passata nel filtro del 1° ordine
    IMU_DGYRO_CUTOFF (VehicleAngularVelocity.cpp in v1.17).
    """
    s = 2j * np.pi * np.asarray(f, float)
    with np.errstate(divide="ignore", invalid="ignore"):
        hd = 1.0 / (1.0 + s / (2 * np.pi * dgyro_cutoff)) if dgyro_cutoff and dgyro_cutoff > 0 else 1.0
        return k * (kp + ki / s + kd * s * hd)


def _margins_from_L(fv, L):
    mag = np.abs(L)
    S = 1.0 / np.abs(1.0 + L)
    kms = int(np.argmax(S))
    out = {"ms": float(S[kms]), "ms_f": float(fv[kms]), "fc": None, "pm": None, "gm": None}
    cross = np.flatnonzero((mag[:-1] >= 1.0) & (mag[1:] < 1.0))
    if cross.size == 0:
        out["why"] = (
            _("il guadagno d'anello resta sopra 1 in tutta la banda stimata")
            if np.all(mag >= 1.0)
            else _("il guadagno d'anello è sotto 1 già all'inizio della banda stimata")
        )
        return out
    c = cross[0]
    l0, l1 = np.log10(mag[c]), np.log10(mag[c + 1])
    frac = l0 / (l0 - l1) if l0 != l1 else 0.0
    fc = float(fv[c] + frac * (fv[c + 1] - fv[c]))
    ph = np.unwrap(np.angle(L))
    ph_c = ph[c] + frac * (ph[c + 1] - ph[c])
    pm = float(np.degrees(ph_c) + 180.0)
    pm = (pm + 180.0) % 360.0 - 180.0
    deg = np.degrees(ph) + 180.0
    j = np.flatnonzero((deg[:-1] > 0) & (deg[1:] <= 0) & (fv[:-1] > fc))
    gm = float(-20 * np.log10(mag[j[0]])) if j.size else None
    # margine di guadagno solo se l'attraversamento di -180° è ben dentro la banda stimata
    if j.size and fv[j[0]] > 0.8 * fv[-1]:
        gm = None
    out.update(fc=fc, pm=pm, gm=gm)
    return out


def loop_margins(est: LoopEstimate, controller, max_rel=0.25) -> Margins:
    """Margini di guadagno/fase e picco di sensitività con incertezza jackknife."""
    if est.P is None:
        return Margins(False, _("comando di coppia non disponibile nel log"))
    f = est.f
    rel_t = est.rel_uncertainty()
    rel_p = _jk_std(np.abs(est.P_reps)) / np.maximum(np.abs(est.P), 1e-12) if est.P_reps.shape[0] > 1 else rel_t
    ok = (rel_t <= max_rel) & (rel_p <= max_rel) & np.isfinite(est.P) & (f >= 0.5)
    # tratto contiguo che parte dalle basse frequenze (sopra si accetta un solo buco di 1 campione)
    start = np.flatnonzero(ok & (f <= 3.0))
    if start.size == 0:
        return Margins(False, _("eccitazione insufficiente alle frequenze dell'anello: impianto non identificabile"))
    k0 = int(start[0])
    k1 = k0
    gap = 0
    for k in range(k0, len(f)):
        if ok[k]:
            k1, gap = k, 0
        else:
            gap += 1
            if gap > 1:
                break
    g = np.arange(k0, k1 + 1)
    if len(g) < 6:
        return Margins(False, _("banda identificata troppo stretta"))
    sel = np.arange(g[0], g[-1] + 1)
    fv = f[sel]
    C = controller(fv)
    L = C * est.P[sel]
    main = _margins_from_L(fv, L)
    band = (float(fv[0]), float(fv[-1]))
    if main["fc"] is None:
        return Margins(False, main["why"] + f" ({band[0]:.1f}–{band[1]:.1f} Hz)", band, ms=main["ms"],
                       ms_f=main["ms_f"], partial=True, f=fv, L=L)
    pms, mss = [], []
    if est.P_reps is not None and est.P_reps.shape[0] >= 3:
        for Pr in est.P_reps:
            mr = _margins_from_L(fv, C * Pr[sel])
            if mr["pm"] is not None:
                pms.append(mr["pm"])
            mss.append(mr["ms"])
    kk = len(pms)
    pm_sd = float(np.sqrt((kk - 1) / kk * np.sum((np.array(pms) - np.mean(pms)) ** 2))) if kk >= 3 else None
    kk = len(mss)
    ms_sd = float(np.sqrt((kk - 1) / kk * np.sum((np.array(mss) - np.mean(mss)) ** 2))) if kk >= 3 else None
    partial = fv[-1] < 1.5 * main["fc"]
    reason = "ok" if not partial else _("banda stimata solo fino a {f:.0f} Hz: Ms potrebbe essere sottostimato").format(
        f=fv[-1])
    return Margins(True, reason, band, main["fc"], main["pm"], main["gm"], main["ms"], main["ms_f"],
                   pm_sd, ms_sd, partial, fv, L)
