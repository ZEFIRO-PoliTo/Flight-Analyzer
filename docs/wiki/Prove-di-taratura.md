# Prove di taratura in hover (Vespa)

## Prima del volo
1. `SDLOG_PROFILE = 17` (predefinito + alta frequenza). Con 131 o senza il bit 16 l'app dà un avviso.
2. Un log = un volo = una configurazione di parametri: niente cambi di guadagni in volo.
3. PX4 con la correzione dell'allocatore del tiltrotor (altrimenti l'app avvisa e le misure non valgono).

## In volo (script `gradini_vespa.py`)
- 3 doppietti per asse: rollio e beccheggio 45 °/s per 0,5 s, imbardata 30 °/s per 1,5 s; assetto 10° per 1,5 s.
- Ogni verso è un gradino separato che parte con il velivolo **in piano e fermo**: tra un verso e l'altro serve
  l'Hold. Un gradino che parte inclinato (> 2°), in rotazione (> 5 °/s) o in movimento (> 0,5 m/s) viene scartato.
- Poi 60 s fermi in Hold senza toccare gli stick (tenuta).

## Nell'app
1. Aprire il log, scheda **Prove a gradino**.
2. Controllare gli avvisi in alto e i gradini scartati con il motivo.
3. Nel riepilogo: per ogni asse e verso mediana / caso peggiore; verde = caso peggiore entro il criterio.
   L'asse è **tarato** solo se tutto è verde in entrambi i versi, con almeno 3 gradini validi per verso.
4. **Esporta PNG e CSV** e allegare i file alla scheda di taratura.
5. Per una serie con P crescente: `FlightAnalyzer.exe gradini P020.ulg P026.ulg P031.ulg` stampa il confronto.
