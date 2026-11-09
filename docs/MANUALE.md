# Flight Analyzer — manuale

Applicazione desktop per analizzare i log di volo PX4 (`.ulg`) e **valutare i controllori su una scala oggettiva**.
Riprende le viste di Flight Review (assetto, velocità angolari, posizione, comandi e spinta, potenza, uscite di motori
e servi, giri motore, vibrazioni e densità spettrale, flag sollevati, parametri, messaggi) in un'app locale con
grafici sincronizzati. In più ha un modulo di analisi PID con punteggio, incertezza, margini di stabilità e confronto
tra tarature diverse, e il report in PDF o HTML.

Pensata per PX4 v1.17 e per VTOL: separa automaticamente multicottero, ala fissa e transizioni. Legge anche i log di
versioni precedenti, con le funzioni che quei log permettono. Interfaccia in **italiano o inglese**, tema **chiaro o
scuro** nei colori del Team Zefiro.

## Novità della 1.2.0

- **Scheda «Prove a gradino»**: misura diretta di ogni gradino (ritardo, sovraelongazione, assestamento, errore,
  rimbalzi, saturazione dei motori), gradini scartati con il motivo, caso peggiore per asse e verso, esito «tarato»
  contro i criteri della scheda di taratura, tenuta in Hold/Position, PNG per gradino e CSV. Anche da riga di comando
  (`gradini`) e nel report.
- **Profilo «Vespa hover»** (`profili/vespa_hover.json`): il punteggio dell'Analisi PID usa le stesse definizioni e
  gli stessi criteri della scheda di taratura. Si sceglie dalla scheda Analisi PID o dal menu Analisi.
- **Gradini in Offboard nella stima.** I tratti in cui il setpoint di velocità angolare è esterno si riconoscono da
  `vehicle_control_mode` (velocità angolare attiva, assetto spento): Acro **e Offboard a velocità angolare**. Prima
  valeva solo l'Acro, e in Offboard la stima usava come strumento un setpoint d'assetto che PX4 non pubblica: i gradini
  quasi non entravano nella stima. Per l'anello d'assetto si escludono i tratti senza setpoint d'assetto.
- **Transitori ai cambi di modo esclusi**: i 50 ms dopo ogni cambio di `nav_state` o di `vehicle_control_mode`
  (setpoint fuori scala per un ciclo, motori saturi) escono da stima, saturazione, eccitazione e prove a gradino.
- **Saturazione misurata sui motori** (`actuator_motors` a piena frequenza, più i tilt usati per il controllo) invece
  che su `control_allocator_status`, registrato a 5 Hz. Avviso «Possibile PX4 senza la correzione dell'allocatore del
  tiltrotor» nel riepilogo, nella scheda e nel report.
- **Consigli corretti**: «ridurre FF» solo se MC_*RATE_FF > 0; con FF = 0 il livello oltre il comando è la coda
  dell'integratore. La grandezza si chiama «livello a fine finestra», non «a regime».
- **Affidabilità dai gradini**: nei voli di prove a gradino conta il numero di gradini validi (almeno 3 per verso) e il
  messaggio dice cosa volare («3 doppietti a 45 °/s»), invece di chiedere 20 s di manovre qualsiasi.

---

## Installazione

### Con l'installer (consigliato, non serve Python)

Si scarica `FlightAnalyzer-<versione>-setup.exe` e si fa doppio clic. L'installer:

- chiede la **lingua** (italiano o inglese), che diventa anche la lingua dell'app;
- installa per l'utente corrente, senza permessi di amministratore;
- crea il collegamento nel menu Start e, se richiesto, sul desktop;
- se richiesto, associa i file `.ulg`: doppio clic su un log e si apre in Flight Analyzer.

In alternativa c'è `FlightAnalyzer-<versione>-portable.exe`, un solo file che parte senza installazione (il primo
avvio è un po' più lento). Al primo avvio chiede la lingua.

