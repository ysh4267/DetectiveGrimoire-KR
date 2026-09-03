"""Scan a built SWF tree for text that still collides.

Two checks against the shipped bytes (not the plan):
  * horizontal -- a glyph run wider than its TextBounds by more than the
    English original was
  * vertical   -- one line's ink descending into the next line's ascenders
"""
import os, sys, glob, json, subprocess, argparse, shutil, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ffdectext
import patch_swf as ps

ROOT = os.path.dirname(HERE)
FFDEC = ['java', '-Xmx2g', '-jar', os.path.join(ROOT, 'tools', 'ffdec', 'ffdec.jar')]


def export(swf, dst):
    os.makedirs(dst, exist_ok=True)
    subprocess.run(FFDEC + ['-format', 'text:formatted', '-export', 'text', dst, swf],
                   capture_output=True, text=True, timeout=900)


def rows_of(parsed):
    y = h = None
    out = []
    for r in parsed['records']:
        vy = ffdectext.get_param(r['params'], 'y')
        vh = ffdectext.get_param(r['params'], 'height')
        if vy:
            y = int(vy)
        if vh:
            h = int(vh)
        out.append((y, h, r['text']))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--dist', default=os.path.join(ROOT, 'dist', 'assets', 'swf-dsk'))
    ap.add_argument('--limit', type=int, default=20)
    a = ap.parse_args()

    tmp = tempfile.mkdtemp(prefix='ovl_')
    vbad, hbad, n_text = [], [], 0
    swfs = sorted(glob.glob(os.path.join(a.dist, '**', '*.swf'), recursive=True))
    for swf in swfs:
        key = os.path.relpath(swf, a.dist).replace(os.sep, '/')[:-4]
        dst = os.path.join(tmp, key.replace('/', '__'))
        export(swf, dst)
        for path in glob.glob(os.path.join(dst, '*.txt')):
            try:
                p = ffdectext.read(path)
            except ValueError:
                continue
            n_text += 1
            cid = os.path.basename(path)[:-4]
            rows = rows_of(p)
            for k in range(1, len(rows)):
                (y1, h1, t1), (y2, h2, t2) = rows[k - 1], rows[k]
                if None in (y1, y2, h1, h2) or not t1.strip() or not t2.strip():
                    continue
                bot = y1 + ps.line_extent(t1)[1] * h1
                top = y2 - ps.line_extent(t2)[0] * h2
                if top < bot:
                    vbad.append((bot - top, key, cid, t1.strip()[:16], t2.strip()[:16]))

            b = p['bounds']
            xmin = int(ffdectext.get_param(b, 'xmin') or 0)
            xmax = int(ffdectext.get_param(b, 'xmax') or 0)
            box = xmax - xmin
            if box <= 0:
                continue
            for g in ps.record_lines(p):
                h = None
                w = 0
                for i in g:
                    v = ffdectext.get_param(p['records'][i]['params'], 'height')
                    if v:
                        h = int(v)
                    if h:
                        w += ps.text_width(p['records'][i]['text'], h)
                if w > box * 1.25:
                    hbad.append((w / box, key, cid, p['records'][g[0]]['text'].strip()[:22]))

    shutil.rmtree(tmp, ignore_errors=True)
    vbad.sort(reverse=True)
    hbad.sort(reverse=True)
    print('texts scanned: %d' % n_text)
    print('vertical collisions : %d' % len(vbad))
    for d, k, c, t1, t2 in vbad[:a.limit]:
        print('   %5.0f twips  %-28s %-5s %r / %r' % (d, k, c, t1, t2))
    print('horizontal >1.25x box: %d' % len(hbad))
    for r, k, c, t in hbad[:a.limit]:
        print('   x%.2f  %-28s %-5s %r' % (r, k, c, t))


if __name__ == '__main__':
    main()
