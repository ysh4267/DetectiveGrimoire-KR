"""Patch one SWF: swap its embedded fonts for a Korean subset, then import
the translated DefineText records.

Usage:  python work/patch_swf.py <swfkey> <translations.json> <outdir>

translations.json:  {"<charId>": ["line1", "line2", ...], ...}
Character ids absent from the file keep their English text (but still get
re-rendered with the replacement font, so their glyphs must be in the subset).
"""
import os, re, sys, json, glob, shutil, subprocess, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import ffdectext
import swffonts

ROOT = os.path.dirname(HERE)
GAME = r'e:/Program Files/SteamLibrary/steamapps/common/Detective Grimoire'
SWFDIR = os.path.join(GAME, 'assets', 'swf-dsk')
RAW = os.path.join(ROOT, 'work', 'text_raw')
BASE_FONT = os.path.join(ROOT, 'work', 'fonts', 'base_kr.ttf')
FFDEC = ['java', '-Xmx3g', '-jar', os.path.join(ROOT, 'tools', 'ffdec', 'ffdec.jar')]

# Latin/punctuation always kept so untranslated bits (names, numbers) survive.
ALWAYS = (
    'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
    " .,!?'\"-:;()[]{}/*&%#@+=<>_|~$^`\\\n\r\t"
    '\u00a9\u00ab\u00bb\u00e9\u00e8\u00e0\u00e5\u00c5\u00fc\u00f6\u017d\u017e'
    '\u2018\u2019\u201c\u201d\u2013\u2014\u2026'
)


def swf_path(key):
    return os.path.join(SWFDIR, key.replace('__', '/') + '.swf')


def _width(s):
    """Rough advance width: CJK counts double."""
    return sum(2 if ord(c) > 0x2000 else 1 for c in s)


