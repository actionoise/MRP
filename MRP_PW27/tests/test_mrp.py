import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from mrp_engine import calcola_mrp, valida_progetto


def carica(nome='progetto_centralina.json'):
    return json.loads((ROOT/'data'/nome).read_text(encoding='utf-8'))


class TestMRP(unittest.TestCase):
    def test_json_privo_di_matricola(self):
        p=carica()
        self.assertNotIn('parametri_personali',p)
        self.assertNotIn('matricola_ultime_4',json.dumps(p))
        self.assertEqual(len(p['fabbisogni']),8)
        self.assertEqual(p['fabbisogni'],[30,20,75,65,55,45,35,25])

    def test_vincoli_centralina(self):
        p=carica()
        m=valida_progetto(p)
        self.assertEqual(len(m['articoli']),30)
        self.assertEqual(max(m['livelli'].values()),2)
        self.assertEqual(len(p['distinta_base']),30)
        self.assertEqual(len(m['genitori']['CMP_C84267']),2)
        self.assertTrue(any(x['quantita']>1 for x in p['distinta_base']))
        self.assertGreaterEqual(sum(a['provenienza']=='ACQUISTATO' for a in p['articoli']),3)
        self.assertGreaterEqual(sum(bool(a['arrivi_programmati']) for a in p['articoli']),2)
        self.assertEqual(set(a['regola_lotto'] for a in p['articoli']),{'FOQ','POQ','L4L'})
        f=m['articoli']['FIN001']
        self.assertEqual((f['lotto_foq'],f['giacenza_iniziale'],f['scorta_sicurezza']),(140,130,35))

    def test_record_finito_originale(self):
        risultato=calcola_mrp(carica())
        self.assertEqual([r['Giacenza prevista'] for r in risultato['records']['FIN001']],
                         [100,80,145,80,165,120,85,60])
        self.assertEqual([o['Settimana arrivo'] for o in risultato['ordini'] if o['Codice']=='FIN001'],[3,5])
        self.assertEqual([o['Quantità'] for o in risultato['ordini'] if o['Codice']=='FIN001'],[140,140])

    def test_indici_scenari_attesi(self):
        p=carica()
        expected={'ORIGINALE':(58,12275,39.44),
                  'TUTTI_L4L':(150,11070,33.44),
                  'TUTTI_POQ':(33,11070,69.67)}
        for scenario,(n,quantita,media) in expected.items():
            with self.subTest(scenario=scenario):
                indici=calcola_mrp(p,scenario)['indicatori']
                self.assertEqual(indici['numero_ordini'],n)
                self.assertEqual(indici['quantita_ordinata'],quantita)
                self.assertEqual(indici['scorta_media'],media)
                self.assertGreater(indici['ordini_da_sollecitare'],0)

    def test_scenari_non_modificano_json(self):
        p=carica()
        prima=copy.deepcopy(p)
        for scenario in ('ORIGINALE','TUTTI_L4L','TUTTI_POQ'):
            calcola_mrp(p,scenario)
        self.assertEqual(p,prima)

    def test_esplosione_sui_rilasci_del_padre(self):
        p={
          'prodotto_finito':'P','fabbisogni':[0,0,2,0],
          'articoli':[
             {'codice':'P','descrizione':'finito','provenienza':'PRODOTTO','lead_time':1,
              'giacenza_iniziale':0,'scorta_sicurezza':0,'regola_lotto':'FOQ','lotto_foq':4},
             {'codice':'C','descrizione':'componente','provenienza':'ACQUISTATO','lead_time':1,
              'giacenza_iniziale':0,'scorta_sicurezza':0,'regola_lotto':'L4L'},
          ],'distinta_base':[{'padre':'P','componente':'C','quantita':2}]
        }
        r=calcola_mrp(p)
        self.assertEqual(r['records']['P'][2]['Arrivi pianificati'],4)
        self.assertEqual(r['records']['C'][1]['Fabbisogni lordi'],8)
        self.assertEqual(r['records']['C'][1]['Arrivi pianificati'],8)
        self.assertEqual([o['Settimana emissione'] for o in r['ordini'] if o['Codice']=='C'],[1])

    def test_componente_condiviso_sommato_una_volta(self):
        p={
          'prodotto_finito':'P','fabbisogni':[0,0,0,1,0],
          'articoli':[
            {'codice':sku,'descrizione':sku,'provenienza':'ACQUISTATO' if sku=='LED' else 'PRODOTTO',
             'lead_time':1,'giacenza_iniziale':0,'scorta_sicurezza':0,'regola_lotto':'L4L'}
            for sku in ('P','A','B','LED')
          ],
          'distinta_base':[
            {'padre':'P','componente':'A','quantita':1},
            {'padre':'P','componente':'B','quantita':1},
            {'padre':'A','componente':'LED','quantita':2},
            {'padre':'B','componente':'LED','quantita':3},
          ]
        }
        r=calcola_mrp(p)
        self.assertEqual(r['records']['LED'][1]['Fabbisogni lordi'],5)
        self.assertEqual(len([o for o in r['ordini'] if o['Codice']=='LED']),1)

    def test_json_alternativo_reale_riutilizzo(self):
        p=carica('esempio_prodotto_alternativo.json')
        self.assertNotEqual(p['prodotto_finito'],'FIN001')
        for scenario in ('ORIGINALE','TUTTI_L4L','TUTTI_POQ'):
            r=calcola_mrp(p,scenario)
            self.assertEqual(len(r['records']),len(p['articoli']))
            self.assertEqual(len(r['records'][p['prodotto_finito']]),8)

    def test_rifiuta_articoli_duplicati(self):
        p=carica()
        p['articoli'].append(copy.deepcopy(p['articoli'][0]))
        with self.assertRaisesRegex(ValueError,'duplicato'):
            valida_progetto(p)

    def test_rifiuta_ciclo(self):
        p=carica()
        # FIN001→ASS_BLE esiste: un ritorno creerebbe un ciclo; qui non è
        # ammesso già per il vincolo che il finito non può essere figlio.
        p['distinta_base'].append({'padre':'ASS_BLE','componente':'FIN001','quantita':1})
        with self.assertRaises(ValueError):
            valida_progetto(p)

    def test_rifiuta_articolo_sconosciuto(self):
        p=carica()
        p['distinta_base'].append({'padre':'ASS_BLE','componente':'INESISTENTE','quantita':1})
        with self.assertRaisesRegex(ValueError,'sconosciuto'):
            valida_progetto(p)

    def test_segnala_rilasci_antecedenti(self):
        r=calcola_mrp(carica())
        self.assertTrue(any(o['Settimana emissione']<1 for o in r['ordini']))
        self.assertTrue(any('da sollecitare' in a.lower() for a in r['avvisi']))


if __name__=='__main__':
    unittest.main()
