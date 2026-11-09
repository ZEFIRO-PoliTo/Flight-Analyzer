"""Strumenti di elaborazione del segnale (solo numpy).

Ricampionamento uniforme, intervalli temporali, spettri di Welch, spettrogrammi
e decimazione min/max per i grafici.
"""

from __future__ import annotations

import numpy as np

# --------------------------------------------------------------------- intervalli


def intersect(a, b):
    """Intersezione di due liste di intervalli [(t0, t1)] ordinate."""
    out = []
    i = j = 0
    a = sorted(a)
    b = sorted(b)
    while i < len(a) and j < len(b):
        lo = max(a[i][0], b[j][0])
        hi = min(a[i][1], b[j][1])
        if hi > lo:
            out.append((lo, hi))
        if a[i][1] < b[j][1]:
            i += 1
        else:
            j += 1
    return out


def total_length(intervals) -> float:
    return float(sum(t1 - t0 for t0, t1 in intervals))


def mask_from_intervals(t, intervals):
    t = np.asarray(t)
    mask = np.zeros(t.shape, dtype=bool)
    for t0, t1 in intervals:
        mask |= (t >= t0) & (t <= t1)
    return mask


def step_intervals(t, values, t_end):
    """Trasforma un segnale a gradini in [(t0, t1, valore)]."""
    t = np.asarray(t, dtype=float)
    values = np.asarray(values)
    if t.size == 0:
        return []
    change = np.flatnonzero(values[1:] != values[:-1]) + 1
    starts = np.concatenate(([0], change))
    out = []
    for k, s in enumerate(starts):
        t0 = t[s]
        t1 = t[starts[k + 1]] if k + 1 < len(starts) else max(t_end, t0)
        out.append((float(t0), float(t1), values[s].item() if hasattr(values[s], "item") else values[s]))
    return out


def intervals_where(t, cond, t_end):
    return [(a, b) for a, b, v in step_intervals(t, np.asarray(cond, dtype=bool), t_end) if v and b > a]


def merge_close(intervals, gap):
    out = []
    for t0, t1 in sorted(intervals):
        if out and t0 - out[-1][1] <= gap:
            out[-1] = (out[-1][0], max(out[-1][1], t1))
        else:
            out.append((t0, t1))
    return out


# ------------------------------------------------------------------ campionamento


def median_rate(t) -> float:
    t = np.asarray(t, dtype=float)
    if t.size < 3:
        return 0.0
    dt = np.diff(t)
    dt = dt[dt > 0]
    if dt.size == 0:
        return 0.0
    return float(1.0 / np.median(dt))


def resample(t, y, grid, method="linear"):
    """Ricampiona y(t) sulla griglia; 'zoh' mantiene l'ultimo valore (setpoint)."""
    t = np.asarray(t, dtype=float)
    y = np.asarray(y, dtype=float)
    if method == "zoh":
        idx = np.searchsorted(t, grid, side="right") - 1
        idx = np.clip(idx, 0, len(t) - 1)
        return y[idx]
    return np.interp(grid, t, y)


def next_pow2(n: int) -> int:
    return 1 << max(0, int(np.ceil(np.log2(max(1, n)))))


# ----------------------------------------------------------------------- spettri


def _segments(x, nperseg, step):
    n = len(x)
    if n < nperseg:
        return np.empty((0, nperseg))
    count = 1 + (n - nperseg) // step
    idx = np.arange(nperseg)[None, :] + step * np.arange(count)[:, None]
    return x[idx]


def welch_cross(x, y, fs, nperseg, overlap=0.5):
    """Spettri di Welch (finestra di Hann, detrend della media).

    Restituisce f, Sxx, Syy, Sxy (complesso, convenzione E[X* Y]) e il numero
    di medie; Sxy/Sxx è lo stimatore H1 della risposta x -> y.
    """
    step = max(1, int(nperseg * (1 - overlap)))
    xs = _segments(np.asarray(x, float), nperseg, step)
    ys = _segments(np.asarray(y, float), nperseg, step)
    f = np.fft.rfftfreq(nperseg, 1.0 / fs)
    if xs.shape[0] == 0:
        z = np.zeros_like(f)
        return f, z, z, z.astype(complex), 0
    w = np.hanning(nperseg)
    scale = 1.0 / (fs * np.sum(w**2))
    xs = (xs - xs.mean(axis=1, keepdims=True)) * w
    ys = (ys - ys.mean(axis=1, keepdims=True)) * w
    X = np.fft.rfft(xs, axis=1)
    Y = np.fft.rfft(ys, axis=1)
    sxx = np.mean(np.abs(X) ** 2, axis=0) * scale
    syy = np.mean(np.abs(Y) ** 2, axis=0) * scale
    sxy = np.mean(np.conj(X) * Y, axis=0) * scale
    if nperseg % 2 == 0:
        sxx[1:-1] *= 2
        syy[1:-1] *= 2
        sxy[1:-1] *= 2
    else:
        sxx[1:] *= 2
        syy[1:] *= 2
        sxy[1:] *= 2
    return f, sxx, syy, sxy, xs.shape[0]


