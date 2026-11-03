"""Motore MRP multilivello indipendente da Streamlit e dal prodotto.

Convenzioni:
- Settimane 1..N (N = len(fabbisogni) = orizzonte_settimane).
- Domanda dipendente generata dai RILASCI dei padri (non dagli arrivi).
- Un articolo condiviso da più padri è elaborato una sola volta, dopo
  aver aggregato le richieste da tutti i suoi padri (ordinamento topologico).
- Ordini da emettere prima della settimana 1 conservano la data originale.
  Per rendere visibili i fabbisogni dei figli ante-S1 senza un inventario storico,
  questi ultimi sono aggregati nella settimana 1 con un avviso esplicito:
  è una convenzione didattica, non un ripianificatore dei periodi passati.
"""

from collections import defaultdict, deque
from math import ceil

SCENARI = ('ORIGINALE', 'TUTTI_L4L', 'TUTTI_POQ')


def _intero(value, label, minimo=0):
    if type(value) is not int or value < minimo:
        raise ValueError(f"{label}: atteso numero intero >= {minimo}")
    return value


def valida_progetto(progetto):
    """Valida un file JSON e restituisce un indice BOM, senza modificarlo."""
    if not isinstance(progetto, dict):
        raise ValueError('La radice del JSON deve essere un oggetto')
    for campo in ('prodotto_finito', 'articoli', 'distinta_base', 'fabbisogni'):
        if campo not in progetto:
            raise ValueError(f"Manca il campo obbligatorio '{campo}'")
    fabbisogni = progetto['fabbisogni']
    if not isinstance(fabbisogni, list) or not fabbisogni:
        raise ValueError('fabbisogni deve essere una lista non vuota')
    orizzonte = _intero(progetto.get('orizzonte_settimane', len(fabbisogni)),
                        'orizzonte_settimane', 1)
    if orizzonte != len(fabbisogni):
        raise ValueError('Lunghezza di fabbisogni diversa da orizzonte_settimane')
    for index, quantita in enumerate(fabbisogni, 1):
        _intero(quantita, f'fabbisogni[{index}]')
    poq_generale = _intero(progetto.get('periodo_poq', 3), 'periodo_poq', 1)

    lista_articoli = progetto['articoli']
    if not isinstance(lista_articoli, list) or not lista_articoli:
        raise ValueError('articoli deve essere una lista non vuota')
    articoli = {}
    for index, articolo in enumerate(lista_articoli):
        if not isinstance(articolo, dict):
            raise ValueError(f'articoli[{index}] non è un oggetto')
        sku = articolo.get('codice')
        if not isinstance(sku, str) or not sku.strip() or sku in articoli:
            raise ValueError(f'Codice articolo mancante o duplicato: {sku}')
        if not isinstance(articolo.get('descrizione'), str) or not articolo['descrizione'].strip():
            raise ValueError(f'Descrizione articolo mancante: {sku}')
        if articolo.get('provenienza') not in ('ACQUISTATO', 'PRODOTTO'):
            raise ValueError(f'Provenienza non valida per {sku}: usare ACQUISTATO o PRODOTTO')
        _intero(articolo.get('lead_time'), f'lead_time di {sku}', 1)
        _intero(articolo.get('giacenza_iniziale'), f'giacenza_iniziale di {sku}')
        _intero(articolo.get('scorta_sicurezza'), f'scorta_sicurezza di {sku}')
        metodo = articolo.get('regola_lotto')
        if metodo not in ('FOQ', 'POQ', 'L4L'):
            raise ValueError(f'Regola lottizzazione non valida per {sku}')
        if metodo == 'FOQ':
            _intero(articolo.get('lotto_foq'), f'lotto_foq di {sku}', 1)
        if metodo == 'POQ':
            _intero(articolo.get('periodo_poq', poq_generale), f'periodo_poq di {sku}', 1)
        if 'periodo_poq' in articolo and articolo['periodo_poq'] is not None:
            _intero(articolo['periodo_poq'], f'periodo_poq di {sku}', 1)
        arrivi = articolo.get('arrivi_programmati', [])
        if not isinstance(arrivi, list):
            raise ValueError(f'arrivi_programmati di {sku} deve essere una lista')
        for arrivo in arrivi:
            if not isinstance(arrivo, dict):
                raise ValueError(f'Arrivo programmato non valido per {sku}')
            settimana = _intero(arrivo.get('settimana'), f'settimana arrivo di {sku}', 1)
            if settimana > orizzonte:
                raise ValueError(f'Arrivo programmato di {sku} oltre orizzonte')
            _intero(arrivo.get('quantita'), f'quantità arrivo di {sku}', 1)
        articoli[sku] = articolo

    finito = progetto['prodotto_finito']
    if finito not in articoli or articoli[finito]['provenienza'] != 'PRODOTTO':
        raise ValueError('prodotto_finito deve essere un codice presente e prodotto internamente')
    links = progetto['distinta_base']
    if not isinstance(links, list):
        raise ValueError('distinta_base deve essere una lista')
    figli, genitori, archi = defaultdict(list), defaultdict(list), set()
    for link in links:
        if not isinstance(link, dict):
            raise ValueError('Ogni riga della distinta base deve essere un oggetto')
        padre, figlio = link.get('padre'), link.get('componente')
        qty = _intero(link.get('quantita'), f'quantita nel legame {padre}->{figlio}', 1)
        if padre not in articoli or figlio not in articoli:
            raise ValueError(f'Articolo sconosciuto nel legame {padre}->{figlio}')
        if padre == figlio or (padre, figlio) in archi:
            raise ValueError(f'Legame ciclico diretto o duplicato {padre}->{figlio}')
        if articoli[padre]['provenienza'] != 'PRODOTTO':
            raise ValueError(f'Articolo acquistato {padre} non può essere padre nella BOM')
        archi.add((padre, figlio))
        figli[padre].append((figlio, qty))
        genitori[figlio].append((padre, qty))
    if genitori[finito]:
        raise ValueError('Il prodotto finito non può essere figlio di un altro articolo')
    # Kahn: il nodo comune aspetta tutti i padri.
    grado = {sku: len(genitori[sku]) for sku in articoli}
    coda = deque(sku for sku in articoli if grado[sku] == 0)
    ordine = []
    while coda:
        padre = coda.popleft()
        ordine.append(padre)
        for figlio, _ in figli[padre]:
            grado[figlio] -= 1
            if grado[figlio] == 0:
                coda.append(figlio)
    if len(ordine) != len(articoli):
        raise ValueError('La distinta base contiene un ciclo')
    raggiungibili = {finito}
    pending = [finito]
    while pending:
        for figlio, _ in figli[pending.pop()]:
            if figlio not in raggiungibili:
                raggiungibili.add(figlio)
                pending.append(figlio)
    fuori_bom = set(articoli) - raggiungibili
    if fuori_bom:
        raise ValueError('Articoli non collegati al prodotto finito: ' + ', '.join(sorted(fuori_bom)))
    livelli = {finito: 0}
    for padre in ordine:
        for figlio, _ in figli[padre]:
            livelli[figlio] = max(livelli.get(figlio, 0), livelli[padre] + 1)
    return {'articoli': articoli, 'figli': dict(figli), 'genitori': dict(genitori),
            'ordine': ordine, 'livelli': livelli, 'orizzonte': orizzonte,
            'periodo_poq': poq_generale}


