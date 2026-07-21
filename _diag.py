import os, traceback
try:
    lines = []
    lines.append('cwd: ' + os.getcwd())
    p = 'test_repro.pdf'
    lines.append('test_repro exists: ' + str(os.path.exists(p)))
    if os.path.exists(p):
        b = open(p, 'rb').read()
        lines.append('size: ' + str(len(b)))
        lines.append('header: ' + repr(b[:8]))
        lines.append('tail: ' + repr(b.rstrip()[-6:]))
        lines.append('xref count: ' + str(b.count(b'xref')))
        lines.append('startxref: ' + str(b'startxref' in b))
    out = os.path.join(os.getcwd(), 'check.txt')
    open(out, 'w').write('\n'.join(lines))
    print('WROTE', out)
except Exception:
    open(os.path.join(os.getcwd(), 'check.txt'), 'w').write('ERR ' + traceback.format_exc())
    print('ERR')