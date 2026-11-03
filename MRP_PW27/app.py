"""Dashboard Streamlit MRP multilivello · PW 27 · dati esterni in JSON.

Avvio: python -m streamlit run app.py

"""

import json
import re
from pathlib import Path

import graphviz
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from mrp_engine import SCENARI, calcola_mrp, valida_progetto

BASE = Path(__file__).resolve().parent
JSON_DEMO = BASE / 'data' / 'progetto_centralina.json'
NOMI_SCENARI = {
    'ORIGINALE': 'BASE · Regole per articolo',
    'TUTTI_L4L': 'SIMULAZIONE · Tutti L4L',
    'TUTTI_POQ': 'SIMULAZIONE · Tutti POQ',
}
COLONNE_ORDINI = [
    'Codice', 'Articolo', 'Riferimenti PCB', 'Quantità', 'Settimana emissione',
    'Settimana arrivo', 'Origine', 'Regola', 'Stato',
]

st.set_page_config(page_title='MRP · Project Work 27', page_icon='🧩',
                   layout='wide', initial_sidebar_state='expanded')
st.markdown('''<style>
.block-container { padding-top: 1.25rem; padding-bottom: 3rem; }
[data-testid="stMetric"] { border:1px solid rgba(125,138,157,.23); border-radius:12px;
 padding:12px 15px; background:rgba(115,133,156,.045); }
[data-testid="stMetricLabel"] {font-size:.9rem}
</style>''', unsafe_allow_html=True)


# Configurazione condivisa dei grafici Plotly. Evita tocchi e clic accidentali
# su smartphone e PC senza rinunciare ai valori visualizzati al passaggio del mouse.
CONFIG_GRAFICI = {
    'scrollZoom': False,       # la rotellina / lo scorrimento non ingrandiscono il grafico
    'doubleClick': False,      # il doppio tocco non modifica gli assi
    'displayModeBar': False,   # nasconde i pulsanti di zoom e selezione
    'displaylogo': False,
}


def mostra_grafico(fig):
    """Mostra il Plotly senza consentire di nascondere curve o barre con un tocco."""
    fig.update_layout(
        dragmode=False,  # disattiva lo zoom/selezione per trascinamento anche su touch
        legend=dict(itemclick=False, itemdoubleclick=False),
    )
    st.plotly_chart(fig, use_container_width=True, config=CONFIG_GRAFICI)


def csv_da_dataframe(df):
    """Separatore ; e BOM UTF-8: apertura semplice in Excel/ONLYOFFICE."""
    return df.to_csv(index=False, sep=';').encode('utf-8-sig')


def riferimenti_componenti(progetto):
    """Indicizza i designatori presenti nel JSON della BOM (R1, LED1, U3...).

    Il riferimento fisico appartiene al legame padre-figlio, non all'articolo
    in astratto: per un componente condiviso si riportano entrambe le schede.
    Non inventa designatori per prodotti o JSON che non li riportano.
    """
    riferimenti = {}
    for legame in progetto.get('distinta_base', []):
        codice = legame.get('componente')
        padre = legame.get('padre', '')
        designatori = legame.get('riferimenti_pcb', '')
        if isinstance(designatori, list):
            designatori = ', '.join(str(x) for x in designatori if x)
        if not codice or not designatori:
            continue
        # Lo stesso SKU può comparire in schede diverse con lo stesso LED1.
        identificazione = f'{padre}: {designatori}' if padre else str(designatori)
        righe = riferimenti.setdefault(codice, [])
        if identificazione not in righe:
            righe.append(identificazione)
    return {codice: ' | '.join(righe) for codice, righe in riferimenti.items()}


# Ricerca unica, riutilizzata da distinta base, archivio e piano ordini.
# Es. R1 e R10 sono designatori DIFFERENTI: il confronto è esatto.
TUTTE_SCHEDE = 'Tutti i sottoassiemi'


def lista_designatori(valore):
    """Normalizza la colonna riferimenti_pcb del JSON (stringa o lista)."""
    if isinstance(valore, (list, tuple)):
        pezzi = [str(x) for x in valore if x is not None]
    else:
        pezzi = [str(valore or '')]
    return [r.upper() for p in pezzi
            for r in re.split(r'[,;\s/|]+', p.strip()) if r]


def discendenti_articolo(meta, radice):
    """Restituisce i codici di un sottoassieme e dei suoi discendenti BOM."""
    visitati = {radice}
    coda = [radice]
    while coda:
        padre = coda.pop()
        for figlio, _ in meta['figli'].get(padre, []):
            if figlio not in visitati:
                visitati.add(figlio)
                coda.append(figlio)
    return visitati


