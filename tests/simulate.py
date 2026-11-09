"""Simulatore di un asse con il rate controller di PX4 v1.14+ (per i test).

Riproduce la catena di PX4: giroscopio -> passa-basso Butterworth del 2° ordine
(IMU_GYRO_CUTOFF) -> errore P/I; derivata del giroscopio filtrato -> filtro del
1° ordine (IMU_DGYRO_CUTOFF) -> termine D; coppia = K(P e + I - D a) + FF sp;
integratore con limite e fattore di riduzione come in rate_control.cpp; un
campione di ritardo tra calcolo e attuazione; motori del 1° ordine.
"""

from __future__ import annotations

import numpy as np


class LPF2:
    """math::LowPassFilter2p di PX4."""

    def __init__(self, fs, fc):
        fr = fs / fc
        ohm = np.tan(np.pi / fr)
        c = 1.0 + 2.0 * np.cos(np.pi / 4.0) * ohm + ohm * ohm
        self.b0 = ohm * ohm / c
        self.b1 = 2.0 * self.b0
        self.b2 = self.b0
        self.a1 = 2.0 * (ohm * ohm - 1.0) / c
        self.a2 = (1.0 - 2.0 * np.cos(np.pi / 4.0) * ohm + ohm * ohm) / c
        self.d1 = self.d2 = 0.0

    def __call__(self, x):
        d0 = x - self.d1 * self.a1 - self.d2 * self.a2
        y = d0 * self.b0 + self.d1 * self.b1 + self.d2 * self.b2
        self.d2 = self.d1
        self.d1 = d0
        return y


class Alpha:
    def __init__(self, fs, fc):
        dt = 1.0 / fs
        tau = 1.0 / (2 * np.pi * fc)
        self.a = dt / (tau + dt)
        self.y = 0.0

    def __call__(self, x):
        self.y += self.a * (x - self.y)
        return self.y


def simulate_cascade(att_sp, fs, att_gain, gains, plant, rate_max=3.8, noise=0.0, dist=None, rate_ff=None):
    """Assetto -> rate: rate_sp = att_gain*(att_sp - att) (+ rate_ff), poi simulate_axis."""
    return simulate_axis(None, fs, gains, plant, noise=noise, dist=dist,
                         outer={"att_sp": att_sp, "k": att_gain, "max": rate_max, "ff": rate_ff})