def wrap_lines(text, n):
    """Split `text` into exactly `n` lines of roughly equal visual width.

    Korean may legally break anywhere, but breaking mid-word reads badly, so
    breaks are placed on word (어절) boundaries via a balanced DP. A single word
    that cannot fit on its own line is split as a last resort.
    """
    words = text.split()
    if n <= 1:
        return [' '.join(words)]
    if not words:
        return [''] * n

    # a word longer than one line's share has to be broken up first
    target = _width(text) / n
    parts = []
    for w in words:
        if _width(w) <= target * 1.35 or len(w) < 4:
            parts.append(w)
            continue
        chunks = max(2, int(round(_width(w) / target)))
        step = max(1, len(w) // chunks)
        parts += [w[i:i + step] for i in range(0, len(w), step)]
    words = parts
    if len(words) < n:
        words += [''] * (n - len(words))

    W = [_width(w) for w in words]
    SP = _width(' ')
    m = len(words)

    def line_width(a, b):                      # words[a:b]
        return sum(W[a:b]) + SP * (b - a - 1)

    INF = float('inf')
    # dp[i][k] = best (max-deviation) cost for words[i:] split into k lines
    dp = [[INF] * (n + 1) for _ in range(m + 1)]
    cut = [[0] * (n + 1) for _ in range(m + 1)]
    dp[m][0] = 0
    for i in range(m - 1, -1, -1):
        for k in range(1, n + 1):
            if k == 1:
                dp[i][1] = abs(line_width(i, m) - target)
                cut[i][1] = m
                continue
            best, bestj = INF, i + 1
            for j in range(i + 1, m - k + 2):
                c = max(abs(line_width(i, j) - target), dp[j][k - 1])
                if c < best:
                    best, bestj = c, j
            dp[i][k], cut[i][k] = best, bestj

    lines, i, k = [], 0, n
    while k > 0:
        j = cut[i][k]
        lines.append(' '.join(words[i:j]))
        i, k = j, k - 1
    # every line but the last keeps a trailing space, matching the originals
    return [l + ' ' if idx < n - 1 and l else l for idx, l in enumerate(lines)]


_fontmetrics = {}


def _metrics():
    if not _fontmetrics:
        from fontTools.ttLib import TTFont
        f = TTFont(BASE_FONT)
        _fontmetrics['upem'] = f['head'].unitsPerEm
        _fontmetrics['cmap'] = f.getBestCmap()
        _fontmetrics['hmtx'] = f['hmtx']
    return _fontmetrics


def text_width(text, height_twips):
    m = _metrics()
    cmap, hmtx, upem = m['cmap'], m['hmtx'], m['upem']
    total = 0
    for ch in text:
        g = cmap.get(ord(ch))
        total += hmtx[g][0] if g else upem // 2
    return total * height_twips / upem


MIN_SCALE = 0.72


def fit_scale(parsed, lines):
    """Largest uniform font scale (<=1) that keeps every line inside the
    original TextBounds.

    The replacement face is wider than the game's own, so even untouched Latin
    can spill out of a masked credit row. Shrinking to the recorded extent puts
    the text back in the footprint the artist laid out.
    """
    b = parsed['bounds']
    xmin = int(ffdectext.get_param(b, 'xmin') or 0)
    xmax = int(ffdectext.get_param(b, 'xmax') or 0)
    box = xmax - xmin
    if box <= 0:
        return 1.0
    heights, h = [], None
    for rec in parsed['records']:
        v = ffdectext.get_param(rec['params'], 'height')
        if v:
            h = int(v)
        heights.append(h)

    scale = 1.0
    for g in record_lines(parsed):
        w = sum(text_width(lines[i], heights[i])
                for i in g if i < len(lines) and heights[i] is not None)
        if w > box:
            scale = min(scale, box / w)
    return max(MIN_SCALE, scale)


def apply_scale(parsed, scale):
    """Return record params with every `height` multiplied by `scale`.

    A height set on one record carries to the following ones, so the scaled
    value is written explicitly onto each record that declared one.
    """
    if scale >= 0.999:
        return [r['params'] for r in parsed['records']]
    out = []
    for rec in parsed['records']:
        p = rec['params']
        h = ffdectext.get_param(p, 'height')
        if h:
            new = max(1, int(round(int(h) * scale)))
            p = re.sub(r'^height .+$', 'height %d' % new, p, count=1, flags=re.M)
        out.append(p)
    return out


def _set_param(params, key, value):
    """Set `key` in a record's param block, appending it if absent."""
    if re.search(r'^%s .+$' % key, params, re.M):
        return re.sub(r'^%s .+$' % key, '%s %d' % (key, value), params,
                      count=1, flags=re.M)
    return params + ('\r\n' if params and not params.endswith('\r\n') else '') + \
        '%s %d' % (key, value)


def record_lines(parsed):
    """Group record indices into visual lines by their y offset.

    A DefineText may put several records on one line (the game splits a name
    plate into "OFFICER " + "JAMES" that way), so records are NOT one-per-line
    and must not be positioned as if they were.
    """
    groups, cur_y, cur = [], None, []
    for i, r in enumerate(parsed['records']):
        y = ffdectext.get_param(r['params'], 'y')
        y = int(y) if y else cur_y
        if cur and y != cur_y:
            groups.append(cur)
            cur = []
        cur_y = y
        cur.append(i)
    if cur:
        groups.append(cur)
    return groups


def realign(parsed, lines):
    """Recompute record x offsets so the block keeps its original alignment.

    The original x values were computed for the English line widths, so
    reusing them leaves Korean ragged. Centred blocks are re-centred on the
    TextBounds; left-aligned blocks keep their shared x. Records sharing a
    line are laid out end to end from the line's start.
    """
    recs = parsed['records']
    if len(recs) < 2:
        return [r['params'] for r in recs]

    b = parsed['bounds']
    xmin = int(ffdectext.get_param(b, 'xmin') or 0)
    xmax = int(ffdectext.get_param(b, 'xmax') or 0)
    tx = int(ffdectext.get_param(b, 'translatex') or 0)
    box = xmax - xmin
    if box <= 0:
        return [r['params'] for r in recs]

    groups = record_lines(parsed)
    starts = []
    for g in groups:
        v = ffdectext.get_param(recs[g[0]]['params'], 'x')
        starts.append(int(v) if v else None)
    known = [v for v in starts if v is not None]
    if len(known) < 2 or max(known) - min(known) < 40:
        return [r['params'] for r in recs]      # left-aligned: leave it alone

    # resolve the effective font height for every record
    heights, h = [], None
    for r in recs:
        v = ffdectext.get_param(r['params'], 'height')
        if v:
            h = int(v)
        heights.append(h)

    centre = xmin + box / 2.0
    out = [r['params'] for r in recs]
    for gi, g in enumerate(groups):
        if starts[gi] is None or heights[g[0]] is None:
            continue
        widths = [text_width(lines[i], heights[i]) if i < len(lines) else 0
                  for i in g]
        total = sum(widths)
        pen = centre - total / 2.0 - tx
        for i, w in zip(g, widths):
            out[i] = _set_param(out[i], 'x', int(round(pen)))
            pen += w
    return out


def subset_font(chars, out_path):
    from fontTools import subset
    from fontTools.ttLib import TTFont
    opts = subset.Options()
    opts.glyph_names = True
    opts.notdef_outline = True
    opts.recalc_bounds = True
    opts.drop_tables += ['GSUB', 'GPOS', 'GDEF', 'morx', 'kerx', 'MERG', 'meta']
    f = TTFont(BASE_FONT)
    s = subset.Subsetter(options=opts)
    s.populate(text=''.join(sorted(set(chars))))
    s.subset(f)
    f.save(out_path)
    return len(set(chars))


def patch(key, translations, outdir, verbose=True, extra_chars=''):
    src = swf_path(key)
    tdir = os.path.join(RAW, key, 'texts')
    if not os.path.isdir(tdir):
        raise SystemExit('no exported texts for %s' % key)

    os.makedirs(outdir, exist_ok=True)
    tmp = tempfile.mkdtemp(prefix='kpatch_')
    imp = os.path.join(tmp, 'texts')
    os.makedirs(imp)

    charset = set(ALWAYS) | set(extra_chars)
    # every embedded font gets swapped, including ones only a dynamic
    # DefineEditText references (those never appear in a DefineText record)
    fonts = set(swffonts.scan(src)[0])
    n_tr = 0
    n_scaled = 0

    for path in sorted(glob.glob(os.path.join(tdir, '*.txt')),
                       key=lambda p: int(os.path.basename(p)[:-4])):
        cid = os.path.basename(path)[:-4]
        try:
            parsed = ffdectext.read(path)
        except ValueError:
            continue  # DefineEditText -- handled separately
        fonts.update(ffdectext.fonts_used(parsed))

        nrec = len(parsed['records'])
        groups = record_lines(parsed)
        new_lines = translations.get(cid)
        if new_lines is not None:
            text = new_lines if isinstance(new_lines, str) else ' '.join(new_lines)
            # wrap to the number of VISUAL lines, then hand each line to the
            # first record on it; records sharing a line get nothing extra
            per_line = wrap_lines(text, len(groups))
            new_lines = [''] * nrec
            for gi, g in enumerate(groups):
                new_lines[g[0]] = per_line[gi]
            n_tr += 1
        else:
            new_lines = [r['text'] for r in parsed['records']]

        charset.update(''.join(new_lines))

        scale = fit_scale(parsed, new_lines)
        if scale < 0.999:
            n_scaled += 1
            for rec, p in zip(parsed['records'], apply_scale(parsed, scale)):
                rec['params'] = p
        if cid in translations:
            for rec, p in zip(parsed['records'], realign(parsed, new_lines)):
                rec['params'] = p
        ffdectext.write(os.path.join(imp, cid + '.txt'), parsed, new_lines)

    font_ttf = os.path.join(tmp, 'kr.ttf')
    n_chars = subset_font(charset, font_ttf)

    # 1) swap every embedded font for the Korean subset
    stage1 = os.path.join(tmp, 'stage1.swf')
    args = FFDEC + ['-replace', src, stage1]
    for fid in sorted(fonts):
        args += [str(fid), font_ttf]
    r = subprocess.run(args, capture_output=True, text=True, timeout=1800)
    if not os.path.exists(stage1):
        raise SystemExit('font replace failed for %s\n%s\n%s' % (key, r.stdout, r.stderr))

    # 2) import the translated texts
    out = os.path.join(outdir, os.path.basename(src))
    r = subprocess.run(FFDEC + ['-importText', stage1, out, tmp],
                       capture_output=True, text=True, timeout=1800)
    sev = [l for l in (r.stdout + r.stderr).splitlines() if 'SEVERE' in l or 'does not contain' in l]

    if verbose:
        print('%-40s fonts=%-14s chars=%-5d translated=%-4d scaled=%-4d missing=%d'
              % (key, sorted(fonts), n_chars, n_tr, n_scaled, len(sev)))
        for l in sev[:5]:
            print('    ', l.strip())
    shutil.rmtree(tmp, ignore_errors=True)
    return out, sev


if __name__ == '__main__':
    key = sys.argv[1]
    tr = json.load(open(sys.argv[2], encoding='utf-8')) if len(sys.argv) > 2 else {}
    outdir = sys.argv[3] if len(sys.argv) > 3 else os.path.join(ROOT, 'work', 'patched')
    patch(key, tr, outdir)