def legami_cercati(progetto, meta, termine='', scheda=TUTTE_SCHEDE):
    """Filtra i singoli riferimenti BOM: R1 sulla BLE != R1 sulla relè."""
    q = termine.strip().casefold()
    # Una stringa del tipo R3, LED1 o U2 è prima di tutto un designatore PCB.
    designatore = bool(re.fullmatch(r'[a-z]{1,8}\d+[a-z]?', q))
    trovati = []
    ramo = (discendenti_articolo(meta, scheda)
            if scheda != TUTTE_SCHEDE else None)
    for legame in progetto.get('distinta_base', []):
        if ramo is not None and legame['padre'] not in ramo:
            continue
        if not q:
            trovati.append(legame)
            continue

        riferimenti = [r.casefold() for r in lista_designatori(legame.get('riferimenti_pcb'))]
        if q in riferimenti:
            trovati.append(legame)
            continue
        # Per i riferimenti corti si evita di trovare R1 dentro R10 o R11
        # e dentro stringhe che non sono veri designatori della scheda.
        if designatore and len(q) <= 3:
            continue

        articolo = meta['articoli'][legame['componente']]
        padre = meta['articoli'][legame['padre']]
        campi = [
            legame['componente'], articolo.get('descrizione', ''),
            legame['padre'], padre.get('descrizione', ''),
            articolo.get('lcsc', ''), articolo.get('codice_produttore', ''),
        ]
        if any(q in str(campo).casefold() for campo in campi):
            trovati.append(legame)
    return trovati


def articoli_cercati(progetto, meta, legami, termine='', scheda=TUTTE_SCHEDE):
    """Trova SKU da usare nei listati; mostra anche prodotti senza designatori."""
    codici = {legame['componente'] for legame in legami}
    q = termine.strip().casefold()
    if scheda == TUTTE_SCHEDE and q:
        is_ref_corto = bool(re.fullmatch(r'[a-z]{1,8}\d+[a-z]?', q)) and len(q) <= 3
        if not is_ref_corto:
            for sku, articolo in meta['articoli'].items():
                if any(q in str(v).casefold() for v in (
                    sku, articolo.get('descrizione', ''),
                    articolo.get('lcsc', ''), articolo.get('codice_produttore', ''),
                )):
                    codici.add(sku)
    if scheda != TUTTE_SCHEDE and not q:
        codici.add(scheda)
    return codici


def ruolo_articolo(sku, progetto, meta):
    """Classifica un articolo per ruolo, senza ipotesi sul tipo di prodotto."""
    if sku == progetto['prodotto_finito']:
        return 'Prodotto finito'
    if meta['articoli'][sku]['provenienza'] == 'PRODOTTO':
        return 'Sottoassieme / articolo prodotto'
    return 'Articolo acquistato'


def antenati_articolo(meta, sku):
    """Risale ai padri di uno SKU per mantenere visibili tutti i livelli BOM."""
    trovati = set()
    coda = [sku]
    while coda:
        corrente = coda.pop()
        for padre, _ in meta['genitori'].get(corrente, []):
            if padre not in trovati:
                trovati.add(padre)
                coda.append(padre)
    return trovati


def panoramica_livelli(progetto, meta):
    """Livello 0 e figli diretti, per qualsiasi prodotto importato dal JSON."""
    finito = progetto['prodotto_finito']
    righe = [{
        'Livello': 0,
        'Codice': finito,
        'Descrizione': meta['articoli'][finito]['descrizione'],
        'Ruolo': 'Prodotto finito',
        'Quantità per padre': '—',
    }]
    for figlio, quantita in meta['figli'].get(finito, []):
        righe.append({
            'Livello': meta['livelli'][figlio],
            'Codice': figlio,
            'Descrizione': meta['articoli'][figlio]['descrizione'],
            'Ruolo': ruolo_articolo(figlio, progetto, meta),
            'Quantità per padre': quantita,
        })
    return pd.DataFrame(righe)


def tabella_risultati_pcb(legami, meta):
    """Una riga per scheda/articolo, necessaria per disambiguare R1 e LED1."""
    colonne = ['Sottoassieme / padre', 'Riferimenti PCB', 'Codice articolo',
               'Descrizione articolo', 'Quantità per padre', 'Provenienza']
    return pd.DataFrame([{
        'Sottoassieme / padre': legame['padre'],
        'Riferimenti PCB': ', '.join(lista_designatori(legame.get('riferimenti_pcb'))) or '—',
        'Codice articolo': legame['componente'],
        'Descrizione articolo': meta['articoli'][legame['componente']]['descrizione'],
        'Quantità per padre': legame['quantita'],
        'Provenienza': meta['articoli'][legame['componente']]['provenienza'],
    } for legame in legami], columns=colonne)


def dataframe_ordini(ordini, riferimenti):
    """Arricchisce solo la vista/export senza cambiare il motore MRP."""
    righe = [dict(o, **{'Riferimenti PCB': riferimenti.get(o['Codice'], '—')})
             for o in ordini]
    return pd.DataFrame(righe, columns=COLONNE_ORDINI)


