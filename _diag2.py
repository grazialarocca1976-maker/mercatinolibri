import os, traceback
out = []
try:
    import gestore_etichette as ge
    import importlib
    importlib.reload(ge)

    libri = [
        {'id_libro': 123, 'titolo': 'Matematica 1 - Autore Lungo', 'barcode': 'BOR85RW0001-123',
         'prevede_fascicoli': True, 'totale_fascicoli': 3, 'fascicoli_consegnati': 1, 'codice_personale': 'BOR85RW0001'},
        {'id_libro': 124, 'titolo': 'Storia Medievale', 'barcode': 'BOR85RW0001-124',
         'prevede_fascicoli': False, 'totale_fascicoli': 0, 'fascicoli_consegnati': 0, 'codice_personale': 'BOR85RW0001'},
        {'id_libro': 125, 'titolo': 'Italiano', 'barcode': '125',
         'prevede_fascicoli': False, 'totale_fascicoli': 0, 'fascicoli_consegnati': 0, 'codice_personale': ''},
    ]
    b = ge.genera_griglia_a4_bytes(libri, layout=None, start_index=0)
    out.append('bytes type: ' + str(type(b)))
    out.append('bytes len: ' + str(len(b) if b else None))
    if b:
        open('test_repro.pdf', 'wb').write(b)
        out.append('header: ' + repr(b[:8]))
        out.append('tail: ' + repr(b.rstrip()[-6:]))
        out.append('xref count: ' + str(b.count(b'xref')))
        out.append('startxref: ' + str(b'startxref' in b))
    else:
        out.append('PDF generation returned None -> check prepara_dati_etichette')
        et = ge.prepara_dati_etichette(libri)
        out.append('prepara count: ' + str(len(et)))
except Exception:
    out.append('ERR ' + traceback.format_exc())

open('check.txt', 'w').write('\n'.join(out))
print('\n'.join(out))