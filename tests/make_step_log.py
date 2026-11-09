"""Log sintetico del Vespa in hover con prove a gradino di rollio in Offboard a velocità angolare (PX4 1.17).

Uso: python tests/make_step_log.py USCITA.ulg [--senza-gradini] [--senza-correzione] [--sdlog131]

Riproduce quello che fa lo script gradini_vespa.py: per ogni gradino Offboard, 0 °/s per 0,5 s, gradino per la durata
scelta, 0 per 0,5 s, poi Hold. Il setpoint arriva ogni 24 ms (come nel log del 4/11). In Offboard
vehicle_attitude_setpoint non viene pubblicato e i flag di vehicle_control_mode sono quelli di PX4 (velocità angolare
attiva, assetto spento). A ogni passaggio in Hold c'è un picco di un ciclo (−120 °/s per 10 ms sul setpoint di rate,
45° sul setpoint d'assetto). Sequenza:

    1–6  sei gradini validi da ±45 °/s per 0,5 s (nel terzo il motore 2 va a fondo scala per 3 campioni)
    7    gradino troncato (0,35 s)
    8    doppietto senza Hold in mezzo: il secondo mezzo parte inclinato e in scivolata
    9    doppietto interrotto da un passaggio in Hold durante il secondo mezzo
    poi 40 s fermo in Hold (tenuta) e atterraggio.

Opzioni: --senza-gradini (solo Hold), --senza-correzione (torque_setpoint_achieved sempre falso e integratori fermi,
come un PX4 senza la correzione dell'allocatore del tiltrotor), --sdlog131 (SDLOG_PROFILE = 131 e motori registrati a
10 Hz).

Accanto al log viene scritto USCITA.verita.json: gradini attesi con l'esito, grandezze vere di ogni gradino (calcolate
qui sui segnali della simulazione a 500 Hz senza rumore, con un calcolo indipendente da steptest) e il tempo al 50%
vero della risposta al gradino dell'anello di rollio.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from simulate import simulate_axis, true_step  # noqa: E402
from ulog_writer import ULogWriter  # noqa: E402

FS = 500.0  # passo della simulazione [Hz]
G = 9.81
GAINS = dict(kp=0.26, ki=0.30, kd=0.004, kff=0.0, k=1.0, int_lim=0.3, gyro_cut=40, dgyro_cut=20)
PLANT = {"b": 30.0, "tau_m": 0.05, "delay": 4, "damping": 0.0, "seed": 11}
ATT_P = 3.5
RATE_MAX = np.radians(120.0)
A = np.radians(45.0)
OFFB_DT = 0.024  # periodo dei setpoint dello script [s]
PY = np.array([0.6917, -0.4083, -0.7083, 0.3917])  # posizione laterale dei 4 rotori (CA_ROTORi_PY)
NAV = {"takeoff": 17, "hold": 4, "offboard": 14, "land": 18}
FLAGS_HOLD = ("auto", "position", "velocity", "altitude", "climb_rate", "attitude", "rates", "allocation")
FLAGS_OFFB = ("offboard", "rates", "allocation")
ALL_FLAGS = ("manual", "auto", "offboard", "position", "velocity", "altitude", "climb_rate", "acceleration",
             "attitude", "rates", "allocation", "termination")


def plan(with_steps=True):
    """Programma dello script: [(tipo, inizio Offboard, pezzi)], pezzi = [(ritardo dall'inizio, durata, verso)]."""
    if not with_steps:
        return []
    out = []
    t = 20.0
    for k, sign in enumerate((1, -1, 1, -1, 1, -1)):
        out.append({"label": f"valido {k + 1}", "t_on": t, "pieces": [(0.5, 0.5, sign)], "hold_after": 1.5,
                    "expect": [True], "sat": k == 2})
        t += 6.0
    out.append({"label": "troncato", "t_on": t, "pieces": [(0.5, 0.35, 1)], "hold_after": 1.4, "expect": [False],
                "reason": ["troncato"]})
    t += 6.0
    out.append({"label": "doppietto senza Hold", "t_on": t, "pieces": [(0.5, 0.5, 1), (2.5, 0.5, -1)],
                "hold_after": 3.5, "expect": [True, False], "reason": [None, "partenza non ferma"]})
    t += 8.0
    t += 4.0  # più tempo in Hold dopo il doppietto senza Hold, per ripartire fermi
    out.append({"label": "doppietto interrotto", "t_on": t, "pieces": [(0.5, 0.5, 1), (2.5, 0.5, -1)],
                "hold_after": 2.7, "expect": [True, False], "reason": [None, "cambio di modo"]})
    t += 7.0
    return out


def build(path, with_steps=True, alloc_fix=True, sdlog131=False, gains=None):
    """Scrive il log e la verità; ``gains`` sostituisce i guadagni del rollio (kp, ki, kd, ...)."""
    gains_used = dict(GAINS, **(gains or {}))
    steps = plan(with_steps)
    t_end_steps = (steps[-1]["t_on"] + 7.0) if steps else 20.0
    t_land = t_end_steps + 40.0
    T = t_land + 8.0
    n = int(T * FS)
    t = np.arange(n) / FS

    # modi e setpoint dello script
    nav = np.full(n, NAV["hold"])
    nav[t < 8.0] = NAV["takeoff"]
    nav[t >= t_land] = NAV["land"]
    ext = np.zeros(n, bool)
    r = np.zeros(n)
    changes = []
    truth_steps = []
    for st in steps:
        t_on, t_off = st["t_on"], st["t_on"] + st["hold_after"]
        sel = slice(int(round(t_on * FS)), int(round(t_off * FS)))
        nav[sel] = NAV["offboard"]
        ext[sel] = True
        changes += [t_on, t_off]
        tick = int(round(OFFB_DT * FS))
        k_on, k_off = int(round(t_on * FS)), int(round(t_off * FS))
        for k, (dt0, dur, sign) in enumerate(st["pieces"]):
            # lo script manda un setpoint ogni 24 ms: i fronti cadono su quella griglia (indici interi)
            ka = k_on + int(round(dt0 / OFFB_DT)) * tick
            kb = min(ka + int(round(dur / OFFB_DT)) * tick, k_off)
            r[ka:kb] = sign * A
            a, b = ka / FS, kb / FS
            truth_steps.append({"plan": st["label"], "t_start": a, "t_end": b, "sign": sign,
                                "valid": st["expect"][k],
                                "reason": (st.get("reason") or [None] * 2)[k] if not st["expect"][k] else None,
                                "sat": bool(st.get("sat")) and k == 0})
        # picco di un ciclo al passaggio in Hold (10 ms a −120 °/s)
        spike = slice(int(round(t_off * FS)), int(round((t_off + 0.010) * FS)))
        ext[spike] = True
        r[spike] = -RATE_MAX
    held = np.where(ext, r, 0.0)
    # istanti dei messaggi dello script (ogni 24 ms in Offboard)
    ticks = []
    for st in steps:
        k0 = int(round(st["t_on"] * FS))
        k1 = int(round((st["t_on"] + st["hold_after"]) * FS))
        ticks += list(range(k0, k1, int(round(OFFB_DT * FS))))
    ticks = np.array(ticks, int)

    # dinamica laterale (Hold: anello di velocità che riporta il velivolo fermo)
    lat = {"vy": 0.0, "y": 0.0}

    def att_sp(i, att):
        vy = lat["vy"]
        sp = float(np.clip(-0.12 * vy, -0.35, 0.35))  # Hold: frena e resta dove si è fermato
        lat["vy"] += (G * np.tan(att) - 0.5 * vy) / FS
        lat["y"] += lat["vy"] / FS
        vys[i], ys[i] = lat["vy"], lat["y"]
        return sp

    vys, ys = np.zeros(n), np.zeros(n)
    rng = np.random.default_rng(3)
    clean = simulate_axis(held, FS, gains_used, PLANT, outer={"att_sp": att_sp, "k": ATT_P, "max": RATE_MAX},
                          external=ext)
    lat.update(vy=0.0, y=0.0)
    vys_c, ys_c = vys.copy(), ys.copy()
    o = simulate_axis(held, FS, gains_used, dict(PLANT, seed=5), noise=0.002,
                      outer={"att_sp": att_sp, "k": ATT_P, "max": RATE_MAX}, external=ext)
    roll_rate, roll, roll_sp_rate, u = o["y"], o["att"], o["r"], o["u"]
    roll_att_sp = o["att_sp"]

    # verità di ogni gradino dalla simulazione senza rumore (500 Hz)
    for ts in truth_steps:
        ts.update(_truth(t, clean["y"], ts["t_start"], ts["t_end"], ts["sign"]))
        k = int(round(ts["t_start"] * FS))
        ts["start_roll_deg"] = float(np.degrees(clean["att"][k]))
        ts["start_vy"] = float(vys_c[k])
    y1 = true_step(FS, gains_used, dict(PLANT, seed=0), 1.0)
    t50 = float(np.flatnonzero(y1 >= 0.5)[0] / FS)

    # --------------------------------------------------------------- log
    us = (t * 1e6).astype(np.int64) + 1_000_000
    w = ULogWriter(start_timestamp=1_000_000)
    i250 = np.arange(0, n, 2)
    i125 = np.arange(0, n, 4)

    def every(hz):
        return np.arange(0, n, int(round(FS / hz)))

    # vehicle_status (a ogni cambio e a 10 Hz)
    vs = np.unique(np.concatenate([every(10), np.flatnonzero(np.diff(nav)) + 1]))
    w.add_format("vehicle_status", ["uint64_t timestamp", "uint8_t nav_state", "uint8_t arming_state",
                                    "uint8_t vehicle_type", "bool is_vtol", "bool in_transition_mode"])
    w.add_topic("vehicle_status", {"timestamp": us[vs], "nav_state": nav[vs], "arming_state": np.where(
        t[vs] < T - 2, 2, 1), "vehicle_type": np.ones(len(vs)), "is_vtol": np.ones(len(vs))})
    w.add_format("vehicle_control_mode", ["uint64_t timestamp", "bool flag_armed"]
                 + [f"bool flag_control_{f}_enabled" for f in ALL_FLAGS])
    cm = {"timestamp": us[vs], "flag_armed": np.ones(len(vs))}
    for f in ALL_FLAGS:
        on_hold, on_offb = f in FLAGS_HOLD, f in FLAGS_OFFB
        cm[f"flag_control_{f}_enabled"] = np.where(nav[vs] == NAV["offboard"], on_offb, on_hold).astype(int)
    w.add_topic("vehicle_control_mode", cm)
    w.add_format("vehicle_land_detected", ["uint64_t timestamp", "bool landed"])
    landed = (t < 3.0) | (t > T - 3.0)
    w.add_topic("vehicle_land_detected", {"timestamp": us[vs], "landed": landed[vs].astype(int)})

    # setpoint di rate: 250 Hz in Hold, ogni 24 ms in Offboard (più il picco al passaggio in Hold)
    in_offb = nav == NAV["offboard"]
    rs_idx = np.unique(np.concatenate([i250[~in_offb[i250]], ticks]).astype(int))
    noise_sp = 0.002 * rng.standard_normal((n, 2))
    w.add_format("vehicle_rates_setpoint", ["uint64_t timestamp", "float roll", "float pitch", "float yaw",
                                            "float[3] thrust_body"])
    w.add_topic("vehicle_rates_setpoint", {"timestamp": us[rs_idx] + 200, "roll": roll_sp_rate[rs_idx],
                                           "pitch": np.where(in_offb[rs_idx], 0.0, noise_sp[rs_idx, 0]),
                                           "yaw": np.where(in_offb[rs_idx], 0.0, noise_sp[rs_idx, 1])})
    pitch_rate = 0.003 * rng.standard_normal(n)
    yaw_rate = 0.003 * rng.standard_normal(n)
    w.add_format("vehicle_angular_velocity", ["uint64_t timestamp", "uint64_t timestamp_sample", "float[3] xyz",
                                              "float[3] xyz_derivative"])
    xyz = np.stack([roll_rate, pitch_rate, yaw_rate], axis=1)
    w.add_topic("vehicle_angular_velocity", {"timestamp": us[i250] + 300, "timestamp_sample": us[i250],
                                             "xyz": xyz[i250], "xyz_derivative": np.zeros((len(i250), 3))})
    pitch = np.radians(0.3) + 0.0005 * rng.standard_normal(n)
    q = _euler_to_q(roll, pitch, np.full(n, 0.4))
    w.add_format("vehicle_attitude", ["uint64_t timestamp", "uint64_t timestamp_sample", "float[4] q"])
    w.add_topic("vehicle_attitude", {"timestamp": us[i250] + 250, "timestamp_sample": us[i250], "q": q[i250]})
    # setpoint d'assetto: non pubblicato in Offboard a velocità angolare; 45° per un ciclo al passaggio in Hold
    asp_idx = i125[~in_offb[i125]]
    roll_sp = roll_att_sp.copy()
    pitch_sp = np.full(n, np.radians(0.3))
    for st in steps:
        k = int(round((st["t_on"] + st["hold_after"]) * FS))
        roll_sp[k] = np.radians(45.0)
        asp_idx = np.union1d(asp_idx, [k])
    qd = _euler_to_q(roll_sp, pitch_sp, np.full(n, 0.4))
    w.add_format("vehicle_attitude_setpoint", ["uint64_t timestamp", "float[4] q_d", "float[3] thrust_body"])
    w.add_topic("vehicle_attitude_setpoint", {"timestamp": us[asp_idx] + 100, "q_d": qd[asp_idx]})

    # motori: miscelazione del comando di rollio, NaN oltre il quarto; tilt fermi a −1
    hover = 0.52
    mot = hover - 0.5 * (PY / np.abs(PY).max())[None, :] * u[:, None] + 0.003 * rng.standard_normal((n, 4))
    mot = np.clip(mot, 0.0, 1.0)
    mot[(t < 3.0) | (t > T - 3.0)] = 0.0
    m_rate = 10.0 if sdlog131 else 250.0
    mi = every(m_rate)
    for ts in truth_steps:
        if ts["sat"]:
            k0 = int(np.searchsorted(t[mi], ts["t_start"] + 0.1))
            mot[mi[k0:k0 + 3], 1] = 1.0
            ts["sat_samples"] = 3
    motors = np.full((n, 12), np.nan)
    motors[:, :4] = mot
    w.add_format("actuator_motors", ["uint64_t timestamp", "uint64_t timestamp_sample", "uint16_t reversible_flags",
                                     "float[12] control"])
    w.add_topic("actuator_motors", {"timestamp": us[mi], "timestamp_sample": us[mi], "control": motors[mi]})
    servos = np.zeros((n, 8))
    servos[:, 4:6] = -1.0
    servos[:, 6:] = np.nan
    w.add_format("actuator_servos", ["uint64_t timestamp", "uint64_t timestamp_sample", "float[8] control"])
    w.add_topic("actuator_servos", {"timestamp": us[mi], "timestamp_sample": us[mi], "control": servos[mi]})

    ca = every(5)
    achieved = np.ones(len(ca)) if alloc_fix else np.zeros(len(ca))
    w.add_format("control_allocator_status", ["uint64_t timestamp", "bool torque_setpoint_achieved",
                                              "float[3] unallocated_torque", "bool thrust_setpoint_achieved"])
    for inst in (0, 1):
        w.add_topic("control_allocator_status", {"timestamp": us[ca] + inst, "torque_setpoint_achieved": achieved if
                                                 inst == 0 else np.ones(len(ca)), "thrust_setpoint_achieved":
                                                 np.ones(len(ca))}, inst)
    ri = every(50)
    integ = o["integ"] if alloc_fix else np.zeros(n)
    w.add_format("rate_ctrl_status", ["uint64_t timestamp", "float rollspeed_integ", "float pitchspeed_integ",
                                      "float yawspeed_integ"])
    w.add_topic("rate_ctrl_status", {"timestamp": us[ri], "rollspeed_integ": integ[ri],
                                     "pitchspeed_integ": 0.01 * np.ones(len(ri)) if alloc_fix else np.zeros(len(ri)),
                                     "yawspeed_integ": np.zeros(len(ri))})
    z = np.where(t < 3.0, 0.0, -np.minimum((t - 3.0) * 4.0, 20.0))
    z = np.where(t > t_land, -np.maximum(20.0 - (t - t_land) * 4.0, 0.0), z)
    lp = i125
    vz = np.gradient(z, 1 / FS)
    w.add_format("vehicle_local_position", ["uint64_t timestamp", "uint64_t timestamp_sample", "float x", "float y",
                                            "float z", "float vx", "float vy", "float vz"])
    w.add_topic("vehicle_local_position", {"timestamp": us[lp], "timestamp_sample": us[lp], "x": np.zeros(len(lp)),
                                           "y": ys[lp], "z": z[lp], "vx": np.zeros(len(lp)), "vy": vys[lp],
                                           "vz": vz[lp]})
    tsi = every(5)
    vel_sp = np.zeros((n, 3))
    vel_sp[:, 1] = np.where(np.abs(vys) > 0.05, vys, 0.0)  # in Hold la traiettoria segue la frenata
    vel_sp[:, 2] = np.where((t > 3.0) & (t < 8.0), -4.0, 0.0)
    vel_sp[t >= t_land, 2] = 4.0
    vel_sp[in_offb] = np.nan
    w.add_format("trajectory_setpoint", ["uint64_t timestamp", "float[3] position", "float[3] velocity"])
    w.add_topic("trajectory_setpoint", {"timestamp": us[tsi], "position": np.stack([np.zeros(n), ys, z], 1)[tsi],
                                        "velocity": vel_sp[tsi]})
    hi = every(10)
    w.add_format("hover_thrust_estimate", ["uint64_t timestamp", "float hover_thrust", "float hover_thrust_var",
                                           "bool valid"])
    w.add_topic("hover_thrust_estimate", {"timestamp": us[hi], "hover_thrust": hover + 0.004 * rng.standard_normal(
        len(hi)), "valid": np.ones(len(hi))})

    floats = {
        "MC_ROLLRATE_P": gains_used["kp"], "MC_ROLLRATE_I": gains_used["ki"], "MC_ROLLRATE_D": gains_used["kd"],
        "MC_ROLLRATE_K": 1.0,
        "MC_ROLLRATE_FF": 0.0, "MC_PITCHRATE_P": 0.15, "MC_PITCHRATE_I": 0.2, "MC_PITCHRATE_D": 0.003,
        "MC_PITCHRATE_K": 1.0, "MC_PITCHRATE_FF": 0.0, "MC_YAWRATE_P": 0.2, "MC_YAWRATE_I": 0.1, "MC_YAWRATE_D": 0.0,
        "MC_YAWRATE_K": 1.0, "MC_YAWRATE_FF": 0.0, "MC_ROLL_P": ATT_P, "MC_PITCH_P": 4.0, "MC_YAW_P": 2.0,
        "MC_RR_INT_LIM": gains_used["int_lim"], "IMU_DGYRO_CUTOFF": 20.0, "IMU_GYRO_CUTOFF": 40.0, "MC_ACRO_R_MAX": 45.0,
    }
    w.params.update({k: float(v) for k, v in floats.items()})
    w.params.update({"SDLOG_PROFILE": 131 if sdlog131 else 17, "SYS_AUTOSTART": 22001, "CA_SV_CS_COUNT": 4,
                     "CA_SV_TL_COUNT": 2, "CA_SV_TL0_CT": 0, "CA_SV_TL1_CT": 0})
    w.add_info("sys_name", "PX4")
    w.add_info("ver_hw", "PX4_SITL")
    w.add_info("ver_sw_release", (1 << 24) | (17 << 16) | (0 << 8) | 255)
    w.write(path)
    meta = {"t50_vero": t50, "guadagni": gains_used, "gradini": truth_steps, "senza_correzione": not alloc_fix, "sdlog131": sdlog131,
            "cambi_di_modo": sorted(changes)}
    Path(str(path) + ".verita.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return meta


def _truth(t, y, t0, t1, sign):
    """Grandezze del gradino sul segnale della simulazione (500 Hz, senza rumore), calcolo diretto."""
    sel = (t >= t0) & (t < t1)
    ts, u = t[sel], sign * y[sel]
    k = int(np.flatnonzero(u >= 0.5 * A)[0]) if np.any(u >= 0.5 * A) else None
    delay = None
    if k is not None and k > 0:
        delay = float(ts[k - 1] + (0.5 * A - u[k - 1]) / (u[k] - u[k - 1]) * (ts[k] - ts[k - 1]) - t0)
    peak = float(u.max())
    out = np.abs(u - A) > 0.1 * A
    if out[-1]:
        settling = None
    else:
        j = int(np.flatnonzero(out)[-1])
        e0, e1 = abs(u[j] - A) - 0.1 * A, abs(u[j + 1] - A) - 0.1 * A
        settling = float(ts[j] + e0 / (e0 - e1) * (ts[j + 1] - ts[j]) - t0)
    w = (t >= t1 - 0.2) & (t < t1)
    err = float(np.mean(np.abs(A - sign * y[w])) / A * 100)
    kp = int(np.argmax(u))
    o = out[kp:]
    bounces = int(np.count_nonzero(o[1:] & ~o[:-1]))
    return {"delay": delay, "overshoot": (peak - A) / A * 100, "settling": settling, "end_error": err,
            "bounces": bounces}


def _euler_to_q(r, p, y):
    cr, sr = np.cos(r / 2), np.sin(r / 2)
    cp, sp = np.cos(p / 2), np.sin(p / 2)
    cy, sy = np.cos(y / 2), np.sin(y / 2)
    return np.stack([cr * cp * cy + sr * sp * sy, sr * cp * cy - cr * sp * sy, cr * sp * cy + sr * cp * sy,
                     cr * cp * sy - sr * sp * cy], axis=1)


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("output")
    ap.add_argument("--senza-gradini", action="store_true")
    ap.add_argument("--senza-correzione", action="store_true")
    ap.add_argument("--sdlog131", action="store_true")
    a = ap.parse_args()
    meta = build(a.output, not a.senza_gradini, not a.senza_correzione, a.sdlog131)
    print(f"scritto {a.output}: {len(meta['gradini'])} gradini, t50 vero {meta['t50_vero'] * 1000:.0f} ms")


if __name__ == "__main__":
    main()
