"""Confronta le stime dai dati con la verità del simulatore (risposta e margini)."""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from flight_analyzer import dsp, loopid  # noqa: E402
from simulate import gust_disturbance, pilot_setpoint, simulate_axis, true_plant, true_step  # noqa: E402

FS = 400.0
PLANT = {"b": 250.0, "tau_m": 0.035, "damping": 0.0, "delay": 1}
TUNES = {
    "A_buono": dict(kp=0.10, ki=0.15, kd=0.0035, kff=0.0, k=1.0, int_lim=0.3, gyro_cut=40, dgyro_cut=20),
    "B_default": dict(kp=0.15, ki=0.20, kd=0.003, kff=0.0, k=1.0, int_lim=0.3, gyro_cut=40, dgyro_cut=20),
    "C_oscill": dict(kp=0.25, ki=0.30, kd=0.0012, kff=0.0, k=1.0, int_lim=0.3, gyro_cut=40, dgyro_cut=20),
}


def truth_margins(gains):
    u, y, damp = true_plant(FS, PLANT, gains, duration=300.0)
    f, suu, _, suy, _ = dsp.welch_cross(u, y, FS, int(FS * 4))
    P = suy / suu
    s = 2j * np.pi * f
    with np.errstate(divide="ignore", invalid="ignore"):
        P = P * (s + damp) / s  # rimuove lo smorzamento aggiunto solo per la prova
    sel = (f >= 0.5) & (f <= 80)
    C = loopid.mc_rate_controller(f[sel], gains["kp"], gains["ki"], gains["kd"], gains["k"], gains["dgyro_cut"])
    return loopid._margins_from_L(f[sel], C * P[sel])


def run(name, gains, duration=120.0, log_fs=None, noise=0.02, seed=1):
    r = pilot_setpoint(duration, FS, amp=1.5, seed=seed)
    d = gust_disturbance(duration, FS, level=8.0, seed=seed + 10)
    out = simulate_axis(r, FS, gains, dict(PLANT, seed=seed), noise=noise, dist=d)
    fs = FS
    rr, yy, uu = r, out["y"], out["u"]
    if log_fs:
        step = int(FS / log_fs)
        rr, yy, uu = rr[::step], yy[::step], uu[::step]
        fs = FS / step
    est = loopid.estimate_loop([{"r": rr, "y": yy, "u": uu}], fs, taps_s=1.0, resp_len=0.5,
                               min_excitation=0.2)
    ts = true_step(FS, gains, PLANT, 0.5)
    tm = loopid.step_metrics(np.arange(len(ts)) / FS, ts)
    em, sp = loopid.step_metrics_spread(est)
    fm = loopid.freq_metrics(est)
    ctrl = lambda ff: loopid.mc_rate_controller(ff, gains["kp"], gains["ki"], gains["kd"], gains["k"], gains["dgyro_cut"])
    mg = loopid.loop_margins(est, ctrl)
    tmg = truth_margins(gains)
    tag = f"{name} fs_log={fs:.0f}"
    print(f"\n== {tag}: blocchi {est.n_blocks} campioni {est.samples}, eccitato {est.excited_time:.0f}s")
    fmt = lambda v, s=1e3: "  —  " if v is None else f"{v * s:6.1f}"
    print(f"   rise[ms] vero {fmt(tm.rise_time)} stimato {fmt(em.rise_time)}")
    print(f"   overshoot[%] vero {tm.overshoot:6.1f} stimato {em.overshoot:6.1f} ± {sp['overshoot'] or 0:.1f}")
    print(f"   settling5%[ms] vero {fmt(tm.settling_time)} stimato {fmt(em.settling_time)}")
    print(f"   finale vero {tm.final:.3f} stimato {em.final:.3f}")
    print(f"   banda -3dB {fm.bandwidth} (limite inf={fm.bandwidth_lower_bound}) Mr {fm.resonance_db} dB @ {fm.resonance_f} valid<= {fm.f_valid_max}")
    print(f"   margini veri: fc {tmg['fc']:.2f} Hz PM {tmg['pm']:.1f} GM {tmg['gm']} Ms {tmg['ms']:.2f}")
    if mg.valid:
        print(f"   margini stimati: fc {mg.crossover_hz:.2f} Hz PM {mg.phase_margin_deg:.1f}±{mg.pm_sd or 0:.1f} GM {mg.gain_margin_db} Ms {mg.ms:.2f}±{mg.ms_sd or 0:.2f} banda {mg.f_band} {mg.reason}")
    else:
        print(f"   margini stimati: non validi ({mg.reason}) Ms parziale {mg.ms}")
    return est, ts


if __name__ == "__main__":
    for name, g in TUNES.items():
        run(name, g)
    run("B_default", TUNES["B_default"], log_fs=50)
    run("B_default", TUNES["B_default"], log_fs=100)
