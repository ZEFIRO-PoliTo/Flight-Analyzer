# Domande frequenti

**L'app dice «Nessun gradino trovato».**
I gradini di velocità angolare si cercano solo in Acro e in Offboard a velocità angolare, quelli d'assetto in
Stabilized e in Offboard d'assetto. Per i log dell'autotune (gradini in Hold) attivare «Ignora il modo».

**Perché il punteggio dell'Analisi PID è diverso dall'esito delle prove a gradino?**
La stima FIR dà una risposta media su tutto il volo, le prove a gradino guardano il caso peggiore di ogni gradino.
Per chiudere un asse fa fede la scheda «Prove a gradino». Con il profilo «Vespa hover» le definizioni sono le stesse.

**Affidabilità bassa: cosa devo volare?**
Il messaggio lo dice (es. «3 doppietti a 45 °/s, partendo in piano e da fermo»). Gradini più piccoli non servono.

**«Possibile PX4 senza la correzione dell'allocatore del tiltrotor».**
In hover torque_setpoint_achieved è quasi sempre falso: il firmware non ha la correzione. Rifare la prova con il
firmware corretto.

**Il .ulg è troppo grande per allegarlo a una issue.**
Caricarlo nella cartella condivisa del team e mettere il link nella issue.