def simulate_axis(r, fs, gains, plant, noise=0.0, dist=None, sub=8, u_extra=None, open_loop_u=None, outer=None,
                  external=None):
    """Simula un asse. ``r`` setpoint a fs [rad/s]. Restituisce un dict di array.

    gains: kp, ki, kd, kff, k, int_lim, gyro_cut, dgyro_cut
    plant: b (rad/s^2 per unità di coppia), tau_m [s], damping [1/s], delay (campioni)
    open_loop_u: se dato, ignora il controllore e applica questo comando.
    outer: anello d'assetto {"att_sp": array o funzione (i, assetto) -> setpoint, "k", "max", "ff"}.
    external: maschera booleana; dove è True il setpoint di rate è ``r`` (Acro/Offboard), altrimenti viene
    dall'anello d'assetto (Hold). La funzione dell'assetto viene chiamata a ogni campione (per i modelli che
    integrano altri stati, come la velocità laterale).
    """
    n = len(r) if r is not None else len(outer["att_sp"])
    dt = 1.0 / fs
    h = dt / sub
    att = 0.0
    lp = LPF2(fs, gains.get("gyro_cut", 40.0))
    al = Alpha(fs, gains.get("dgyro_cut", 20.0))
    kp, ki, kd = gains["kp"], gains["ki"], gains["kd"]
    kff, k = gains.get("kff", 0.0), gains.get("k", 1.0)
    lim = gains.get("int_lim", 0.3)
    b, tau, damp = plant["b"], plant["tau_m"], plant.get("damping", 0.0)
    delay = int(plant.get("delay", 1))
    rng = np.random.default_rng(plant.get("seed", 0))
    omega = 0.0
    act = 0.0
    integ = 0.0
    yf_prev = 0.0
    queue = [0.0] * max(1, delay)
    out = {k_: np.zeros(n) for k_ in ("y", "a", "u", "integ", "omega", "sat", "r", "att", "att_sp")}
    dist = np.zeros(n) if dist is None else dist
    for i in range(n):
        y_raw = omega + (noise * rng.standard_normal() if noise else 0.0)
        yf = lp(y_raw)
        acc = al((yf - yf_prev) * fs)
        yf_prev = yf
        if outer is not None:
            asp = outer["att_sp"](i, att) if callable(outer["att_sp"]) else outer["att_sp"][i]
            out["att_sp"][i] = asp
        if outer is not None and (external is None or not external[i]):
            ri = outer["k"] * (asp - att)
            if outer.get("ff") is not None:
                ri += outer["ff"][i]
            ri = float(np.clip(ri, -outer["max"], outer["max"]))
        else:
            ri = r[i]
        out["r"][i] = ri
        out["att"][i] = att
        if open_loop_u is not None:
            u = open_loop_u[i]
        else:
            e = ri - yf
            u = k * kp * e + integ - k * kd * acc + kff * ri
            if u_extra is not None:
                u += u_extra[i]
            sat = abs(u) > 1.0
            if sat:
                out["sat"][i] = 1.0
            # integratore come in RateControl::updateIntegral (senza anti-windup da allocatore)
            if not (sat and np.sign(e) == np.sign(u)):
                fct = e / np.radians(400.0)
                fct = max(0.0, 1.0 - fct * fct)
                integ = np.clip(integ + fct * k * ki * e * dt, -lim, lim)
            u = float(np.clip(u, -1.0, 1.0))
        out["y"][i] = yf
        out["a"][i] = acc
        out["u"][i] = u
        out["integ"][i] = integ
        out["omega"][i] = omega
        queue.append(u)
        u_app = queue.pop(0)
        for _ in range(sub):
            act += h * (u_app - act) / tau
            omega += h * (b * act - damp * omega + dist[i])
            att += h * omega
    return out


def pilot_setpoint(duration, fs, amp, seed=1, hold=(0.25, 1.2), smooth=0.03, zero_prob=0.45):
    """Setpoint "da pilota": gradini e impulsi casuali smussati dal movimento dello stick."""
    rng = np.random.default_rng(seed)
    n = int(duration * fs)
    r = np.zeros(n)
    i = 0
    while i < n:
        length = int(rng.uniform(*hold) * fs)
        if rng.random() < zero_prob:
            val = 0.0
        else:
            val = amp * rng.uniform(0.3, 1.0) * rng.choice([-1.0, 1.0])
        r[i : i + length] = val
        i += length
    alpha = 1.0 / (1.0 + smooth * fs)
    out = np.zeros(n)
    acc = 0.0
    for j in range(n):
        acc += alpha * (r[j] - acc)
        out[j] = acc
    return out


def gust_disturbance(duration, fs, level, seed=3, fc=1.5):
    rng = np.random.default_rng(seed)
    n = int(duration * fs)
    w = rng.standard_normal(n)
    a = 1.0 / (1.0 + fs / (2 * np.pi * fc))
    out = np.zeros(n)
    acc = 0.0
    for j in range(n):
        acc += a * (w[j] - acc)
        out[j] = acc
    return level * out / (np.std(out) + 1e-12)


def true_step(fs, gains, plant, duration=1.0):
    r = np.ones(int(duration * fs))
    return simulate_axis(r, fs, gains, plant)["y"]


def true_plant(fs, plant, gains, duration=400.0, seed=7):
    """Risposta in frequenza vera comando -> giroscopio filtrato (anello aperto)."""
    rng = np.random.default_rng(seed)
    n = int(duration * fs)
    u = 0.05 * rng.standard_normal(n)
    pl = dict(plant)
    pl["damping"] = max(pl.get("damping", 0.0), 2.0)  # evita la deriva dell'integratore puro
    out = simulate_axis(np.zeros(n), fs, gains, pl, open_loop_u=u)
    return u, out["y"], pl["damping"]