def grafico_saldo(record, codice, sicurezza):
    x = [r['Settimana'] for r in record]
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=x, y=[r['Giacenza prevista'] for r in record],
                             mode='lines+markers', name='Giacenza prevista',
                             line=dict(color='#2389d1', width=3), marker=dict(size=8)))
    fig.add_trace(go.Scatter(x=x, y=[sicurezza] * len(x), mode='lines',
                             name='Scorta di sicurezza',
                             line=dict(color='#e8a13c', dash='dash', width=2)))
    fig.update_layout(
    title=f'Scorte previste · {codice}',
    height=410,
    margin=dict(t=95, b=35, l=20, r=20),
    xaxis=dict(title='Settimana', dtick=1),
    yaxis_title='Pezzi',
    hovermode='x unified',
    legend=dict(
        orientation='h',
        x=0,
        y=1.02,
        yanchor='bottom'
    )
)
    return fig


def grafico_domanda(progetto):
    x = list(range(1, len(progetto['fabbisogni'])+1))
    fig = go.Figure(go.Bar(x=x, y=progetto['fabbisogni'],
                           marker_color='#2694c7', text=progetto['fabbisogni'],
                           textposition='outside', name='Domanda prodotto finito'))
    fig.update_layout(title='Fabbisogni lordi del prodotto finito', height=310,
                      margin=dict(t=50,b=35,l=20,r=20),
                      xaxis=dict(title='Settimana', dtick=1), yaxis_title='Pezzi')
    return fig


def grafico_ordini_settimanali(ordini, orizzonte):
    conteggi = [sum(o['Settimana arrivo'] == w for o in ordini)
                for w in range(1, orizzonte+1)]
    fig = go.Figure(go.Bar(x=list(range(1, orizzonte+1)),y=conteggi,
                           marker_color='#22a587',text=conteggi,textposition='outside'))
    fig.update_layout(title='Ordini pianificati per settimana di arrivo', height=310,
                      margin=dict(t=50,b=35,l=20,r=20),
                      xaxis=dict(title='Settimana',dtick=1), yaxis_title='N. ordini')
    return fig


def albero_bom(meta, completo, riferimenti, prodotto_finito):
    """La stessa etichetta SKU appare una sola volta anche con più genitori."""
    g = graphviz.Digraph('BOM', graph_attr={'rankdir':'TB', 'bgcolor':'transparent',
                                           'nodesep':'.26', 'ranksep':'.52',
                                           'splines':'polyline', 'pad':'.2'},
                         node_attr={'shape':'box','style':'rounded,filled',
                                    'fontname':'Arial', 'fontsize':'10',
                                    'color':'#8da4b7', 'penwidth':'1.25'},
                         edge_attr={'color':'#8296a8','fontname':'Arial','fontsize':'10'})
    padri = meta['genitori']
    figli = meta['figli']
    visibili = {prodotto_finito}
    legami = []
    for padre in meta['ordine']:
        discendenti = list(figli.get(padre, []))
        if not completo and meta['livelli'][padre] >= 1:
            # Nel disegno breve: preferenza a componente comune, impiego >1 e PCB.
            discendenti.sort(key=lambda item: (
                0 if len(padri.get(item[0], [])) > 1 else 1,
                0 if item[1] > 1 else 1,
                0 if item[0].startswith('PCB_') else 1,
                item[0]))
            discendenti = discendenti[:5]
        if padre not in visibili:
            continue
        for figlio, qty in discendenti:
            visibili.add(figlio)
            legami.append((padre, figlio, qty))
    for sku in meta['ordine']:
        if sku not in visibili:
            continue
        a = meta['articoli'][sku]
        condiviso = len(padri.get(sku, [])) > 1
        fill = ('#b7d7fb' if sku == prodotto_finito else
                '#f9eac0' if condiviso else
                '#dceefe' if a['provenienza'] == 'PRODOTTO' else '#e0f2e8')
        desc = a['descrizione'][:29] + ('…' if len(a['descrizione']) > 29 else '')
        ref = riferimenti.get(sku, '')
        ref_breve = (ref[:39] + '…') if len(ref) > 40 else ref
        testo_ref = f"\\nPCB: {ref_breve}" if ref else ''
        livello = ('Livello 0 · PRODOTTO FINITO' if sku == prodotto_finito
                   else f"Livello {meta['livelli'][sku]}")
        g.node(sku, f"{sku}\\n{desc}{testo_ref}\\n{livello}",
               fillcolor=fill, tooltip=ref or sku)
    for padre, figlio, qty in legami:
        g.edge(padre, figlio, label=f'×{qty}')
    return g


