# MRP — Project Work 27 · Nuova versione JSON indipendente

Software Python per **pianificazione dei fabbisogni di materiali (MRP)** su distinta base multilivello, con dashboard **Streamlit**, tabelle **pandas** e grafici interattivi **Plotly**. È pronto con l'esempio della **centralina BLE/Wi-Fi ESP32 + scheda relè**.

**Cambiamento principale rispetto alla versione precedente:** il file `data/progetto_centralina.json` **non contiene la matricola, il nome, il cognome o la sezione `parametri_personali`**. I valori ottenuti dalle formule universitarie sono già inseriti come normali dati numerici, come accadrebbe in un archivio aziendale. Il motore MRP non legge dati personali e può caricare **altre distinte base nel medesimo formato JSON**, senza modifiche al codice.

## 1. Installazione e avvio su Windows

**Requisito:** installare Python 3.10 o successivo (preferibilmente 3.11 o 3.12) e avere una connessione Internet durante la prima installazione delle librerie.

1. Estrai completamente il file ZIP in una cartella, per esempio `Documenti\MRP_PW27`.
2. Fai doppio clic su **`AVVIA_WINDOWS.bat`**. Il programma prepara l'ambiente e installa le librerie richieste.
3. Si apre la dashboard nel browser. Se non si apre automaticamente, visita **http://localhost:8501**.
4. Per interrompere l'applicazione chiudi il terminale o premi `Ctrl+C`.

### In alternativa: avvio manuale dal terminale

Da PowerShell o dal terminale integrato di Visual Studio Code, **nella cartella estratta**:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

Questi comandi non richiedono l'attivazione dello script PowerShell e quindi evitano il problema della policy di esecuzione. Se su Windows `python` non funziona, prova `py -3` al primo comando.

Su Linux/macOS puoi eseguire `./avvia_linux_mac.sh` oppure usare `python3 -m venv .venv`, poi i corrispondenti comandi `.venv/bin/python ...`.

## 2. Come usare la dashboard

Il progetto dimostrativo viene letto automaticamente da `data/progetto_centralina.json`. Per usarne un altro, carica un file `.json` tramite **"Carica un altro progetto JSON"** nella barra laterale. Non c'è alcun campo per la matricola.

Le schede della dashboard sono:

- **Panoramica:** domanda settimanale, numero ordini, articoli acquistati, scorta media e urgenze.
- **Distinta base:** albero a colori con livelli, collegamenti padre→figlio, quantità di impiego, identificazione dei componenti comuni; tabella BOM completa ed esportazione CSV. Il diagramma è abbreviato per default; un interruttore mostra tutti i componenti.
- **Record MRP:** seleziona un articolo nella barra laterale per vedere il grafico Plotly, gli otto periodi, gli arrivi, i fabbisogni netti e gli ordini pianificati. È esportabile in CSV.
- **Piano ordini:** ordini per produzione e acquisto con quantità, settimana di emissione e arrivo, tipo, regola e segnalazione "da sollecitare"; esportazione **del piano completo in CSV**, leggibile con Excel/ONLYOFFICE.
- **Confronto scenari:** BASE (regole per articolo), TUTTI_L4L e TUTTI_POQ. Vengono confrontati numero ordini, quantità e scorta media prevista.
- **Archivio e JSON:** tutti i parametri articolo, arrivi programmati, domanda settimanale e file JSON scaricabile.

Gli scenari di confronto sostituiscono le politiche di lottizzazione **solo nei calcoli in memoria**, lasciando intatti i dati del file caricato. Nello scenario BASE il prodotto finito rimane FOQ; negli scenari TUTTI_L4L e TUTTI_POQ si confronta il comportamento ipotetico con una regola unica per *tutti* gli articoli, compreso il finito.

## 3. Quali file contiene lo ZIP?

```text
MRP_PW27_NuovaVersione/
  AVVIA_WINDOWS.bat
  avvia_linux_mac.sh
  app.py                         dashboard Streamlit
  mrp_engine.py                  validazione JSON, esplosione e lottizzazione MRP
  esegui_mrp.py                  calcolo ed esportazione senza Streamlit
  requirements.txt
  README.md
  GUIDA_JSON.md                  struttura dati, estratti utilizzabili nell'elaborato
  data/
    progetto_centralina.json    30 articoli, BOM completa, NO dati personali
    esempio_prodotto_alternativo.json  un secondo prodotto per provare il riuso
  documentazione/
    BOM_BLE_Board_2026-10-16.csv
    BOM_relayboard_2026-10-16.csv
  tests/
    test_mrp.py                  verifiche matematiche e dei vincoli
```

## 4. Dati del prodotto usato nel Project Work

I numeri seguenti sono **input già calcolati** secondo la traccia; il software li tratta come dati di progetto e non ha bisogno della matricola.

| Parametro | Valore |
|---|---:|
| Prodotto finito | `FIN001` |
| Orizzonte | 8 settimane |
| Domanda settimanale | `[30, 20, 75, 65, 55, 45, 35, 25]` |
| Giacenza iniziale finito | 130 |
| Scorta sicurezza finito e acquistati | 35 |
| Regola prodotto finito | FOQ |
| Lotto fisso finito | 140 |
| Periodo POQ | 3 settimane |
| Lead time finito | 2 settimane |

