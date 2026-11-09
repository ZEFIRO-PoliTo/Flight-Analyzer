"""Flag sollevati durante il volo: failsafe, failure detector, stimatore (EKF2), batteria.

Per ogni flag che diventa attivo almeno una volta restituisce gli intervalli in
cui è stato attivo, il numero di attivazioni, la durata totale e una
descrizione. Nomi e significati vengono dai messaggi di PX4 1.17
(FailsafeFlags.msg, FailureDetectorStatus.msg, EstimatorStatusFlags.msg,
VehicleStatus.msg, BatteryStatus.msg).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from . import dsp
from .i18n import N_, _

# gravità: 3 = failsafe/guasto, 2 = avviso, 1 = informativo
SEVERITY_LABELS = {3: N_("critico"), 2: N_("avviso"), 1: N_("informativo")}

FAILSAFE_FLAGS = {
    "angular_velocity_invalid": (3, N_("Velocità angolare non valida")),
    "attitude_invalid": (3, N_("Assetto non valido")),
    "local_altitude_invalid": (3, N_("Quota locale non valida")),
    "local_position_invalid": (3, N_("Posizione locale stimata non valida")),
    "local_position_invalid_relaxed": (2, N_("Posizione locale non valida anche con requisiti di precisione ridotti")),
    "local_velocity_invalid": (3, N_("Velocità locale stimata non valida")),
    "global_position_invalid": (3, N_("Posizione globale stimata non valida")),
    "global_position_invalid_relaxed": (2, N_("Posizione globale non valida anche con requisiti di precisione ridotti")),
    "auto_mission_missing": (1, N_("Nessuna missione disponibile")),
    "offboard_control_signal_lost": (1, N_("Segnale offboard perso")),
    "home_position_invalid": (2, N_("Posizione di home non disponibile")),
    "manual_control_signal_lost": (3, N_("Segnale del radiocomando perso")),
    "gcs_connection_lost": (2, N_("Collegamento con la stazione di terra perso")),
    "battery_warning": (2, N_("Avviso batteria (livello da BatteryStatus)")),
    "battery_low_remaining_time": (3, N_("Batteria scarica in base al tempo di volo residuo")),
    "battery_unhealthy": (3, N_("Batteria non in buono stato")),
    "geofence_breached": (3, N_("Geofence violato")),
    "mission_failure": (3, N_("Missione fallita")),
    "vtol_fixed_wing_system_failure": (3, N_("Guasto del sistema ad ala fissa (dopo il quad-chute)")),
    "wind_limit_exceeded": (2, N_("Limite di vento superato")),
    "flight_time_limit_exceeded": (2, N_("Tempo di volo massimo superato")),
    "position_accuracy_low": (2, N_("Precisione della posizione sotto soglia (ancora considerata valida)")),
    "navigator_failure": (3, N_("Il navigatore non è riuscito a eseguire un modo")),
    "fd_critical_failure": (3, N_("Guasto critico: limite di assetto/quota superato o ATS esterno")),
    "fd_esc_arming_failure": (3, N_("Un ESC non si è armato")),
    "fd_imbalanced_prop": (3, N_("Elica sbilanciata rilevata")),
    "fd_motor_failure": (3, N_("Guasto motore")),
}
# sempre attivi se la funzione non si usa: si segnalano solo se cambiano (come Flight Review)
SKIP_IF_ALWAYS_SET = {"auto_mission_missing", "offboard_control_signal_lost"}

FAILURE_DETECTOR = {
    "fd_roll": (3, N_("Failure detector: limite di rollio superato")),
    "fd_pitch": (3, N_("Failure detector: limite di beccheggio superato")),
    "fd_alt": (3, N_("Failure detector: limite di quota superato")),
    "fd_ext": (3, N_("Failure detector: segnale di terminazione esterno")),
    "fd_arm_escs": (3, N_("Failure detector: ESC non armati")),
    "fd_battery": (3, N_("Failure detector: guasto batteria")),
    "fd_imbalanced_prop": (3, N_("Failure detector: elica sbilanciata")),
    "fd_motor": (3, N_("Failure detector: guasto motore")),
}

ESTIMATOR_FLAGS = {
    # stato del filtro che indica un problema
    "cs_mag_field_disturbed": (2, N_("EKF2: campo magnetico diverso dall'intensità attesa")),
    "cs_mag_fault": (3, N_("EKF2: magnetometro dichiarato guasto e non più usato")),
    "cs_rng_stuck": (2, N_("EKF2: telemetro bloccato (nessun valore nuovo per più di 10 s)")),
    "cs_gnss_yaw_fault": (2, N_("EKF2: imbardata da GNSS dichiarata guasta")),
    "cs_rng_fault": (2, N_("EKF2: telemetro dichiarato guasto")),
    "cs_inertial_dead_reckoning": (3, N_("EKF2: navigazione inerziale senza misure che limitino la deriva di velocità")),
    "cs_wind_dead_reckoning": (2, N_("EKF2: navigazione basata solo su misure relative al vento")),
    "cs_ev_yaw_fault": (2, N_("EKF2: imbardata da visione esterna dichiarata guasta")),
    "cs_baro_fault": (3, N_("EKF2: barometro dichiarato guasto")),
    "cs_gnss_fault": (3, N_("EKF2: misure GNSS (posizione, velocità) dichiarate guaste")),
    "cs_gnss_hgt_fault": (2, N_("EKF2: quota GNSS dichiarata guasta")),
    "cs_gnd_effect": (1, N_("EKF2: protezione dall'effetto suolo sul barometro attiva")),
    # errori numerici
    "fs_bad_mag_x": (3, N_("EKF2: errore numerico nella fusione del magnetometro X")),
    "fs_bad_mag_y": (3, N_("EKF2: errore numerico nella fusione del magnetometro Y")),
    "fs_bad_mag_z": (3, N_("EKF2: errore numerico nella fusione del magnetometro Z")),
    "fs_bad_hdg": (3, N_("EKF2: errore numerico nella fusione della prua")),
    "fs_bad_mag_decl": (3, N_("EKF2: errore numerico nella fusione della declinazione magnetica")),
    "fs_bad_airspeed": (3, N_("EKF2: errore numerico nella fusione della velocità all'aria")),
    "fs_bad_sideslip": (3, N_("EKF2: errore numerico nella fusione della derapata sintetica")),
    "fs_bad_optflow_x": (3, N_("EKF2: errore numerico nella fusione del flusso ottico X")),
    "fs_bad_optflow_y": (3, N_("EKF2: errore numerico nella fusione del flusso ottico Y")),
    "fs_bad_acc_vertical": (3, N_("EKF2: dati dell'accelerometro verticale non plausibili")),
    "fs_bad_acc_clipping": (3, N_("EKF2: saturazione (clipping) dell'accelerometro")),
    # misure scartate dal test di innovazione
    "reject_hor_vel": (2, N_("EKF2: velocità orizzontale scartata dal test di innovazione")),
    "reject_ver_vel": (2, N_("EKF2: velocità verticale scartata dal test di innovazione")),
    "reject_hor_pos": (2, N_("EKF2: posizione orizzontale scartata dal test di innovazione")),
    "reject_ver_pos": (2, N_("EKF2: posizione verticale scartata dal test di innovazione")),
    "reject_yaw": (2, N_("EKF2: imbardata scartata dal test di innovazione")),
    "reject_airspeed": (2, N_("EKF2: velocità all'aria scartata dal test di innovazione")),
    "reject_sideslip": (2, N_("EKF2: derapata sintetica scartata dal test di innovazione")),
    "reject_hagl": (2, N_("EKF2: altezza dal suolo scartata dal test di innovazione")),
    "reject_optflow_x": (2, N_("EKF2: flusso ottico X scartato dal test di innovazione")),
    "reject_optflow_y": (2, N_("EKF2: flusso ottico Y scartato dal test di innovazione")),
}

SOURCE_LABELS = {"failsafe_flags": N_("Failsafe"), "vehicle_status": N_("Stato del veicolo"),
                 "failure_detector_status": N_("Failure detector"), "estimator_status_flags": N_("Stimatore (EKF2)"),
                 "battery_status": N_("Batteria")}


@dataclass
class Flag:
    key: str
    source: str
    severity: int
    description: str  # in italiano: tradurre con _() quando si mostra
    intervals: list = field(default_factory=list)
    always_set: bool = False

    @property
    def count(self):
        return len(self.intervals)

    @property
    def total(self):
        return float(sum(b - a for a, b in self.intervals))

    @property
    def first(self):
        return self.intervals[0][0] if self.intervals else None

    def label(self):
        return f"{self.key}" + (f" [{self.source.split(':')[-1]}]" if ":" in self.source else "")


def _active_intervals(log, topic, field, inst, predicate):
    s = log.series(topic, field, inst)
    if s is None or len(s) == 0:
        return None, None
    active = predicate(s.y)
    if not np.any(active):
        return [], s
    return dsp.intervals_where(s.t, active, log.duration), s


def raised_flags(log, include_info=True):
    """Elenco dei flag attivati almeno una volta, ordinati per gravità e istante."""
    out = []

    def add(topic, inst, key, sev, desc, predicate=lambda y: y > 0.5, skip_always=False):
        iv, s = _active_intervals(log, topic, key, inst, predicate)
        if not iv:
            return
        always = bool(np.all(predicate(s.y)))
        if skip_always and always:
            return
        src = topic if inst == 0 else f"{topic}:{inst}"
        out.append(Flag(key, src, sev, desc, iv, always))

    for key, (sev, desc) in FAILSAFE_FLAGS.items():
        if key == "battery_warning":
            add("failsafe_flags", 0, key, sev, desc, predicate=lambda y: y >= 1)
        else:
            add("failsafe_flags", 0, key, sev, desc, skip_always=key in SKIP_IF_ALWAYS_SET)
    add("vehicle_status", 0, "failsafe", 3, N_("Failsafe attivo"))
    add("vehicle_status", 0, "failsafe_and_user_took_over", 2, N_("Failsafe attivo ma il pilota ha ripreso il controllo"))
    add("vehicle_status", 0, "gcs_connection_lost", 2, N_("Collegamento con la stazione di terra perso"))
    for key, (sev, desc) in FAILURE_DETECTOR.items():
        add("failure_detector_status", 0, key, sev, desc)
    for inst in log.instances("estimator_status_flags") or [0]:
        for key, (sev, desc) in ESTIMATOR_FLAGS.items():
            add("estimator_status_flags", inst, key, sev, desc)
    for inst in log.instances("battery_status") or [0]:
        add("battery_status", inst, "warning", 2, N_("Avviso batteria (1 basso, 2 critico, 3 emergenza)"),
            predicate=lambda y: y >= 1)
    if not include_info:
        out = [f for f in out if f.severity > 1]
    # gcs_connection_lost esiste sia in failsafe_flags sia in vehicle_status: tieni il primo
    seen, uniq = set(), []
    for f in out:
        if f.key == "gcs_connection_lost" and any(g.key == "gcs_connection_lost" for g in uniq):
            continue
        if (f.key, f.source) in seen:
            continue
        seen.add((f.key, f.source))
        uniq.append(f)
    uniq.sort(key=lambda f: (-f.severity, f.first if f.first is not None else 0.0))
    return uniq


def flag_topics_present(log):
    return [t for t in ("failsafe_flags", "failure_detector_status", "estimator_status_flags", "vehicle_status")
            if log.has(t)]


def describe(flag: Flag) -> str:
    return _(flag.description)