def tabella_bom(progetto, m, legami=None):
    if legami is None:
        legami = progetto['distinta_base']
    colonne = ['Livello padre', 'Codice padre', 'Descrizione padre',
               'Codice figlio', 'Descrizione figlio', 'Coeff. impiego',
               'Provenienza figlio', 'Riferimenti PCB']
    return pd.DataFrame([{
        'Livello padre': m['livelli'][link['padre']],
        'Codice padre': link['padre'],
        'Descrizione padre': m['articoli'][link['padre']]['descrizione'],
        'Codice figlio': link['componente'],
        'Descrizione figlio': m['articoli'][link['componente']]['descrizione'],
        'Coeff. impiego': link['quantita'],
        'Provenienza figlio': m['articoli'][link['componente']]['provenienza'],
        'Riferimenti PCB': link.get('riferimenti_pcb') or '—',
    } for link in legami], columns=colonne)


with st.sidebar:
    st.title('Elaborazione MRP')
    st.caption('PW_Informatica per le aziende digitali')
    upload = st.file_uploader('Carica un altro progetto JSON', type=['json'],
                             help='Lo stesso motore funziona con altri prodotti, purché il file rispetti lo schema.')

try:
    sorgente = upload.getvalue() if upload is not None else JSON_DEMO.read_bytes()
    progetto = json.loads(sorgente.decode('utf-8-sig'))
    m = valida_progetto(progetto)
    riferimenti_pcb = riferimenti_componenti(progetto)
    prodotto_finito = progetto['prodotto_finito']
    articolo_finito = m['articoli'][prodotto_finito]
    risultati = {sc: calcola_mrp(progetto, sc) for sc in SCENARI}
except (ValueError, TypeError, KeyError, UnicodeDecodeError, json.JSONDecodeError) as errore:
    st.error('Errore nei dati del progetto: ' + str(errore))
    st.info('Correggi il JSON oppure carica il file di esempio incluso nella cartella data.')
    st.stop()

with st.sidebar:
    st.success('✓ File caricato e distinta base validata')
    st.caption('File: ' + (upload.name if upload else 'progetto_centralina.json (esempio)'))
    st.divider()
    scenario = st.selectbox('Scenario di pianificazione', SCENARI,
                            format_func=lambda x: NOMI_SCENARI[x])
    st.divider()
    st.subheader('🔎 Cerca componente')
    termine_ricerca = st.text_input(
        'Riferimento Componente, codice o descrizione',
        placeholder='',
        help='La ricerca non distingue maiuscole e minuscole.',
    )
    # I sottoassiemi sono gli articoli padre sotto il prodotto finito,
    # identificati dalla BOM caricata; non richiedono riferimenti PCB.
    schede_disponibili = sorted({legame['padre']
                                for legame in progetto['distinta_base']
                                if legame['padre'] != prodotto_finito},
                               key=lambda sku: (m['livelli'][sku], sku))
    # La chiave lega la selezione al prodotto caricato e ne evita il riuso
    # accidentale passando da centralina a bicicletta.
    import hashlib
    chiave_progetto = hashlib.sha256(sorgente).hexdigest()[:12]
    scheda_ricerca = st.selectbox(
        'Filtra per sottoassiemi e componenti',
        [TUTTE_SCHEDE] + schede_disponibili,
        key=f'filtro_sottoassiemi_{chiave_progetto}',
        format_func=lambda codice: (
            codice if codice == TUTTE_SCHEDE
            else f"L{m['livelli'][codice]} · {codice} · {m['articoli'][codice]['descrizione'][:35]}"),
    )
    if not schede_disponibili:
        st.caption('Nessun sottoassieme nella BOM: ricerca disponibile per codice e descrizione.')
    filtro_attivo = bool(termine_ricerca.strip() or scheda_ricerca != TUTTE_SCHEDE)
    legami_filtrati = legami_cercati(progetto, m, termine_ricerca, scheda_ricerca)
    codici_filtrati = articoli_cercati(progetto, m, legami_filtrati,
                                       termine_ricerca, scheda_ricerca)
    riferimenti_filtrati = (riferimenti_componenti({'distinta_base': legami_filtrati})
                           if filtro_attivo else riferimenti_pcb)
    if filtro_attivo:
        st.caption(f"Trovati {len(legami_filtrati)} collegamenti BOM e "
                   f"{len(codici_filtrati)} codici articolo.")
    sku_ordinati = sorted(m['articoli'], key=lambda s:(m['livelli'][s],s))
    # L0 rimane SEMPRE selezionabile, anche durante una ricerca per R1 / LED1.
    # Per i componenti trovati sono visibili anche i rispettivi antenati nella BOM.
    if filtro_attivo:
        codici_contesto = {prodotto_finito}
        for sku in codici_filtrati:
            codici_contesto.update(antenati_articolo(m, sku))
        visibili = codici_filtrati | codici_contesto
        opzioni_sku = [s for s in sku_ordinati if s in visibili]
    else:
        opzioni_sku = sku_ordinati
    if filtro_attivo and not codici_filtrati:
        st.warning('Nessun componente trovato. Il prodotto finito resta disponibile.')
    default_sku = (next((s for s in sku_ordinati if s in codici_filtrati), prodotto_finito)
                   if termine_ricerca.strip() and codici_filtrati else prodotto_finito)
    selezionato = st.selectbox('Naviga fra gli articoli', opzioni_sku,
                               index=opzioni_sku.index(default_sku),
                               format_func=lambda sku: (
                                   f"L{m['livelli'][sku]} · {ruolo_articolo(sku, progetto, m)}"
                                   f" · {sku} · "
                                   + (f"[{riferimenti_filtrati[sku]}] · "
                                      if sku in riferimenti_filtrati else '')
                                   + m['articoli'][sku]['descrizione'][:33]
                               ))
    if filtro_attivo:
        st.caption('Nel selettore sono mostrati i componenti trovati e il relativo '
                   'percorso nella distinta base, compreso il prodotto finito L0.')
    st.divider()
    st.caption('I dati si aggiornano in base al JSON caricato')

