import os, traceback
out = []
try:
    import gestore_etichette as ge
    import importlib
    importlib.reload(ge)

    # Edge cases: accenti, molti libri, layout personalizzato
    libri = []
    for i in range(1, 31):
        libri.append({
            'id_libro': 100 + i,
            'titolo': f"Matematicà 1 - Autore {i} con àccènti ò",
            'barcode': f"BOR85RW0001-{100+i}",
            'prevede_fascicoli': i % 2 == 0,
            'totale_fascicoli': 3,
            'fascicoli_consegnati': 1,
            'codice_personale': 'BOR85RW0001',
        })
    # Standard
    b1 = ge.genera_griglia_a4_bytes(libri, layout=None, start_index=0)
    out.append('standard len: ' + str(len(b1) if b1 else None))
    # Personalizzato 24 etichette A4
    lay = ge.calcola_layout_personalizzato(210, 297, 24)
    b2 = ge.genera_griglia_a4_bytes(libri, layout=lay, start_index=0)
    out.append('personalizzato len: ' + str(len(b2) if b2 else None))
    out.append('personalizzato layout: ' + str(lay))
    # start_index antispreco
    b3 = ge.genera_griglia_a4_bytes(libri, layout=None, start_index=11)
    out.append('start_index len: ' + str(len(b3) if b3 else None))
    if b1:
        open('test_std.pdf', 'wb').write(b1)
    if b2:
        open('test_pers.pdf', 'wb').write(b2)
    out.append('ALL OK')
except Exception:
    out.append('ERR ' + traceback.format_exc())

open('check.txt', 'w').write('\n'.join(out))
print('\n'.join(out))