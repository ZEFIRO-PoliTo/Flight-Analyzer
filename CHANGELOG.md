# Novità delle versioni

## 1.2.0 — novembre 2026
- Nuova scheda **Prove a gradino**: misura diretta di ogni gradino (ritardo, sovraelongazione, assestamento, errore,
  rimbalzi, saturazione dei motori), gradini scartati con il motivo, caso peggiore per asse e verso, esito «tarato»,
  tenuta in Hold/Position, PNG per gradino e CSV; comando `gradini`; sezione nel report.
- Nuovo profilo **Vespa hover** (`profili/vespa_hover.json`) con le definizioni e i criteri della scheda di taratura.
- Stima FIR: i gradini in Offboard a velocità angolare ora entrano nella stima (tratti esterni da
  `vehicle_control_mode`); l'anello d'assetto esclude i tratti senza setpoint d'assetto.
- I 50 ms dopo ogni cambio di modo sono esclusi da stima, saturazione e prove a gradino.
- Saturazione misurata su `actuator_motors` a piena frequenza; avviso «Possibile PX4 senza la correzione
  dell'allocatore del tiltrotor».
- Consigli: «ridurre FF» solo se FF > 0; «livello a fine finestra» al posto di «a regime».
- Affidabilità dai gradini validi nei voli di prove a gradino.

## 1.1.0 — novembre 2026
- Installer ed eseguibile portatile per Windows, interfaccia in italiano e inglese, finestra delle impostazioni,
  tema chiaro/scuro nei colori del team.
- Nuove schede: Potenza, Motori e servi, Giri motore, Flag sollevati; densità spettrale di potenza nel tempo.
- Navigazione dei grafici con rotella e trascinamento, menu «Vai a»; report PDF diretto.

## 1.0.0 — ottobre 2026
- Prima versione: viste in stile Flight Review, analisi PID con punteggio 0–100, incertezza, margini di
  stabilità, confronto tra log, report HTML.