res = risultati[scenario]
st.title('Pianificazione dei fabbisogni di materiali')
st.caption('Motore MRP multilivello · FOQ / POQ / L4L · ordini di acquisto e produzione')
st.markdown(f"**{progetto.get('nome_progetto','Progetto MRP')}**")
if scenario != 'ORIGINALE':
    st.info('Scenario di confronto: le regole di lottizzazione sono sostituite SOLO in memoria; '
            'il file JSON originale non viene modificato.')

k1, k2, k3, k4 = st.columns(4)
k1.metric('Articoli', len(m['articoli']))
k2.metric('Livelli BOM', max(m['livelli'].values()) + 1)
k3.metric('Ordini pianificati', res['indicatori']['numero_ordini'])
k4.metric('Scorta media prevista', f"{res['indicatori']['scorta_media']:.2f}")

# Il finito non ha designatori PCB propri: è l'articolo padre di tutta la BOM.
# La descrizione è letta dal JSON: centralina, bicicletta o qualsiasi altro prodotto.
st.subheader('📦 Prodotto finito · Livello 0')
st.markdown(f"**{prodotto_finito} — {articolo_finito['descrizione']}**")
st.caption('Prodotto completo identificato dal campo prodotto_finito del JSON. '
           'Le lavorazioni finali (ad esempio assemblaggio e collaudo, con eventuale '
           'programmazione) fanno parte del ciclo produttivo: non sono designatori '
           'PCB né nuovi livelli della distinta base.')
figli_diretti = m['figli'].get(prodotto_finito, [])
if figli_diretti:
    st.markdown('**Articoli direttamente necessari al prodotto finito:** ' +
                ' · '.join(f"`{codice}` ×{quantita} ({m['articoli'][codice]['descrizione']})"
                           for codice, quantita in figli_diretti))
st.caption(f"Pianificazione: {articolo_finito['regola_lotto']} nello scenario BASE; "
           f"lead time: {articolo_finito['lead_time']} settimane. "
           'Le quantità e gli ordini sono calcolati dal motore MRP.')

if filtro_attivo:
    st.subheader('🔎 Risultati della ricerca')
    st.caption('Il filtro segue i rami della distinta base del prodotto caricato. '
               'Se presenti, i riferimenti PCB sono specifici di ogni scheda; '
               'la ricerca filtra anche distinta base, piano ordini e archivio.')
    if legami_filtrati:
        st.dataframe(tabella_risultati_pcb(legami_filtrati, m),
                     use_container_width=True, hide_index=True)
    elif codici_filtrati:
        st.info('Articolo trovato per codice o descrizione, ma nessun collegamento BOM '
                'corrisponde al filtro. È disponibile nel selettore laterale.')
    else:
        st.warning('Nessun risultato. Verifica il termine o cambia il sottoassieme.')

sezioni = st.tabs(['📊 Panoramica', '🌳 Distinta base', '📈 Record MRP',
                   '📦 Piano ordini', '⚖️ Confronto scenari', '🗂️ Archivio e JSON'])

with sezioni[0]:
    st.markdown('**Struttura iniziale: prodotto finito e articoli diretti (L0 → L1)**')
    st.dataframe(panoramica_livelli(progetto, m), use_container_width=True,
                 hide_index=True)
    a, b = st.columns(2)
    with a:
        mostra_grafico(grafico_domanda(progetto))
    with b:
        mostra_grafico(grafico_ordini_settimanali(res['ordini'],progetto['orizzonte_settimane']))
    s1,s2,s3,s4 = st.columns(4)
    s1.metric('Settimane', progetto['orizzonte_settimane'])
    s2.metric('Articoli acquistati', sum(v['provenienza']=='ACQUISTATO' for v in m['articoli'].values()))
    s3.metric('Quantità totale ordinata', res['indicatori']['quantita_ordinata'])
    s4.metric('Ordini da sollecitare', res['indicatori']['ordini_da_sollecitare'])
    st.caption('La quantità totale somma unità di articoli differenti; la scorta media è la media '
               'aritmetica delle giacenze previste per articolo e settimana.')
    if res['indicatori']['ordini_da_sollecitare']:
        st.warning('Sono presenti ordini con settimana di emissione antecedente alla S1. '
                   'Consultare il piano ordini e gli avvisi per la gestione delle urgenze.')