La BOM comprende **30 codici articolo**, 30 relazioni padre-figlio, tre livelli 0–1–2, due schede prodotte internamente (`ASS_BLE`, `ASS_RELE`) e materiali acquistati. Il LED **`CMP_C84267`** è un **unico articolo magazzino condiviso** fra i due sottoassiemi; il suo fabbisogno viene aggregato prima della lottizzazione. Sono presenti coefficienti di impiego 2 e 3 e arrivi programmati di almeno due articoli.

### Valori attesi del motore sull'esempio

| Scenario | N. ordini | Quantità totale | Scorta media prevista |
|---|---:|---:|---:|
| BASE | 58 | 12.275 | 39,44 |
| TUTTI_L4L | 150 | 11.070 | 33,44 |
| TUTTI_POQ | 33 | 11.070 | 69,67 |

La **quantità totale** è la somma di pezzi di SKU diversi, quindi non costituisce una misura di prodotti omogenei; l'indicatore di scorta media è la media delle **giacenze previste di ogni SKU su ogni settimana**, non una valorizzazione economica.

## 5. Come caricare un'altra distinta base

L'altro JSON incluso, **`data/esempio_prodotto_alternativo.json`**, descrive un diverso kit con propria BOM, domanda, scorte e politiche: serve per provare che non è necessario modificare `app.py` o `mrp_engine.py`.

Per crearne uno tuo:

1. Assegna un **codice unico** a ogni articolo nell'array `articoli`.
2. Indica per ciascuno `descrizione`, `provenienza`, `lead_time`, `giacenza_iniziale`, `scorta_sicurezza`, `regola_lotto` e gli eventuali `lotto_foq`, `periodo_poq`, `arrivi_programmati`.
3. Inserisci i legami `padre`, `componente`, `quantita` nell'array `distinta_base`.
4. Inserisci `prodotto_finito`, `orizzonte_settimane` e l'array `fabbisogni` della stessa lunghezza dell'orizzonte.
5. Caricalo dal pannello laterale; l'app verifica eventuali codici mancanti, duplicati, cicli e articoli scollegati.

**Importante:** la traccia universitaria richiede otto settimane, perciò il file della centralina ne contiene 8. Il motore è capace di gestire anche altri orizzonti con un'altra configurazione JSON, per il suo riutilizzo in contesti differenti.

## 6. Avvio senza dashboard e verifica dei calcoli

Puoi calcolare gli ordini direttamente dal terminale, senza installare Streamlit:

```powershell
python esegui_mrp.py --input data/progetto_centralina.json --scenario ORIGINALE --out output_mrp
```

Questo comando genera `piano_ordini.csv`, `riepilogo.json` e **un file CSV di record MRP per ogni articolo** nella cartella `output_mrp/`. L'output è calcolato al momento, non precompilato nel file di input.

Esegui i test del motore (si basano solo sulle librerie standard):

```powershell
python -m unittest discover -s tests -v
```

I test verificano i parametri del finito, le giacenze delle 8 settimane, le 3 politiche di lottizzazione, i totali, il legame fra rilasci padre e domande dei figli, l'aggregazione del componente comune, la validazione BOM e l'indipendenza da altre configurazioni JSON.

## 7. Precisazioni sul funzionamento e limiti della simulazione

- I fabbisogni dei componenti derivano dalle **emissioni degli ordini pianificati dei rispettivi padri**, moltiplicate per i coefficienti di impiego. Non vengono generati semplicemente moltiplicando la domanda finale per la BOM.
- L'MRP conserva la vera settimana di rilascio degli ordini anche quando è `0` o negativa e li marca **"DA SOLLECITARE"**. Se un rilascio di un padre genera fabbisogni di componenti **prima della settimana 1**, questi ultimi sono riportati in settimana 1 per una simulazione didattica con avviso esplicito. Non rappresenta un'esatta ricostruzione del magazzino in periodi precedenti, per la quale servirebbero saldi e ricevimenti storici.
- I valori delle giacenze, dei lead time, delle politiche e degli arrivi programmati non imposti dalla traccia sono **ipotesi didattiche**. Vanno adeguati prima dell'impiego aziendale.
- I due PCB nudi `PCB_BLE` e `PCB_RELE` sono stati aggiunti alla BOM MRP perché non erano presenti come componenti fisici nelle esportazioni EasyEDA. La quantità del connettore femmina relè è stata impostata a 2 per la configurazione prevista: la relativa BOM CAD originaria ne indicava una. **Verificare e allineare EasyEDA** prima di fabbricare le schede.
- Il solo articolo comune fra i due rami è il LED `CMP_C84267`. Le resistenze da 22,1 kΩ dei due PCB hanno codici e footprint diversi, quindi restano SKU distinti.
- L'esportazione CSV **non trasmette ordini ai fornitori**: crea un piano consultabile da responsabile acquisti, produzione e magazzino.
- La dashboard è **locale** e non comprende login, database centrale, connessioni MQTT o aggiornamenti magazzino in tempo reale. Queste funzioni restano possibili sviluppi futuri.

## 8. Per l'elaborato

Inserisci le figure della BOM semplificata e della centralina, poi i calcoli universitari **nel testo della relazione**. Usa `GUIDA_JSON.md` per mostrare piccoli estratti del JSON, spiegando che tutti gli altri componenti sono presenti nel file completo. Presenta un esempio numerico del record FIN001 e le tabelle di confronto BASE/TUTTI_L4L/TUTTI_POQ, evidenziando i limiti degli ordini ante-S1.