**Come si ottengono i due file.** Sono creati su Windows da `build_windows.bat` (serve Python; per l'installer anche
[Inno Setup 6](https://jrsoftware.org/isdl.php)) oppure, senza installare nulla, dalla GitHub Action
`.github/workflows/build-windows.yml`: si carica il progetto in un repository GitHub, si apre **Actions → Build
Windows → Run workflow** e a fine lavoro i file si scaricano dagli «Artifacts». Pubblicando un tag `v1.1.0` la stessa
Action li allega alla release. Vedi [Creare l'eseguibile](#creare-leseguibile-e-linstaller).

### Da sorgente (per chi sviluppa)

Serve Python 3.9 o successivo.

```bash
pip install -r requirements.txt
python -m flight_analyzer                 # apre l'app
python -m flight_analyzer volo.ulg        # apre l'app con un log
```

Le dipendenze sono `numpy`, `matplotlib`, `PySide6`, `reportlab` (report PDF) e `pypdf` (scheda di taratura). Il
lettore ULog è interno, quindi `pyulog` non serve. Su Windows si può fare doppio clic su `avvia.bat`: al primo avvio
installa da solo le librerie e, se qualcosa va storto, lascia l'errore visibile nella console. `avvia.pyw` parte senza
console.

## Le schede

| Scheda | Contenuto |
|---|---|
| Panoramica | Riepilogo (versione PX4, hardware, tempi di volo per fase, profilo di log, batteria, potenza elettrica massima, vibrazioni, messaggi, flag, dropout); traccia vista dall'alto colorata per fase con il profilo di missione (waypoint numerati, decollo, transizione, atterraggio, percorso pianificato, cerchi di loiter, setpoint di posizione); quota con la quota del waypoint attivo |
| Analisi PID | Punteggi per asse, risposte al gradino, risposta in frequenza e robustezza (con la spiegazione di cosa significa «anello chiuso \|T\|»), dati usati, diagnosi, confronto con altri log; scelta del profilo (PX4 standard o Vespa hover) |
| Prove a gradino | Gradini trovati e scartati con il motivo, grafico di ogni gradino (comando, risposta, fascia, punti del 50%, picco, motori), riepilogo per asse e verso con mediana, caso peggiore ed esito, stima FIR affiancata, tenuta in Hold, avvisi, parametri del volo; esportazione PNG e CSV |
| Assetto / Velocità angolari | Setpoint contro stimato (e ground truth nei log SITL) |
| Posizione e velocità | Posizione, velocità e quota con i setpoint, velocità all'aria, nelle unità scelte |
| Comandi e spinta | Come «Actuator Controls» di Flight Review: coppia e spinta normalizzate dell'istanza multicottero [0] e di quella ad ala fissa [1], con spinta verso l'alto (−z) e in avanti (x), più la norma della spinta richiesta |
| Potenza | Come «Power» di Flight Review: tensione, corrente, consumo (mAh/100) e carica residua della batteria; potenza elettrica V·I della batteria e di ogni ESC; potenza applicata dagli ESC in % (oppure il comando dei motori in %); alimentazioni di bordo 5 V / 3,3 V. Qui si vede la regolazione della potenza dei propulsori durante la transizione |
| Motori e servi | Uscite dei motori (0…1), dei servi con il nome della superficie (−1…1), angolo dei tilt in gradi (da `CA_SV_TL*_MINA/MAXA`, 0° = rotore verso l'alto) e uscite fisiche Main/AUX (PWM in µs) |
| Giri motore | Giri degli ESC (`esc_status`) o del sensore di giri (`rpm`) e temperatura degli ESC |
| Vibrazioni e spettri | Accelerazioni grezze e metriche di vibrazione con le fasce di Flight Review; **densità spettrale di potenza nel tempo** di accelerazione, velocità angolare e accelerazione angolare (spettrogrammi come Flight Review); spettro e spettrogramma di giroscopio, accelerometro e coppia con le frequenze dei filtri PX4 |
| Sistema | CPU e RAM, comandi del pilota |
| Flag | Tutti i flag sollevati in volo (failsafe, failure detector, stimatore EKF2, batteria) con gravità, prima attivazione, numero di attivazioni, durata e descrizione, più il diagramma nel tempo |
| Parametri | Tutti i parametri con filtro; evidenzia quelli diversi dal default e quelli cambiati in volo |
| Messaggi | Messaggi del log e cambi di parametro; doppio clic per centrare i grafici su quell'istante |
| Esplora dati | Qualunque campo di qualunque topic |

Le schede che non servono si nascondono da **File → Impostazioni → Schede**.

**Nota sui log SITL.** In Gazebo Classic PX4 pubblica giri e correnti degli ESC calcolati dal comando (giri = comando ×
6000), non misurati: i grafici lo segnalano.

## Navigare nei grafici

Tutti i grafici temporali condividono l'asse dei tempi: zoomando in una scheda si zoomano anche le altre. Passando col
mouse, la barra di stato mostra i valori di tutte le curve, il modo di volo e la fase.

| Azione | Effetto |
|---|---|
| Rotella | zoom sul tempo attorno al mouse |
| Ctrl + rotella | zoom verticale («Adatta Y» o il tasto A lo annullano) |
| Maiusc + rotella | scorrimento nel tempo |
| Trascinamento (tasto sinistro) | spostamento nel tempo |
| Doppio clic, tasto Home, «Tutto il log» | tutto il log |
| Frecce ← →, tasti + − | scorrimento e zoom da tastiera (dopo un clic sul grafico) |
| Menu «Vai a» | porta tutti i grafici su una fase VTOL, un modo di volo o il tratto in volo |
| Clic su una voce di legenda | nasconde o mostra quella curva |
| ◀ / ▶ oppure Ctrl+B | nasconde il pannello laterale; F11 schermo intero |

Restano disponibili anche gli strumenti di matplotlib (lente, spostamento, salva). **File → Salva grafico corrente**
esporta in PNG, SVG o PDF.

**Sfondo.** Nei VTOL lo sfondo è colorato per fase: azzurro multicottero, arancio transizione, verde ala fissa. La
striscia in alto indica il modo di volo, con il nome scritto sopra. Si cambia da **Visualizza → Sfondo dei grafici**.

## Impostazioni

**File → Impostazioni** (Ctrl+,). Tutto resta salvato tra un avvio e l'altro.

- **Generale:** lingua (italiano o inglese, si applica al riavvio), tema chiaro, scuro o come il sistema, fase da
  analizzare all'apertura, analisi PID automatica all'apertura, scorciatoia sul desktop.
- **Unità di misura:** angoli in gradi o radianti, velocità in m/s, km/h o nodi, quote in metri o piedi.
- **Grafici:** sfondo, spessore delle linee, dimensione del testo, punti disegnati per curva, legenda cliccabile,
  navigazione con rotella e trascinamento.
- **Schede:** quali schede mostrare.
- **Esportazione:** formato predefinito del report (PDF o HTML), risposta in frequenza e parametri di valutazione nel
  report.
- **Scheda di taratura:** nomi di responsabile e verificatore, che precompileranno la scheda di taratura (la
  compilazione automatica arriva con il modulo «Prove a gradino»).

Il tema scuro si attiva anche al volo da **Visualizza → Tema scuro**. I report usano sempre il tema chiaro.

## Prove a gradino

La scheda misura direttamente, gradino per gradino, le prove di taratura in hover del Vespa e le giudica con i
criteri della scheda di taratura. È complementare al punteggio dell'Analisi PID: la stima FIR dà una risposta media,
la scheda di taratura chiede che **ogni** gradino rispetti i criteri **nel caso peggiore**. Tutto si misura rispetto al
comando registrato nel log, mai rispetto a tempi teorici.

### Dove si cercano i gradini

- **Velocità angolare**: in `vehicle_rates_setpoint`, solo nei tratti con il setpoint esterno, cioè con
  `vehicle_control_mode` che ha la velocità angolare attiva e l'assetto spento (Acro, Offboard a velocità angolare,
  come con lo script `gradini_vespa.py`). Rollio, beccheggio e imbardata.
- **Assetto**: in `vehicle_attitude_setpoint` (q_d), in Stabilized o in Offboard d'assetto. Rollio e beccheggio.
- Un gradino inizia quando |comando| supera **20 °/s** (assetto **3°**) e finisce quando torna sotto, o al cambio di
  modo se arriva prima. **A** = mediana del comando sul tratto sopra il 90% del suo massimo, meno il valore prima del
  gradino (mediana degli 0,3 s precedenti). I comandi prodotti da Hold/Position non sono gradini; i picchi di un ciclo
  (sotto 50 ms) neanche.
- **Ignora il modo** (e `--ignora-modo`): cerca i gradini in tutto il volo in multicottero con una soglia regolabile,
  per i log dell'autotune (gradini iniettati in Hold).

### Gradini scartati, con il motivo

- **cambio di modo** (`nav_state` o `vehicle_control_mode`) da 0,4 s prima dell'inizio alla fine del gradino. Lo
  script entra in Offboard 0,5 s prima del gradino, ma nei log la distanza è 0,48–0,49 s (setpoint ogni 24 ms): con 0,5 s
  esatti verrebbe scartato ogni gradino;
- **troncato**: durata sotto il 90% della mediana dei gradini dello stesso asse; **troppo corto**: sotto 0,2 s;
- **partenza non ferma** (media degli 0,1 s prima dell'inizio): rollio o beccheggio oltre 2°, velocità angolare
  sull'asse oltre 5 °/s, velocità orizzontale (vx, vy) oltre 0,5 m/s;
- **comando anche su un altro asse**: setpoint degli altri assi che si scosta dal valore di prima di più di 3 °/s
  (assetto 1°);
- **flag di failsafe** attivo durante il gradino (`failsafe_flags`, `vehicle_status`); se scatta dopo la fine viene
  solo annotato.

Tutte le soglie stanno nella sezione `gradini` di `profili/vespa_hover.json`.

### Grandezze di ogni gradino

| Grandezza | Definizione |
|---|---|
| Ritardo | t(risposta al 50% di A) − t(comando al 50% di A) |
| Sovraelongazione | (picco − A)/A durante il gradino, in % (negativa se la risposta non arriva ad A) |
| Assestamento | dall'istante del comando al 50% all'ultimo istante fuori dalla fascia ±10% di A (assetto: ±1°), finché dura il gradino; «non assestato» se a fine gradino è ancora fuori |
| Errore | media di \|comando − risposta\| negli ultimi 0,2 s del gradino, in % di A; assetto: in gradi, da 1 s dopo l'inizio alla fine |
| Rimbalzi | uscite dalla fascia dopo il picco (almeno 2 campioni fuori, o fino alla fine del gradino) |
| Saturazione | % dei campioni di `actuator_motors`, dall'inizio del gradino a 0,5 s dopo la fine, con almeno un motore ≤ 0,02 o ≥ 0,98 (solo le uscite con valori finiti), con quale motore e verso quale limite; i 50 ms dopo un cambio di modo sono esclusi |

**Convenzione dei tempi.** Comando: `timestamp` di `vehicle_rates_setpoint` / `vehicle_attitude_setpoint`, tenuto
fino al campione successivo (il comando al 50% è il primo campione oltre metà di A). Risposta: `timestamp_sample` di
`vehicle_angular_velocity` / `vehicle_attitude`, interpolata linearmente. La convenzione è scritta anche nel CSV.

Il gradino «dura» dall'istante del comando al 50% fino all'istante in cui il comando torna al valore di partenza
(escluso): l'ultimo campione, dove il comando è già sceso, non entra né nell'assestamento né nell'errore.

### Criteri ed esito

Per ogni asse e per ogni verso: mediana e caso peggiore di ogni grandezza ed esito per criterio (verde = caso
peggiore entro il criterio). L'asse è **«tarato»** solo se il caso peggiore rispetta tutti i criteri in entrambi i
versi. Con meno di 3 gradini validi per verso compare un avviso. I criteri sono la soglia «ok» del profilo «Vespa
hover»:

| | Ritardo | Sovraelong. | Assestamento | Errore | Rimbalzi | Saturazione |
|---|---|---|---|---|---|---|
| Velocità angolare rollio e beccheggio (45 °/s) | ≤ 0,12 s | ≤ 15% | ≤ 0,35 s | ≤ 5% | ≤ 1 | ≤ 5% |
| Velocità angolare imbardata (30 °/s, provvisorio) | ≤ 0,25 s | ≤ 15% | ≤ 1,0 s | ≤ 10% | ≤ 1 | ≤ 10% |
| Assetto rollio e beccheggio (10°) | ≤ 0,25 s | ≤ 10% | ≤ 0,8 s (±1°) | ≤ 0,5° dopo 1 s | 0 | ≤ 5% |

Accanto c'è la **stima FIR** dello stesso asse con le stesse definizioni: se ritardo, sovraelongazione o assestamento
differiscono dalla mediana dei gradini più di due volte l'incertezza stimata, compare un avviso.

### Tenuta

Tratti in Position/Hold in cui al velivolo si chiede di stare fermo (velocità di `trajectory_setpoint` sotto
0,3 m/s; un Hold con una salita o un riposizionamento non conta), tolto il primo secondo. Criteri: errore di assetto di
rollio e beccheggio RMS ≤ 1° e picco ≤ 3°; posizione entro ±0,5 m in orizzontale e ±0,3 m in verticale dalla media
del tratto; integratori di rollio e beccheggio entro ±0,15; motori sempre tra 0,05 e 0,95; spinta di hover stimata
(media e deviazione standard). Tratti più corti di 30 s (ma di almeno 5 s) sono valutati come indicativi.

### Avvisi

- **Possibile PX4 senza la correzione dell'allocatore del tiltrotor**: in hover `torque_setpoint_achieved` di
  `control_allocator_status` è falso per almeno il 90% del tempo (con o senza integratori fermi). Le misure di quel
  log non valgono. Compare anche nel riepilogo del volo.
- **SDLOG_PROFILE senza alta frequenza**: bit 16 assente o `actuator_motors` sotto 100 Hz.
- **Parametri cambiati in volo** (da `param_changes`): la prova non vale.

### Esportazione

«Esporta PNG e CSV» (e il comando `gradini`) scrive nella cartella del log:

- `<log>_riepilogo.png`: parametri, avvisi, gradini validi sovrapposti per asse e verso, tabella con mediana, caso
  peggiore ed esito (senza gradini: la tenuta);
- `<log>_riepilogo.csv`: una riga per gradino (anche gli scartati, con il motivo) più le righe di riepilogo (mediana,
  caso peggiore, esito per asse e verso), con la versione dell'app e la convenzione dei tempi. In italiano separatore
  «;» e virgola decimale (si apre direttamente con Excel), in inglese «,» e punto;
- `<log>_gradini/`: un PNG per gradino (comando, risposta, fascia, motori), gli scartati con `_scartato` nel nome.

## Analisi PID

Si scelgono la **fase** (multicottero, ala fissa o tutto), l'**anello** (velocità angolare o assetto) e
l'**intervallo**: tutto il volo nella fase, oppure solo il tratto visibile nei grafici temporali (si zooma su una
manovra e si analizza solo quella). Vengono usati solo i tratti in volo, togliendo mezzo secondo ai bordi.

Per ogni asse l'app mostra:

- la **risposta al gradino** stimata dai dati, con banda di incertezza ±2σ e linea dell'obiettivo di tempo di salita;
- la **risposta in frequenza** dell'anello chiuso (banda a −3 dB, picco di risonanza);
- per l'anello di rate multicottero, **guadagno d'anello, sensitività, margine di fase e di guadagno** se il volo
  contiene abbastanza eccitazione;
- la **tabella delle metriche** con valore, incertezza, punti, soglie e peso;
- la **diagnosi** in testo, con i parametri PX4 su cui agire (es. «ridurre MC_ROLLRATE_P del 10–20% oppure
  aumentare MC_ROLLRATE_D»).

**Confronto tra tarature.** Con «Aggiungi log di confronto…» si sovrappongono le risposte di altri log e si ottiene
una tabella dei punteggi affiancati. È il modo più rapido per vedere se una modifica ai guadagni ha migliorato le
cose.

### Come viene stimata la risposta

1. **Risposta impulsiva finita ai minimi quadrati** dal setpoint alla misura, su tutti i dati della fase. La risposta
   al gradino è la sua somma cumulativa. Flight Review usa invece finestre da 1 s con deconvoluzione: nel simulatore
   di prova quel metodo sovrastima la sovraelongazione quando l'integratore è lento (10% stimato contro 1% vero),
   mentre questo no.
2. **Variabili strumentali.** Nei modi Stabilized, Position, Hold e Mission il setpoint di rate viene dall'anello
   d'assetto, quindi contiene anche la reazione del controllore alle raffiche, e la stima diretta si sbilancia. L'app
   usa allora il setpoint d'assetto come riferimento esterno. Dove il setpoint di rate è già esterno usa i minimi
   quadrati normali: tratti con `vehicle_control_mode` che ha la velocità angolare attiva e l'assetto spento (Acro e
   **Offboard a velocità angolare**; se il topic manca, solo Acro) ed eccitazione dell'autotune. Per l'anello
   d'assetto si escludono i tratti con `flag_control_attitude_enabled = 0`, dove il setpoint d'assetto non viene
   pubblicato e il valore rimasto fermo non è un dato.
3. **Cambi di modo.** I 50 ms dopo ogni cambio di `nav_state` o di `vehicle_control_mode` escono dalle equazioni (le
   loro righe vengono tolte, il tratto non viene spezzato) e nel setpoint il picco viene sostituito dall'interpolazione
   tra prima e dopo. Nel grafico di ogni gradino queste zone sono tratteggiate in rosso.
4. **Incertezza** con jackknife a blocchi: i dati vengono divisi in blocchi, la stima viene ripetuta escludendone uno
   alla volta e la dispersione dà i valori «±».
5. **Robustezza** (solo rate multicottero). L'impianto P(f) si ottiene dal rapporto tra le risposte setpoint→misura e
   setpoint→comando di coppia, una stima valida anche in anello chiuso. Il controllore C(f) viene ricostruito dai
   parametri del log secondo la legge di `RateControl::update` di PX4 v1.17: `K·(P·e + I∫e − D·ω̇)`, con ω̇ filtrata
   da `IMU_DGYRO_CUTOFF`. Da L = C·P si ricavano frequenza di attraversamento, margine di fase, margine di guadagno e
   picco di sensitività Ms.

### Scala di valutazione

Ogni metrica vale **100 punti** alla soglia «ottimo», **60** a «accettabile» e **0** a «da rivedere», con
interpolazione lineare. Il punteggio dell'asse è la media pesata delle metriche disponibili. Il punteggio dell'anello
pesa rollio 0,4, beccheggio 0,4 e imbardata 0,2. Il giudizio è: Ottimo ≥ 85, Buono ≥ 70, Accettabile ≥ 55,
altrimenti Da rivedere.

Soglie predefinite per l'anello di rate multicottero:

| Metrica | 100 | 60 | 0 | Peso | Riferimento |
|---|---|---|---|---|---|
| Sovraelongazione | 5% | 15% | 35% | 25 | 2° ordine: smorzamento 0,69 / 0,52 / 0,32 |
| Tempo di salita 10–90% / obiettivo | 1,0× | 1,5× | 3,0× | 15 | obiettivo = `MC_AT_RISE_TIME` (0,14 s default PX4), 2× per l'imbardata |
| Assestamento 5% / obiettivo di salita | 2,5× | 4× | 6× | 15 | 2° ordine ben smorzato: assestamento ≈ 2× salita |
| Errore del livello a fine finestra | 3% | 10% | 25% | 10 | livello = media dell'ultimo 30% della finestra |
| Margine di fase | 50° | 35° | 20° | 15 | valori classici di progetto |
| Picco di risonanza in anello chiuso | 1 dB | 3 dB | 6 dB | 5 | — |
| Rumore sul comando di coppia > 30 Hz (RMS) | 0,01 | 0,03 | 0,08 | 5 | euristica |
| Tempo con motori al limite | 0,5% | 3% | 10% | 5 | euristica |
| Integratore oltre l'80% del limite | 1% | 5% | 20% | 5 | euristica |

Per gli anelli d'assetto l'obiettivo di salita è `2,2/MC_ROLL_P` (multicottero) e `2,2·FW_R_TC` (ala fissa), cioè la
risposta ideale del primo ordine imposta dal guadagno d'assetto. Per il rate ad ala fissa l'obiettivo è
`2,2·FW_R_TC/4`, un anello interno quattro volte più veloce dell'esterno (euristica).

«Tempo con motori al limite» è la quota dei campioni di `actuator_motors` (piena frequenza, solo uscite con valori
finiti) con almeno un motore ≤ 0,02 o ≥ 0,98 sull'intero tratto analizzato, più i tilt se sono usati per il controllo
(`CA_SV_TLx_CT` ≠ 0; nel Vespa sono fermi a fine corsa in hover e non contano); in ala fissa contano le superfici. Fino
alla 1.1.0 veniva da `unallocated_torque` di `control_allocator_status`, registrato solo a 5 Hz (2–3 campioni in un
gradino da 0,5 s). La saturazione dei motori nei singoli gradini è nella scheda «Prove a gradino».

Le metriche che il log non permette di calcolare (es. margini senza eccitazione, rumore con log a 50 Hz) vengono
escluse e il peso ridistribuito. Il punteggio non viene dato se resta meno di metà del peso.

**Affidabilità** (alta, media o bassa). Nei voli di prove a gradino (con tratti in Acro o in Offboard per quell'anello)
conta il numero di gradini validi dell'asse: alta con almeno 3 per verso, media con almeno 3 in tutto, altrimenti
bassa, e il messaggio dice cosa volare («3 doppietti a 45 °/s, partendo in piano e da fermo»; 30 °/s per l'imbardata,
10° per l'assetto). Negli altri voli dipende da quanti secondi di manovre utili ci sono (consigliati almeno 20 s per
asse); se ci sono anche gradini validi vale il migliore dei due criteri. Scende poi con la frequenza di log bassa
rispetto al tempo di salita, con stime disperse e con guadagni cambiati durante il volo. Gli assi ad affidabilità bassa
sono mostrati ma non entrano nel punteggio complessivo, e le loro indicazioni sono precedute da un avviso.

**Profilo.** Tutte le soglie, i pesi e gli obiettivi si modificano da **Analisi → Profilo di valutazione…**, si
salvano in JSON e restano attivi ai riavvii. Per confrontare log tra loro bisogna usare lo stesso profilo. In
`profili/px4_standard.json` c'è quello predefinito.

### Profilo «Vespa hover»

`profili/vespa_hover.json` porta nel punteggio le definizioni e i criteri della scheda di taratura, perché il voto
che i ragazzi inseguono sia quello della scheda. Si attiva dalla scelta «Profilo» della scheda Analisi PID o da
**Analisi → Usa il profilo Vespa hover**. Per gli anelli multicottero (rate e assetto) le grandezze della risposta
stimata (FIR) si calcolano come nelle prove a gradino, con la stessa funzione: gradino unitario = ampiezza comandata
(45 °/s per 0,5 s per rollio e beccheggio, 30 °/s per 1,5 s per l'imbardata, 10° per 1,5 s per l'assetto), ritardo al
50%, sovraelongazione (picco − A)/A, assestamento nella fascia ±10% (assetto ±1°), errore negli ultimi 0,2 s (assetto:
dopo 1 s, in gradi), rimbalzi; la saturazione è misurata nelle finestre dei gradini validi, se ci sono. La risposta
stimata viene spostata di mezzo campione in avanti: il setpoint è riportato sulla griglia di calcolo tenendo il valore,
quindi i suoi fronti vi compaiono in media mezzo campione dopo l'istante vero. Il profilo PX4 standard resta com'è.

Soglie: **«ok» (60 punti) = criterio della scheda**; **«good» (100 punti) = 70% del criterio**, cioè un margine
di circa il 30% che assorbe la dispersione tra un volo e l'altro (ritardo e sovraelongazione variano di qualche ms e di
qualche punto tra gradini uguali); **«bad» (0 punti) = 200% del criterio**: al doppio del limite la taratura è
chiaramente da rifare. Per i rimbalzi, che sono numeri interi, good 0, ok = criterio e bad = criterio + 2; per
l'assetto, che non ammette rimbalzi, ok vale 0,5 (cioè nessun rimbalzo). Il margine di fase, che non è nella scheda,
resta con le soglie PX4 (50°/35°/20°) e peso 10.

| Metrica | Peso | Rate rollio/beccheggio 100 / 60 / 0 | Rate imbardata | Assetto |
|---|---|---|---|---|
| Ritardo | 20 | 0,084 / 0,12 / 0,24 s | 0,175 / 0,25 / 0,5 s | 0,175 / 0,25 / 0,5 s |
| Sovraelongazione | 20 | 10,5 / 15 / 30% | 10,5 / 15 / 30% | 7 / 10 / 20% |
| Assestamento | 15 (assetto 20) | 0,245 / 0,35 / 0,7 s | 0,7 / 1,0 / 2,0 s | 0,56 / 0,8 / 1,6 s |
| Errore | 15 | 3,5 / 5 / 10% | 7 / 10 / 20% | 0,35 / 0,5 / 1,0° |
| Rimbalzi | 10 (assetto 15) | 0 / 1 / 3 | 0 / 1 / 3 | 0 / 0,5 / 2 |
| Saturazione | 10 | 3,5 / 5 / 10% | 7 / 10 / 20% | 3,5 / 5 / 10% |
| Margine di fase | 10 | 50 / 35 / 20° | 50 / 35 / 20° | — |

Nel file ci sono anche le soglie del rilevamento dei gradini (`gradini`) e della tenuta (`tenuta`). Nessuna soglia è
scritta nel codice: per cambiarle si modifica il JSON (o lo si carica dalla scheda «Prove a gradino» con «Carica
criteri…»).

### Validazione

`tests/` contiene un simulatore di un asse con la stessa legge di controllo e la stessa catena di filtri di PX4 v1.17
e un generatore di voli VTOL sintetici in formato ULog. Questo permette di confrontare le stime con la verità.
Risultati sul rollio, con rumore del giroscopio e raffiche:

| Taratura | Salita vera / stimata | Sovraelongazione vera / stimata | Margine di fase vero / stimato |
|---|---|---|---|
| Smorzata | 114 / 109 ms | 0,8 / 2,0 ± 1,5 % | 68° / 64° ± 8° |
| PX4 default | 51 / 47 ms | 5,5 / 5,3 ± 3,3 % | 51° / 45° ± 6° |
| Oscillante | 29 / 27 ms | 49 / 52 ± 2 % | 23,5° / 24,8° ± 2,2° |
| PX4 default, log a 50 Hz | 51 / 52 ms | 5,5 / 5,6 ± 3,3 % | 51° / 45° ± 6° |

Il picco di sensitività Ms è più delicato perché dipende dalle frequenze sopra l'attraversamento, dove i comandi del
pilota hanno poca energia. Per questo viene mostrato ma non entra nel punteggio. La robustezza è valutata con il
margine di fase.

**Prove a gradino** (`tests/check_steptest.py`, 65 controlli):

- sistema del secondo ordine con ritardo (smorzamento 0,7 / 0,45 / 0,25), verità su griglia di 1 µs, segnale a 250 Hz
  con rumore: ritardo entro 2 ms, sovraelongazione entro 0,6 punti, assestamento entro 4 ms, errore entro 0,4 punti,
  rimbalzi esatti;
- tre tarature del rate controller PX4 1.17 (`tests/simulate.py`) in log sintetici del Vespa con gradini in Offboard
  (`tests/make_step_log.py`: setpoint ogni 24 ms, niente setpoint d'assetto in Offboard, picco di un ciclo a ogni
  passaggio in Hold): grandezze di ogni gradino valido uguali alla simulazione senza rumore entro 1 ms e 0,3 punti;
  ritardo della stima FIR entro il 10% del tempo al 50% vero (−3%, −6%, −7%);
- gradino troncato, partenza inclinata e in scivolata, doppietto interrotto da un passaggio in Hold, saturazione di
  3 campioni, log senza gradini, PX4 senza la correzione dell'allocatore, SDLOG_PROFILE = 131 con motori a 10 Hz.

`tests/regressione_vespa.py` confronta i log veri con le misure fatte a parte (prova 0 del 4/11, caduta, rollio del 7/11
con P 0,307, prova 5 del 27/10).

Per rilanciare la validazione:

```bash
python tests/validate_loopid.py
python tests/make_synthetic_log.py prova.ulg --taratura B
python tests/check_synthetic.py prova.ulg
python tests/check_steptest.py
python tests/regressione_vespa.py 2026-11-04_rollio_prova0.ulg 2026-11-07_rollrate_P0307.ulg 27-10-2026_prova5.ulg
python tests/check_i18n.py
python tests/smoke_gui.py volo_B.ulg volo_C.ulg vecchio.ulg cartella_uscita
```

## Volo di prova consigliato

Per punteggi confrontabili tra un volo e l'altro conviene sempre la stessa sequenza:

1. `SDLOG_PROFILE` con il bit «High rate»: **17** (default + alta frequenza). Con il profilo di default i rate sono
   registrati a 50 Hz: l'analisi funziona, ma con affidabilità più bassa e senza la metrica di rumore.
2. Per la scheda di taratura del Vespa: **3 doppietti per asse** con lo script `gradini_vespa.py` (Offboard a velocità
   angolare, 45 °/s per 0,5 s per rollio e beccheggio, 30 °/s per 1,5 s per l'imbardata; 10° per 1,5 s per l'assetto),
   ogni verso come gradino separato che parte con il velivolo in piano e fermo. Gradini più piccoli non servono:
   l'affidabilità conta i gradini validi, non i secondi di manovre.
3. Senza script, per ciascun asse **20–30 s di impulsi brevi e netti** sullo stick (in entrambi i versi, con pause di
   1–2 s), in Stabilized o Acro. Per l'ala fissa, gli stessi impulsi a velocità costante: il rate controller ad ala fissa scala i
   guadagni con la velocità, quindi tratti a velocità diverse vanno analizzati separatamente.
4. Per i **margini di stabilità** serve eccitazione fino a circa due volte la frequenza di attraversamento. Il modo più
   comodo è l'autotune PX4 con `MC_AT_APPLY = 0`, che inietta i gradini sul setpoint di rate ma non cambia i guadagni.
   Si avvia con `MC_AT_START` in Position/Hold; muovere gli stick interrompe l'iniezione.
5. Non cambiare i guadagni durante il volo che si vuole valutare, oppure restringere l'intervallo di analisi a un
   tratto con una sola taratura. L'app segnala i cambi di parametro.

Nei log SITL (Gazebo) le schede Assetto, Velocità angolari e Posizione mostrano anche la ground truth del simulatore.

## Report e riga di comando

- **Esporta PDF** (barra degli strumenti o Ctrl+P): crea subito `<log>.report.pdf` accanto al log e propone di aprirlo.
- **Esporta report…** (Ctrl+E): si sceglie dove salvarlo e il formato, PDF o HTML (pagina unica, senza file esterni).
- **Esporta risultati JSON**: gli stessi numeri per elaborazioni successive.

Il report contiene riepilogo, punteggi, tabelle delle metriche, diagnosi, grafici, gli eventuali log di confronto e,
se il log ha prove a gradino o tratti di tenuta, la sezione **«Prove a gradino»** (parametri del volo, avvisi, gradini
sovrapposti, tabella per asse e verso con mediana, caso peggiore ed esito, elenco dei gradini, tenuta). In
fondo, sia nel PDF sia nell'HTML, ci sono i **parametri di valutazione** usati: profilo, soglie 100/60/0 e pesi di ogni
metrica per ogni anello, obiettivi del tempo di salita, eccitazione minima e regole del punteggio. Così un report si
può sempre rileggere sapendo con che metro è stato fatto. Il report è nella lingua dell'interfaccia.

Senza interfaccia grafica:

```bash
python -m flight_analyzer report volo.ulg                          # volo.report.pdf
python -m flight_analyzer report volo.ulg -o report.html --json risultati.json --confronta volo_prima.ulg
python -m flight_analyzer report volo.ulg -o report_en.pdf --lingua en
python -m flight_analyzer punteggio volo_A.ulg volo_B.ulg volo_C.ulg --fase MC --anello rate
python -m flight_analyzer punteggio volo.ulg --fase FW --anello att --dettagli
python -m flight_analyzer punteggio volo.ulg --profilo profili/vespa_hover.json
python -m flight_analyzer gradini P020.ulg P026.ulg P031.ulg              # prove a gradino, serie con P crescente
python -m flight_analyzer gradini autotune.ulg --ignora-modo --soglia 8
python -m flight_analyzer gradini volo.ulg --profilo-gradini criteri.json --lingua en --senza-png-gradini
```

Il comando `punteggio` stampa una tabella dei punteggi di più log: è utile per confrontare una serie di tarature. Il
comando `gradini` scrive PNG e CSV per ogni log (vedi «Prove a gradino») e stampa una tabella di confronto tra i log:
per ogni asse il P, i gradini validi per verso, il caso peggiore di ogni grandezza e l'esito. Gli stessi comandi
funzionano con l'eseguibile: `FlightAnalyzer.exe report volo.ulg`.

## Creare l'eseguibile e l'installer

Va fatto su Windows (PyInstaller crea eseguibili per il sistema su cui gira). Due strade:

1. **Sul proprio PC:** doppio clic su `build_windows.bat`. Installa PyInstaller, controlla le traduzioni, crea
   `dist\FlightAnalyzer\` (cartella dell'app), `dist\portable\FlightAnalyzer.exe` (file unico) e, se trova Inno
   Setup 6, `dist\FlightAnalyzer-<versione>-setup.exe`.
2. **Su GitHub, senza installare nulla:** la Action `Build Windows` fa gli stessi passi su una macchina Windows di
   GitHub, prova l'eseguibile creando un report e pubblica installer ed eseguibile portatile tra gli «Artifacts» (e
   nella release, se si pubblica un tag `vX.Y.Z`).

File coinvolti: `packaging/flight_analyzer.spec` (PyInstaller), `packaging/setup.iss` (Inno Setup: lingua,
collegamenti, associazione `.ulg`), `packaging/avvio_app.py` (punto di ingresso). La versione si cambia in
`flight_analyzer/__init__.py` (e in `pyproject.toml`).

L'icona e i loghi (team e Politecnico) stanno in `flight_analyzer/resources`. L'icona (risposta al gradino con il logo
di Zefiro) si rigenera con `tools/crea_icona.py`, che richiede Pillow.

**Antivirus.** Gli eseguibili creati con PyInstaller e non firmati a volte vengono segnalati da Windows SmartScreen
(«Ulteriori informazioni → Esegui comunque»).

## Traduzioni

I testi sono scritti in italiano nel codice, marcati con `_()` (o `N_()` per le costanti), e tradotti in inglese in
`flight_analyzer/i18n_en.py`. `python tests/check_i18n.py` controlla che ogni testo abbia la traduzione, che i
segnaposto `{nome}` coincidano e che nessun modulo usi `_` come variabile (romperebbe la traduzione). Per aggiungere
una lingua basta un altro catalogo con la stessa struttura e una voce in `i18n.SUPPORTED`.

## Limiti noti

- I margini di stabilità sono calcolati solo per l'anello di rate multicottero, dove la legge di controllo PX4 è nota.
  Per l'ala fissa i guadagni dipendono dalla velocità all'aria e il modello non è incluso.
- In ala fissa l'imbardata non ha un anello d'assetto (c'è la coordinazione di virata) e non viene valutata.
- Le soglie su rumore, saturazione e integratore sono euristiche: vanno ritarate sul proprio velivolo dopo i primi
  voli.
- Nei modi con controllo di posizione il setpoint d'assetto contiene a sua volta una retroazione lenta, quindi la
  stima dell'anello d'assetto può risentirne alle basse frequenze.
- Sui log sintetici il ritardo della stima FIR esce qualche millisecondo più corto di quello vero (−3…−7%), anche
  dopo la correzione del mezzo campione: per chiudere un asse fanno fede le prove a gradino.
- I gradini d'assetto si cercano solo su rollio e beccheggio; l'imbardata d'assetto (direzione assoluta) no.

## Struttura

```
flight_analyzer/
  ulog.py       lettore ULog
  logdata.py    serie temporali, modi di volo, fasi VTOL, riepilogo
  dsp.py        ricampionamento, spettri, decimazione
  loopid.py     identificazione (FIR, variabili strumentali, jackknife), metriche, margini
  scoring.py    profili (PX4 standard, Vespa hover), soglie, punteggi
  analysis.py   selezione dati, metriche aggiuntive, affidabilità, diagnosi
  modes.py      tratti per tipo di comando (vehicle_control_mode), transitori ai cambi di modo, saturazione, avvisi
  steptest.py   prove a gradino: rilevamento, grandezze, scarti, riepilogo, tenuta, CSV e PNG
  flags.py      flag sollevati (failsafe, failure detector, EKF2, batteria)
  plots.py      grafici matplotlib
  report.py     report PDF, HTML e JSON
  config.py     impostazioni (unità, grafici, schede, esportazione)
  theme.py      colori del team, tema chiaro e scuro
  i18n.py       traduzione; i18n_en.py catalogo inglese
  gui.py        interfaccia PySide6
  resources/    icona e loghi
packaging/      PyInstaller e installer (Inno Setup)
tests/          simulatore, generatori di log (VTOL, prove a gradino del Vespa), validazioni, regressione sui log veri,
                prova della GUI, controllo delle traduzioni
tools/          generazione dell'icona
profili/        profili di valutazione: px4_standard.json (predefinito) e vespa_hover.json (scheda di taratura)
```