class SpectralAccumulator:
    """Somma spettri incrociati su più segmenti di volo, pesando per il numero di medie."""

    def __init__(self, n_channels: int):
        self.n = n_channels
        self.f = None
        self.auto = None
        self.cross = None
        self.count = 0

    def add(self, signals, fs, nperseg):
        signals = [np.asarray(s, float) for s in signals]
        f, s00, _, _, n = welch_cross(signals[0], signals[0], fs, nperseg)
        if n == 0:
            return
        if self.f is None:
            self.f = f
            self.auto = np.zeros((self.n, f.size))
            self.cross = np.zeros((self.n, self.n, f.size), dtype=complex)
        for i in range(self.n):
            for j in range(i, self.n):
                _, sii, _, sij, _ = welch_cross(signals[i], signals[j], fs, nperseg)
                if i == j:
                    self.auto[i] += sii * n
                self.cross[i, j] += sij * n
                if i != j:
                    self.cross[j, i] += np.conj(sij) * n
        self.count += n

    def get(self):
        if self.count == 0:
            return None
        return self.f, self.auto / self.count, self.cross / self.count, self.count


def psd(x, fs, nperseg=None):
    x = np.asarray(x, float)
    if nperseg is None:
        nperseg = min(len(x), next_pow2(int(fs * 2)))
    nperseg = max(8, min(nperseg, len(x)))
    f, sxx, _, _, n = welch_cross(x, x, fs, nperseg)
    return f, sxx, n


def spectrogram(x, fs, nperseg=256, overlap=0.75):
    x = np.asarray(x, float)
    step = max(1, int(nperseg * (1 - overlap)))
    segs = _segments(x, nperseg, step)
    if segs.shape[0] == 0:
        return None
    w = np.hanning(nperseg)
    segs = (segs - segs.mean(axis=1, keepdims=True)) * w
    S = np.abs(np.fft.rfft(segs, axis=1)) ** 2 / (fs * np.sum(w**2))
    S[:, 1:-1] *= 2
    f = np.fft.rfftfreq(nperseg, 1.0 / fs)
    t = (np.arange(segs.shape[0]) * step + nperseg / 2) / fs
    return t, f, S.T


def band_rms(f, p, f_lo, f_hi):
    sel = (f >= f_lo) & (f <= f_hi)
    if np.count_nonzero(sel) < 2:
        return float("nan")
    return float(np.sqrt(_trapz(p[sel], f[sel])))


_trapz = getattr(np, "trapezoid", None) or getattr(np, "trapz")


# -------------------------------------------------------------------- decimazione


def minmax_decimate(t, y, n_bins=2000):
    """Riduce a ~2*n_bins punti mantenendo minimi e massimi (picchi visibili)."""
    t = np.asarray(t)
    y = np.asarray(y)
    n = len(t)
    if n <= 2 * n_bins:
        return t, y
    per = int(np.ceil(n / n_bins))
    m = (n // per) * per
    tt = t[:m].reshape(-1, per)
    yy = y[:m].reshape(-1, per)
    with np.errstate(invalid="ignore"):
        finite = np.isfinite(yy)
        safe_hi = np.where(finite, yy, -np.inf)
        safe_lo = np.where(finite, yy, np.inf)
        imax = np.argmax(safe_hi, axis=1)
        imin = np.argmin(safe_lo, axis=1)
    rows = np.arange(tt.shape[0])
    first = np.minimum(imin, imax)
    second = np.maximum(imin, imax)
    t_out = np.empty(2 * tt.shape[0])
    y_out = np.empty(2 * tt.shape[0])
    t_out[0::2] = tt[rows, first]
    t_out[1::2] = tt[rows, second]
    y_out[0::2] = yy[rows, first]
    y_out[1::2] = yy[rows, second]
    if m < n:
        t_out = np.concatenate((t_out, t[m:]))
        y_out = np.concatenate((y_out, y[m:]))
    return t_out, y_out
