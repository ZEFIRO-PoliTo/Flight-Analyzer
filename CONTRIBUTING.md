# Contribuire a Flight Analyzer

Grazie! Questa pagina spiega come proporre una modifica senza rompere niente a chi usa l'app.

## Le regole in una riga

`main` contiene sempre una versione funzionante. Nessuno scrive direttamente su `main`: ogni modifica parte da un ramo
(*branch*), arriva come *pull request*, passa i test automatici e viene approvata da un manutentore.

## Preparare l'ambiente

```bash
git clone <indirizzo del repository>
cd FlightAnalyzer
python -m venv .venv
.venv\Scripts\activate              # Windows   (Linux/macOS: source .venv/bin/activate)
pip install -r requirements.txt
python -m flight_analyzer           # deve aprirsi l'app
```

Chi non usa la riga di comando può fare tutto con **GitHub Desktop** (Clone, Branch, Commit, Push, Create pull request).

## Il percorso di una modifica

1. **Issue.** Se non c'è già, aprire una issue che descrive il problema o la richiesta e assegnarsela, così due persone
   non lavorano sulla stessa cosa.
2. **Ramo.** Partendo da `main` aggiornato, creare un ramo con un nome che dica cosa fa:
   `fix/ritardo-gradini-assetto`, `feature/scheda-taratura-pdf`, `docs/guida-autotune`.
3. **Modifiche e commit.** Commit piccoli, con un messaggio che dice *cosa* e *perché*:
   `Prove a gradino: scarta i gradini con flag di failsafe attivo`.
4. **Test in locale** (vedi sotto).
5. **Pull request** verso `main`. Nella descrizione: cosa cambia, come è stato provato, `Chiude #<numero issue>`.
6. **Revisione.** Un manutentore legge, commenta, chiede modifiche o approva. Le modifiche richieste si fanno sullo
   stesso ramo: la pull request si aggiorna da sola.
7. **Merge.** Lo fa il manutentore («Squash and merge»): su `main` resta un commit per pull request.

Chi non ha i permessi di scrittura fa lo stesso partendo da un *fork* (copia del repository nel proprio account).

## Test da lanciare prima della pull request

```bash
python tests/check_i18n.py          # ogni testo nuovo ha la traduzione inglese
python tests/check_steptest.py      # prove a gradino su segnali e log sintetici
python tests/make_synthetic_log.py volo_B.ulg --taratura B
python tests/check_synthetic.py volo_B.ulg
python tests/validate_loopid.py     # identificazione contro il simulatore
```

Gli stessi test girano da soli su GitHub a ogni pull request (scheda **Actions**): la pull request si può unire solo
se sono verdi. Chi tocca l'interfaccia lancia anche `tests/smoke_gui.py` (vedi l'intestazione del file).

Chi ha i log veri del Vespa lancia anche `python tests/regressione_vespa.py <log...>`: confronta i risultati con le
misure di riferimento. I log non vanno nel repository (sono troppo grandi): stanno nella cartella condivisa del team.

## Regole del codice

- **Testi dell'interfaccia** sempre con `_("…")` (o `N_("…")` per le costanti) e la traduzione in
  `flight_analyzer/i18n_en.py`. Mai usare `_` come nome di variabile nei moduli che la importano.
- **Soglie e criteri** nei profili JSON (`profili/`), non nel codice.
- **Funzioni esistenti**: non cambiarne il comportamento senza dirlo nella pull request e nel CHANGELOG.
- **Unità**: angoli in radianti dentro l'analisi, gradi solo per mostrare; tempi in secondi dall'inizio del log.
- **Dipendenze nuove**: da discutere prima in una issue (pesano sull'eseguibile).

## Versioni e release (solo manutentori)

Numerazione `MAGGIORE.MINORE.CORREZIONE` (es. 1.2.0 → 1.2.1 per una correzione, 1.3.0 per una funzione nuova).

1. Aggiornare la versione in `flight_analyzer/__init__.py` e `pyproject.toml` e la sezione in `CHANGELOG.md`, con una
   pull request come le altre.
2. Dopo il merge: **Releases → Draft a new release → Choose a tag → `v1.2.1`** (nuovo tag su `main`), titolo
   `Flight Analyzer 1.2.1`, note copiate dal CHANGELOG, **Publish release**.
3. L'azione «Build Windows» parte da sola, controlla che il tag coincida con la versione nel codice, crea
   installer ed eseguibile portatile e li allega alla release (circa 15 minuti, scheda **Actions**).