with sezioni[1]:
    st.subheader('Struttura padre → figlio della distinta base')
    st.caption('Azzurro intenso = prodotto finito di livello 0 · Blu = altri articoli prodotti · '
               'Verde = articolo acquistato · '
               'Giallo = componente condiviso fra più padri. I numeri sugli archi '
               'sono coefficienti di impiego per una unità del padre.')
    completo = st.toggle('Mostra tutti i componenti (diagramma completo)', value=False)
    st.graphviz_chart(albero_bom(m, completo, riferimenti_pcb, prodotto_finito), use_container_width=True)
    if not completo:
        st.info('Diagramma ridotto per leggibilità: tutti i legami della BOM sono riportati nella tabella qui sotto.')
    st.caption('I riferimenti PCB (R1, R2, R3, LED1, U1...) identificano la posizione '
               'del componente sulle schede; il codice articolo identifica il ricambio.')
    df_bom = tabella_bom(progetto, m, legami_filtrati if filtro_attivo else None)
    if filtro_attivo:
        st.caption(f"Legami BOM mostrati: {len(df_bom)} su {len(progetto['distinta_base'])}. "
                   'Il diagramma sopra resta completo per mostrare il contesto.')
    st.dataframe(df_bom, use_container_width=True, hide_index=True)
    st.download_button('⬇️ Esporta distinta base' + (' filtrata' if filtro_attivo else '') + ' CSV',
                       csv_da_dataframe(df_bom),
                       'distinta_base_filtrata.csv' if filtro_attivo else 'distinta_base_completa.csv',
                       mime='text/csv')
    comuni = [(sku, m['genitori'][sku]) for sku in m['articoli']
              if len(m['genitori'].get(sku,[])) > 1
              and (not filtro_attivo or sku in codici_filtrati)]
    if comuni:
        st.markdown('**Articoli comuni a più padri**')
        for sku, padri in comuni:
            posizioni = riferimenti_pcb.get(sku, 'Nessun designatore indicato')
            st.success(f"{sku} · {m['articoli'][sku]['descrizione']} · " +
                       ', '.join(f'{p} ×{q}' for p,q in padri) +
                       f' · PCB: {posizioni}')
    st.caption(f"Legami con coefficiente >1: " +
               str(sum(l['quantita'] > 1 for l in progetto['distinta_base'])))

with sezioni[2]:
    a = m['articoli'][selezionato]
    st.subheader(a['descrizione'])
    st.caption(f"{selezionato} · Livello {m['livelli'][selezionato]} · "
               f"{ruolo_articolo(selezionato, progetto, m)} · "
               f"{'Acquisto' if a['provenienza']=='ACQUISTATO' else 'Produzione interna'}")
    if selezionato == prodotto_finito:
        st.info('Questo è il prodotto finito L0, completo dopo le lavorazioni previste. '
                'I designatori di posizione, quando presenti, appartengono ai '
                'componenti e ai relativi collegamenti della distinta base.')
    if selezionato in riferimenti_filtrati:
        st.info(f"📍 **Riferimenti sulla scheda:** {riferimenti_filtrati[selezionato]}")
    elif a['provenienza'] == 'ACQUISTATO':
        st.caption('Riferimento PCB non indicato nel JSON per questo articolo.')
    t1,t2,t3,t4 = st.columns(4)
    t1.metric('Giacenza iniziale', a['giacenza_iniziale'])
    t2.metric('Scorta di sicurezza', a['scorta_sicurezza'])
    t3.metric('Lead time', f"{a['lead_time']} sett.")
    metodo = a['regola_lotto'] if scenario=='ORIGINALE' else ('L4L' if scenario=='TUTTI_L4L' else 'POQ')
    t4.metric('Regola applicata', metodo)
    if metodo == 'FOQ':
        st.caption(f"Lotto fisso FOQ: {a['lotto_foq']} unità o multipli")
    elif metodo == 'POQ':
        st.caption(f"Periodo POQ: {a.get('periodo_poq') or progetto.get('periodo_poq', 2)} settimane")
    padri = m['genitori'].get(selezionato,[])
    if padri:
        st.markdown('**Usato nei padri:** ' + ', '.join(f'`{p}` (×{q})' for p,q in padri))
    figli = m['figli'].get(selezionato,[])
    if figli:
        dettagli = []
        for figlio, q in figli:
            designatori = next((legame.get('riferimenti_pcb', '')
                                for legame in progetto['distinta_base']
                                if legame.get('padre') == selezionato
                                and legame.get('componente') == figlio), '')
            dettagli.append(f'`{figlio}` (×{q})' +
                            (f' · **{designatori}**' if designatori else ''))
        st.markdown('**Componenti diretti (designatori PCB):** ' + ', '.join(dettagli))
    record = res['records'][selezionato]
    mostra_grafico(grafico_saldo(record,selezionato,a['scorta_sicurezza']))
    df = pd.DataFrame(record)
    df.insert(0, 'Riferimenti PCB', riferimenti_filtrati.get(selezionato, '—'))
    df.insert(0, 'Articolo', a['descrizione'])
    df.insert(0, 'Codice', selezionato)
    st.markdown('**Record MRP settimanale**')
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button('⬇️ Esporta record articolo CSV', csv_da_dataframe(df),
                       f"mrp_{selezionato}_{scenario.lower()}.csv", mime='text/csv')
    ordini_articolo = dataframe_ordini(
        [o for o in res['ordini'] if o['Codice']==selezionato], riferimenti_filtrati)
    st.markdown('**Ordini pianificati per questo articolo**')
    if ordini_articolo.empty:
        st.info('Nessun nuovo ordine necessario nel periodo.')
    else:
        st.dataframe(ordini_articolo, use_container_width=True,hide_index=True)
    if any(r['di cui anticipati'] for r in record):
        st.warning('Il fabbisogno S1 include esigenze nate da rilasci padre antecedenti '
                   'all’orizzonte: è una convenzione didattica esplicitata nel README.')

