"""Esegue la logica della GUI con il sostituto di Qt (tests/qt_stub.py).

Uso: python tests/smoke_gui.py LOG_B.ulg LOG_C.ulg VECCHIO.ulg CARTELLA_USCITA [LOG_GRADINI.ulg]

LOG_GRADINI è un log con prove a gradino (tests/make_step_log.py); se manca viene creato nella cartella di uscita.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))

import qt_stub  # noqa: E402

qt_stub.install()

from matplotlib.backend_bases import KeyEvent, MouseEvent  # noqa: E402

from flight_analyzer import config, gui, i18n, theme  # noqa: E402

log_b, log_c, log_old, out = sys.argv[1:5]
out = Path(out)
out.mkdir(parents=True, exist_ok=True)
if len(sys.argv) > 5:
    log_steps = sys.argv[5]
else:
    import make_step_log  # noqa: E402

    log_steps = str(out / "gradini_sintetico.ulg")
    make_step_log.build(log_steps)
Qt = qt_stub.Qt
errors = qt_stub.QMessageBox.shown


def check(cond, msg):
    if not cond:
        raise AssertionError(msg)
    print("  ok:", msg)


def no_errors(step):
    if errors:
        for e in errors:
            print("ERRORE MOSTRATO:", getattr(e, "args", e), getattr(e, "_detailed", ""))
        raise AssertionError(f"finestre di errore durante: {step}")


def mouse(panel, name, xdata, ydata=None, ax=None, **kw):
    ax = ax or panel.tf.axes[0]
    if ydata is None:
        ydata = sum(ax.get_ylim()) / 2
    x, y = ax.transData.transform((xdata, ydata))
    ev = MouseEvent(name, panel.canvas, x, y, **kw)
    panel.canvas.callbacks.process(name, ev)


def key(panel, k):
    ax = panel.tf.axes[0]
    x, y = ax.transAxes.transform((0.5, 0.5))
    panel.canvas.callbacks.process("key_press_event", KeyEvent("key_press_event", panel.canvas, k, x, y))


def xlim(panel):
    return tuple(round(v, 3) for v in panel.tf.axes[0].get_xlim())


app = qt_stub.QApplication([])
gui.load_config(qt_stub.QSettings())
gui.apply_theme(app, config.CFG["theme"])
win = gui.MainWindow()
print("1. apertura log")
win.load(log_b)
no_errors("apertura")
check(win.log is not None and win.log.name == Path(log_b).name, "log caricato")
check(win.t_pid.results is not None, "analisi PID eseguita all'apertura")
print("   riquadro:", win.t_pid.overall.text().replace("\n", " | "))
check("Ottimo" in win.t_pid.overall.text() or "Buono" in win.t_pid.overall.text(), "giudizio complessivo presente")
check(win.t_pid.tree.topLevelItemCount() == 3, "tre assi nella tabella punteggi")
check(len(win.t_pid.tree.topLevelItem(0).children) >= 5, "metriche del rollio elencate")
check("Rollio" in win.t_pid.diag.html, "diagnosi compilate")
check(win.t_overview.table.rowCount() > 8, "riepilogo compilato")
check(win.t_params.model.rowCount() > 20, "parametri caricati")
check(win.t_msgs.table.rowCount() >= 8, "messaggi caricati")
check(win.tabs.count() == len(config.TAB_KEYS), f"{win.tabs.count()} schede")

print("2. tutte le schede")
for i in range(win.tabs.count()):
    win.tabs.setCurrentIndex(i)
no_errors("schede")
check(len(win._built) >= 14, "tutte le schede costruite")
shots = ((win.t_overview, "panoramica"), (win.t_att, "assetto"), (win.t_rates, "rate"), (win.t_pos, "posizione"),
         (win.t_ctrl, "comandi"), (win.t_power, "potenza"), (win.t_out, "uscite"), (win.t_rpm, "giri"),
         (win.t_vib, "vibrazioni"), (win.t_sys, "sistema"), (win.t_flags, "flag"), (win.t_explore, "esplora"))
for tab, name in shots:
    tab.panel.fig.set_size_inches(14, 9)
    tab.panel.fig.savefig(out / f"gui_{name}.png", dpi=80)
check(win.t_power.panel.tf is not None and len(win.t_power.panel.tf.axes) >= 3, "grafici di potenza")
check(win.t_rpm.panel.tf is not None, "grafico dei giri motore")
check(len(win.t_out.panel.tf.axes) >= 2, "uscite motori e servi")

print("3. flag sollevati")
flags = win.t_flags.flags
check(len(flags) >= 4, f"{len(flags)} flag nella tabella: " + ", ".join(f.key for f in flags))
check(all(f.key != "auto_mission_missing" for f in flags), "flag sempre attivo e non usato escluso")
check(win.t_flags.table.item(0, 2).text() == "avviso", "gravità in italiano")
win.t_flags.show_info.setChecked(False)
check(all(f.severity > 1 for f in win.t_flags.flags), "filtro dei flag informativi")
win.t_flags.show_info.setChecked(True)
win.tabs.setCurrentWidget(win.t_flags)
first = win.t_flags.flags[0].first
win.t_flags._goto(0, 0)
check(win.xrange[0] <= first <= win.xrange[1], f"doppio clic sul flag centra i grafici (t = {first:.1f} s)")
no_errors("flag")

print("4. reticolo e lettura valori")
panel = win.t_rates.panel
win.tabs.setCurrentWidget(win.t_rates)
panel.full_view()
panel.canvas.draw()
mouse(panel, "motion_notify_event", 50.0, 0.0)
check(win.readout.text().startswith("t = 50."), f"lettura valori: {win.readout.text()[:80]}")

print("5. zoom sincronizzato e navigazione")
ax = panel.tf.axes[0]
ax.set_xlim(40.0, 60.0)
check(win.xrange == (40.0, 60.0), "intervallo condiviso aggiornato")
win.tabs.setCurrentWidget(win.t_att)
check(xlim(win.t_att.panel) == (40.0, 60.0), "assetto allineato allo zoom")
p = win.t_att.panel
p.canvas.draw()
mouse(p, "scroll_event", 50.0, button="up", step=1)
lo, hi = p.tf.axes[0].get_xlim()
check(hi - lo < 19.9 and lo < 50 < hi, f"rotella: zoom attorno al mouse ({lo:.1f}–{hi:.1f} s)")
mouse(p, "scroll_event", 50.0, button="down", step=-1)
mouse(p, "scroll_event", 50.0, button="down", step=-1)
lo2, hi2 = p.tf.axes[0].get_xlim()
check(hi2 - lo2 > hi - lo, "rotella indietro: zoom out")
before = xlim(p)
mouse(p, "button_press_event", 50.0, button=1)
mouse(p, "motion_notify_event", 45.0, button=1)
mouse(p, "button_release_event", 45.0, button=1)
after = xlim(p)
check(after[0] > before[0] + 4, f"trascinamento: spostamento nel tempo {before} → {after}")
ax0 = p.tf.axes[0]
y0 = ax0.get_ylim()
mouse(p, "scroll_event", 50.0, button="up", step=1, key="control")
check(ax0.get_ylim()[1] - ax0.get_ylim()[0] < y0[1] - y0[0], "Ctrl+rotella: zoom verticale")
key(p, "right")
check(xlim(p)[0] > after[0], "freccia destra: scorrimento")
key(p, "a")
check(not getattr(ax0, "_fa_user_y", False), "tasto A: asse verticale riadattato")
mouse(p, "button_press_event", 50.0, button=1, dblclick=True)
check(xlim(p)[0] <= 0.5 and xlim(p)[1] >= win.log.duration - 1, "doppio clic: tutto il log")
segs = win.t_att.goto._segs
check(any("Ala fissa" in s[0] for s in segs), f"menu «Vai a» con {len(segs)} voci")
idx = next(i for i, s in enumerate(segs) if "Ala fissa" in s[0])
win.t_att.goto._pick(idx)
a, b = segs[idx][1], segs[idx][2]
check(abs(p.tf.axes[0].get_xlim()[0] - a) < 0.1 * (b - a) and win.xrange is not None, "«Vai a» porta alla fase")
no_errors("navigazione")

print("6. analisi su intervallo, fasi e anelli")
win.on_xrange(40.0, 60.0)
win.t_pid.range.setCurrentIndex(1)
win.t_pid.run()
res = win.t_pid.results[0][1]
check(all(40.0 <= a and b <= 60.0 for a, b in res.intervals), "analisi limitata all'intervallo visibile")
win.t_pid.range.setCurrentIndex(0)
for phase_idx in (0, 1, 2):
    for loop_idx in (0, 1):
        win.t_pid.phase.setCurrentIndex(phase_idx)
        win.t_pid.loop.setCurrentIndex(loop_idx)
        win.t_pid.run()
        r = win.t_pid.results[0][1]
        print(f"   {r.phase}/{r.loop}: {r.grade} {r.score}")
no_errors("fasi/anelli")
win.t_pid.phase.setCurrentIndex(0)
win.t_pid.loop.setCurrentIndex(0)

print("7. confronto tra log")
qt_stub.QFileDialog.next_open_many = ([log_c], "")
win.add_comparison()
no_errors("confronto")
check(len(win.comparisons) == 1 and len(win.t_pid.results) == 2, "log di confronto analizzato")
check(win.t_pid.cmp_table.rowCount() == 2, "tabella di confronto compilata")
for i in range(3):
    win.t_pid.axis.setCurrentIndex(i)
win.t_pid.show_band.setChecked(False)
win.t_pid.show_band.setChecked(True)
check("|T|" in win.t_pid.t_info.text() and "1/(4f)" in win.t_pid.t_info.text(), "spiegazione di |T| presente")
win.t_pid._toggle_t_info(False)
check(not win.t_pid.t_info.isVisible(), "spiegazione di |T| richiudibile")
win.t_pid._toggle_t_info(True)
for pp, name in ((win.t_pid.p_step, "pid_gradino"), (win.t_pid.p_freq, "pid_frequenza"), (win.t_pid.p_data, "pid_dati")):
    pp.fig.set_size_inches(13, 5)
    pp.fig.savefig(out / f"gui_{name}.png", dpi=80)

print("8. esplora dati, spettri, messaggi, parametri")
top = next(t for t in win.t_explore.tree.items if t.text(0).startswith("battery_status"))
for ch in top.children[:2]:
    ch.setCheckState(0, Qt.CheckState.Checked)
win.t_explore.tree.itemChanged.emit(top.children[0], 0)
check(win.t_explore.panel.tf is not None and len(win.t_explore.panel.tf.axes) == 1, "grafico di esplorazione")
win.t_explore.search.setText("rates")
win.t_explore._clear()
names = [win.t_vib.combo.itemText(i) for i in range(win.t_vib.combo.count())]
check(len(names) == 6, "viste delle vibrazioni: " + " | ".join(names))
for i in range(win.t_vib.combo.count()):
    win.t_vib.combo.setCurrentIndex(i)
    win.t_vib.panel.fig.set_size_inches(14, 9)
    win.t_vib.panel.fig.savefig(out / f"gui_vibrazioni_{i}.png", dpi=70)
win.t_vib.combo.setCurrentIndex(1)
check(win.t_vib.panel.tf is not None and len(win.t_vib.panel.tf.axes) == 3, "spettrogrammi PSD come Flight Review")
win.t_msgs._goto(3, 0)
check(win.xrange is not None, "doppio clic su messaggio centra i grafici")
win.t_params.only_changed.setChecked(True)
win.t_params.filter.setText("MC_ROLL")
no_errors("esplora/spettri/messaggi/parametri")

print("9. profilo di valutazione")
dlg = gui.ProfileDialog(win.profile, win)
prof = dlg._collect()
check(prof["loops"]["mc_rate"]["metrics"]["overshoot"]["good"] == 5.0, "profilo letto dal dialogo")
dlg._tables[("mc_rate", None)].item(0, 1).setText("8")
dlg._targets[("mc_rate", "roll")].setText("0,10")
dlg._accept()
check(dlg.profile["loops"]["mc_rate"]["rise_target_s"]["roll"] == 0.10, "obiettivo con virgola decimale accettato")
dlg._tables[("mc_rate", None)].item(0, 2).setText("8")
n_err = len(errors)
dlg._accept()
check(len(errors) == n_err + 1, "soglie non valide rifiutate")
dlg._tables[("mc_rate", None)].item(0, 2).setText("abc")
dlg._accept()
check(len(errors) == n_err + 2, "valore non numerico rifiutato con un messaggio")
errors.clear()
qt_stub.QDialog.exec_result = qt_stub.QDialog.DialogCode.Accepted
win.edit_profile()
check("profilo" in qt_stub.QSettings.store, "profilo salvato nelle impostazioni")
win2 = gui.MainWindow()
check(win2.profile == win.profile, "profilo ricaricato all'avvio")

print("10. esportazioni")
qt_stub.QFileDialog.next_save = (str(out / "report_gui.html"), "Pagina HTML (*.html)")
win.export_report()
no_errors("report HTML")
html_txt = (out / "report_gui.html").read_text(encoding="utf-8")
check(len(html_txt) > 100_000 and "Parametri di valutazione" in html_txt, "report HTML con i parametri in fondo")
qt_stub.QFileDialog.next_save = (str(out / "report_gui"), "Report PDF (*.pdf)")
win.export_report()
no_errors("report PDF da dialogo")
check((out / "report_gui.pdf").read_bytes()[:4] == b"%PDF", "estensione .pdf aggiunta dal filtro scelto")
win.export_pdf_quick()
no_errors("PDF diretto")
quick = Path(log_b).with_suffix(".report.pdf")
check(quick.exists() and quick.stat().st_size > 50_000, f"PDF diretto accanto al log ({quick.stat().st_size // 1024} kB)")
qt_stub.QFileDialog.next_save = (str(out / "risultati_gui.json"), "")
win.export_json()
check((out / "risultati_gui.json").exists(), "JSON scritto")
win.tabs.setCurrentWidget(win.t_pid)
win.t_pid.views.setCurrentIndex(1)
qt_stub.QFileDialog.next_save = (str(out / "grafico.png"), "")
win.save_current_plot()
check((out / "grafico.png").exists(), "grafico corrente salvato (anche dalla pagina della frequenza)")
check(len(win._recent()) >= 1, "elenco dei recenti aggiornato")

print("11. visualizzazione: unità, sfondo, legenda, pannelli")
win.tabs.setCurrentWidget(win.t_att)
win.set_display("angle_unit", "rad")
check(win.t_att.panel.tf.axes[0].get_ylabel() == "[rad]", "assetto in radianti")
check(qt_stub.QSettings.store.get("unita_angoli") == "rad", "unità salvata nelle impostazioni")
win.set_display("angle_unit", "deg")
check(win.t_att.panel.tf.axes[0].get_ylabel() == "[°]", "assetto in gradi")
for bg in ("phases", "modes", "none", "both"):
    win.set_display("background", bg)
win.tabs.setCurrentWidget(win.t_pos)
panel = win.t_pos.panel
panel.canvas.draw()
fmap = panel.fig._fa_legend_map
check(len(fmap) > 0, f"voci di legenda cliccabili: {len(fmap) // 2}")
origs, h, txt = next(v for k, v in fmap.items() if k is v[2])
bb = txt.get_window_extent()


def click():
    ev = MouseEvent("button_press_event", panel.canvas, (bb.x0 + bb.x1) / 2, (bb.y0 + bb.y1) / 2, button=1)
    panel.canvas.callbacks.process("button_press_event", ev)


click()
check(not origs[0].get_visible(), f"clic sulla voce «{txt.get_text()}» nasconde la curva")
click()
check(origs[0].get_visible(), "secondo clic la mostra di nuovo")
win.tabs.setCurrentWidget(win.t_pid)
win.toggle_side_panel()
check(win.t_pid.side_toggle.side.isHidden(), "pannello laterale PID nascosto")
win.toggle_side_panel()
check(not win.t_pid.side_toggle.side.isHidden(), "pannello laterale PID mostrato")
win.tabs.setCurrentWidget(win.t_overview)
win.toggle_side_panel()
check(win.t_overview.table.isHidden(), "riepilogo della panoramica nascosto")
win.tabs.setCurrentWidget(win.t_flags)
win.toggle_side_panel()
check(win.t_flags.side.isHidden(), "elenco dei flag nascosto")
win.toggle_fullscreen()
no_errors("visualizzazione")

print("12. impostazioni")
dlg = gui.SettingsDialog(win)
vals = dlg.values()
check(vals["theme"] == "light" and vals["language"] == "it", "impostazioni lette dal dialogo")
gui.SettingsDialog._select(dlg.theme, "dark")
gui.SettingsDialog._select(dlg.speed, "km/h")
gui.SettingsDialog._select(dlg.alt, "ft")
dlg.tab_checks["rpm"].setChecked(False)
dlg.tab_checks["explore"].setChecked(False)
dlg.line_width.setValue(1.5)


class _Dlg:
    def __init__(self, *a):
        pass

    def exec(self):
        return True

    def values(self):
        return dict(dlg.values())


real = gui.SettingsDialog
gui.SettingsDialog = _Dlg
win.edit_settings()
gui.SettingsDialog = real
no_errors("impostazioni")
check(theme.current() == "dark", "tema scuro applicato")
check(win.tabs.count() == len(config.TAB_KEYS) - 2 and win.tabs.indexOf(win.t_rpm) < 0, "schede nascoste")
check(qt_stub.QSettings.store.get("impostazioni/hidden_tabs") == "rpm,explore", "schede nascoste salvate")
check(qt_stub.QSettings.store.get("impostazioni/speed_unit") == "km/h", "unità di velocità salvata")
win.tabs.setCurrentWidget(win.t_pos)
labels = " ".join(ax.get_ylabel() for ax in win.t_pos.panel.tf.axes)
check("km/h" in labels and "ft" in labels, f"posizione in km/h e piedi: {labels}")
check(win.t_pos.panel.fig.get_facecolor()[:3] != (1.0, 1.0, 1.0), "figura con sfondo scuro")
for tab, name in ((win.t_pos, "scuro_posizione"), (win.t_power, "scuro_potenza")):
    win.tabs.setCurrentWidget(tab)
    tab.panel.fig.set_size_inches(14, 9)
    tab.panel.fig.savefig(out / f"gui_{name}.png", dpi=80)
win.tabs.setCurrentWidget(win.t_pid)
win.t_pid.p_freq.fig.savefig(out / "gui_scuro_pid_frequenza.png", dpi=80)
qt_stub.QFileDialog.next_save = (str(out / "report_scuro.pdf"), "")
win.export_report()
no_errors("report in tema scuro")
check(theme.current() == "dark", "il report non cambia il tema dell'app")
win2 = gui.MainWindow()
gui.load_config(qt_stub.QSettings())
check(config.CFG["hidden_tabs"] == ["rpm", "explore"] and config.CFG["line_width"] == 1.5, "impostazioni ricaricate")
win.set_display("theme", "light")
config.update({"hidden_tabs": [], "speed_unit": "m/s", "alt_unit": "m", "line_width": 1.0})
gui.save_config(qt_stub.QSettings())
win._rebuild_tabs()
check(win.tabs.count() == len(config.TAB_KEYS), "schede ripristinate")

print("12b. prove a gradino e profilo Vespa hover")
win.load(log_steps)
no_errors("log con gradini")
win.tabs.setCurrentWidget(win.t_steps)
no_errors("scheda prove a gradino")
res = win.t_steps.result
check(res is not None and len(res.steps) == 11, f"{len(res.steps)} gradini trovati nel log sintetico")
check(win.t_steps.table.rowCount() == 11, "elenco dei gradini compilato")
check(sum(s.valid for s in res.steps) == 8, "8 gradini validi, 3 scartati con il motivo")
check(win.t_steps.summary.rowCount() == 2, "riepilogo per verso")
check("TARATO" in win.t_steps.summary.item(0, 9).text(), "esito dell'asse nel riepilogo")
check("Stima FIR" in win.t_steps.info.html and "Tenuta" in win.t_steps.info.html, "FIR affiancato e tenuta")
bad_row = next(i for i, s in enumerate(res.steps) if not s.valid)
win.t_steps.table.selectRow(bad_row)
check("SCARTATO" in win.t_steps.p_detail.fig.axes[0].get_title(loc="left"), "grafico del gradino scartato con il motivo")
win.t_steps.p_detail.fig.set_size_inches(12, 7)
win.t_steps.p_detail.fig.savefig(out / "gui_gradino_scartato.png", dpi=80)
win.t_steps.views.setCurrentIndex(1)
win.t_steps.over_axis.setCurrentIndex(0)
check(win.t_steps.panel.tf is not None, "vista di tutto il volo con i gradini")
win.t_steps.panel.fig.set_size_inches(14, 5)
win.t_steps.panel.fig.savefig(out / "gui_gradini_volo.png", dpi=80)
win.t_steps.export()
no_errors("esportazione PNG e CSV")
png, csv_path, step_dir = __import__("flight_analyzer.steptest", fromlist=["x"]).output_paths(log_steps)
check(png.exists() and csv_path.exists() and len(list(step_dir.glob("*.png"))) == 11, "PNG riassuntivo, CSV e PNG per gradino")
check("1.2.0" in csv_path.read_text(encoding="utf-8-sig").splitlines()[1], "versione scritta nel CSV")
win.t_steps.ignore_mode.setChecked(True)
win.t_steps.run()
check(win.t_steps.result.ignore_mode, "opzione «ignora il modo»")
win.t_steps.ignore_mode.setChecked(False)
qt_stub.QFileDialog.next_open = (str(HERE.parent / "profili" / "vespa_hover.json"), "")
win.t_steps.load_criteria()
check("profilo_gradini" in qt_stub.QSettings.store, "criteri caricati e salvati")
win.t_steps.reset_criteria()
check("profilo_gradini" not in qt_stub.QSettings.store, "criteri forniti con l'app ripristinati")
win.tabs.setCurrentWidget(win.t_pid)
win.t_pid.prof_combo.setCurrentIndex(1)
win.t_pid._profile_chosen(1)
no_errors("profilo Vespa hover")
r = win.t_pid.results[0][1]
keys = [it.key for it in r.axes["roll"].card.items]
check("delay" in keys and "overshoot_cmd" in keys and "rise_ratio" not in keys, "punteggio con le definizioni della scheda")
check(r.axes["roll"].card.confidence in ("alta", "media"), f"affidabilità dai gradini: {r.axes['roll'].card.confidence}")
dlg = gui.ProfileDialog(win.profile, win)
prof = dlg._collect()
check(prof["loops"]["mc_rate"].get("definizioni") == "scheda" and "yaw" in prof["loops"]["mc_rate"]["metrics_asse"],
      "il dialogo del profilo conserva definizioni e soglie per asse")
check(("mc_rate", "yaw") in dlg._tables, "scheda delle soglie dell'imbardata")
dlg._defaults()
check(("mc_rate", "yaw") not in dlg._tables and ("mc_rate", None) in dlg._tables, "ritorno al PX4 standard")
win.use_px4_profile()
check(win.t_pid.prof_combo.currentIndex() == 0, "profilo PX4 standard riattivato")
qt_stub.QFileDialog.next_save = (str(out / "report_gradini.html"), "")
win.export_report()
no_errors("report con prove a gradino")
check("Prove a gradino" in (out / "report_gradini.html").read_text(encoding="utf-8"), "sezione «Prove a gradino» nel report")

print("13. log senza volo e file non valido")
win.clear_comparisons()
win.load(log_old)
no_errors("log vecchio")
print("   riquadro:", win.t_pid.overall.text().replace("\n", " | "))
for i in range(win.tabs.count()):
    win.tabs.setCurrentIndex(i)
no_errors("schede log vecchio")
bad = out / "non_un_log.ulg"
bad.write_bytes(b"questo non e un log")
win.load(str(bad))
check(len(errors) == 1, "file non valido segnalato con un errore")
print("   messaggio:", errors[0].args[2] if len(errors[0].args) > 2 else errors[0].args)
errors.clear()

print("14. interfaccia in inglese")
qt_stub.QSettings.store["lingua"] = "en"
gui.load_config(qt_stub.QSettings())
i18n.set_language(config.CFG["language"])
check(i18n.language() == "en", "lingua letta dalle impostazioni (scritta dall'installer)")
win_en = gui.MainWindow()
tabs_en = [win_en.tabs.tabText(i) for i in range(win_en.tabs.count())]
check(tabs_en[:4] == ["Overview", "PID analysis", "Step tests", "Attitude"], "schede in inglese: " + ", ".join(tabs_en))
win_en.load(log_b)
no_errors("log in inglese")
txt = win_en.t_pid.overall.text()
print("   box:", txt.replace("\n", " | "))
check(any(g in txt for g in ("Excellent", "Good", "Acceptable", "Needs work")), "giudizio in inglese")
check("Multicopter" in txt and "Roll" in win_en.t_pid.diag.html, "titolo e diagnosi in inglese")
keys = [win_en.t_overview.table.item(r, 0).text() for r in range(win_en.t_overview.table.rowCount())]
check("Log duration" in keys and "Raised flags (critical / warnings)" in keys, "riepilogo in inglese")
for i in range(win_en.tabs.count()):
    win_en.tabs.setCurrentIndex(i)
no_errors("schede in inglese")
check(win_en.t_flags.table.item(0, 2).text() == "warning", "gravità dei flag in inglese")
for tab, name in ((win_en.t_overview, "en_panoramica"), (win_en.t_power, "en_potenza"), (win_en.t_flags, "en_flag")):
    tab.panel.fig.set_size_inches(14, 9)
    tab.panel.fig.savefig(out / f"gui_{name}.png", dpi=80)
win_en.t_pid.p_freq.fig.savefig(out / "gui_en_pid_frequenza.png", dpi=80)
qt_stub.QFileDialog.next_save = (str(out / "report_en.pdf"), "")
win_en.export_report()
qt_stub.QFileDialog.next_save = (str(out / "report_en.html"), "")
win_en.export_report()
no_errors("report in inglese")
en_html = (out / "report_en.html").read_text(encoding="utf-8")
check("Evaluation parameters" in en_html and "Parametri di valutazione" not in en_html, "report HTML in inglese")
check(win_en.t_pid.t_info.text().startswith("Closed loop |T|"), "spiegazione di |T| in inglese")
win_en.restart()
check(qt_stub.QProcess.started and qt_stub.QProcess.started[-1][1][:2] == ["-m", "flight_analyzer"], "riavvio dell'app")
i18n.set_language("it")
qt_stub.QSettings.store["lingua"] = "it"
print("\nTUTTO OK")
