"""Genera un volo VTOL sintetico in formato ULog PX4 v1.17 con guadagni noti.

Uso: python tests/make_synthetic_log.py USCITA.ulg [--taratura A|B|C] [--default-rate]

Sequenza: a terra -> decollo -> multicottero (90 s) -> transizione -> ala fissa
(90 s) -> transizione inversa -> multicottero (40 s) -> atterraggio.
Accanto al log viene scritto USCITA.verita.json con le risposte vere.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from simulate import gust_disturbance, pilot_setpoint, simulate_axis, simulate_cascade  # noqa: E402
from ulog_writer import ULogWriter  # noqa: E402

from flight_analyzer import loopid  # noqa: E402

FS = 400.0
MC_PLANT = {
    "roll": {"b": 250.0, "tau_m": 0.035, "delay": 1},
    "pitch": {"b": 200.0, "tau_m": 0.035, "delay": 1},
    "yaw": {"b": 40.0, "tau_m": 0.05, "delay": 1, "damping": 0.5},
}
FW_PLANT = {
    "roll": {"b": 45.0, "tau_m": 0.05, "delay": 1, "damping": 9.0},
    "pitch": {"b": 30.0, "tau_m": 0.05, "delay": 1, "damping": 6.0},
    "yaw": {"b": 12.0, "tau_m": 0.05, "delay": 1, "damping": 3.0},
}
TUNINGS = {
    "A": {"roll": (0.10, 0.15, 0.0035), "pitch": (0.12, 0.15, 0.004), "yaw": (0.20, 0.10, 0.0)},
    "B": {"roll": (0.15, 0.20, 0.003), "pitch": (0.15, 0.20, 0.003), "yaw": (0.20, 0.10, 0.0)},
    "C": {"roll": (0.25, 0.30, 0.0012), "pitch": (0.24, 0.30, 0.0012), "yaw": (0.45, 0.25, 0.0)},
}
MC_ATT_P = {"roll": 6.5, "pitch": 6.5, "yaw": 2.8}
FW_RATE = {"roll": (0.05, 0.10, 0.20), "pitch": (0.08, 0.10, 0.20), "yaw": (0.05, 0.05, 0.25)}  # P, I, FF
FW_TC = {"roll": 0.4, "pitch": 0.4}


def euler_to_q(r, p, y):
    cr, sr = np.cos(r / 2), np.sin(r / 2)
    cp, sp = np.cos(p / 2), np.sin(p / 2)
    cy, sy = np.cos(y / 2), np.sin(y / 2)
    return np.stack([
        cr * cp * cy + sr * sp * sy,
        sr * cp * cy - cr * sp * sy,
        cr * sp * cy + sr * cp * sy,
        cr * cp * sy - sr * sp * cy,
    ], axis=1)


def mc_gains(tune, axis):
    p, i, d = TUNINGS[tune][axis]
    return dict(kp=p, ki=i, kd=d, kff=0.0, k=1.0, int_lim=0.3, gyro_cut=40, dgyro_cut=20)


def fw_gains(axis):
    p, i, ff = FW_RATE[axis]
    return dict(kp=p, ki=i, kd=0.0, kff=ff, k=1.0, int_lim=0.4, gyro_cut=40, dgyro_cut=20)


def truth(tune, amp=0.1):
    """Risposte al gradino vere (gradino piccolo per restare nel campo lineare)."""
    out = {}

    def met(y, dur):
        k = int(dur * FS)
        return loopid.step_metrics(np.arange(k) / FS, y[:k] / amp).__dict__

    for axis in ("roll", "pitch", "yaw"):
        g = mc_gains(tune, axis)
        out[f"mc_rate.{axis}"] = met(simulate_axis(np.full(int(FS), amp), FS, g, MC_PLANT[axis])["y"], 0.7 if axis != "yaw" else 1.4)
        att = simulate_cascade(np.full(int(4 * FS), amp), FS, MC_ATT_P[axis], g, MC_PLANT[axis])["att"]
        out[f"mc_att.{axis}"] = met(att, {"roll": 1.7, "pitch": 1.7, "yaw": 3.0}[axis])
        g = fw_gains(axis)
        out[f"fw_rate.{axis}"] = met(simulate_axis(np.full(int(2 * FS), amp), FS, g, FW_PLANT[axis])["y"], 1.1)
        if axis in FW_TC:
            att = simulate_cascade(np.full(int(5 * FS), amp), FS, 1 / FW_TC[axis], g, FW_PLANT[axis], rate_max=1.5)["att"]
            out[f"fw_att.{axis}"] = met(att, 3.0)
    return out


def build(path, tune="B", default_rate=False, seed=5):
    rng = np.random.default_rng(seed)
    # tempi delle fasi [s]
    T_END = 252.0
    t = np.arange(0, T_END, 1 / FS)
    n = len(t)
    phase = np.full(n, "GROUND", dtype=object)
    segs = [("GROUND", 0, 7), ("MC", 7, 98), ("TRANS_FW", 98, 106), ("FW", 106, 196),
            ("TRANS_MC", 196, 204), ("MC", 204, 247), ("GROUND", 247, T_END)]
    for name, a, b in segs:
        phase[(t >= a) & (t < b)] = name

    rates = {a: np.zeros(n) for a in ("roll", "pitch", "yaw")}
    rate_sp = {a: np.zeros(n) for a in rates}
    att = {a: np.zeros(n) for a in rates}
    att_sp = {a: np.zeros(n) for a in rates}
    torque0 = {a: np.zeros(n) for a in rates}
    torque1 = {a: np.zeros(n) for a in rates}
    integ0 = {a: np.zeros(n) for a in rates}
    integ1 = {a: np.zeros(n) for a in rates}
    accel = {a: np.zeros(n) for a in rates}
    yaw_offset = 0.3
    for k_seg, (name, a, b) in enumerate(segs):
        if name == "GROUND":
            continue
        sel = (t >= a) & (t < b)
        m = int(np.count_nonzero(sel))
        dur = m / FS
        for j, axis in enumerate(("roll", "pitch", "yaw")):
            s = seed * 100 + k_seg * 10 + j
            if name == "MC" or name.startswith("TRANS"):
                g = mc_gains(tune, axis)
                amp = {"roll": 0.35, "pitch": 0.3, "yaw": 1.2}[axis] * (0.3 if name.startswith("TRANS") else 1.0)
                if axis == "yaw":
                    yaw_rate_cmd = pilot_setpoint(dur, FS, amp, seed=s, hold=(0.4, 2.0))
                    sp_att = np.cumsum(yaw_rate_cmd) / FS
                else:
                    sp_att = pilot_setpoint(dur, FS, amp, seed=s)
                d = gust_disturbance(dur, FS, level=8.0 if axis != "yaw" else 2.0, seed=s + 7)
                o = simulate_cascade(sp_att, FS, MC_ATT_P[axis], g, dict(MC_PLANT[axis], seed=s), noise=0.02, dist=d)
                torque0[axis][sel] = o["u"]
                integ0[axis][sel] = o["integ"]
            else:
                g = fw_gains(axis)
                d = gust_disturbance(dur, FS, level=3.0, seed=s + 7)
                if axis == "yaw":
                    r = pilot_setpoint(dur, FS, 0.15, seed=s)
                    o = simulate_axis(r, FS, g, dict(FW_PLANT[axis], seed=s), noise=0.02, dist=d)
                    sp_att = None
                else:
                    amp = {"roll": 0.5, "pitch": 0.15}[axis]
                    sp_att = pilot_setpoint(dur, FS, amp, seed=s, hold=(0.8, 3.0))
                    o = simulate_cascade(sp_att, FS, 1 / FW_TC[axis], g, dict(FW_PLANT[axis], seed=s), noise=0.02, dist=d,
                                         rate_max=1.5)
                torque1[axis][sel] = o["u"]
                integ1[axis][sel] = o["integ"]
            rates[axis][sel] = o["y"]
            accel[axis][sel] = o["a"]
            rate_sp[axis][sel] = o["r"]
            base = yaw_offset if axis == "yaw" else 0.0
            att[axis][sel] = o["att"] + base
            if sp_att is not None:
                att_sp[axis][sel] = sp_att + base
            else:
                att_sp[axis][sel] = att[axis][sel]
            if axis == "yaw":
                yaw_offset = att[axis][sel][-1]

    # ------------------------------------------------------------- scrittura log
    w = ULogWriter(start_timestamp=0)
    us = (t * 1e6).astype(np.int64) + 1_000_000  # il log parte a 1 s dal boot

    def every(rate_hz):
        step = max(1, int(round(FS / rate_hz)))
        return np.arange(0, n, step)

    hi = not default_rate
    r_av = every(400 if hi else 100)  # in SITL vehicle_angular_velocity è a 100 Hz di default
    r_sp = every(400 if hi else 50)
    r_att = every(200 if hi else 20)
    r_tq = every(400 if hi else 50)
    r_slow = every(10)
    r_mid = every(50)

    w.add_format("vehicle_status", ["uint64_t timestamp", "uint64_t armed_time", "uint64_t takeoff_time",
                                    "uint8_t arming_state", "uint8_t nav_state", "uint8_t vehicle_type", "bool is_vtol",
                                    "bool in_transition_mode", "bool in_transition_to_fw", "uint8_t[2] _padding0"])
    idx = every(5)
    ph = phase[idx]
    armed = np.where((t[idx] >= 5) & (t[idx] < 249), 2, 1)
    nav = np.where(ph == "FW", 3, np.where(np.isin(ph, ["TRANS_FW", "TRANS_MC"]), 3, 15))
    nav = np.where((t[idx] > 204) & (ph == "MC"), 2, nav)
    vtype = np.where(np.isin(ph, ["FW", "TRANS_MC"]), 2, 1)
    trans = np.isin(ph, ["TRANS_FW", "TRANS_MC"]).astype(int)
    w.add_topic("vehicle_status", {"timestamp": us[idx], "armed_time": np.full(len(idx), 6_000_000),
                                   "takeoff_time": np.full(len(idx), 8_000_000), "arming_state": armed, "nav_state": nav,
                                   "vehicle_type": vtype, "is_vtol": np.ones(len(idx)), "in_transition_mode": trans,
                                   "in_transition_to_fw": (ph == "TRANS_FW").astype(int)})
    w.add_format("vtol_vehicle_status", ["uint64_t timestamp", "uint8_t vehicle_vtol_state", "bool fixed_wing_system_failure"])
    vstate = np.select([ph == "TRANS_FW", ph == "TRANS_MC", ph == "FW"], [1, 2, 4], 3)
    w.add_topic("vtol_vehicle_status", {"timestamp": us[idx], "vehicle_vtol_state": vstate})
    w.add_format("vehicle_land_detected", ["uint64_t timestamp", "bool freefall", "bool ground_contact", "bool maybe_landed", "bool landed"])
    w.add_topic("vehicle_land_detected", {"timestamp": us[idx], "landed": (ph == "GROUND").astype(int),
                                          "maybe_landed": (ph == "GROUND").astype(int)})

    w.add_format("vehicle_rates_setpoint", ["uint64_t timestamp", "float roll", "float pitch", "float yaw",
                                            "float[3] thrust_body", "bool reset_integral", "uint8_t[7] _padding0"])
    thr = np.zeros((n, 3))
    thr[:, 2] = np.where(np.isin(phase, ["MC", "TRANS_FW", "TRANS_MC"]), -0.55, 0.0)
    w.add_topic("vehicle_rates_setpoint", {"timestamp": us[r_sp] + 500, "roll": rate_sp["roll"][r_sp],
                                           "pitch": rate_sp["pitch"][r_sp], "yaw": rate_sp["yaw"][r_sp],
                                           "thrust_body": thr[r_sp]})
    w.add_format("vehicle_angular_velocity", ["uint64_t timestamp", "uint64_t timestamp_sample", "float[3] xyz",
                                              "float[3] xyz_derivative"])
    xyz = np.stack([rates["roll"], rates["pitch"], rates["yaw"]], axis=1)
    dxyz = np.stack([accel["roll"], accel["pitch"], accel["yaw"]], axis=1)
    w.add_topic("vehicle_angular_velocity", {"timestamp": us[r_av] + 300, "timestamp_sample": us[r_av],
                                             "xyz": xyz[r_av], "xyz_derivative": dxyz[r_av]})
    q = euler_to_q(att["roll"], att["pitch"], att["yaw"])
    qd = euler_to_q(att_sp["roll"], att_sp["pitch"], att_sp["yaw"])
    w.add_format("vehicle_attitude", ["uint64_t timestamp", "uint64_t timestamp_sample", "float[4] q",
                                      "float[4] delta_q_reset", "uint8_t quat_reset_counter", "uint8_t[7] _padding0"])
    w.add_topic("vehicle_attitude", {"timestamp": us[r_att] + 200, "timestamp_sample": us[r_att], "q": q[r_att]})
    w.add_format("vehicle_attitude_setpoint", ["uint64_t timestamp", "float yaw_sp_move_rate", "float[4] q_d",
                                               "float[3] thrust_body"])
    w.add_topic("vehicle_attitude_setpoint", {"timestamp": us[r_att] + 100, "q_d": qd[r_att], "thrust_body": thr[r_att]})
    w.add_format("vehicle_torque_setpoint", ["uint64_t timestamp", "uint64_t timestamp_sample", "float[3] xyz"])
    t0 = np.stack([torque0[a] for a in ("roll", "pitch", "yaw")], axis=1)
    t1 = np.stack([torque1[a] for a in ("roll", "pitch", "yaw")], axis=1)
    w.add_topic("vehicle_torque_setpoint", {"timestamp": us[r_tq] + 400, "timestamp_sample": us[r_tq], "xyz": t0[r_tq]}, 0)
    w.add_topic("vehicle_torque_setpoint", {"timestamp": us[r_tq] + 400, "timestamp_sample": us[r_tq], "xyz": t1[r_tq]}, 1)
    w.add_format("vehicle_thrust_setpoint", ["uint64_t timestamp", "uint64_t timestamp_sample", "float[3] xyz"])
    w.add_topic("vehicle_thrust_setpoint", {"timestamp": us[r_tq] + 400, "timestamp_sample": us[r_tq], "xyz": thr[r_tq]}, 0)
    w.add_format("rate_ctrl_status", ["uint64_t timestamp", "float rollspeed_integ", "float pitchspeed_integ", "float yawspeed_integ"])
    ri = every(50)
    w.add_topic("rate_ctrl_status", {"timestamp": us[ri], "rollspeed_integ": integ0["roll"][ri],
                                     "pitchspeed_integ": integ0["pitch"][ri], "yawspeed_integ": integ0["yaw"][ri]}, 0)
    w.add_topic("rate_ctrl_status", {"timestamp": us[ri], "rollspeed_integ": integ1["roll"][ri],
                                     "pitchspeed_integ": integ1["pitch"][ri], "yawspeed_integ": integ1["yaw"][ri]}, 1)
    # motori (quad + tilt) e servi
    hover = 0.55
    mot = np.full((n, 12), np.nan)
    mc_on = np.isin(phase, ["MC", "TRANS_FW", "TRANS_MC"])
    mix = np.array([[-1, 1, 1], [1, -1, 1], [1, 1, -1], [-1, -1, -1]], float) * 0.5
    for k in range(4):
        mot[:, k] = np.where(mc_on, hover + t0 @ mix[k], np.where(phase == "FW", 0.6 if k < 2 else 0.0, 0.0))
    mot[:, :4] = np.clip(mot[:, :4], 0, 1)
    w.add_format("actuator_motors", ["uint64_t timestamp", "uint64_t timestamp_sample", "uint16_t reversible_flags",
                                     "float[12] control", "uint8_t[6] _padding0"])
    am = every(100 if hi else 10)
    w.add_topic("actuator_motors", {"timestamp": us[am], "timestamp_sample": us[am], "control": mot[am]})
    serv = np.full((n, 8), np.nan)
    serv[:, 0] = np.clip(t1[:, 0], -1, 1)
    serv[:, 1] = np.clip(-t1[:, 0], -1, 1)
    serv[:, 2] = np.clip(t1[:, 1] + t1[:, 2], -1, 1)
    serv[:, 3] = np.clip(t1[:, 1] - t1[:, 2], -1, 1)
    serv[:, 4] = np.where(phase == "FW", 1.0, np.where(np.isin(phase, ["TRANS_FW", "TRANS_MC"]), 0.0, -1.0))
    w.add_format("actuator_servos", ["uint64_t timestamp", "uint64_t timestamp_sample", "float[8] control"])
    w.add_topic("actuator_servos", {"timestamp": us[am], "timestamp_sample": us[am], "control": serv[am]})
    w.add_format("control_allocator_status", ["uint64_t timestamp", "bool torque_setpoint_achieved",
                                              "float[3] unallocated_torque", "bool thrust_setpoint_achieved",
                                              "float[3] unallocated_thrust", "int8_t[16] actuator_saturation",
                                              "uint16_t handled_motor_failure_mask", "uint16_t motor_stop_mask"])
    ca = every(50)
    unalloc = np.clip(np.abs(t0) - 0.5, 0, None) * np.sign(t0)
    w.add_topic("control_allocator_status", {"timestamp": us[ca], "torque_setpoint_achieved": (np.abs(unalloc[ca]).max(axis=1) < 1e-3).astype(int),
                                             "unallocated_torque": unalloc[ca]})

    # posizione: integrazione di un profilo di velocità (continua)
    tt = t
    alt = np.interp(tt, [0, 7, 15, 98, 106, 196, 204, 240, 247, T_END], [0, 0, 15, 15, 30, 40, 30, 15, 0, 0])
    z = -alt
    speed = np.interp(tt, [0, 98, 106, 196, 204, 210, T_END], [0, 0, 18, 18, 3, 1.5, 0])
    heading = np.where(tt > 106, (tt - 106) * 18.0 / 150.0, 0.0)
    heading = np.where(tt > 196, heading[np.searchsorted(tt, 196)] + 0 * tt, heading)
    vn = speed * np.cos(heading) + 0.3 * rng.standard_normal(n) * (phase == "MC")
    ve = speed * np.sin(heading)
    x = np.cumsum(vn) / FS
    y = np.cumsum(ve) / FS
    vx, vy, vz = np.gradient(x, 1 / FS), np.gradient(y, 1 / FS), np.gradient(z, 1 / FS)
    lp = every(50)
    lat0, lon0, alt0 = 45.0703, 7.6869, 240.0
    w.add_format("vehicle_local_position", ["uint64_t timestamp", "uint64_t timestamp_sample", "float x", "float y",
                                            "float z", "float vx", "float vy", "float vz", "double ref_lat",
                                            "double ref_lon", "float ref_alt", "bool xy_valid", "bool z_valid",
                                            "bool xy_global", "uint8_t[1] _padding0"])
    w.add_topic("vehicle_local_position", {"timestamp": us[lp], "timestamp_sample": us[lp], "x": x[lp], "y": y[lp],
                                           "z": z[lp], "vx": vx[lp], "vy": vy[lp], "vz": vz[lp],
                                           "ref_lat": np.full(len(lp), lat0), "ref_lon": np.full(len(lp), lon0),
                                           "ref_alt": np.full(len(lp), alt0), "xy_valid": np.ones(len(lp)),
                                           "z_valid": np.ones(len(lp)), "xy_global": np.ones(len(lp))})

    def to_ll(n_, e_):
        return lat0 + np.degrees(n_ / 6371000.0), lon0 + np.degrees(e_ / (6371000.0 * np.cos(np.radians(lat0))))

    # missione: decollo VTOL, transizione, 6 waypoint sul cerchio, atterraggio VTOL
    t_circle = 2 * np.pi * 150.0 / 18.0
    wp_t = [7.0, 98.0] + [106.0 + k * t_circle / 6 for k in range(6)] + [204.0]
    wp_cmd = [84, 3000] + [16] * 5 + [17] + [85]
    items = []
    for seq, (tw, cmd) in enumerate(zip(wp_t, wp_cmd)):
        kk = min(n - 1, int(tw * FS))
        if cmd == 3000:
            la, lo = float("nan"), float("nan")
        elif cmd == 85:
            la, lo = to_ll(x[-1], y[-1])
        else:
            la, lo = to_ll(x[kk + int(2 * FS) if cmd == 84 else kk], y[kk + int(2 * FS) if cmd == 84 else kk])
        items.append((tw, seq, cmd, la, lo, alt0 + float(alt[min(n - 1, kk + int(8 * FS))])))
    w.add_format("navigator_mission_item", ["uint64_t timestamp", "uint16_t sequence_current", "uint16_t nav_cmd",
                                            "float latitude", "float longitude", "float time_inside",
                                            "float acceptance_radius", "float loiter_radius", "float yaw",
                                            "float altitude", "uint8_t frame", "uint8_t origin",
                                            "bool loiter_exit_xtrack", "bool force_heading", "bool altitude_is_relative",
                                            "bool autocontinue", "bool vtol_back_transition", "uint8_t[1] _padding0"])
    w.add_topic("navigator_mission_item", {
        "timestamp": np.array([1_000_000 + int(it[0] * 1e6) for it in items]),
        "sequence_current": np.array([it[1] for it in items]), "nav_cmd": np.array([it[2] for it in items]),
        "latitude": np.array([it[3] for it in items]), "longitude": np.array([it[4] for it in items]),
        "altitude": np.array([it[5] for it in items]),
        "loiter_radius": np.array([80.0 if it[2] == 17 else 0.0 for it in items]),
        "acceptance_radius": np.full(len(items), 10.0), "autocontinue": np.ones(len(items))})
    w.add_format("position_setpoint", ["uint64_t timestamp", "bool valid", "uint8_t type", "float vx", "float vy",
                                       "float vz", "double lat", "double lon", "float alt", "float yaw",
                                       "float loiter_radius", "float acceptance_radius", "uint8_t[2] _padding0"])
    w.add_format("position_setpoint_triplet", ["uint64_t timestamp", "position_setpoint previous",
                                               "position_setpoint current", "position_setpoint next"])
    pst = every(5)
    act = np.searchsorted(np.array(wp_t), t[pst], side="right") - 1
    cur_lat = np.array([items[max(a_, 0)][3] for a_ in act])
    cur_lon = np.array([items[max(a_, 0)][4] for a_ in act])
    cur_alt = np.array([items[max(a_, 0)][5] for a_ in act])
    valid = (t[pst] > 7) & (t[pst] < 247) & np.isfinite(cur_lat)
    w.add_topic("position_setpoint_triplet", {"timestamp": us[pst], "current.timestamp": us[pst],
                                              "current.valid": valid.astype(int), "current.type": np.zeros(len(pst)),
                                              "current.lat": np.nan_to_num(cur_lat), "current.lon": np.nan_to_num(cur_lon),
                                              "current.alt": cur_alt, "current.loiter_radius": np.full(len(pst), 80.0)})
    w.add_format("trajectory_setpoint", ["uint64_t timestamp", "float[3] position", "float[3] velocity",
                                         "float[3] acceleration", "float[3] jerk", "float yaw", "float yawspeed"])
    pos_sp = np.stack([x + 0.4 * np.sin(tt), y, z], axis=1)
    w.add_topic("trajectory_setpoint", {"timestamp": us[lp], "position": pos_sp[lp],
                                        "velocity": np.stack([vx, vy, vz], axis=1)[lp]})
    w.add_format("vehicle_global_position", ["uint64_t timestamp", "uint64_t timestamp_sample", "double lat", "double lon",
                                             "float alt", "float alt_ellipsoid"])
    gp = every(10)
    w.add_topic("vehicle_global_position", {"timestamp": us[gp], "timestamp_sample": us[gp],
                                            "lat": lat0 + x[gp] / 111_111.0,
                                            "lon": lon0 + y[gp] / (111_111.0 * np.cos(np.radians(lat0))),
                                            "alt": 240 + alt[gp]})
    w.add_format("airspeed_validated", ["uint64_t timestamp", "float indicated_airspeed_m_s", "float calibrated_airspeed_m_s",
                                        "float true_airspeed_m_s"])
    ias = np.interp(tt, [0, 98, 106, 196, 204, 210, T_END], [0, 1, 18, 18, 5, 1, 0]) + 0.3 * np.sin(0.7 * tt)
    w.add_topic("airspeed_validated", {"timestamp": us[lp], "indicated_airspeed_m_s": ias[lp],
                                       "calibrated_airspeed_m_s": ias[lp], "true_airspeed_m_s": ias[lp] * 1.02})
    # sensori
    w.add_format("sensor_combined", ["uint64_t timestamp", "float[3] gyro_rad", "uint32_t gyro_integral_dt",
                                     "int32_t accelerometer_timestamp_relative", "float[3] accelerometer_m_s2",
                                     "uint32_t accelerometer_integral_dt", "uint8_t accelerometer_clipping",
                                     "uint8_t gyro_clipping", "uint8_t accel_calibration_count",
                                     "uint8_t gyro_calibration_count"])
    sc = every(400 if hi else 100)
    vib = 0.6 * np.sin(2 * np.pi * 87.0 * tt)[:, None] * mc_on[:, None]
    acc = np.stack([0.2 * rng.standard_normal(n), 0.2 * rng.standard_normal(n), -9.81 + 0.3 * rng.standard_normal(n)], axis=1) + vib
    w.add_topic("sensor_combined", {"timestamp": us[sc], "gyro_rad": xyz[sc] + 0.01 * rng.standard_normal((len(sc), 3)),
                                    "gyro_integral_dt": np.full(len(sc), 2500), "accelerometer_m_s2": acc[sc],
                                    "accelerometer_integral_dt": np.full(len(sc), 2500)})
    w.add_format("vehicle_imu_status", ["uint64_t timestamp", "uint32_t accel_device_id", "uint32_t gyro_device_id",
                                        "float accel_vibration_metric", "float gyro_vibration_metric",
                                        "float delta_angle_coning_metric"])
    vi = every(2)
    w.add_topic("vehicle_imu_status", {"timestamp": us[vi], "accel_vibration_metric": 1.5 + 2.0 * mc_on[vi] + 0.2 * rng.random(len(vi)),
                                       "gyro_vibration_metric": 0.02 + 0.03 * mc_on[vi]})
    w.add_format("battery_status", ["uint64_t timestamp", "bool connected", "float voltage_v", "float current_a",
                                    "float current_average_a", "float discharged_mah", "float remaining"])
    bi = every(5)
    current = np.where(mc_on[bi], 42.0, np.where(phase[bi] == "FW", 14.0, 0.8))
    mah = np.cumsum(current) / 5 / 3.6
    volt = 25.2 - 0.004 * mah - 0.012 * current
    w.add_topic("battery_status", {"timestamp": us[bi], "connected": np.ones(len(bi)), "voltage_v": volt, "current_a": current,
                                   "current_average_a": current, "discharged_mah": mah, "remaining": 1 - mah / 10000})
    # ESC con telemetria (struttura annidata come in PX4: esc_status.esc[i].*)
    w.add_format("esc_report", ["uint64_t timestamp", "int32_t esc_rpm", "float esc_voltage", "float esc_current",
                                "float esc_temperature", "uint8_t esc_power"])
    w.add_format("esc_status", ["uint64_t timestamp", "uint8_t esc_count", "uint8_t esc_online_flags",
                                "esc_report[8] esc"])
    ei = every(20)
    esc = {"timestamp": us[ei], "esc_count": np.full(len(ei), 4), "esc_online_flags": np.full(len(ei), 15)}
    m4 = np.nan_to_num(mot[ei, :4])
    for k in range(8):
        on = k < 4
        u = m4[:, k] if on else np.zeros(len(ei))
        esc[f"esc[{k}].timestamp"] = us[ei]
        esc[f"esc[{k}].esc_rpm"] = (u * 7800 + 40 * rng.standard_normal(len(ei))).clip(0) * on
        esc[f"esc[{k}].esc_voltage"] = np.interp(us[ei], us[bi], volt) * on
        esc[f"esc[{k}].esc_current"] = (u ** 1.5 * 22.0) * on
        esc[f"esc[{k}].esc_temperature"] = (30 + 0.08 * np.cumsum(u) / 20) * on
        esc[f"esc[{k}].esc_power"] = np.round(u * 100) * on
    w.add_topic("esc_status", esc)
    w.add_format("system_power", ["uint64_t timestamp", "float voltage5v_v", "float[4] sensors3v3"])
    sp_i = every(2)
    w.add_topic("system_power", {"timestamp": us[sp_i], "voltage5v_v": 5.08 + 0.02 * rng.standard_normal(len(sp_i))})
    # flag: avviso batteria verso la fine, una breve perdita del collegamento GCS, missione assente per tutto il log
    w.add_format("failsafe_flags", ["uint64_t timestamp", "uint8_t battery_warning", "bool gcs_connection_lost",
                                    "bool auto_mission_missing", "bool wind_limit_exceeded", "bool fd_critical_failure"])
    fi = every(5)
    w.add_topic("failsafe_flags", {"timestamp": us[fi], "battery_warning": (t[fi] > 230).astype(int),
                                   "gcs_connection_lost": ((t[fi] > 150) & (t[fi] < 152.5)).astype(int),
                                   "auto_mission_missing": np.ones(len(fi)),
                                   "wind_limit_exceeded": ((t[fi] > 120.5) & (t[fi] < 126)).astype(int),
                                   "fd_critical_failure": np.zeros(len(fi))})
    w.add_format("estimator_status_flags", ["uint64_t timestamp", "bool cs_gnd_effect", "bool reject_hor_vel",
                                            "bool cs_mag_field_disturbed"])
    w.add_topic("estimator_status_flags", {"timestamp": us[fi], "cs_gnd_effect": ((t[fi] > 6) & (t[fi] < 10)).astype(int),
                                           "reject_hor_vel": ((t[fi] > 60) & (t[fi] < 60.6)).astype(int),
                                           "cs_mag_field_disturbed": np.zeros(len(fi))})
    w.add_format("cpuload", ["uint64_t timestamp", "float load", "float ram_usage"])
    w.add_topic("cpuload", {"timestamp": us[every(2)], "load": 0.45 + 0.05 * rng.random(len(every(2))),
                            "ram_usage": np.full(len(every(2)), 0.6)})
    w.add_format("manual_control_setpoint", ["uint64_t timestamp", "uint64_t timestamp_sample", "bool valid",
                                             "uint8_t data_source", "float roll", "float pitch", "float yaw", "float throttle"])
    w.add_topic("manual_control_setpoint", {"timestamp": us[r_mid], "timestamp_sample": us[r_mid], "valid": np.ones(len(r_mid)),
                                            "data_source": np.ones(len(r_mid)),
                                            "roll": np.clip(att_sp["roll"][r_mid] / 0.6, -1, 1),
                                            "pitch": np.clip(att_sp["pitch"][r_mid] / 0.6, -1, 1),
                                            "yaw": np.clip(rate_sp["yaw"][r_mid] / 2.0, -1, 1),
                                            "throttle": np.where(mc_on[r_mid], 0.1, 0.0)})

    # parametri e info
    p = {}
    for axis, pref in (("roll", "MC_ROLLRATE"), ("pitch", "MC_PITCHRATE"), ("yaw", "MC_YAWRATE")):
        kp, ki, kd = TUNINGS[tune][axis]
        p.update({f"{pref}_P": kp, f"{pref}_I": ki, f"{pref}_D": kd, f"{pref}_FF": 0.0, f"{pref}_K": 1.0,
                  f"{pref}_MAX": 220.0})
    p.update({"MC_ROLL_P": 6.5, "MC_PITCH_P": 6.5, "MC_YAW_P": 2.8, "MC_RR_INT_LIM": 0.3, "MC_PR_INT_LIM": 0.3,
              "MC_YR_INT_LIM": 0.3, "IMU_GYRO_CUTOFF": 40.0, "IMU_DGYRO_CUTOFF": 20.0, "MC_AT_RISE_TIME": 0.14,
              "IMU_GYRO_RATEMAX": 400, "SDLOG_PROFILE": 17 if hi else 1, "SYS_AUTOSTART": 13030, "SYS_HITL": 0,
              "FW_R_TC": 0.4, "FW_P_TC": 0.4, "FW_RR_IMAX": 0.4, "FW_PR_IMAX": 0.4, "FW_YR_IMAX": 0.4,
              "FW_AIRSPD_TRIM": 18.0, "VT_TYPE": 1, "CA_AIRFRAME": 3,
              "CA_SV_CS_COUNT": 4, "CA_SV_CS0_TYPE": 1, "CA_SV_CS1_TYPE": 2, "CA_SV_CS2_TYPE": 7, "CA_SV_CS3_TYPE": 8,
              "CA_SV_TL_COUNT": 1, "CA_SV_TL0_MINA": 0.0, "CA_SV_TL0_MAXA": 90.0})
    for axis, pref in (("roll", "FW_RR"), ("pitch", "FW_PR"), ("yaw", "FW_YR")):
        kp, ki, ff = FW_RATE[axis]
        p.update({f"{pref}_P": kp, f"{pref}_I": ki, f"{pref}_D": 0.0, f"{pref}_FF": ff})
    w.params = p
    w.defaults = {"MC_ROLLRATE_P": 0.15, "MC_PITCHRATE_P": 0.15, "MC_ROLLRATE_D": 0.003, "SDLOG_PROFILE": 1}
    w.add_info("sys_name", "PX4")
    w.add_info("ver_hw", "CUBEPILOT_CUBEORANGE")
    w.add_info("ver_sw", "a5eb12d2ab591251faa009f76b2685b8cc64405d")
    w.add_info("ver_sw_release", (1 << 24) | (17 << 16) | (0 << 8) | 255)
    w.add_info("sys_uuid", "000600000000363232335118003a0043")
    w.add_message(1_100_000, 6, "[logger] Start file log (type: full)")
    w.add_message(6_000_000, 6, "[commander] Armed by RC")
    w.add_message(8_000_000, 6, "[commander] Takeoff detected")
    w.add_message(98_000_000, 6, "[vtol_att_control] Transition to fixed-wing")
    w.add_message(120_500_000, 4, "[commander] Wind speed is above limit (9.1 m/s)")
    w.add_message(196_000_000, 6, "[vtol_att_control] Transition to multicopter")
    w.add_message(247_500_000, 6, "[commander] Landing detected")
    w.add_message(250_000_000, 6, "[commander] Disarmed by landing")
    w.write(path)
    tr = truth(tune)
    Path(str(path) + ".verita.json").write_text(json.dumps(tr, indent=1))
    return tr


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("uscita")
    ap.add_argument("--taratura", default="B", choices=list(TUNINGS))
    ap.add_argument("--default-rate", action="store_true")
    ap.add_argument("--seed", type=int, default=5)
    a = ap.parse_args()
    build(a.uscita, a.taratura, a.default_rate, a.seed)
    print("scritto", a.uscita)
