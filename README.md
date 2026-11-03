# MRP — Project Work 27

Applicazione Python per la **pianificazione dei fabbisogni di materiali (MRP)** su distinta base multilivello, con dashboard **Streamlit**, tabelle **pandas** e grafici interattivi **Plotly**.

## Gestione dei dati

Il progetto carica di default un esempio basato su una centralina BLE/Wi-Fi ESP32 con scheda relè.
Per testare l’applicativo con un prodotto diverso, è possibile utilizzare il pulsante Upload e 
caricare il file JSON alternativo (progetto bicicletta) incluso nella cartella data.
L’applicativo mantiene separati i dati del prodotto dal motore di calcolo MRP: legge dal file 
JSON gli articoli, la distinta base, le giacenze e i parametri di pianificazione, quindi esegue 
i calcoli e visualizza i risultati. È quindi possibile analizzare prodotti diversi senza modificare
il codice, purché i file JSON rispettino la struttura prevista.


## Installazione e avvio su Windows

### Requisiti

- **Python 3.10 o successivo**, preferibilmente 3.11 o 3.12.
- Una connessione Internet durante la prima installazione delle librerie.

### Avvio automatico

1. Scarica il progetto e, se è in formato ZIP, estrailo completamente in una cartella, ad esempio `Documenti\MRP_PW27`.
2. Apri la cartella che contiene `app.py` e fai doppio clic su `AVVIA_WINDOWS.bat`.
3. Il programma prepara l’ambiente e installa le librerie richieste.
4. La dashboard si apre nel browser. Se non si apre automaticamente, visita [http://localhost:8501](http://localhost:8501).
5. Per interrompere l’applicazione, premi `Ctrl+C` nel terminale oppure chiudi la finestra del terminale.

### Avvio manuale

Apri PowerShell o il terminale integrato di Visual Studio Code nella cartella che contiene `app.py`, quindi esegui:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Una volta avviata l’applicazione, apri [http://localhost:8501](http://localhost:8501) nel browser.

Per gli avvii successivi è sufficiente eseguire:

```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```