def calcola_mrp(progetto, scenario='ORIGINALE'):
    """Esegue l'esplosione multilivello e restituisce record, ordini e indicatori.

    Nessuna modifica ai dati di input: TUTTI_L4L e TUTTI_POQ sono simulazioni.
    """
    if scenario not in SCENARI:
        raise ValueError('Scenario non riconosciuto: ' + str(scenario))
    m = valida_progetto(progetto)
    n = m['orizzonte']
    richieste = {sku: defaultdict(int) for sku in m['articoli']}
    pre_origini = {sku: defaultdict(int) for sku in m['articoli']}
    for t, valore in enumerate(progetto['fabbisogni'], 1):
        richieste[progetto['prodotto_finito']][t] = valore
    records, ordini, avvisi = {}, [], []

    for sku in m['ordine']:
        a = m['articoli'][sku]
        metodo = (a['regola_lotto'] if scenario == 'ORIGINALE'
                  else ('L4L' if scenario == 'TUTTI_L4L' else 'POQ'))
        periodo = a.get('periodo_poq') or m['periodo_poq']
        if metodo == 'POQ':
            _intero(periodo, f'periodo_poq di {sku}', 1)
        lotto = a.get('lotto_foq')
        sicurezza = a['scorta_sicurezza']
        programmati = defaultdict(int)
        for arrivo in a.get('arrivi_programmati', []):
            programmati[arrivo['settimana']] += arrivo['quantita']
        richieste_pre = {t: q for t, q in richieste[sku].items() if t < 1 and q > 0}
        quantita_urgente = sum(richieste_pre.values())
        grossi = {t: richieste[sku][t] for t in range(1, n + 1)}
        if quantita_urgente:
            grossi[1] += quantita_urgente
            dettagli = ', '.join(f'S{t}: {q}' for t, q in sorted(richieste_pre.items()))
            avvisi.append(f'{sku}: richieste ante-orizzonte ({dettagli}) aggregate in S1 '
                          'per simulazione; verificare consegne urgenti.')
        saldo = a['giacenza_iniziale']
        tabella = []
        for settimana in range(1, n + 1):
            programmato = programmati[settimana]
            lordo = grossi[settimana]
            senza_ricezione = saldo + programmato - lordo
            fabbisogno_netto = max(0, sicurezza - senza_ricezione)
            ricevuto = 0
            if fabbisogno_netto > 0:
                if metodo == 'L4L':
                    ricevuto = fabbisogno_netto
                elif metodo == 'FOQ':
                    ricevuto = ceil(fabbisogno_netto / lotto) * lotto
                else:
                    # Period order quantity: copre il picco massimo del deficit
                    # nel blocco di P settimane, inclusi gli arrivi già confermati.
                    saldo_proiettato = saldo
                    deficit_massimo = 0
                    ultima = min(n, settimana + periodo - 1)
                    for futura in range(settimana, ultima + 1):
                        saldo_proiettato += programmati[futura] - grossi[futura]
                        deficit_massimo = max(deficit_massimo, sicurezza - saldo_proiettato)
                    ricevuto = max(0, deficit_massimo)
                emissione = settimana - a['lead_time']
                ordini.append({
                    'Codice': sku, 'Articolo': a['descrizione'], 'Quantità': ricevuto,
                    'Settimana emissione': emissione, 'Settimana arrivo': settimana,
                    'Origine': ('Acquisto' if a['provenienza'] == 'ACQUISTATO' else 'Produzione'),
                    'Regola': metodo,
                    'Stato': ('DA SOLLECITARE (prima S1)' if emissione < 1 else 'Pianificato'),
                })
                if emissione < 1:
                    avvisi.append(f'{sku}: ordine di {ricevuto} unità da emettere in '
                                  f'S{emissione} per arrivo in S{settimana}: da sollecitare.')
                for figlio, coefficiente in m['figli'].get(sku, []):
                    richiesta = ricevuto * coefficiente
                    richieste[figlio][emissione] += richiesta
                    if emissione < 1:
                        pre_origini[figlio][emissione] += richiesta
            saldo = senza_ricezione + ricevuto
            tabella.append({
                'Settimana': settimana,
                'Fabbisogni lordi': lordo,
                'di cui anticipati': quantita_urgente if settimana == 1 else 0,
                'Arrivi programmati': programmato,
                'Fabbisogni netti': fabbisogno_netto,
                'Arrivi pianificati': ricevuto,
                'Emissioni pianificate': 0,
                'Giacenza prevista': saldo,
            })
        records[sku] = tabella

    emissioni_per_articolo = defaultdict(lambda: defaultdict(int))
    for ordine in ordini:
        emissioni_per_articolo[ordine['Codice']][ordine['Settimana emissione']] += ordine['Quantità']
    for sku, tabella in records.items():
        for riga in tabella:
            riga['Emissioni pianificate'] = emissioni_per_articolo[sku][riga['Settimana']]
    giacenze = [riga['Giacenza prevista'] for tabella in records.values() for riga in tabella]
    ordini.sort(key=lambda x: (x['Settimana emissione'], x['Codice'], x['Settimana arrivo']))
    return {
        'scenario': scenario,
        'records': records,
        'ordini': ordini,
        'avvisi': list(dict.fromkeys(avvisi)),
        'indicatori': {
            'numero_ordini': len(ordini),
            'quantita_ordinata': sum(ordine['Quantità'] for ordine in ordini),
            'scorta_media': round(sum(giacenze) / len(giacenze), 2),
            'ordini_da_sollecitare': sum(ordine['Settimana emissione'] < 1 for ordine in ordini),
        },
        'meta': m,
    }
