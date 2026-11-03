# Come spiegare il file JSON nell'elaborato PW 27

## Testo introduttivo (adattabile)

> Dopo aver calcolato i parametri previsti dalla traccia e definito la distinta base multilivello, ho organizzato le informazioni necessarie alla pianificazione in un file JSON. Le sezioni principali contengono i fabbisogni settimanali, l'archivio degli articoli e le relazioni padre-figlio della distinta base. Non è necessario inserire la matricola nel file: il programma utilizza i valori numerici già calcolati. La separazione dei dati dal motore Python consente di caricare anche altri prodotti senza intervenire sull'algoritmo.

## Estratto 1 — Dati generali e domanda del finito

Estratto illustrativo di campi realmente presenti nel JSON della centralina:

```json
{
  "prodotto_finito": "FIN001",
  "orizzonte_settimane": 8,
  "periodo_poq": 3,
  "fabbisogni": [30, 20, 75, 65, 55, 45, 35, 25]
}
```

## Estratto 2 — Un articolo dell'archivio

**È un solo elemento** dell'array `articoli`, non il file completo:

```json
{
  "codice": "FIN001",
  "descrizione": "Centralina BLE ESP32 + scheda relè, programmata e collaudata",
  "provenienza": "PRODOTTO",
  "lead_time": 2,
  "giacenza_iniziale": 130,
  "scorta_sicurezza": 35,
  "regola_lotto": "FOQ",
  "lotto_foq": 140,
  "periodo_poq": 3,
  "arrivi_programmati": []
}
```

## Estratto 3 — Gerarchia della distinta base

È un estratto dell'array `distinta_base`, non la lista completa:

```json
{
  "distinta_base": [
    {"padre": "FIN001", "componente": "ASS_BLE", "quantita": 1},
    {"padre": "FIN001", "componente": "ASS_RELE", "quantita": 1},
    {"padre": "ASS_BLE", "componente": "CMP_C84267", "quantita": 1, "riferimenti_pcb": "LED1"},
    {"padre": "ASS_RELE", "componente": "CMP_C84267", "quantita": 1, "riferimenti_pcb": "LED1"}
  ]
}
```

Le due righe finali mostrano il **medesimo articolo LED C84267** impiegato dai due sottoassiemi: quando la BOM viene esplosa, il motore somma il fabbisogno del LED derivante da entrambi i padri.

## Come presentarlo senza sovraccaricare la relazione

Puoi inserire tre brevi **screenshot di Visual Studio Code** (inizio del JSON, anagrafica FIN001, alcune righe della distinta base), aggiungendo una didascalia che precisi **"estratti: il file contiene tutti i 30 articoli e la distinta base completa"**. Successivamente descrivi `mrp_engine.py` e `app.py`, e presenta le tabelle MRP effettivamente calcolate. Non affermare che le tabelle MRP siano già contenute nel file JSON: esse vengono prodotte dal motore e possono essere esportate come CSV.
