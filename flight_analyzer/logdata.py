"""Accesso di alto livello a un log PX4: serie temporali, modi, fasi VTOL, metadati."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np

from . import config, dsp
from .i18n import N_, _
from .ulog import ULog

NAV_STATES = {
    0: "Manual",
    1: "Altitude",
    2: "Position",
    3: "Mission",
    4: "Hold",
    5: "Return",
    6: "Position slow",
    8: "Altitude cruise",
    10: "Acro",
    12: "Descend",
    13: "Termination",
    14: "Offboard",
    15: "Stabilized",
    17: "Takeoff",
    18: "Land",
    19: "Follow me",
    20: "Precision land",
    21: "Orbit",
    22: "VTOL takeoff",
}
for _i in range(23, 31):
    NAV_STATES[_i] = f"External {_i - 22}"

PHASE_LABELS = {"MC": N_("Multicottero"), "FW": N_("Ala fissa"), "TRANS": N_("Transizione"), "ALTRO": N_("Altro")}

# MAV_CMD dei punti di missione più comuni
NAV_CMDS = {16: N_("waypoint"), 17: N_("loiter"), 18: N_("loiter a giri"), 19: N_("loiter a tempo"),
            20: N_("ritorno"), 21: N_("atterraggio"), 22: N_("decollo"), 31: N_("loiter a quota"),
            84: N_("decollo VTOL"), 85: N_("atterraggio VTOL"), 93: N_("attesa"), 178: N_("cambio velocità"),
            3000: N_("transizione VTOL")}
EARTH_R = 6371000.0


@dataclass
class Series:
    t: np.ndarray  # secondi dall'inizio del log
    y: np.ndarray

    def __len__(self):
        return len(self.t)

    def slice(self, t0, t1):
        sel = (self.t >= t0) & (self.t <= t1)
        return Series(self.t[sel], self.y[sel])


def quat_to_euler(q0, q1, q2, q3):
    """Quaternione (w, x, y, z) PX4 -> roll, pitch, yaw [rad] (convenzione ZYX)."""
    roll = np.arctan2(2 * (q0 * q1 + q2 * q3), 1 - 2 * (q1 * q1 + q2 * q2))
    pitch = np.arcsin(np.clip(2 * (q0 * q2 - q3 * q1), -1.0, 1.0))
    yaw = np.arctan2(2 * (q0 * q3 + q1 * q2), 1 - 2 * (q2 * q2 + q3 * q3))
    return roll, pitch, yaw


class LogData:
    """Log caricato con indici e grandezze derivate pronte per GUI e analisi."""

    def __init__(self, path):
        self.path = Path(path)
        self.ulog = ULog(self.path)
        self.t0_us = self.ulog.start_timestamp
        self._topics: dict = {}
        for d in self.ulog.datasets:
            self._topics.setdefault(d.name, {})[d.multi_id] = d
        self.duration = max(0.0, (self.ulog.last_timestamp - self.t0_us) / 1e6)
        self.params = dict(self.ulog.initial_parameters)
        self.param_changes = [((ts - self.t0_us) / 1e6, k, v) for ts, k, v in self.ulog.changed_parameters]
        self.defaults = {}
        for bit in sorted(self.ulog.default_parameters):
            for k, v in self.ulog.default_parameters[bit].items():
                self.defaults.setdefault(k, v)
        self.messages = [((m.timestamp - self.t0_us) / 1e6, m.level_name, m.text) for m in self.ulog.messages]
        self.info = dict(self.ulog.info)
        self._cache: dict = {}
        self.modes = self._compute_modes()
        self.armed = self._compute_armed()
        self.airborne = self._compute_airborne()
        self.phases = self._compute_phases()
        self.is_vtol = self._detect_vtol()

    # ---------------------------------------------------------------- accesso dati
    @property
    def name(self) -> str:
        return self.path.name

    def topic_names(self):
        return sorted(self._topics)

    def instances(self, topic):
        return sorted(self._topics.get(topic, {}))

    def dataset(self, topic, instance=0):
        return self._topics.get(topic, {}).get(instance)

    def has(self, topic, field=None, instance=0) -> bool:
        d = self.dataset(topic, instance)
        if d is None:
            return False
        return field is None or field in d.data

    def fields(self, topic, instance=0, numeric_only=True):
        d = self.dataset(topic, instance)
        if d is None:
            return []
        out = []
        for name, arr in d.data.items():
            if name == "timestamp" or name.startswith("_padding"):
                continue
            if numeric_only and d.field_types.get(name) == "char":
                continue
            out.append(name)
        return out

    def _time(self, d, use_sample: bool):
        key = (d.name, d.multi_id, use_sample)
        if key in self._cache:
            return self._cache[key]
        ts = d.data["timestamp"].astype(np.float64)
        if use_sample and "timestamp_sample" in d.data:
            tss = d.data["timestamp_sample"].astype(np.float64)
            ok = tss > 0
            if np.count_nonzero(ok) > 0.9 * len(tss):
                ts = np.where(ok, tss, ts)
        t = (ts - self.t0_us) / 1e6
        self._cache[key] = t
        return t

    def series(self, topic, field, instance=0, use_sample=False):
        """Serie (t [s], y) ordinata e senza campioni non validi, oppure None."""
        d = self.dataset(topic, instance)
        if d is None or field not in d.data:
            return None
        t = self._time(d, use_sample)
        y = d.data[field].astype(np.float64)
        ok = np.isfinite(t) & np.isfinite(y) & (d.data["timestamp"] > 0)
        if not np.any(ok):
            return None
        t, y = t[ok], y[ok]
        if np.any(np.diff(t) < 0):
            order = np.argsort(t, kind="stable")
            t, y = t[order], y[order]
        return Series(t, y)

    def first_series(self, candidates, use_sample=False):
        """Prima serie disponibile tra [(topic, campo, istanza)]; restituisce (serie, etichetta)."""
        for cand in candidates:
            topic, field = cand[0], cand[1]
            inst = cand[2] if len(cand) > 2 else 0
            s = self.series(topic, field, inst, use_sample)
            if s is not None and len(s) > 1:
                return s, f"{topic}.{field}" + (f" [{inst}]" if inst else "")
        return None, None

    def rate(self, topic, instance=0) -> float:
        d = self.dataset(topic, instance)
        if d is None:
            return 0.0
        return dsp.median_rate(self._time(d, False))

    def param(self, name, default=None):
        return self.params.get(name, default)

    def attitude_euler(self, topic="vehicle_attitude", qfield="q", instance=0, use_sample=False):
        """Angoli di Eulero (roll, pitch, yaw) da un topic con quaternione.

        Con ``use_sample=True`` i tempi sono quelli di campionamento (timestamp_sample), se il topic li ha.
        """
        key = ("euler", topic, qfield, instance, use_sample)
        if key in self._cache:
            return self._cache[key]
        qs = [self.series(topic, f"{qfield}[{i}]", instance, use_sample) for i in range(4)]
        if any(s is None for s in qs):
            self._cache[key] = None
            return None
        n = min(len(s) for s in qs)
        t = qs[0].t[:n]
        q = [s.y[:n] for s in qs]
        norm = np.sqrt(q[0] ** 2 + q[1] ** 2 + q[2] ** 2 + q[3] ** 2)
        ok = norm > 0.5
        r, p, y = quat_to_euler(*(c[ok] / norm[ok] for c in q))
        out = (Series(t[ok], r), Series(t[ok], p), Series(t[ok], y))
        self._cache[key] = out
        return out

    # ------------------------------------------------------------ stati di volo
    def _status_field(self, *names):
        for n in names:
            s = self.series("vehicle_status", n)
            if s is not None:
                return s
        return None

    def _compute_modes(self):
        s = self._status_field("nav_state")
        if s is None:
            return []
        return [(a, b, int(v)) for a, b, v in dsp.step_intervals(s.t, s.y.astype(int), self.duration)]

    def _compute_armed(self):
        self.armed_known = True
        s = self._status_field("arming_state")
        if s is not None:
            return dsp.intervals_where(s.t, s.y == 2, self.duration)
        s = self.series("actuator_armed", "armed")
        if s is not None:
            return dsp.intervals_where(s.t, s.y > 0, self.duration)
        self.armed_known = False
        return [(0.0, self.duration)]

    def _compute_airborne(self):
        """Intervalli in volo. ``airborne_known`` dice se il log permette di saperlo."""
        s = self.series("vehicle_land_detected", "landed")
        self.airborne_known = s is not None or self.armed_known
        if s is None:
            return list(self.armed)
        flying = dsp.intervals_where(s.t, s.y < 0.5, self.duration)
        return dsp.intersect(flying, self.armed)

    def _compute_phases(self):
        vt = self._status_field("vehicle_type")
        tr = self._status_field("in_transition_mode")
        if vt is not None:
            labels = np.where(vt.y == 2, "FW", np.where(vt.y == 1, "MC", "ALTRO")).astype(object)
            if tr is not None and len(tr) == len(vt):
                labels = np.where(tr.y > 0.5, "TRANS", labels)
            return dsp.step_intervals(vt.t, labels, self.duration)
        rw = self._status_field("is_rotary_wing")
        if rw is not None:
            labels = np.where(rw.y > 0.5, "MC", "FW").astype(object)
            if tr is not None and len(tr) == len(rw):
                labels = np.where(tr.y > 0.5, "TRANS", labels)
            return dsp.step_intervals(rw.t, labels, self.duration)
        vv = self.series("vtol_vehicle_status", "vehicle_vtol_state")
        if vv is not None:
            mapping = {1: "TRANS", 2: "TRANS", 3: "MC", 4: "FW"}
            labels = np.array([mapping.get(int(v), "ALTRO") for v in vv.y], dtype=object)
            return dsp.step_intervals(vv.t, labels, self.duration)
        guess = "FW" if any(k.startswith("FW_") for k in self.params) and not any(
            k.startswith("MC_ROLLRATE") for k in self.params
        ) else "MC"
        return [(0.0, self.duration, guess)]

    def _detect_vtol(self) -> bool:
        s = self._status_field("is_vtol")
        if s is not None and np.any(s.y > 0.5):
            return True
        return self.has("vtol_vehicle_status")

    def phase_intervals(self, phase):
        """Intervalli della fase richiesta ('MC', 'FW', 'TRANS' o 'ALL')."""
        if phase == "ALL":
            return [(0.0, self.duration)]
        return [(a, b) for a, b, p in self.phases if p == phase and b > a]

    def phase_time(self, phase, airborne_only=True) -> float:
        iv = self.phase_intervals(phase)
        if airborne_only:
            iv = dsp.intersect(iv, self.airborne)
        return dsp.total_length(iv)

    # ------------------------------------------------------------------ missione
    def local_reference(self):
        """Origine del sistema locale (lat, lon, alt AMSL) o None."""
        if "_ref" in self._cache:
            return self._cache["_ref"]
        ref = None
        d = self.dataset("vehicle_local_position")
        if d is not None and "ref_lat" in d.data and "ref_lon" in d.data:
            lat, lon = d.data["ref_lat"].astype(float), d.data["ref_lon"].astype(float)
            ok = np.isfinite(lat) & np.isfinite(lon) & ((np.abs(lat) > 1e-6) | (np.abs(lon) > 1e-6))
            if np.any(ok):
                k = int(np.flatnonzero(ok)[-1])
                alt = float(d.data["ref_alt"][k]) if "ref_alt" in d.data else 0.0
                ref = (float(lat[k]), float(lon[k]), alt)
        if ref is None:
            # stima dall'accoppiamento posizione globale / locale
            glat, glon = self.series("vehicle_global_position", "lat"), self.series("vehicle_global_position", "lon")
            galt = self.series("vehicle_global_position", "alt")
            x, y, z = (self.series("vehicle_local_position", c) for c in "xyz")
            if None not in (glat, glon, x, y) and len(glat) and len(x):
                t = glat.t[len(glat) // 2]
                lx, ly = np.interp(t, x.t, x.y), np.interp(t, y.t, y.y)
                lat0 = float(np.interp(t, glat.t, glat.y)) - np.degrees(lx / EARTH_R)
                lon0 = float(np.interp(t, glon.t, glon.y)) - np.degrees(ly / (EARTH_R * np.cos(np.radians(lat0))))
                alt0 = 0.0
                if galt is not None and z is not None:
                    alt0 = float(np.interp(t, galt.t, galt.y)) + float(np.interp(t, z.t, z.y))
                ref = (lat0, lon0, alt0)
        self._cache["_ref"] = ref
        return ref

    def to_local(self, lat, lon):
        """Latitudine/longitudine -> (nord, est) [m] rispetto all'origine locale (approssimazione piana)."""
        ref = self.local_reference()
        if ref is None:
            return None
        lat = np.asarray(lat, float)
        lon = np.asarray(lon, float)
        north = np.radians(lat - ref[0]) * EARTH_R
        east = np.radians(lon - ref[1]) * EARTH_R * np.cos(np.radians(ref[0]))
        return north, east

    def mission(self):
        """Punti di missione registrati e setpoint di posizione attivi, in coordinate locali.

        Restituisce {"items": [dict(seq, cmd, label, t, north, east, alt, loiter_radius)],
        "setpoints": dict(t, north, east, alt, type, loiter_radius) o None}.
        """
        if "_mission" in self._cache:
            return self._cache["_mission"]
        out = {"items": [], "setpoints": None}
        ref = self.local_reference()
        d = self.dataset("navigator_mission_item")
        if d is not None and ref is not None and "latitude" in d.data:
            t = self._time(d, False)
            seen = set()
            for k in range(len(d)):
                seq = int(d.data["sequence_current"][k]) if "sequence_current" in d.data else k
                lat, lon = float(d.data["latitude"][k]), float(d.data["longitude"][k])
                if seq in seen or not np.isfinite(lat) or not np.isfinite(lon) or (abs(lat) < 1e-6 and abs(lon) < 1e-6):
                    continue
                seen.add(seq)
                n, e = self.to_local(lat, lon)
                cmd = int(d.data["nav_cmd"][k]) if "nav_cmd" in d.data else 16
                alt = float(d.data["altitude"][k]) if "altitude" in d.data else float("nan")
                rel = bool(d.data["altitude_is_relative"][k]) if "altitude_is_relative" in d.data else False
                out["items"].append({
                    "seq": seq, "cmd": cmd, "label": NAV_CMDS.get(cmd, f"MAV_CMD {cmd}"), "t": float(t[k]),
                    "north": float(n), "east": float(e), "alt": alt if rel else alt - ref[2],
                    "loiter_radius": abs(float(d.data["loiter_radius"][k])) if "loiter_radius" in d.data else 0.0,
                })
            out["items"].sort(key=lambda it: it["seq"])
        d = self.dataset("position_setpoint_triplet")
        if d is not None and ref is not None and "current.lat" in d.data:
            t = self._time(d, False)
            valid = d.data["current.valid"].astype(bool) if "current.valid" in d.data else np.ones(len(d), bool)
            lat, lon = d.data["current.lat"].astype(float), d.data["current.lon"].astype(float)
            ok = valid & np.isfinite(lat) & np.isfinite(lon) & ((np.abs(lat) > 1e-6) | (np.abs(lon) > 1e-6))
            if np.any(ok):
                n, e = self.to_local(lat[ok], lon[ok])
                alt = d.data["current.alt"].astype(float)[ok] - ref[2] if "current.alt" in d.data else None
                out["setpoints"] = {
                    "t": t[ok], "north": n, "east": e, "alt": alt,
                    "type": d.data["current.type"][ok] if "current.type" in d.data else None,
                    "loiter_radius": d.data["current.loiter_radius"].astype(float)[ok] if "current.loiter_radius" in d.data else None,
                }
        self._cache["_mission"] = out
        return out

    # ------------------------------------------------------------------ riepilogo
    def summary(self):
        """Dati riassuntivi del volo per la scheda Panoramica e il report (etichette già tradotte).

        I valori che richiedono attenzione iniziano con «⚠».
        """
        from .flags import raised_flags

        ka, ua = config.alt_scale()
        ks, us = config.speed_scale()
        out = {}
        out[_("File")] = self.name
        out[_("Durata log")] = _fmt_duration(self.duration)
        air = dsp.total_length(self.airborne)
        out[_("Tempo in volo")] = _fmt_duration(air) if air else "—"
        ver = self.ulog.version_string() or str(self.info.get("ver_sw", "—"))[:12]
        out[_("Versione PX4")] = ver
        out[_("Hardware")] = str(self.info.get("ver_hw", "—"))
        out[_("Sistema")] = str(self.info.get("sys_name", "—"))
        if "SYS_AUTOSTART" in self.params:
            out[_("Airframe (SYS_AUTOSTART)")] = str(self.params["SYS_AUTOSTART"])
        types = sorted({p for _a, _b, p in self.phases})
        out[_("Tipo veicolo")] = ("VTOL — " if self.is_vtol else "") + ", ".join(_(PHASE_LABELS.get(p, p)) for p in types)
        for phase in ("MC", "FW", "TRANS"):
            tt = self.phase_time(phase)
            if tt > 0:
                out[_("Tempo in volo — {fase}").format(fase=_(PHASE_LABELS[phase]).lower())] = _fmt_duration(tt)
        prof = self.params.get("SDLOG_PROFILE")
        if prof is not None:
            out[_("Profilo di log (SDLOG_PROFILE)")] = f"{int(prof)} " + (
                _("(alta frequenza attiva)") if int(prof) & 16 else _("(senza alta frequenza)"))
        rg = self.rate("vehicle_angular_velocity")
        rs = self.rate("vehicle_rates_setpoint")
        if rg:
            out[_("Frequenza log velocità angolare / setpoint")] = f"{rg:.0f} Hz / {rs:.0f} Hz"
        z = self.series("vehicle_local_position", "z")
        if z is not None:
            out[_("Quota max relativa")] = f"{(-np.nanmin(z.y) + z.y[0]) * ka:.1f} {ua}"
        vx = self.series("vehicle_local_position", "vx")
        vy = self.series("vehicle_local_position", "vy")
        if vx is not None and vy is not None and len(vx) == len(vy):
            out[_("Velocità orizzontale max")] = f"{np.nanmax(np.hypot(vx.y, vy.y)) * ks:.1f} {us}"
            x = self.series("vehicle_local_position", "x")
            y = self.series("vehicle_local_position", "y")
            if x is not None and y is not None and len(x) == len(y):
                out[_("Distanza percorsa")] = f"{np.nansum(np.hypot(np.diff(x.y), np.diff(y.y))) * ka:.0f} {ua}"
        ias = self.series("airspeed_validated", "indicated_airspeed_m_s")
        if ias is not None and np.any(np.isfinite(ias.y)) and np.nanmax(ias.y) > 0.5:
            out[_("Velocità all'aria max (IAS)")] = f"{np.nanmax(ias.y) * ks:.1f} {us}"
        bv = self.series("battery_status", "voltage_v") or self.series("battery_status", "voltage_filtered_v")
        if bv is not None:
            valid = bv.y[bv.y > 1]
            if valid.size:
                out[_("Batteria: tensione min / max")] = f"{valid.min():.2f} V / {valid.max():.2f} V"
        cur = self.series("battery_status", "current_a")
        if cur is not None and np.any(cur.y > 0):
            out[_("Batteria: corrente max")] = f"{np.nanmax(cur.y):.1f} A"
            if bv is not None and len(bv) == len(cur):
                out[_("Potenza elettrica max")] = f"{np.nanmax(bv.y * np.maximum(cur.y, 0)):.0f} W"
        mah = self.series("battery_status", "discharged_mah")
        if mah is not None and np.any(mah.y > 0):
            out[_("Batteria: consumo")] = f"{np.nanmax(mah.y):.0f} mAh"
        vib = self.series("vehicle_imu_status", "accel_vibration_metric")
        if vib is not None:
            vmax = float(np.nanmax(vib.y))
            out[_("Vibrazioni accel. (max)")] = ("⚠ " if vmax > 9.81 else "") + f"{vmax:.1f} m/s²"
        n_err = sum(1 for _t, lvl, _m in self.messages if lvl in ("EMERGENZA", "ALLARME", "CRITICO", "ERRORE"))
        n_warn = sum(1 for _t, lvl, _m in self.messages if lvl == "AVVISO")
        out[_("Messaggi errore / avviso")] = f"{n_err} / {n_warn}"
        try:
            fl = raised_flags(self, include_info=False)
        except Exception:  # noqa: BLE001 - il riepilogo non deve fallire per i flag
            fl = []
        n_crit = sum(1 for f in fl if f.severity >= 3)
        out[_("Flag sollevati (critici / avvisi)")] = ("⚠ " if n_crit else "") + f"{n_crit} / {len(fl) - n_crit}"
        try:
            from .modes import allocator_fix_warning

            w = allocator_fix_warning(self)
            if w:
                out[_("Allocatore del tiltrotor")] = "⚠ " + w
        except Exception:  # noqa: BLE001 - il riepilogo non deve fallire per gli avvisi
            pass
        drops = self.ulog.dropouts
        out[_("Dropout del logger")] = (
            _("{n} (totale {s:.2f} s)").format(n=len(drops), s=sum(d.duration_ms for d in drops) / 1000)
            if drops else _("nessuno"))
        if self.ulog.corrupt:
            out[_("Integrità file")] = "⚠ " + _("parti del file corrotte o troncate")
        return out


def _fmt_duration(sec) -> str:
    sec = float(sec)
    m, s = divmod(int(round(sec)), 60)
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"