with sezioni[3]:
    st.subheader('Piano degli ordini di acquisto e produzione')
    ordini_df = dataframe_ordini(res['ordini'], riferimenti_pcb)
    c1,c2,c3 = st.columns(3)
    c1.metric('Numero di ordini',len(ordini_df))
    c2.metric('Quantità totale',res['indicatori']['quantita_ordinata'])
    c3.metric('Da sollecitare',res['indicatori']['ordini_da_sollecitare'])
    if ordini_df.empty:
        st.info('Nessun ordine nel periodo.')
    else:
        provenienza = st.multiselect('Filtra per tipologia', ['Acquisto','Produzione'],
                                     default=['Acquisto','Produzione'])
        mostra = ordini_df[ordini_df['Origine'].isin(provenienza)]
        if filtro_attivo:
            mostra = mostra[mostra['Codice'].isin(codici_filtrati)].copy()
            mostra['Riferimenti PCB'] = mostra['Codice'].map(
                lambda sku: riferimenti_filtrati.get(sku, '—'))
            st.caption(f'Ordini corrispondenti alla ricerca: {len(mostra)} su {len(ordini_df)}.')
        st.dataframe(
    mostra.rename(columns={'Origine': 'Provenienza'}),
    use_container_width=True,
    hide_index=True
)
        if filtro_attivo:
            st.download_button('⬇️ Scarica ordini filtrati CSV', csv_da_dataframe(mostra),
                               f'piano_ordini_filtrato_{scenario.lower()}.csv', mime='text/csv')
        st.download_button('⬇️ Scarica piano ordini completo CSV',csv_da_dataframe(ordini_df),
                           f'piano_ordini_{scenario.lower()}.csv',mime='text/csv',
                           help='Esporta il piano COMPLETO, indipendentemente dal filtro a video.')
    da_sollecitare = [o for o in res['ordini'] if o['Settimana emissione'] < 1
                     and (not filtro_attivo or o['Codice'] in codici_filtrati)]
    if da_sollecitare:
        with st.expander(f"⚠️ {len(da_sollecitare)} ordini con emissione prima della S1"):
            st.dataframe(dataframe_ordini(da_sollecitare, riferimenti_filtrati),
                         use_container_width=True, hide_index=True)
    if res['avvisi']:
        with st.expander(f"Avvisi MRP ({len(res['avvisi'])})"):
            for a in res['avvisi']:
                st.write('⚠️ ' + a)

