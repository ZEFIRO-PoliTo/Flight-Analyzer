"""Log minimo senza volo (solo stato e sensori a terra), per provare che l'app non si blocchi.

Uso: python tests/make_minimal_log.py USCITA.ulg
"""

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ulog_writer import ULogWriter  # noqa: E402


def build(path):
    w = ULogWriter(start_timestamp=1_000_000)
    n = 500
    t = (np.arange(n) * 10_000 + 1_000_000).astype(np.int64)
    w.add_format("vehicle_status", ["uint64_t timestamp", "uint8_t nav_state", "uint8_t arming_state"])
    w.add_topic("vehicle_status", {"timestamp": t[::50], "nav_state": np.zeros(10), "arming_state": np.ones(10)})
    w.add_format("sensor_combined", ["uint64_t timestamp", "float[3] gyro_rad", "float[3] accelerometer_m_s2"])
    w.add_topic("sensor_combined", {"timestamp": t,
                                    "gyro_rad": 0.001 * np.random.default_rng(0).standard_normal((n, 3)),
                                    "accelerometer_m_s2": np.tile([0.0, 0.0, -9.81], (n, 1))})
    w.add_message(1_500_000, "6", "log di prova senza volo")
    w.params.update({"SYS_AUTOSTART": 4001, "MC_ROLLRATE_P": 0.15})
    w.write(path)


if __name__ == "__main__":
    build(sys.argv[1])
    print(f"scritto {sys.argv[1]}")
