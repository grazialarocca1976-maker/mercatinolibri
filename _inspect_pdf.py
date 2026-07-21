import os, traceback
out = []
try:
    p = r'c:\Users\terre\Downloads\etichette_a4_marconi (9).pdf'
    out.append('exists: ' + str(os.path.exists(p)))
    if os.path.exists(p):
        b = open(p, 'rb').read()
        out.append('size: ' + str(len(b)))
        out.append('head: ' + repr(b[:20]))
        out.append('tail: ' + repr(b[-40:]))
        out.append('xref count: ' + str(b.count(b'xref')))
        out.append('startxref: ' + str(b'startxref' in b))
        # Try to find any readable text streams
        out.append('has /Text: ' + str(b'/Text' in b))
        out.append('has BT/ET: ' + str(b'BT' in b and b'ET' in b))
except Exception:
    out.append('ERR ' + traceback.format_exc())
open('check.txt', 'w').write('\n'.join(out))
print('done')