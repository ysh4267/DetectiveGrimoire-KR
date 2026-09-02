"""Flag translated lines that render wider than the original text box.

DefineText carries a TextBounds rect in twips and each record carries a font
height (also twips). Measuring the Korean string with the real font metrics
tells us whether it will spill out of the speech bubble.
"""
import os, sys, json, glob, re, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ffdectext
import patch_swf

ROOT = os.path.dirname(HERE)
RAW = os.path.join(ROOT, 'work', 'text_raw')
CHUNKS = os.path.join(ROOT, 'work', 'chunks')
KO = os.path.join(ROOT, 'work', 'ko')

_cache = {}


def metrics():
    if 'm' not in _cache:
        from fontTools.ttLib import TTFont
        f = TTFont(os.path.join(ROOT, 'work', 'fonts', 'base_kr.ttf'))
        upem = f['head'].unitsPerEm
        cmap = f.getBestCmap()
        hmtx = f['hmtx']
        _cache['m'] = (upem, cmap, hmtx)
    return _cache['m']


def advance(text, height_twips):
    """Width in twips of `text` rendered at `height_twips`."""
    upem, cmap, hmtx = metrics()
    total = 0
    for ch in text:
        gname = cmap.get(ord(ch))
        if gname is None:
            total += upem // 2
            continue
        total += hmtx[gname][0]
    return total * height_twips / upem


def check(swfkey, translations, tolerance=1.15):
    """Flag lines whose Korean renders wider than the English they replace.

    Both sides are measured with the SAME replacement font, so this is a pure
    "did the translation grow the line" signal -- unlike comparing against the
    original TextBounds, which was authored for a different (narrower) face.
    """
    tdir = os.path.join(RAW, swfkey, 'texts')
    out = []
    for path in sorted(glob.glob(os.path.join(tdir, '*.txt')),
                       key=lambda p: int(os.path.basename(p)[:-4])):
        cid = os.path.basename(path)[:-4]
        if cid not in translations:
            continue
        try:
            parsed = ffdectext.read(path)
        except ValueError:
            continue

        b = parsed['bounds']
        xmin = int(ffdectext.get_param(b, 'xmin') or 0)
        xmax = int(ffdectext.get_param(b, 'xmax') or 0)
        box = xmax - xmin
        if box <= 0:
            continue

        # mirror the build exactly: wrap to visual lines, hand each to the
        # first record on it, then apply the same auto-shrink
        recs = parsed['records']
        groups = patch_swf.record_lines(parsed)
        ko = translations[cid]
        text = ko if isinstance(ko, str) else ' '.join(ko)
        per_line = patch_swf.wrap_lines(text, len(groups))
        lines = [''] * len(recs)
        for gi, g in enumerate(groups):
            lines[g[0]] = per_line[gi]
        scale = patch_swf.fit_scale(parsed, lines)

        heights, h = [], None
        for rec in recs:
            v = ffdectext.get_param(rec['params'], 'height')
            if v:
                h = int(v)
            heights.append(h)

        for gi, g in enumerate(groups):
            if heights[g[0]] is None:
                continue
            w_ko = sum(advance(lines[i], heights[i] * scale) for i in g)
            w_en = sum(advance(recs[i]['text'], heights[i]) for i in g)
            if w_en <= 0:
                continue
            if w_ko > box * 1.05:
                out.append({
                    'swf': swfkey, 'id': cid, 'line': gi,
                    'box': box, 'width': round(w_ko),
                    'grow': round(w_ko / w_en, 2),
                    'vs_box': round(w_ko / box, 2),
                    'scale': round(scale, 2),
                    'ko': per_line[gi],
                    'en': ''.join(recs[i]['text'] for i in g),
                })
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--json', help='write full report here')
    args = ap.parse_args()

    index = json.load(open(os.path.join(CHUNKS, '_index.json'), encoding='utf-8'))
    per_swf = {}
    for row in index:
        kp = os.path.join(KO, row['file'])
        if not os.path.exists(kp):
            continue
        try:
            tr = json.load(open(kp, encoding='utf-8'))
        except Exception as e:
            print('!! unreadable %s: %s' % (row['file'], e))
            continue
        for swf in row['swfs']:
            per_swf.setdefault(swf, {}).update(tr)

    allrep = []
    for key in sorted(per_swf):
        allrep += check(key, per_swf[key])

    allrep.sort(key=lambda r: -r['grow'])
    print('overflowing lines: %d' % len(allrep))
    for r in allrep[:40]:
        print('  %-30s %-5s L%d  grow=%.2f box=%.2f  %s' % (r['swf'], r['id'], r['line'], r['grow'], r['vs_box'], r['ko'][:38]))
    if args.json:
        json.dump(allrep, open(args.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print('\nwrote', args.json)


if __name__ == '__main__':
    main()
