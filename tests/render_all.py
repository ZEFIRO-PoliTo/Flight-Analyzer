"""Renderizza tutti i grafici in PNG (backend Agg) per controllarli senza GUI."""
import sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import matplotlib
matplotlib.use("Agg")
from matplotlib.figure import Figure
from flight_analyzer.logdata import LogData
from flight_analyzer import analysis, plots

log = LogData(sys.argv[1]); out = Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
others = [LogData(p) for p in sys.argv[3:]]
def save(name, builder, *a, size=(13, 7.5), **kw):
    t = time.time(); fig = Figure(figsize=size, dpi=90); r = builder(fig, *a, **kw); fig.savefig(out / f"{name}.png"); print(name, f"{time.time()-t:.2f}s"); return fig, r
save("1_panoramica", plots.build_overview, log)
save("2_assetto", plots.build_attitude, log)
save("3_rate", plots.build_rates, log)
save("4_posizione", plots.build_position, log)
save("5a_comandi", plots.build_controls, log)
save("5b_potenza", plots.build_power, log)
save("5c_uscite", plots.build_outputs, log)
save("5d_giri", plots.build_rpm, log)
save("6_vibrazioni", plots.build_vibration, log)
save("6b_psd", plots.build_psd_spectrograms, log)
save("7_spettro", plots.build_spectrum, log, "Accelerometro (sensor_combined)")
save("8_sistema", plots.build_system, log)
save("8b_flag", plots.build_flags, log)
res = analysis.analyze(log, "MC", "rate")
cmp_res = [analysis.analyze(o, "MC", "rate") for o in others]
save("9_pid_gradino", plots.build_step_responses, [res] + cmp_res, size=(13, 4.2))
save("10_pid_frequenza", plots.build_frequency, res.axes["roll"], [c.axes["roll"] for c in cmp_res],
     [log.name] + [o.name for o in others], size=(13, 4.2))
save("11_pid_dati", plots.build_analysis_timeline, log, res, "roll", size=(13, 5))
resf = analysis.analyze(log, "FW", "att")
save("12_fw_assetto_gradino", plots.build_step_responses, [resf], size=(13, 4.2))
fig, tf = save("13_esplora", plots.build_explorer, log, [("vehicle_status", 0, "nav_state"), ("battery_status", 0, "voltage_v"), ("battery_status", 0, "current_a")])
# zoom + lettura valori
fig, tf = save("14_rate_zoom", plots.build_rates, log)
tf.axes[0].set_xlim(40, 44); tf.autoscale_y(); tf.set_cursor(41.5); fig.savefig(out / "14_rate_zoom.png")
print(tf.readout(41.5)[:200])
