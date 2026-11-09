"""Catalogo inglese dell'interfaccia: testo italiano → traduzione.

Generato a partire dai testi marcati con _() e N_(); tests/check_i18n.py controlla che
sia completo e che i segnaposto {nome} coincidano. Per aggiungere una voce basta
scriverla qui con il testo italiano identico a quello del codice.
"""

EN = {
    'Multicottero':
        'Multicopter',
    'Ala fissa':
        'Fixed-wing',
    'Tutto il volo':
        'Whole flight',
    'Velocità angolare (rate)':
        'Angular rate',
    'Assetto':
        'Attitude',
    "in ala fissa l'imbardata non ha un anello d'assetto (coordinazione di virata)":
        'in fixed-wing flight yaw has no attitude loop (turn coordination)',
    'setpoint o misura non presenti nel log':
        'setpoint or measurement missing from the log',
    'setpoint':
        'setpoint',
    'misura':
        'measurement',
    'frequenza di log troppo bassa':
        'logging rate too low',
    "setpoint d'assetto (anello esterno)":
        'attitude setpoint (outer loop)',
    'stima non riuscita':
        'estimation failed',
    'serve il comando di coppia registrato ad almeno 90 Hz':
        'the torque command must be logged at 90 Hz or more',
    'Il log non permette di distinguere volo e terra: analizzato tutto il tratto selezionato.':
        'The log does not allow flight and ground to be told apart: the whole selected interval was analyzed.',
    'Il log contiene più fasi (multicottero/ala fissa): analizzarle insieme mescola controllori diversi.':
        'The log contains more than one phase (multicopter/fixed-wing): analyzing them together mixes different controllers.',
    'Tutti gli assi hanno affidabilità bassa: il punteggio complessivo è solo indicativo.':
        'All axes have low confidence: the overall score is only indicative.',
    'comando':
        'command',
    'strumento':
        'instrument',
    'non assestato entro la finestra di risposta':
        'not settled within the response window',
    "dati troppo brevi per stimare l'incertezza":
        'data too short to estimate the uncertainty',
    'guadagni modificati durante il volo: il risultato mescola tarature diverse':
        'gains changed during the flight: the result mixes different tunings',
    'n.d.':
        'n/a',
    'Nessun problema rilevato su questo asse.':
        'No issues found on this axis.',
    'Gli assi con affidabilità bassa sono esclusi dal punteggio complessivo.':
        'Axes with low confidence are excluded from the overall score.',
    'nessun tratto di volo abbastanza lungo (servono almeno {s:.0f} s continui) nella fase scelta':
        'no flight segment long enough in the selected phase (at least {s:.0f} s of continuous flight are needed)',
    'guadagni del rate controller non presenti nei parametri':
        'rate controller gains not found in the parameters',
    'a {f:.1f} Hz':
        'at {f:.1f} Hz',
    'attraversamento a {f:.1f} Hz':
        'crossover at {f:.1f} Hz',
    'Assestamento lento con poca sovraelongazione: tipico di un integratore lento.':
        'Slow settling with little overshoot: typical of a slow integrator.',
    'Rumore elevato sul comando di coppia sopra 30 Hz: ridurre IMU_DGYRO_CUTOFF, controllare vibrazioni e filtri notch.':
        'High noise on the torque command above 30 Hz: reduce IMU_DGYRO_CUTOFF, check vibrations and notch filters.',
    'Solo {t:.1f} s di volo utile nella fase scelta.':
        'Only {t:.1f} s of usable flight in the selected phase.',
    't salita {tr:.0f} ms, obiettivo {tg:.0f} ms ({nota})':
        'rise time {tr:.0f} ms, target {tg:.0f} ms ({nota})',
    't assestamento {ts:.0f} ms':
        'settling time {ts:.0f} ms',
    'Risposta lenta (salita {tr} contro obiettivo {tg:.0f} ms): {azione}.':
        'Slow response (rise time {tr} vs. target {tg:.0f} ms): {azione}.',
    "verificare l'integratore dell'anello di rate":
        'check the rate loop integrator',
    "verificare FF/I dell'anello di rate":
        'check the rate loop FF/I',
    'Picco di risonanza in anello chiuso di {db:.1f} dB a {f:.1f} Hz: smorzamento insufficiente.':
        'Closed-loop resonance peak of {db:.1f} dB at {f:.1f} Hz: insufficient damping.',
    'Margine di fase {pm:.0f}° sotto il minimo consigliato: rischio di oscillazioni con raffiche o variazioni di massa.':
        'Phase margin of {pm:.0f}° below the recommended minimum: risk of oscillations with gusts or mass changes.',
    "Integratore oltre l'80% del limite per il {v:.1f}% del tempo: possibile sbilanciamento (baricentro, eliche, trim) o limite {lim} troppo basso.":
        'Integrator above 80% of its limit for {v:.1f}% of the time: possible imbalance (center of gravity, propellers, trim) or {lim} limit too low.',
    "Picco stretto nell'errore di tracking a {f:.1f} Hz ({db:.0f} dB sopra il fondo): possibile oscillazione o vibrazione strutturale.":
        'Narrow peak in the tracking error at {f:.1f} Hz ({db:.0f} dB above the noise floor): possible oscillation or structural vibration.',
    "Margini di stabilità non stimabili: {motivo}. Per stimarli servono impulsi brevi e netti sullo stick o l'eccitazione dell'autotune con MC_AT_APPLY = 0.":
        'Stability margins cannot be estimated: {motivo}. Estimating them requires short, sharp stick inputs or the autotune excitation with MC_AT_APPLY = 0.',
    "Parametri del controllore cambiati durante il volo ({nomi}): restringere l'analisi a un intervallo con una sola taratura.":
        'Controller parameters changed during the flight ({nomi}): restrict the analysis to an interval with a single tuning.',
    "nessun tratto in volo nella fase e nell'intervallo scelti":
        'no airborne segment in the selected phase and interval',
    'eccitazione limitata: {s:.0f} s di manovre utili (consigliati ≥ 20 s)':
        'limited excitation: {s:.0f} s of usable maneuvers (≥ 20 s recommended)',
    'eccitazione scarsa: {s:.0f} s di manovre utili (consigliati ≥ 20 s)':
        'poor excitation: {s:.0f} s of usable maneuvers (≥ 20 s recommended)',
    'frequenza di log bassa ({f:.0f} Hz): meno di 4 campioni nel tempo di salita':
        'low logging rate ({f:.0f} Hz): fewer than 4 samples within the rise time',
    'stima dispersa (sovraelongazione ± {s:.0f} punti)':
        'scattered estimate (overshoot ± {s:.0f} points)',
    'Sovraelongazione {ov:.0f}% con margine di fase di {pm:.0f}°: anello poco smorzato. Possibili azioni: ridurre {p} del 10–20%':
        'Overshoot {ov:.0f}% with a phase margin of {pm:.0f}°: poorly damped loop. Possible actions: reduce {p} by 10–20%',
    'aumentare {p}':
        'increase {p}',
    'aumentare {ff} o {p}':
        'increase {ff} or {p}',
    'ridurre {tc}':
        'reduce {tc}',
    'Assestamento lento con poca sovraelongazione: tipico di un integratore lento, valutare {i} più alto.':
        'Slow settling with little overshoot: typical of a slow integrator, consider a higher {i}.',
    'Rumore elevato sul comando di coppia sopra 30 Hz: ridurre {d} o IMU_DGYRO_CUTOFF, controllare vibrazioni e filtri notch.':
        'High noise on the torque command above 30 Hz: reduce {d} or IMU_DGYRO_CUTOFF, check vibrations and notch filters.',
    'il log non contiene volo in modalità {fase}':
        'the log contains no flight in {fase} mode',
    'frequenza di log modesta ({f:.0f} Hz): abilitare il profilo di log ad alta frequenza':
        'moderate logging rate ({f:.0f} Hz): enable the high-rate logging profile',
    'stima moderatamente dispersa (sovraelongazione ± {s:.0f} punti)':
        'moderately scattered estimate (overshoot ± {s:.0f} points)',
    ' oppure aumentare {d}':
        ' or increase {d}',
    'Sovraelongazione {ov:.0f}%: ridurre {ff} (se la risposta anticipa) o {p}.':
        'Overshoot {ov:.0f}%: reduce {ff} (if the response leads the setpoint) or {p}.',
    'aumentare {i}':
        'increase {i}',
    'aumentare {ff} o {i}':
        'increase {ff} or {i}',
    'Sovraelongazione {ov:.0f}%: possibili azioni: aumentare {d} o ridurre {p}.':
        'Overshoot {ov:.0f}%: possible actions: increase {d} or reduce {p}.',
    'Sovraelongazione {ov:.0f}%: possibili azioni: ridurre {p}.':
        'Overshoot {ov:.0f}%: possible action: reduce {p}.',
    "Sovraelongazione dell'assetto {ov:.0f}%: ridurre {p} o verificare prima l'anello di rate.":
        'Attitude overshoot {ov:.0f}%: reduce {p} or check the rate loop first.',
    "Sovraelongazione dell'assetto {ov:.0f}%: aumentare {tc} per una risposta più morbida o verificare l'anello di rate.":
        'Attitude overshoot {ov:.0f}%: increase {tc} for a softer response or check the rate loop.',
    'Panoramica':
        'Overview',
    'Analisi PID':
        'PID analysis',
    'Velocità angolari':
        'Angular rates',
    'Posizione e velocità':
        'Position and velocity',
    'Comandi e spinta':
        'Controls and thrust',
    'Potenza':
        'Power',
    'Motori e servi':
        'Motors and servos',
    'Giri motore':
        'Motor RPM',
    'Vibrazioni e spettri':
        'Vibration and spectra',
    'Sistema':
        'System',
    'Flag':
        'Flags',
    'Parametri':
        'Parameters',
    'Messaggi':
        'Messages',
    'Esplora dati':
        'Data explorer',
    'critico':
        'critical',
    'avviso':
        'warning',
    'informativo':
        'info',
    'Failsafe':
        'Failsafe',
    'Stato del veicolo':
        'Vehicle status',
    'Failure detector':
        'Failure detector',
    'Stimatore (EKF2)':
        'Estimator (EKF2)',
    'Batteria':
        'Battery',
    'Velocità angolare non valida':
        'Angular velocity invalid',
    'Assetto non valido':
        'Attitude invalid',
    'Quota locale non valida':
        'Local altitude invalid',
    'Posizione locale stimata non valida':
        'Local position estimate invalid',
    'Posizione locale non valida anche con requisiti di precisione ridotti':
        'Local position invalid even with relaxed accuracy requirements',
    'Velocità locale stimata non valida':
        'Local velocity estimate invalid',
    'Posizione globale stimata non valida':
        'Global position estimate invalid',
    'Posizione globale non valida anche con requisiti di precisione ridotti':
        'Global position invalid even with relaxed accuracy requirements',
    'Nessuna missione disponibile':
        'No mission available',
    'Segnale offboard perso':
        'Offboard control signal lost',
    'Posizione di home non disponibile':
        'Home position not available',
    'Segnale del radiocomando perso':
        'Manual control (RC) signal lost',
    'Collegamento con la stazione di terra perso':
        'Ground station (GCS) connection lost',
    'Avviso batteria (livello da BatteryStatus)':
        'Battery warning (level from BatteryStatus)',
    'Batteria scarica in base al tempo di volo residuo':
        'Battery low based on the remaining flight time',
    'Batteria non in buono stato':
        'Battery unhealthy',
    'Geofence violato':
        'Geofence breached',
    'Missione fallita':
        'Mission failure',
    'Guasto del sistema ad ala fissa (dopo il quad-chute)':
        'Fixed-wing system failure (after quad-chute)',
    'Limite di vento superato':
        'Wind limit exceeded',
    'Tempo di volo massimo superato':
        'Maximum flight time exceeded',
    'Precisione della posizione sotto soglia (ancora considerata valida)':
        'Position accuracy below threshold (still considered valid)',
    'Il navigatore non è riuscito a eseguire un modo':
        'The navigator failed to execute a mode',
    'Guasto critico: limite di assetto/quota superato o ATS esterno':
        'Critical failure: attitude/altitude limit exceeded or external ATS',
    'Un ESC non si è armato':
        'An ESC failed to arm',
    'Elica sbilanciata rilevata':
        'Imbalanced propeller detected',
    'Guasto motore':
        'Motor failure',
    'Failure detector: limite di rollio superato':
        'Failure detector: roll limit exceeded',
    'Failure detector: limite di beccheggio superato':
        'Failure detector: pitch limit exceeded',
    'Failure detector: limite di quota superato':
        'Failure detector: altitude limit exceeded',
    'Failure detector: segnale di terminazione esterno':
        'Failure detector: external termination signal',
    'Failure detector: ESC non armati':
        'Failure detector: ESCs not armed',
    'Failure detector: guasto batteria':
        'Failure detector: battery failure',
    'Failure detector: elica sbilanciata':
        'Failure detector: imbalanced propeller',
    'Failure detector: guasto motore':
        'Failure detector: motor failure',
    "EKF2: campo magnetico diverso dall'intensità attesa":
        'EKF2: magnetic field strength differs from the expected value',
    'EKF2: magnetometro dichiarato guasto e non più usato':
        'EKF2: magnetometer declared faulty and no longer used',
    'EKF2: telemetro bloccato (nessun valore nuovo per più di 10 s)':
        'EKF2: range finder stuck (no new value for more than 10 s)',
    'EKF2: imbardata da GNSS dichiarata guasta':
        'EKF2: GNSS yaw declared faulty',
    'EKF2: telemetro dichiarato guasto':
        'EKF2: range finder declared faulty',
    'EKF2: navigazione inerziale senza misure che limitino la deriva di velocità':
        'EKF2: inertial dead reckoning (no measurements constraining the velocity drift)',
    'EKF2: navigazione basata solo su misure relative al vento':
        'EKF2: navigation based only on wind-relative measurements',
    'EKF2: imbardata da visione esterna dichiarata guasta':
        'EKF2: external vision yaw declared faulty',
    'EKF2: barometro dichiarato guasto':
        'EKF2: barometer declared faulty',
    'EKF2: misure GNSS (posizione, velocità) dichiarate guaste':
        'EKF2: GNSS measurements (position, velocity) declared faulty',
    'EKF2: quota GNSS dichiarata guasta':
        'EKF2: GNSS height declared faulty',
    "EKF2: protezione dall'effetto suolo sul barometro attiva":
        'EKF2: barometer ground-effect protection active',
    'EKF2: errore numerico nella fusione del magnetometro X':
        'EKF2: numerical error in magnetometer X fusion',
    'EKF2: errore numerico nella fusione del magnetometro Y':
        'EKF2: numerical error in magnetometer Y fusion',
    'EKF2: errore numerico nella fusione del magnetometro Z':
        'EKF2: numerical error in magnetometer Z fusion',
    'EKF2: errore numerico nella fusione della prua':
        'EKF2: numerical error in heading fusion',
    'EKF2: errore numerico nella fusione della declinazione magnetica':
        'EKF2: numerical error in magnetic declination fusion',
    "EKF2: errore numerico nella fusione della velocità all'aria":
        'EKF2: numerical error in airspeed fusion',
    'EKF2: errore numerico nella fusione della derapata sintetica':
        'EKF2: numerical error in synthetic sideslip fusion',
    'EKF2: errore numerico nella fusione del flusso ottico X':
        'EKF2: numerical error in optical flow X fusion',
    'EKF2: errore numerico nella fusione del flusso ottico Y':
        'EKF2: numerical error in optical flow Y fusion',
    "EKF2: dati dell'accelerometro verticale non plausibili":
        'EKF2: implausible vertical accelerometer data',
    "EKF2: saturazione (clipping) dell'accelerometro":
        'EKF2: accelerometer clipping',
    'EKF2: velocità orizzontale scartata dal test di innovazione':
        'EKF2: horizontal velocity rejected by the innovation test',
    'EKF2: velocità verticale scartata dal test di innovazione':
        'EKF2: vertical velocity rejected by the innovation test',
    'EKF2: posizione orizzontale scartata dal test di innovazione':
        'EKF2: horizontal position rejected by the innovation test',
    'EKF2: posizione verticale scartata dal test di innovazione':
        'EKF2: vertical position rejected by the innovation test',
    'EKF2: imbardata scartata dal test di innovazione':
        'EKF2: yaw rejected by the innovation test',
    "EKF2: velocità all'aria scartata dal test di innovazione":
        'EKF2: airspeed rejected by the innovation test',
    'EKF2: derapata sintetica scartata dal test di innovazione':
        'EKF2: synthetic sideslip rejected by the innovation test',
    'EKF2: altezza dal suolo scartata dal test di innovazione':
        'EKF2: height above ground rejected by the innovation test',
    'EKF2: flusso ottico X scartato dal test di innovazione':
        'EKF2: optical flow X rejected by the innovation test',
    'EKF2: flusso ottico Y scartato dal test di innovazione':
        'EKF2: optical flow Y rejected by the innovation test',
    'Failsafe attivo':
        'Failsafe active',
    'Failsafe attivo ma il pilota ha ripreso il controllo':
        'Failsafe active but the pilot took over',
    'Avviso batteria (1 basso, 2 critico, 3 emergenza)':
        'Battery warning (1 low, 2 critical, 3 emergency)',
    'Rotella: zoom · trascina: sposta · doppio clic: tutto il log · Ctrl+rotella: zoom verticale · clic sulla legenda: nascondi curva':
        'Wheel: zoom · drag: pan · double-click: whole log · Ctrl+wheel: vertical zoom · click on the legend: hide curve',
    'Multicottero · rate':
        'Multicopter · rate',
    'Multicottero · assetto':
        'Multicopter · attitude',
    'Ala fissa · rate':
        'Fixed-wing · rate',
    'Ala fissa · assetto':
        'Fixed-wing · attitude',
    'Origine':
        'Source',
    'Gravità':
        'Severity',
    'Prima attivazione [s]':
        'First raised [s]',
    'Attivazioni':
        'Occurrences',
    'Durata totale [s]':
        'Total duration [s]',
    'Descrizione':
        'Description',
    'Fasi VTOL e modi di volo':
        'VTOL phases and flight modes',
    'Solo fasi VTOL':
        'VTOL phases only',
    'Solo modi di volo':
        'Flight modes only',
    'Nessuno':
        'None',
    'Gradi (° e °/s)':
        'Degrees (° and °/s)',
    'Radianti (rad e rad/s)':
        'Radians (rad and rad/s)',
    'Apri un file .ulg (menu File o trascinalo nella finestra)':
        'Open a .ulg file (File menu, or drag it into the window)',
    'Vuoi creare una scorciatoia di Flight Analyzer sul desktop?':
        'Do you want to create a Flight Analyzer shortcut on the desktop?',
    'errore non specificato':
        'unspecified error',
    'Mostra {cosa}':
        'Show {cosa}',
    'Nascondi {cosa}':
        'Hide {cosa}',
    'Salva grafico':
        'Save plot',
    'Immagine PNG (*.png);;Vettoriale SVG (*.svg);;PDF (*.pdf)':
        'PNG image (*.png);;SVG vector image (*.svg);;PDF (*.pdf)',
    'Porta tutti i grafici temporali su una fase o un modo di volo':
        'Move all time plots to a phase or flight mode',
    'Vai a:':
        'Go to:',
    'il riepilogo':
        'the summary',
    "l'elenco dei flag":
        'the flag list',
    'Mostra anche i flag informativi':
        'Also show informational flags',
    'es. MC_ROLLRATE, IMU_, FW_R':
        'e.g. MC_ROLLRATE, IMU_, FW_R',
    'Solo diversi dal default':
        'Only non-default values',
    'Cerca topic o campo…':
        'Search topic or field…',
    'Deseleziona tutto':
        'Deselect all',
    "l'elenco dei topic":
        'the topic list',
    'Tutto il volo nella fase':
        'Whole flight in the selected phase',
    "Solo l'intervallo visibile nei grafici temporali":
        'Only the interval visible in the time plots',
    'Analizza':
        'Analyze',
    'Aggiungi log di confronto…':
        'Add comparison log…',
    'Rimuovi confronti':
        'Remove comparisons',
    'Apri un log per iniziare':
        'Open a log to start',
    'Mostra incertezza':
        'Show uncertainty',
    'Cosa significa «anello chiuso |T|»?':
        'What does “closed loop |T|” mean?',
    'Risposta al gradino':
        'Step response',
    'Risposta in frequenza e robustezza':
        'Frequency response and robustness',
    'Dati usati':
        'Data used',
    'punteggi e diagnosi':
        'scores and diagnosis',
    'Analisi in corso…':
        'Analyzing…',
    'Profilo di valutazione':
        'Evaluation profile',
    'Carica…':
        'Load…',
    'Salva come…':
        'Save as…',
    'Nome del profilo:':
        'Profile name:',
    'Carica profilo':
        'Load profile',
    'Profilo JSON (*.json)':
        'JSON profile (*.json)',
    'Salva profilo':
        'Save profile',
    'Impostazioni':
        'Settings',
    'Lingua:':
        'Language:',
    'Tema:':
        'Theme:',
    "Fase da analizzare all'apertura:":
        'Phase to analyze when a log is opened:',
    "Esegui l'analisi PID appena si apre un log":
        'Run the PID analysis as soon as a log is opened',
    'Generale':
        'General',
    'Angoli e velocità angolari:':
        'Angles and angular rates:',
    'Velocità:':
        'Speed:',
    'metri (m)':
        'meters (m)',
    'piedi (ft)':
        'feet (ft)',
    'Quote e distanze:':
        'Altitudes and distances:',
    'Unità di misura':
        'Units',
    'Sfondo dei grafici:':
        'Plot background:',
    'Spessore delle linee (×):':
        'Line width (×):',
    'Dimensione del testo (×):':
        'Text size (×):',
    'Punti disegnati per curva:':
        'Points drawn per curve:',
    'Clic sulla legenda per nascondere o mostrare una curva':
        'Click on the legend to hide or show a curve',
    'Rotella per lo zoom e trascinamento per spostarsi':
        'Mouse wheel to zoom and drag to pan',
    'Grafici':
        'Plots',
    'Schede':
        'Tabs',
    'HTML (pagina web)':
        'HTML (web page)',
    'Formato predefinito del report:':
        'Default report format:',
    'Includi la risposta in frequenza':
        'Include the frequency response',
    'Includi i parametri di valutazione in fondo al report':
        'Include the evaluation parameters at the end of the report',
    'Esportazione':
        'Export',
    'Responsabile:':
        'Person in charge:',
    'Verificato da:':
        'Checked by:',
    'Scheda di taratura':
        'Tuning sheet',
    'Ripristina predefiniti':
        'Restore defaults',
    '&File':
        '&File',
    'Apri log…':
        'Open log…',
    'Apri recenti':
        'Open recent',
    'Esporta PDF':
        'Export PDF',
    'Crea subito il report PDF accanto al log e lo apre (Ctrl+P)':
        'Create the PDF report next to the log right away and open it (Ctrl+P)',
    'Esporta report…':
        'Export report…',
    'Sceglie dove salvare il report, in PDF o HTML (Ctrl+E)':
        'Choose where to save the report, as PDF or HTML (Ctrl+E)',
    'Esporta risultati JSON…':
        'Export JSON results…',
    'Salva grafico corrente…':
        'Save current plot…',
    'Impostazioni…':
        'Settings…',
    'Esci':
        'Quit',
    '&Analisi':
        '&Analysis',
    'Profilo di valutazione…':
        'Evaluation profile…',
    'Rimuovi log di confronto':
        'Remove comparison logs',
    '&Visualizza':
        '&View',
    'Unità degli angoli':
        'Angle units',
    'Sfondo dei grafici':
        'Plot background',
    'Tema scuro':
        'Dark theme',
    'Nascondi/mostra pannello laterale':
        'Hide/show side panel',
    'Schermo intero':
        'Full screen',
    'A&iuto':
        '&Help',
    'Guida rapida':
        'Quick guide',
    'Informazioni':
        'About',
    'Principale':
        'Main',
    'errore sconosciuto':
        'unknown error',
    'Errore':
        'Error',
    'Apri log di volo':
        'Open flight log',
    'Log PX4 (*.ulg);;Tutti i file (*)':
        'PX4 logs (*.ulg);;All files (*)',
    'Log di confronto':
        'Comparison logs',
    'Log PX4 (*.ulg)':
        'PX4 logs (*.ulg)',
    'Report pronto':
        'Report ready',
    'Report PDF (*.pdf)':
        'PDF report (*.pdf)',
    'Pagina HTML (*.html)':
        'HTML page (*.html)',
    'Esporta report':
        'Export report',
    'Esporta risultati':
        'Export results',
    'Desktop non disponibile':
        'Desktop not available',
    'Non è stato possibile individuare la cartella Desktop.':
        'The Desktop folder could not be found.',
    'Adatta Y':
        'Fit Y',
    "Riadatta l'asse verticale ai dati visibili (tasto A)":
        'Fit the vertical axis to the visible data (A key)',
    'Tutto il log':
        'Whole log',
    "Mostra l'intero log (doppio clic o tasto Home)":
        'Show the whole log (double-click or Home key)',
    'Voce':
        'Item',
    'Valore':
        'Value',
    'Riepilogo del volo':
        'Flight summary',
    'Doppio clic su un flag per portare i grafici sulla sua prima attivazione.':
        'Double-click a flag to move the plots to its first occurrence.',
    'Nessun flag sollevato':
        'No flags raised',
    'Filtro:':
        'Filter:',
    'Parametro':
        'Parameter',
    'Default':
        'Default',
    'Modificato in volo':
        'Changed in flight',
    'Tempo [s]':
        'Time [s]',
    'Livello':
        'Level',
    'Messaggio':
        'Message',
    "Doppio clic su un messaggio per centrare i grafici temporali su quell'istante.":
        'Double-click a message to center the time plots on that instant.',
    'PARAMETRO':
        'PARAMETER',
    'Topic / campo':
        'Topic / field',
    'Campioni':
        'Samples',
    'Topic e campi':
        'Topics and fields',
    'Fase:':
        'Phase:',
    'Anello:':
        'Loop:',
    'Intervallo:':
        'Interval:',
    'Asse / metrica':
        'Axis / metric',
    'Punti':
        'Points',
    'Soglie 100/60/0':
        'Thresholds 100/60/0',
    'Peso':
        'Weight',
    'Diagnosi e indicazioni':
        'Diagnosis and suggestions',
    'Asse per frequenza e dati:':
        'Axis for frequency and data:',
    'Nessuna analisi':
        'No analysis',
    'Analisi dei controllori…':
        'Analyzing the controllers…',
    'Eccitazione minima (picco-picco in 1 s, rad o rad/s):':
        'Minimum excitation (peak-to-peak within 1 s, rad or rad/s):',
    'Profilo personalizzato':
        'Custom profile',
    "Il cambio di lingua si applica al riavvio dell'app.":
        'The language change takes effect when the app is restarted.',
    'Chiaro':
        'Light',
    'Scuro':
        'Dark',
    'Come il sistema':
        'Same as the system',
    'Automatica (la fase più lunga)':
        'Automatic (the longest phase)',
    'Crea scorciatoia sul desktop':
        'Create desktop shortcut',
    'Desktop:':
        'Desktop:',
    'metri al secondo (m/s)':
        'meters per second (m/s)',
    'chilometri orari (km/h)':
        'kilometers per hour (km/h)',
    'nodi (kn)':
        'knots (kn)',
    'Le grandezze della valutazione PID restano nelle unità della scala di valutazione (%, s, dB, gradi di fase).':
        'The PID evaluation quantities stay in the units of the evaluation scale (%, s, dB, degrees of phase).',
    'Più punti = più dettaglio ma grafici più lenti; con lo zoom il dettaglio aumenta comunque.':
        'More points = more detail but slower plots; zooming in shows more detail anyway.',
    'Schede da mostrare nella finestra principale:':
        'Tabs to show in the main window:',
    'Nomi usati per precompilare la scheda di taratura.':
        'Names used to prefill the tuning sheet.',
    'Scorciatoia creata sul desktop.':
        'Shortcut created on the desktop.',
    'Vibrazioni nel tempo':
        'Vibration over time',
    'Densità spettrale di potenza nel tempo (come Flight Review)':
        'Power spectral density over time (as in Flight Review)',
    'La nuova lingua si applica al riavvio. Riavviare ora?':
        'The new language takes effect after a restart. Restart now?',
    'Elaborazione…':
        'Processing…',
    'Attenzione: il file contiene parti corrotte o troncate':
        'Warning: the file contains corrupted or truncated parts',
    'Lettura dei log di confronto…':
        'Reading the comparison logs…',
    'Creazione del report PDF…':
        'Creating the PDF report…',
    'Creazione del report…':
        'Creating the report…',
    'Esportazione…':
        'Exporting…',
    '(nessuno)':
        '(none)',
    'Impossibile creare la scorciatoia: {dettaglio}':
        'Unable to create the shortcut: {dettaglio}',
    'Vista:':
        'View:',
    'Log':
        'Log',
    'Totale':
        'Total',
    'Metrica':
        'Metric',
    'Ottimo (100)':
        'Excellent (100)',
    'Accettabile (60)':
        'Acceptable (60)',
    'Da rivedere (0)':
        'Needs work (0)',
    'Valore non valido':
        'Invalid value',
    'Scorciatoia non creata':
        'Shortcut not created',
    'Come leggere i punteggi':
        'How to read the scores',
    "Per ogni asse l'app stima dai dati di volo la risposta al gradino dell'anello scelto (rate o assetto) e la confronta con soglie fisse: sovraelongazione, tempo di salita rispetto a un obiettivo, assestamento, errore a regime, picco di risonanza e, per il rate multicottero, il margine di fase calcolato dal guadagno d'anello. Ogni metrica vale 100 punti alla soglia ottima, 60 a quella accettabile e 0 a quella da rivedere.":
        'For each axis the app estimates, from the flight data, the step response of the selected loop (rate or attitude) and compares it with fixed thresholds: overshoot, rise time relative to a target, settling, steady-state error, resonance peak and, for the multicopter rate loop, the phase margin computed from the loop gain. Each metric is worth 100 points at the excellent threshold, 60 at the acceptable one and 0 at the needs-work one.',
    "Affidabilità: alta, media o bassa a seconda di quanta eccitazione c'è nel volo, della frequenza di log e della dispersione della stima (jackknife a blocchi). Gli assi ad affidabilità bassa non entrano nel totale.":
        'Confidence: high, medium or low depending on how much excitation the flight contains, on the logging rate and on the scatter of the estimate (block jackknife). Axes with low confidence are not included in the total.',
    "Per confrontare due tarature usa lo stesso profilo e manovre simili; aggiungi l'altro log con «Aggiungi log di confronto…».":
        'To compare two tunings, use the same profile and similar maneuvers; add the other log with “Add comparison log…”.',
    'Navigare nei grafici':
        'Navigating the plots',
    'Rotella: zoom sul tempo attorno al mouse; Ctrl+rotella: zoom verticale; Maiusc+rotella: scorrimento.':
        'Wheel: time zoom around the mouse; Ctrl+wheel: vertical zoom; Shift+wheel: scroll.',
    'Trascinamento con il tasto sinistro: spostamento nel tempo; doppio clic: tutto il log.':
        'Left-button drag: pan in time; double-click: whole log.',
    "Tastiera, dopo un clic sul grafico: frecce per scorrere, + e − per lo zoom, Home per tutto il log, A per riadattare l'asse verticale.":
        'Keyboard, after clicking on the plot: arrows to scroll, + and − to zoom, Home for the whole log, A to refit the vertical axis.',
    'Menu «Vai a»: porta tutti i grafici su una fase VTOL, un modo di volo o il tratto in volo.':
        '“Go to” menu: moves all plots to a VTOL phase, a flight mode or the airborne segment.',
    'Clic su una voce di legenda: nasconde o mostra quella curva.':
        'Click on a legend entry: hides or shows that curve.',
    '◀ / ▶ (o Ctrl+B) nasconde il pannello laterale per allargare i grafici; F11 schermo intero.':
        '◀ / ▶ (or Ctrl+B) hides the side panel to enlarge the plots; F11 full screen.',
    'Volo di prova consigliato':
        'Recommended test flight',
    'Parametro SDLOG_PROFILE con il bit «High rate» (es. 17 = default + alta frequenza).':
        'SDLOG_PROFILE parameter with the “High rate” bit set (e.g. 17 = default + high rate).',
    'Per ogni asse almeno 20–30 s di impulsi brevi e netti sullo stick, alternati a pause, in Stabilized o Acro.':
        'For each axis, at least 20–30 s of short, sharp stick inputs alternated with pauses, in Stabilized or Acro.',
    'Per stimare i margini di stabilità: autotune PX4 con MC_AT_APPLY = 0 (solo registrazione, i guadagni non vengono cambiati), avviato in Position/Hold.':
        'To estimate the stability margins: PX4 autotune with MC_AT_APPLY = 0 (logging only, the gains are not changed), started in Position/Hold.',
    'Non cambiare i guadagni durante il volo analizzato.':
        'Do not change the gains during the analyzed flight.',
    'Spettro: ':
        'Spectrum: ',
    'Guida':
        'Guide',
    'Analisi dei log PX4 (.ulg) e valutazione oggettiva dei controllori.':
        'PX4 log (.ulg) analysis and objective controller evaluation.',
    'Team Zefiro — reparto di Meccanica del volo':
        'Team Zefiro — Flight Mechanics division',
    'Lettore ULog interno, grafici matplotlib, interfaccia PySide6.':
        'Built-in ULog reader, matplotlib plots, PySide6 interface.',
    'Report salvato in:\n{p}\n\nAprirlo ora?':
        'Report saved to:\n{p}\n\nOpen it now?',
    'attivo per tutto il log':
        'active for the whole log',
    '{n} flag, di cui {c} critici':
        '{n} flags, {c} of them critical',
    'Grafici temporali centrati su t = {t:.1f} s':
        'Time plots centered on t = {t:.1f} s',
    '{v} a {t:.1f} s':
        '{v} at {t:.1f} s',
    '{n} parametri; {d} diversi dal default':
        '{n} parameters; {d} differ from the default',
    '{n} parametri (il log non contiene i valori di default)':
        '{n} parameters (the log does not contain the default values)',
    'affidabilità':
        'confidence',
    '{s:.0f} s analizzati':
        '{s:.0f} s analyzed',
    'Confronto con: {nomi}':
        'Compared with: {nomi}',
    'Profilo non valido':
        'Invalid profile',
    'Profilo «{nome}» attivo':
        'Profile “{nome}” active',
    'Lettura di {nome}…':
        'Reading {nome}…',
    "Intervallo per l'analisi PID: {a:.1f}–{b:.1f} s (premi Analizza)":
        'Interval for the PID analysis: {a:.1f}–{b:.1f} s (press Analyze)',
    'Non è stato possibile creare la scorciatoia sul desktop.':
        'The desktop shortcut could not be created.',
    'Obiettivo tempo di salita, {asse} [s]:':
        'Rise-time target, {asse} [s]:',
    'Risultati salvati in {p}':
        'Results saved to {p}',
    'Segnali':
        'Signals',
    '{metrica}: le tre soglie devono essere diverse':
        '{metrica}: the three thresholds must be different',
    '{metrica}: le soglie devono essere in ordine monotono':
        '{metrica}: the thresholds must be in monotonic order',
    'Affidabilità':
        'Confidence',
    '{metrica}: «{testo}» non è un numero':
        '{metrica}: “{testo}” is not a number',
    'Obiettivo del tempo di salita non valido: «{testo}»':
        'Invalid rise-time target: “{testo}”',
    'Transizione':
        'Transition',
    'Altro':
        'Other',
    'waypoint':
        'waypoint',
    'loiter':
        'loiter',
    'loiter a giri':
        'loiter (turns)',
    'loiter a tempo':
        'loiter (time)',
    'ritorno':
        'return',
    'atterraggio':
        'landing',
    'decollo':
        'takeoff',
    'loiter a quota':
        'loiter to altitude',
    'decollo VTOL':
        'VTOL takeoff',
    'atterraggio VTOL':
        'VTOL landing',
    'attesa':
        'delay',
    'cambio velocità':
        'speed change',
    'transizione VTOL':
        'VTOL transition',
    'File':
        'File',
    'Durata log':
        'Log duration',
    'Tempo in volo':
        'Flight time',
    'Versione PX4':
        'PX4 version',
    'Hardware':
        'Hardware',
    'Tipo veicolo':
        'Vehicle type',
    'Messaggi errore / avviso':
        'Error / warning messages',
    'Flag sollevati (critici / avvisi)':
        'Raised flags (critical / warnings)',
    'Dropout del logger':
        'Logger dropouts',
    'nessuno':
        'none',
    'Airframe (SYS_AUTOSTART)':
        'Airframe (SYS_AUTOSTART)',
    'Profilo di log (SDLOG_PROFILE)':
        'Logging profile (SDLOG_PROFILE)',
    'Frequenza log velocità angolare / setpoint':
        'Angular rate / setpoint logging rate',
    'Quota max relativa':
        'Max relative altitude',
    'Velocità orizzontale max':
        'Max horizontal speed',
    "Velocità all'aria max (IAS)":
        'Max airspeed (IAS)',
    'Batteria: corrente max':
        'Battery: max current',
    'Batteria: consumo':
        'Battery: consumption',
    'Vibrazioni accel. (max)':
        'Accel. vibration (max)',
    'Integrità file':
        'File integrity',
    'parti del file corrotte o troncate':
        'parts of the file are corrupted or truncated',
    '(alta frequenza attiva)':
        '(high rate enabled)',
    '(senza alta frequenza)':
        '(without high rate)',
    'Distanza percorsa':
        'Distance traveled',
    'Batteria: tensione min / max':
        'Battery: min / max voltage',
    'Potenza elettrica max':
        'Max electrical power',
    '{n} (totale {s:.2f} s)':
        '{n} (total {s:.2f} s)',
    'Tempo in volo — {fase}':
        'Flight time — {fase}',
    "stima a variabili strumentali (setpoint dell'anello esterno come riferimento)":
        'instrumental-variable estimate (outer-loop setpoint as reference)',
    "dati insufficienti per stimare l'incertezza (servono almeno 3 blocchi)":
        'not enough data to estimate the uncertainty (at least 3 blocks are needed)',
    "il guadagno d'anello resta sopra 1 in tutta la banda stimata":
        'the loop gain stays above 1 over the whole estimated band',
    "il guadagno d'anello è sotto 1 già all'inizio della banda stimata":
        'the loop gain is already below 1 at the start of the estimated band',
    'comando di coppia non disponibile nel log':
        'torque command not available in the log',
    "eccitazione insufficiente alle frequenze dell'anello: impianto non identificabile":
        'insufficient excitation at the loop frequencies: the plant cannot be identified',
    'banda identificata troppo stretta':
        'identified band too narrow',
    'banda stimata solo fino a {f:.0f} Hz: Ms potrebbe essere sottostimato':
        'band estimated only up to {f:.0f} Hz: Ms may be underestimated',
    "Anello chiuso |T|: per ogni frequenza indica quanta parte di una variazione del setpoint arriva sulla misura. 0 dB (|T| = 1) significa che l'asse segue il comando perfettamente; −3 dB segna la banda passante, cioè fino a che frequenza il drone segue i comandi; un picco sopra 0 dB indica poco smorzamento (sovraelongazione, oscillazioni). La fase dice con quanto ritardo segue: −90° alla frequenza f equivalgono a un ritardo di 1/(4f). Il guadagno d'anello L = C·P (terzo grafico) è invece l'anello aperto, da cui si ricavano margini e sensitività.":
        'Closed loop |T|: at each frequency it shows how much of a setpoint change reaches the measurement. 0 dB (|T| = 1) means that the axis follows the command perfectly; −3 dB marks the bandwidth, i.e. the highest frequency at which the drone still follows the commands; a peak above 0 dB indicates low damping (overshoot, oscillations). The phase tells how late the response is: −90° at frequency f corresponds to a delay of 1/(4f). The loop gain L = C·P (third plot) is instead the open loop, from which margins and sensitivity are derived.',
    'Rollio':
        'Roll',
    'Beccheggio':
        'Pitch',
    'Imbardata':
        'Yaw',
    'alettone sx':
        'left aileron',
    'alettone dx':
        'right aileron',
    'equilibratore':
        'elevator',
    'timone':
        'rudder',
    'elevone sx':
        'left elevon',
    'elevone dx':
        'right elevon',
    'coda a V sx':
        'left V-tail',
    'coda a V dx':
        'right V-tail',
    'flap sx':
        'left flap',
    'flap dx':
        'right flap',
    'aerofreno':
        'airbrake',
    'personalizzata':
        'custom',
    'coda ad A sx':
        'left A-tail',
    'coda ad A dx':
        'right A-tail',
    'alettone canale unico':
        'single-channel aileron',
    'ruotino':
        'steering wheel',
    'spoiler sx':
        'left spoiler',
    'spoiler dx':
        'right spoiler',
    'Giri motore (esc_status)':
        'Motor RPM (esc_status)',
    'Giroscopio (velocità angolare filtrata)':
        'Gyroscope (filtered angular rate)',
    'Giroscopio grezzo (sensor_combined)':
        'Raw gyroscope (sensor_combined)',
    'Accelerometro (sensor_combined)':
        'Accelerometer (sensor_combined)',
    'Coppia richiesta (vehicle_torque_setpoint)':
        'Requested torque (vehicle_torque_setpoint)',
    'Posizione locale (NED)':
        'Local position (NED)',
    'Velocità locale (NED)':
        'Local velocity (NED)',
    'Quota':
        'Altitude',
    'Accelerazione grezza (sensor_combined)':
        'Raw acceleration (sensor_combined)',
    "Metrica di vibrazione dell'accelerometro (verde < 0,5 g, arancio < 1 g, rosso oltre)":
        'Accelerometer vibration metric (green < 0.5 g, orange < 1 g, red above)',
    'Metrica di vibrazione del giroscopio':
        'Gyroscope vibration metric',
    "Densità spettrale dell'accelerazione":
        'Acceleration power spectral density',
    'Densità spettrale della velocità angolare':
        'Angular velocity power spectral density',
    "Densità spettrale dell'accelerazione angolare":
        'Angular acceleration power spectral density',
    'Frequenza [Hz]':
        'Frequency [Hz]',
    'PSD [unità²/Hz]':
        'PSD [units²/Hz]',
    'Spettrogramma (asse z)':
        'Spectrogram (z axis)',
    "Tempo dall'inizio del log [s]":
        'Time since log start [s]',
    'Carico CPU e RAM':
        'CPU and RAM load',
    'Comandi del pilota (manual_control_setpoint)':
        'Pilot inputs (manual_control_setpoint)',
    'Flag sollevati nel tempo':
        'Raised flags over time',
    "Traccia (vista dall'alto) e profilo di missione":
        'Track (top view) and mission profile',
    'Quota, fasi VTOL (sfondo) e modi di volo (striscia in alto)':
        'Altitude, VTOL phases (background) and flight modes (top strip)',
    'Velocità':
        'Speed',
    'transizione':
        'transition',
    'Anello chiuso |T| = misura / setpoint':
        'Closed loop |T| = measurement / setpoint',
    'Fase di T (ritardo della risposta)':
        'Phase of T (response delay)',
    'quota stimata (-z)':
        'estimated altitude (-z)',
    'ground truth':
        'ground truth',
    "Velocità all'aria":
        'Airspeed',
    'Il log non contiene coppia e spinta richieste (vehicle_torque_setpoint).':
        'The log does not contain the requested torque and thrust (vehicle_torque_setpoint).',
    'Il log non contiene dati di potenza (battery_status, esc_status, actuator_motors).':
        'The log does not contain power data (battery_status, esc_status, actuator_motors).',
    'Il log non contiene uscite di motori o servi.':
        'The log does not contain motor or servo outputs.',
    'Il log non contiene giri motore (esc_status o rpm).\nServono ESC con telemetria (DShot, UAVCAN) o un sensore di giri.':
        'The log does not contain motor RPM (esc_status or rpm).\nESCs with telemetry (DShot, UAVCAN) or an RPM sensor are needed.',
    'in SITL Gazebo Classic PX4 li calcola dal comando (comando × 6000), non sono misurati':
        'in Gazebo Classic SITL, PX4 computes them from the command (command × 6000): they are not measured',
    'Temperatura degli ESC':
        'ESC temperature',
    'Spettrogrammi non disponibili: servono accelerometro o giroscopio registrati ad almeno 100 Hz (SDLOG_PROFILE con alta frequenza).':
        'Spectrograms not available: the accelerometer or gyroscope must be logged at 100 Hz or more (SDLOG_PROFILE with high rate).',
    'Segnale non presente o registrato a frequenza troppo bassa':
        'Signal missing or logged at too low a rate',
    'Est [m]':
        'East [m]',
    'Nord [m]':
        'North [m]',
    'Posizione locale non registrata':
        'Local position not logged',
    'percorso pianificato':
        'planned path',
    'Tempo [ms]':
        'Time [ms]',
    'Risposta in frequenza non disponibile':
        'Frequency response not available',
    '−3 dB (banda passante)':
        '−3 dB (bandwidth)',
    'Robustezza (L = C·P stimato)':
        'Robustness (estimated L = C·P)',
    'tratti analizzati':
        'analyzed segments',
    'Comando di coppia':
        'Torque command',
    "Seleziona uno o più campi nell'elenco a sinistra":
        'Select one or more fields in the list on the left',
    'misurata (filtrata)':
        'measured (filtered)',
    'setpoint TECS':
        'TECS setpoint',
    'Spinta totale richiesta (norma del vettore, 1 = spinta massima)':
        'Total requested thrust (vector norm, 1 = maximum thrust)',
    'Comandi — istanza multicottero [0]: coppia e spinta normalizzate (±1 = massimo)':
        'Controls — multicopter instance [0]: normalized torque and thrust (±1 = maximum)',
    'Comandi — istanza ala fissa [1] (VTOL in ala fissa)':
        'Controls — fixed-wing instance [1] (VTOL in fixed-wing flight)',
    'rollio':
        'roll',
    'beccheggio':
        'pitch',
    'imbardata':
        'yaw',
    'Batteria (come «Power» di Flight Review)':
        'Battery (like the Flight Review “Power” plot)',
    'valori misti':
        'mixed values',
    'Potenza elettrica = tensione × corrente [W]':
        'Electrical power = voltage × current [W]',
    'Uscite motori (actuator_motors) — comando 0…1, 1 = spinta massima del motore':
        'Motor outputs (actuator_motors) — command 0…1, 1 = maximum motor thrust',
    'Densità spettrale di potenza':
        'Power spectral density',
    'solo in volo':
        'airborne only',
    'Nessun flag sollevato in questo volo.':
        'No flags raised in this flight.',
    'Il log non contiene i topic dei flag (failsafe_flags, estimator_status_flags).':
        'The log does not contain the flag topics (failsafe_flags, estimator_status_flags).',
    'inizio':
        'start',
    'fine':
        'end',
    'quota (-z)':
        'altitude (-z)',
    'quota del waypoint attivo':
        'active waypoint altitude',
    'velocità al suolo':
        'ground speed',
    "velocità all'aria (IAS)":
        'airspeed (IAS)',
    'setpoint di posizione':
        'position setpoint',
    'Risposta al gradino unitario':
        'Unit step response',
    'stima':
        'estimate',
    'stima incerta (>20%)':
        'uncertain estimate (>20%)',
    "|L| guadagno d'anello":
        '|L| loop gain',
    '|S| sensitività':
        '|S| sensitivity',
    'integratore':
        'integrator',
    'In volo':
        'Airborne',
    'stimato':
        'estimated',
    'Velocità angolare':
        'Angular rate',
    'spinta':
        'thrust',
    'tensione [V]':
        'voltage [V]',
    'corrente [A]':
        'current [A]',
    'superficie':
        'surface',
    'Uscite servi (actuator_servos) — comando −1…1, ±1 = fine corsa':
        'Servo outputs (actuator_servos) — command −1…1, ±1 = end of travel',
    'somma dei tre assi':
        'sum of the three axes',
    'non disponibile':
        'not available',
    "spinta verso l'alto (−z)":
        'upward thrust (−z)',
    'spinta in avanti (x)':
        'forward thrust (x)',
    'consumo [mAh/100]':
        'discharged [mAh/100]',
    'carica residua [0 = vuota, 10 = piena]':
        'remaining charge [0 = empty, 10 = full]',
    'stima tensione a vuoto [V]':
        'estimated open-circuit voltage [V]',
    'in SITL le correnti degli ESC sono simulate da PX4, non misurate':
        'in SITL the ESC currents are simulated by PX4, not measured',
    "Angolo dei tilt — da CA_SV_TL*_MINA/MAXA, 0° = rotore verso l'alto":
        'Tilt angle — from CA_SV_TL*_MINA/MAXA, 0° = rotor pointing up',
    'sensore di giri':
        'RPM sensor',
    'incertezza (±2σ)':
        'uncertainty (±2σ)',
    'obiettivo t salita':
        'rise-time target',
    'non valutabile':
        'not assessable',
    'a':
        'at',
    'Margini non validi:':
        'Invalid margins:',
    'grafico':
        'plot',
    'Modo':
        'Mode',
    'batteria':
        'battery',
    'Potenza applicata dagli ESC [%] (esc_power)':
        'Power applied by the ESCs [%] (esc_power)',
    'Potenza ai motori: comando di ogni motore in % del massimo (actuator_motors)':
        'Motor power: command of each motor in % of the maximum (actuator_motors)',
    'Alimentazioni di bordo':
        'Onboard power rails',
    'uscita':
        'output',
    'confronto':
        'comparison',
    'modo':
        'mode',
    'Motore':
        'Motor',
    "Uscite ({name}) — valore inviato all'uscita (PWM in µs o valore del simulatore)":
        'Outputs ({name}) — value sent to the output (PWM in µs or simulator value)',
    'Servo':
        'Servo',
    'Uscita':
        'Output',
    "Punti per metrica: 100 alla soglia «ottimo», 60 alla soglia «accettabile», 0 alla soglia «da rivedere», con interpolazione lineare; oltre l'ultima soglia 0 punti.":
        'Points per metric: 100 at the “excellent” threshold, 60 at the “acceptable” threshold, 0 at the “needs work” threshold, with linear interpolation; beyond the last threshold, 0 points.',
    "Punteggio dell'asse: media pesata dei punti delle metriche disponibili; serve almeno metà del peso totale, altrimenti l'asse è «non valutabile».":
        'Axis score: weighted mean of the points of the available metrics; at least half of the total weight is required, otherwise the axis is “not assessable”.',
    "Punteggio dell'anello: rollio 0,4, beccheggio 0,4, imbardata 0,2; gli assi con affidabilità bassa sono esclusi.":
        'Loop score: roll 0.4, pitch 0.4, yaw 0.2; axes with low confidence are excluded.',
    'Giudizio: ottimo ≥ 85, buono ≥ 70, accettabile ≥ 55, altrimenti da rivedere.':
        'Rating: excellent ≥ 85, good ≥ 70, acceptable ≥ 55, otherwise needs work.',
    "Obiettivo del tempo di salita automatico: MC_AT_RISE_TIME per il rate multicottero (doppio per l'imbardata), 2,2/MC_ROLL_P (o PITCH/YAW) per l'assetto multicottero, 2,2·FW_R_TC per l'assetto ad ala fissa e 2,2·FW_R_TC/4 per il rate ad ala fissa.":
        'Automatic rise-time target: MC_AT_RISE_TIME for the multicopter rate loop (doubled for yaw), 2.2/MC_ROLL_P (or PITCH/YAW) for the multicopter attitude loop, 2.2·FW_R_TC for the fixed-wing attitude loop and 2.2·FW_R_TC/4 for the fixed-wing rate loop.',
    'Identificazione':
        'Identification',
    'Robustezza':
        'Robustness',
    "Per l'anello di rate multicottero, dal rapporto tra le risposte setpoint→misura e setpoint→comando si ottiene l'impianto P(f); con il controllore PX4 ricostruito dai parametri (P, I, D, K, IMU_DGYRO_CUTOFF) si calcolano il guadagno d'anello L = C·P, il margine di fase, il margine di guadagno e il picco di sensitività Ms. Serve eccitazione fino a circa due volte la frequenza di attraversamento.":
        'For the multicopter rate loop, the ratio between the setpoint→measurement and setpoint→command responses gives the plant P(f); with the PX4 controller rebuilt from the parameters (P, I, D, K, IMU_DGYRO_CUTOFF), the loop gain L = C·P, the phase margin, the gain margin and the sensitivity peak Ms are computed. Excitation up to about twice the crossover frequency is needed.',
    'Valutazione dei controllori':
        'Controller evaluation',
    'Metodo':
        'Method',
    'Il log non contiene tratti di volo analizzabili.':
        'The log contains no flight segments that can be analyzed.',
    'Punteggio 0–100: ottimo ≥ 85, buono ≥ 70, accettabile ≥ 55. Tra parentesi l’affidabilità della stima; gli assi ad affidabilità bassa non entrano nel punteggio complessivo.':
        'Score 0–100: excellent ≥ 85, good ≥ 70, acceptable ≥ 55. The confidence of the estimate is shown in brackets; axes with low confidence are not included in the overall score.',
    'Parametri di valutazione':
        'Evaluation parameters',
    'Analisi del volo':
        'Flight analysis',
    'profilo di valutazione':
        'evaluation profile',
    'Tempo usato':
        'Time used',
    'Soglie 100 / 60 / 0':
        'Thresholds 100 / 60 / 0',
    'Note':
        'Notes',
    'Pagina {n}':
        'Page {n}',
    'automatico':
        'automatic',
    'Profilo':
        'Profile',
    'Generato il {data} con Flight Analyzer {ver}':
        'Generated on {data} with Flight Analyzer {ver}',
    'Anello':
        'Loop',
    'Punteggio':
        'Score',
    'Giudizio':
        'Rating',
    '100 punti':
        '100 points',
    '60 punti':
        '60 points',
    '0 punti':
        '0 points',
    'Obiettivo del tempo di salita':
        'Rise-time target',
    'eccitazione minima':
        'minimum excitation',
    'Multicottero — anello di velocità angolare (rate)':
        'Multicopter — angular rate loop',
    'Multicottero — anello di assetto':
        'Multicopter — attitude loop',
    'Ala fissa — anello di velocità angolare (rate)':
        'Fixed-wing — angular rate loop',
    'Ala fissa — anello di assetto':
        'Fixed-wing — attitude loop',
    'PX4 standard (predefinito)':
        'PX4 standard (default)',
    'Ottimo':
        'Excellent',
    'Buono':
        'Good',
    'Accettabile':
        'Acceptable',
    'Da rivedere':
        'Needs work',
    'Non valutabile':
        'Not assessable',
    'alta':
        'high',
    'media':
        'medium',
    'bassa':
        'low',
    'Sovraelongazione':
        'Overshoot',
    'Tempo di salita / obiettivo':
        'Rise time / target',
    'Tempo di assestamento (5%) / obiettivo di salita':
        'Settling time (5%) / rise-time target',
    'Margine di fase':
        'Phase margin',
    'Picco di risonanza in anello chiuso':
        'Closed-loop resonance peak',
    'Rumore sul comando (> 30 Hz, RMS)':
        'Command noise (> 30 Hz, RMS)',
    "Tempo con integratore oltre l'80% del limite":
        'Time with the integrator above 80% of its limit',
    'impostato nel profilo':
        'set in the profile',
    'MC_AT_RISE_TIME predefinito':
        'default MC_AT_RISE_TIME',
    'oltre la finestra':
        'beyond the window',
    '2,2 × {par} / 4 (anello interno 4 volte più veloce)':
        '2.2 × {par} / 4 (inner loop 4 times faster)',
    '2,2 / {par} (risposta ideale del 1° ordine)':
        '2.2 / {par} (ideal first-order response)',
    '2,2 × {par} (risposta ideale del 1° ordine)':
        '2.2 × {par} (ideal first-order response)',
    '2 × {src} (imbardata più lenta)':
        '2 × {src} (slower yaw)',
    '2 × 2,2 × {par} (euristica)':
        '2 × 2.2 × {par} (heuristic)',
    'EMERGENZA':
        'EMERGENCY',
    'ALLARME':
        'ALERT',
    'CRITICO':
        'CRITICAL',
    'ERRORE':
        'ERROR',
    'AVVISO':
        'WARNING',
    'NOTA':
        'NOTICE',
    'INFO':
        'INFO',
    'DEBUG':
        'DEBUG',
    'dimensione array non valida':
        'invalid array size',
    'Il file non è un log ULog valido (intestazione non riconosciuta).':
        'The file is not a valid ULog log (unrecognized header).',
    'Il log usa flag incompatibili sconosciuti: impossibile leggerlo.':
        'The log uses unknown incompatible flags: it cannot be read.',
    'annidamento dei formati troppo profondo':
        'format nesting too deep',
    'Team Zefiro — Meccanica del volo':
        'Team Zefiro — Flight Mechanics',
    'Confronto tra i log (caso peggiore dei gradini validi, entrambi i versi)':
        'Comparison between logs (worst case of the valid steps, both directions)',
    'Nessun gradino trovato nei log.':
        'No steps found in the logs.',
    'asse':
        'axis',
    'validi +/−':
        'valid +/−',
    'ritardo':
        'delay',
    'sovr.%':
        'ovsh.%',
    'assest.':
        'settl.',
    'errore':
        'error',
    'rimb.':
        'bnc.',
    'sat.%':
        'sat.%',
    'esito':
        'result',
    'n.ass.':
        'n.sett.',
    'tarato':
        'tuned',
    'non tarato':
        'not tuned',
    '{n} gradini trovati, {v} validi':
        '{n} steps found, {v} valid',
    '{n} PNG dei singoli gradini in {cartella}':
        '{n} PNGs of the single steps in {cartella}',
    'al minimo':
        'at minimum',
    'al massimo':
        'at maximum',
    'nelle finestre dei gradini validi':
        'in the windows of the valid steps',
    'su tutto il tratto analizzato':
        'over the whole analyzed span',
    'Stima poco affidabile: le indicazioni che seguono vanno confermate con le prove a gradino.':
        'Low-confidence estimate: confirm the hints below with the step tests.',
    'gradino stimato di {a:g} {u} per {d:g} s':
        'estimated step of {a:g} {u} for {d:g} s',
    'volare {n} doppietti a {a:g} {u}, partendo in piano e da fermo':
        'fly {n} doublets at {a:g} {u}, starting level and at rest',
    ', ma la sovraelongazione è già oltre il criterio: prima ridurla':
        ', but the overshoot is already beyond the criterion: reduce it first',
    'Non assestato entro la fine del gradino':
        'Not settled by the end of the step',
    'Tutte le grandezze della risposta stimata rispettano i criteri della scheda.':
        'All quantities of the estimated response meet the tuning-sheet criteria.',
    'non assestato entro la fine del gradino (fascia {f})':
        'not settled by the end of the step (band {f})',
    'fascia {f} del comando':
        'band {f} of the command',
    'livello a fine gradino {v:.0f}% del comando':
        'level at the end of the step {v:.0f}% of the command',
    '{p} gradini validi nel verso + e {n} nel verso − (ne servono {k} per verso): {cosa}':
        '{p} valid steps in the + direction and {n} in the − direction ({k} per direction needed): {cosa}',
    'ridurre {ff} (ora {v:g})':
        'reduce {ff} (now {v:g})',
    "con {ff} = 0 è la coda dell'integratore, cioè una risposta lenta che carica l'integratore: aumentare {p} oppure ridurre {i}":
        'with {ff} = 0 this is the integrator tail, i.e. a slow response that winds up the integrator: increase {p} or reduce {i}',
    'Ritardo {d:.0f} ms (criterio ≤ {c:.0f} ms): aumentare {p}':
        'Delay {d:.0f} ms (criterion ≤ {c:.0f} ms): increase {p}',
    'livello a fine finestra {v:.3f}':
        'level at the end of the window {v:.3f}',
    'Motori al limite per il {v:.1f}% del tempo: il controllore chiede più coppia di quella disponibile (manovre troppo aggressive o margine di spinta ridotto).':
        'Motors at their limit for {v:.1f}% of the time: the controller asks for more torque than is available (maneuvers too aggressive or reduced thrust margin).',
    'Sovraelongazione {ov:.0f}% rispetto al comando (criterio ≤ {c:g}%): ridurre {p}':
        'Overshoot {ov:.0f}% of the command (criterion ≤ {c:g}%): reduce {p}',
    'la risposta a fine gradino è al {v:.0f}% del comando: {azione}':
        'the response at the end of the step is at {v:.0f}% of the command: {azione}',
    'Assestamento {t:.0f} ms (criterio ≤ {c:.0f} ms)':
        'Settling {t:.0f} ms (criterion ≤ {c:.0f} ms)',
    ': oscillazione poco smorzata (vedi sovraelongazione e rimbalzi).':
        ': poorly damped oscillation (see overshoot and bounces).',
    '{b:.0f} rimbalzi fuori dalla fascia dopo il picco (criterio ≤ {c:g}): anello poco smorzato, ridurre {p}{d}.':
        '{b:.0f} bounces out of the band after the peak (criterion ≤ {c:g}): poorly damped loop, reduce {p}{d}.',
    'Motori al limite per il {v:.1f}% del tempo (criterio ≤ {c:g}%): il controllore chiede più coppia di quella disponibile; con i motori al minimo controllare baricentro e margine di spinta.':
        'Motors at their limit for {v:.1f}% of the time (criterion ≤ {c:g}%): the controller asks for more torque than is available; with motors at minimum check the center of gravity and the thrust margin.',
    'Il livello a fine finestra si ferma al {v:.0f}% del comando: {azione}.':
        'The level at the end of the window stops at {v:.0f}% of the command: {azione}.',
    'Il livello a fine finestra supera il comando ({v:.0f}%): {azione}.':
        'The level at the end of the window exceeds the command ({v:.0f}%): {azione}.',
    "Sovraelongazione dell'assetto {ov:.0f}% (criterio ≤ {c:g}%): ridurre {p} o verificare prima l'anello di rate.":
        'Attitude overshoot {ov:.0f}% (criterion ≤ {c:g}%): reduce {p} or check the rate loop first.',
    'Errore a fine gradino {e:.1f} {u} (criterio ≤ {c:g} {u}): {cosa}.':
        'Error at the end of the step {e:.1f} {u} (criterion ≤ {c:g} {u}): {cosa}.',
    ": stessa causa dell'errore a fine gradino.":
        ': same cause as the error at the end of the step.',
    ' o aumentare {d}':
        ' or increase {d}',
    ', oppure {cosa}':
        ', or {cosa}',
    'Prove a gradino':
        'Step tests',
    '#':
        '#',
    'Tipo':
        'Type',
    'Asse':
        'Axis',
    'Verso':
        'Direction',
    'Inizio [s]':
        'Start [s]',
    'Durata [s]':
        'Duration [s]',
    'A':
        'A',
    'Ritardo [s]':
        'Delay [s]',
    'Sovraelong. [%]':
        'Overshoot [%]',
    'Assest. [s]':
        'Settling [s]',
    'Rimbalzi':
        'Bounces',
    'Saturaz. [%]':
        'Saturation [%]',
    'Esito / motivo':
        'Result / reason',
    "PX4 standard: definizioni rispetto al valore finale. Vespa hover: criteri della scheda di taratura, rispetto all'ampiezza comandata":
        'PX4 standard: definitions relative to the final value. Vespa hover: tuning-sheet criteria, relative to the commanded amplitude',
    'Vespa hover (scheda di taratura)':
        'Vespa hover (tuning sheet)',
    'Carica criteri…':
        'Load criteria…',
    'Profilo JSON con le sezioni «gradini» e «tenuta» e i criteri ok degli anelli mc_rate e mc_att (come profili/vespa_hover.json)':
        'JSON profile with the "gradini" and "tenuta" sections and the ok criteria of the mc_rate and mc_att loops (like profili/vespa_hover.json)',
    'Vespa hover':
        'Vespa hover',
    "Torna ai criteri forniti con l'app (profili/vespa_hover.json)":
        'Back to the criteria shipped with the app (profili/vespa_hover.json)',
    'Ignora il modo':
        'Ignore the mode',
    "Cerca i gradini in tutto il volo in multicottero, non solo in Acro/Offboard/Stabilized: per i log dell'autotune, con gradini iniettati in Hold":
        'Look for steps in the whole multicopter flight, not only in Acro/Offboard/Stabilized: for autotune logs, with steps injected in Hold',
    'Esporta PNG e CSV':
        'Export PNG and CSV',
    'PNG riassuntivo, CSV (una riga per gradino più il riepilogo) e un PNG per gradino, nella cartella del log':
        'Summary PNG, CSV (one row per step plus the summary) and one PNG per step, in the log folder',
    'Mediana / caso peggiore dei gradini validi; verde = caso peggiore entro il criterio':
        'Median / worst case of the valid steps; green = worst case within the criterion',
    'Gradino selezionato':
        'Selected step',
    'riepilogo e tenuta':
        'summary and hold',
    'Apri un log con prove a gradino':
        'Open a log with step tests',
    'Carica criteri':
        'Load criteria',
    "Ogni metrica vale 100 punti alla soglia «ottimo», 60 a «accettabile» e 0 a «da rivedere» (interpolazione lineare). Il peso decide quanto conta nel punteggio dell'asse. Obiettivo del tempo di salita: «auto» lo ricava dai parametri del log (MC_AT_RISE_TIME, MC_ROLL_P, FW_R_TC…), oppure un valore in secondi. Nel profilo «Vespa hover» la soglia «accettabile» è il criterio della scheda di taratura e le grandezze sono misurate rispetto all'ampiezza comandata.":
        'Each metric is worth 100 points at the "excellent" threshold, 60 at "acceptable" and 0 at "needs work" (linear interpolation). The weight sets how much it counts in the axis score. Rise-time target: "auto" derives it from the log parameters (MC_AT_RISE_TIME, MC_ROLL_P, FW_R_TC…), or a value in seconds. In the "Vespa hover" profile the "acceptable" threshold is the tuning-sheet criterion and the quantities are measured relative to the commanded amplitude.',
    'PX4 standard':
        'PX4 standard',
    'Usa il profilo PX4 standard':
        'Use the PX4 standard profile',
    'Usa il profilo Vespa hover (scheda di taratura)':
        'Use the Vespa hover profile (tuning sheet)',
    'Profilo:':
        'Profile:',
    'Criteri:':
        'Criteria:',
    'soglia:':
        'threshold:',
    'Riepilogo per asse e verso (mediana / caso peggiore)':
        'Summary per axis and direction (median / worst case)',
    'Stima FIR affiancata e tenuta':
        'FIR estimate side by side and hold',
    'Asse:':
        'Axis:',
    'Prove a gradino…':
        'Step tests…',
    'Nessun gradino trovato nel log.':
        'No steps found in the log.',
    'Esportazione completata':
        'Export completed',
    'Aprire la cartella?':
        'Open the folder?',
    'Esportazione delle prove a gradino…':
        'Exporting the step tests…',
    'Esito':
        'Result',
    'il profilo non contiene i criteri della scheda (sezione «gradini» e anelli mc_rate/mc_att con «definizioni»: «scheda»)':
        'the profile does not contain the tuning-sheet criteria ("gradini" section and mc_rate/mc_att loops with "definizioni": "scheda")',
    'entro i criteri':
        'within the criteria',
    'fuori criterio':
        'out of criteria',
    'valido':
        'valid',
    'non assestato':
        'not settled',
    'Validi':
        'Valid',
    'Stima FIR (stesse definizioni, profilo dei criteri)':
        'FIR estimate (same definitions, criteria profile)',
    'Tenuta in Hold/Position (tratti fermi, senza comandi)':
        'Hold quality in Hold/Position (still stretches, no commands)',
    'Convenzione dei tempi':
        'Time convention',
    'Scritti {n} file nella cartella del log:\n{cartella}':
        '{n} files written in the log folder:\n{cartella}',
    'Parametri del volo':
        'Flight parameters',
    'asse: non valutabile':
        'axis: not assessable',
    'asse: TARATO':
        'axis: TUNED',
    'asse: NON TARATO':
        'axis: NOT TUNED',
    'nessun asse con gradini':
        'no axis with steps',
    'sovraelongazione':
        'overshoot',
    'assestamento':
        'settling',
    'punteggio':
        'score',
    'nessun tratto in Hold/Position con velocità richiesta nulla':
        'no Hold/Position stretch with zero requested speed',
    'criterio: ≤ {v}':
        'criterion: ≤ {v}',
    'rollio tra':
        'roll between',
    'e':
        'and',
    'Definizioni della scheda di taratura: gradino di {a} per {d}.':
        'Tuning-sheet definitions: step of {a} for {d}.',
    "Soglie solo per l'asse {asse}.":
        'Thresholds for the {asse} axis only.',
    'Allocatore del tiltrotor':
        'Tiltrotor allocator',
    'SDLOG_PROFILE senza alta frequenza ({cosa}): ritardi e saturazione dei gradini sono imprecisi. Usare SDLOG_PROFILE = 17 (predefinito + alta frequenza).':
        'SDLOG_PROFILE without high rate ({cosa}): step delays and saturation are inaccurate. Use SDLOG_PROFILE = 17 (default + high rate).',
    '. Le misure di questo log non valgono.':
        '. The measurements of this log are not valid.',
    'motori registrati a {f:.0f} Hz':
        'motors logged at {f:.0f} Hz',
    ' e gli integratori di rate_ctrl_status sono fermi':
        ' and the rate_ctrl_status integrators are frozen',
    "Possibile PX4 senza la correzione dell'allocatore del tiltrotor: in hover torque_setpoint_achieved è falso per il {p:.0f}% del tempo":
        'Possible PX4 without the tiltrotor allocator fix: in hover torque_setpoint_achieved is false for {p:.0f}% of the time',
    'VALIDO':
        'VALID',
    'Motori [0–1]':
        'Motors [0–1]',
    'n. ass.':
        'n. sett.',
    'comando al 50%':
        'command at 50%',
    'fine del gradino':
        'end of the step',
    'finestra della saturazione':
        'saturation window',
    'Uscite dei motori':
        'Motor outputs',
    'risposta':
        'response',
    'gradino valido':
        'valid step',
    'gradino scartato':
        'rejected step',
    'Tempo dal comando al 50% [s]':
        'Time from the command at 50% [s]',
    'risposta al 50%':
        'response at 50%',
    'picco':
        'peak',
    'assestato':
        'settled',
    'SCARTATO':
        'REJECTED',
    'verso +':
        'direction +',
    'verso −':
        'direction −',
    'Risposta / A':
        'Response / A',
    'criterio':
        'criterion',
    'Celle: mediana / caso peggiore dei gradini validi; verde = entro il criterio. Tempi: {conv}.':
        'Cells: median / worst case of the valid steps; green = within the criterion. Times: {conv}.',
    'escluso (50 ms dopo un cambio di modo)':
        'excluded (50 ms after a mode change)',
    'fascia ±{b} {u}':
        'band ±{b} {u}',
    'sovraelong. {v}%':
        'overshoot {v}%',
    'assestamento {v}':
        'settling {v}',
    'rimbalzi {v}':
        'bounces {v}',
    'saturazione {v}%':
        'saturation {v}%',
    'criteri':
        'criteria',
    'Tenuta':
        'Hold quality',
    'ritardo {v} s':
        'delay {v} s',
    'errore {v} {u}':
        'error {v} {u}',
    'Affidabilità alta con almeno 20 s di manovre utili, media tra 8 e 20 s, bassa sotto 8 s; scende anche con meno di 8 campioni nel tempo di salita, con stime disperse (sovraelongazione ± oltre 5 punti) o con guadagni cambiati in volo. Nei voli di prove a gradino (Acro, Offboard) contano invece i gradini validi: alta con almeno 3 per verso, media con almeno 3 in tutto, altrimenti bassa.':
        'High confidence with at least 20 s of useful maneuvers, medium between 8 and 20 s, low below 8 s; it also drops with fewer than 8 samples in the rise time, with scattered estimates (overshoot ± more than 5 points) or with gains changed in flight. In step-test flights (Acro, Offboard) the valid steps count instead: high with at least 3 per direction, medium with at least 3 in total, otherwise low.',
    'Saturazione: quota dei campioni di actuator_motors (piena frequenza) con almeno un motore ≤ 0,02 o ≥ 0,98, più i tilt usati per il controllo; i 50 ms dopo ogni cambio di modo sono esclusi.':
        'Saturation: share of actuator_motors samples (full rate) with at least one motor ≤ 0.02 or ≥ 0.98, plus the tilts used for control; the 50 ms after each mode change are excluded.',
    "Definizioni della scheda di taratura (anelli marcati «gradino della scheda»): grandezze della risposta stimata calcolate per un gradino dell'ampiezza e della durata indicate, rispetto all'ampiezza comandata: ritardo dal comando al 50% alla risposta al 50%, sovraelongazione (picco − A)/A, assestamento nella fascia, errore medio negli ultimi 0,2 s (assetto: dopo 1 s, in gradi), rimbalzi fuori dalla fascia dopo il picco. La soglia da 60 punti è il criterio della scheda.":
        'Tuning-sheet definitions (loops marked "tuning-sheet step"): quantities of the estimated response computed for a step of the given amplitude and duration, relative to the commanded amplitude: delay from the command at 50% to the response at 50%, overshoot (peak − A)/A, settling in the band, mean error over the last 0.2 s (attitude: after 1 s, in degrees), bounces out of the band after the peak. The 60-point threshold is the tuning-sheet criterion.',
    "Per ogni asse si stima ai minimi quadrati la risposta impulsiva (FIR) dal setpoint alla misura usando tutti i tratti in volo della fase scelta; la risposta al gradino è la sua somma cumulativa. Quando il setpoint di velocità angolare è prodotto dall'anello d'assetto (modi Stabilized, Position, Hold, Mission) si usano le variabili strumentali, con il setpoint d'assetto come riferimento esterno: così la reazione del controllore alle raffiche non falsa la stima. Dove il setpoint di velocità angolare è già esterno (vehicle_control_mode con velocità angolare attiva e assetto spento: Acro e Offboard a velocità angolare) si usa il setpoint stesso; per l'anello d'assetto si escludono i tratti senza setpoint d'assetto. I 50 ms dopo ogni cambio di modo escono dalle equazioni. L'incertezza (banda ±2σ e valori ±) viene da un jackknife a blocchi di dati.":
        'For each axis the finite impulse response (FIR) from setpoint to measurement is estimated by least squares using all airborne stretches of the selected phase; the step response is its cumulative sum. When the rate setpoint comes from the attitude loop (Stabilized, Position, Hold, Mission modes) instrumental variables are used, with the attitude setpoint as external reference, so the controller reaction to gusts does not bias the estimate. Where the rate setpoint is already external (vehicle_control_mode with rate control on and attitude control off: Acro and Offboard rate) the setpoint itself is used; for the attitude loop the stretches without an attitude setpoint are excluded. The 50 ms after each mode change are removed from the equations. The uncertainty (±2σ band and ± values) comes from a block jackknife.',
    "Ogni gradino del comando registrato viene misurato direttamente: ritardo dal comando al 50% alla risposta al 50% (comando: timestamp; risposta: timestamp_sample), sovraelongazione (picco − A)/A, assestamento nella fascia ±10% di A (assetto ±1°), errore medio negli ultimi 0,2 s (assetto: dopo 1 s), rimbalzi dopo il picco, saturazione dei motori fino a 0,5 s dopo la fine. Si scartano i gradini con un cambio di modo da 0,4 s prima dell'inizio alla fine, quelli troncati (sotto il 90% della durata mediana), quelli che partono inclinati, in rotazione o in movimento e quelli con comandi sugli altri assi.":
        'Each step of the logged command is measured directly: delay from the command at 50% to the response at 50% (command: timestamp; response: timestamp_sample), overshoot (peak − A)/A, settling in the ±10% band of A (attitude ±1°), mean error over the last 0.2 s (attitude: after 1 s), bounces after the peak, motor saturation up to 0.5 s after the end. Steps are rejected with a mode change from 0.4 s before the start to the end, when truncated (below 90% of the median duration), when they start tilted, rotating or moving, and with commands on the other axes.',
    'gradino della scheda: {g}; fascia {f}':
        'tuning-sheet step: {g}; band {f}',
    'Gradini trovati':
        'Steps found',
    'Criteri':
        'Criteria',
    'Riepilogo per asse e verso (mediana / caso peggiore dei gradini validi)':
        'Summary per axis and direction (median / worst case of the valid steps)',
    'Errore del livello a fine finestra':
        'Error of the level at the end of the window',
    'Tempo con motori al limite (≤ 0,02 o ≥ 0,98)':
        'Time with motors at their limit (≤ 0.02 or ≥ 0.98)',
    'Ritardo (comando al 50% → risposta al 50%)':
        'Delay (command at 50% → response at 50%)',
    'Sovraelongazione rispetto al comando':
        'Overshoot relative to the command',
    'Assestamento nella fascia':
        'Settling in the band',
    'Errore a fine gradino':
        'Error at the end of the step',
    'Errore dopo 1 s':
        'Error after 1 s',
    'Rimbalzi dopo il picco':
        'Bounces after the peak',
    'profilo {nome} non trovato nella cartella profili':
        'profile {nome} not found in the profili folder',
    'comando: timestamp; risposta: timestamp_sample':
        'command: timestamp; response: timestamp_sample',
    'Vel. ang.':
        'Rate',
    'Ritardo':
        'Delay',
    'Assestamento':
        'Settling',
    'Saturazione':
        'Saturation',
    'Errore di rollio RMS':
        'Roll error RMS',
    'Errore di rollio di picco':
        'Peak roll error',
    'Errore di beccheggio RMS':
        'Pitch error RMS',
    'Errore di beccheggio di picco':
        'Peak pitch error',
    'Scostamento orizzontale dalla media':
        'Horizontal deviation from the mean',
    'Scostamento verticale dalla media':
        'Vertical deviation from the mean',
    'Integratore di rollio (max |valore|)':
        'Roll integrator (max |value|)',
    'Integratore di beccheggio (max |valore|)':
        'Pitch integrator (max |value|)',
    'Motori (min – max)':
        'Motors (min – max)',
    'Spinta di hover stimata (media ± dev. std)':
        'Estimated hover thrust (mean ± std. dev.)',
    'versione':
        'version',
    'log':
        'log',
    'riga':
        'row',
    'n':
        'n',
    'tipo':
        'type',
    'verso':
        'direction',
    'inizio [s]':
        'start [s]',
    'fine [s]':
        'end [s]',
    'durata [s]':
        'duration [s]',
    'ampiezza A':
        'amplitude A',
    'unità':
        'unit',
    'comando al 50% [s]':
        'command at 50% [s]',
    'ritardo [s]':
        'delay [s]',
    'sovraelongazione [%]':
        'overshoot [%]',
    'assestamento [s]':
        'settling [s]',
    'unità errore':
        'error unit',
    'rimbalzi':
        'bounces',
    'saturazione [%]':
        'saturation [%]',
    'motori saturi':
        'saturated motors',
    'motivo dello scarto':
        'rejection reason',
    'note':
        'notes',
    'convenzione dei tempi':
        'time convention',
    'ok':
        'ok',
    'fuori':
        'out',
    'risposta non registrata':
        'response not logged',
    "Nessun gradino trovato: i gradini di velocità angolare si cercano in Acro e in Offboard a velocità angolare, quelli d'assetto in Stabilized e in Offboard d'assetto (per i log dell'autotune usare «Ignora il modo»).":
        'No steps found: rate steps are searched in Acro and Offboard rate mode, attitude steps in Stabilized and Offboard attitude mode (for autotune logs use "Ignore the mode").',
    'gradino':
        'step',
    'troppo corto ({d} s)':
        'too short ({d} s)',
    'cambio di modo a {t} s ({da} → {a})':
        'mode change at {t} s ({da} → {a})',
    'troncato: {d} s contro la mediana di {m} s':
        'truncated: {d} s against the median of {m} s',
    'velocità angolare {v} °/s':
        'angular rate {v} °/s',
    'velocità orizzontale {v} m/s':
        'horizontal speed {v} m/s',
    'partenza non ferma: {cosa}':
        'start not at rest: {cosa}',
    'la finestra della saturazione comprende il cambio di modo a {t} s ({da} → {a})':
        'the saturation window includes the mode change at {t} s ({da} → {a})',
    'Parametri del controllore cambiati durante il volo ({nomi}): la prova non vale, serve un log per ogni configurazione.':
        'Controller parameters changed during the flight ({nomi}): the test is not valid, one log per configuration is needed.',
    'sì':
        'yes',
    'no':
        'no',
    'mediana':
        'median',
    'caso peggiore':
        'worst case',
    'stick mossi per il {p:.0f}% del tratto':
        'sticks moved for {p:.0f}% of the stretch',
    'tratto di {d:.0f} s, più corto dei {m:.0f} s richiesti: valori indicativi':
        '{d:.0f} s stretch, shorter than the required {m:.0f} s: indicative values',
    'stima non disponibile':
        'estimate not available',
    'comando anche su {asse} ({v} {u})':
        'command also on {asse} ({v} {u})',
    'flag «{f}» attivo durante il gradino ({t} s)':
        'flag "{f}" active during the step ({t} s)',
    'flag «{f}» a {t} s, dopo la fine del gradino':
        'flag "{f}" at {t} s, after the end of the step',
    'verso {s}: {n} gradini validi su {t} (ne servono almeno {k})':
        'direction {s}: {n} valid steps out of {t} (at least {k} needed)',
    '{g}: stima FIR {f} contro mediana dei gradini {m} (oltre ±2σ = {s})':
        '{g}: FIR estimate {f} against step median {m} (beyond ±2σ = {s})',
    'riepilogo':
        'summary',
    'riepilogo — esito':
        'summary — result',
    'criterio del ritardo':
        'delay criterion',
    'fine del gradino della scheda':
        'end of the tuning-sheet step',
}