with sezioni[4]:
    st.subheader('Confronto delle politiche di lottizzazione')
    confronto = pd.DataFrame([{
        'Scenario': NOMI_SCENARI[sc],
        'Numero ordini': risultati[sc]['indicatori']['numero_ordini'],
        'Quantità totale ordinata': risultati[sc]['indicatori']['quantita_ordinata'],
        'Scorta media prevista': risultati[sc]['indicatori']['scorta_media'],
        'Ordini da sollecitare': risultati[sc]['indicatori']['ordini_da_sollecitare'],
    } for sc in SCENARI])
    st.dataframe(confronto, use_container_width=True,hide_index=True)
    g1,g2 = st.columns(2)
    with g1:
        f=go.Figure(go.Bar(x=confronto['Scenario'],y=confronto['Numero ordini'],
                           marker_color=['#2985c6','#1caa91','#d59c42'],
                           text=confronto['Numero ordini'],textposition='outside'))
        f.update_layout(
    title='Numero ordini per scenario',
    height=420,
    margin=dict(t=70, b=105, l=20, r=20),
    xaxis=dict(
        tickangle=-25,
        automargin=True
    ),
    yaxis=dict(
        title='Numero ordini',
        range=[0, max(confronto['Numero ordini']) * 1.25]
    )
)
        mostra_grafico(f)
    with g2:
        f=go.Figure(go.Bar(x=confronto['Scenario'],y=confronto['Scorta media prevista'],
                           marker_color=['#2985c6','#1caa91','#d59c42'],
                           text=confronto['Scorta media prevista'],textposition='outside'))
        f.update_layout(title='Scorta media prevista',height=345,margin=dict(t=50,b=55,l=10,r=10))
        mostra_grafico(f)
    st.download_button('⬇️ Esporta confronto CSV',csv_da_dataframe(confronto),
                       'confronto_scenari.csv',mime='text/csv')
    st.caption('Il confronto applica provvisoriamente L4L o POQ a tutti gli articoli, '
               'compreso il finito: il progetto BASE mantiene invece FOQ sul finito, '
               'come richiesto dalla traccia.')

with sezioni[5]:
    st.subheader('Archivio articoli e dati di input')
    keys = [('codice','Codice'),('descrizione','Descrizione'),('provenienza','Provenienza'),
            ('lead_time','LT (sett.)'),('giacenza_iniziale','Giacenza iniziale'),
            ('scorta_sicurezza','Scorta sicurezza'),('regola_lotto','Regola'),
            ('lotto_foq','Lotto FOQ'),('periodo_poq','Periodo POQ'),('lcsc','Codice LCSC')]
    anag = pd.DataFrame([{
        **{'Codice': a['codice'],
           'Livello': m['livelli'][a['codice']],
           'Ruolo': ruolo_articolo(a['codice'], progetto, m),
           'Riferimenti PCB': riferimenti_pcb.get(a['codice'], '—')},
        **{titolo: a.get(k) for k, titolo in keys if k != 'codice'}
    } for a in progetto['articoli']])
    # Il prodotto finito non deve sparire dall'archivio durante una ricerca PCB.
    anag_visibile = (anag[anag['Codice'].isin(codici_filtrati | {prodotto_finito})].copy()
                     if filtro_attivo else anag)
    if filtro_attivo:
        anag_visibile['Riferimenti PCB'] = anag_visibile['Codice'].map(
            lambda sku: riferimenti_filtrati.get(sku, '—'))
        st.caption(f'Articoli corrispondenti: {len(codici_filtrati)}. '
                   f'Nella tabella il prodotto finito {prodotto_finito} rimane '
                   'visibile come contesto anche se non corrisponde al filtro.')
    st.dataframe(anag_visibile,use_container_width=True,hide_index=True)
    if filtro_attivo:
        st.download_button('⬇️ Scarica archivio filtrato CSV', csv_da_dataframe(anag_visibile),
                           'archivio_articoli_filtrato.csv', mime='text/csv')
    st.download_button('⬇️ Scarica archivio articoli completo CSV',csv_da_dataframe(anag),
                       'archivio_articoli.csv',mime='text/csv')
    st.markdown('**Domanda settimanale del prodotto finito**')
    st.dataframe(pd.DataFrame({'Settimana':range(1,progetto['orizzonte_settimane']+1),
                               'Fabbisogni lordi':progetto['fabbisogni']}),
                 use_container_width=True,hide_index=True)
    st.markdown('**Arrivi programmati già confermati**')
    arrivi = [{'Articolo':a['codice'],
               'Riferimenti PCB': riferimenti_pcb.get(a['codice'], '—'),
               'Settimana':x['settimana'],'Quantità':x['quantita']}
             for a in progetto['articoli'] for x in a.get('arrivi_programmati',[])]
    if filtro_attivo:
        arrivi = [r for r in arrivi if r['Articolo'] in codici_filtrati]
    if arrivi:
        st.dataframe(pd.DataFrame(arrivi),use_container_width=True,hide_index=True)
    else:
        st.caption('Nessun arrivo programmato per i filtri selezionati.'
                   if filtro_attivo else 'Nessun arrivo programmato.')
    with st.expander('Visualizza JSON di input'):
        st.json(progetto,expanded=1)
    st.download_button('⬇️ Scarica JSON di input',sorgente,
                       'progetto_input.json',mime='application/json')
    if progetto.get('assunzioni'):
        with st.expander('Assunzioni e verifiche progettuali'):
            for nota in progetto['assunzioni']:
                st.write('• ' + nota)
    st.caption('Il JSON contiene input e vincoli; tabelle MRP, giacenze e ordini '
               'sono calcolati dal motore Python a ogni esecuzione.')
