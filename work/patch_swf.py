"""Patch one SWF: swap its embedded fonts for a Korean subset, then import
the translated DefineText records.

Usage:  python work/patch_swf.py <swfkey> <translations.json> <outdir>

translations.json:  {"<charId>": ["line1", "line2", ...], ...}
Character ids absent from the file keep their English text (but still get
re-rendered with the replacement font, so their glyphs must be in the subset).
"""
import os, sys, json, glob, shutil, subprocess, tempfile

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


def wrap_lines(text, n, trailing_space=True):
    """Split `text` into exactly `n` lines of roughly equal visual width,
    preferring spaces as break points."""
    text = ' '.join(text.split())
    if n <= 1:
        return [text]
    target = _width(text) / n
    lines, rest = [], text
    for remaining in range(n, 1, -1):
        if not rest:
            lines.append('')
            continue
        # candidate break positions: after a space, else anywhere (CJK wraps free)
        best, best_cost = None, None
        for i in range(1, len(rest)):
            if rest[i - 1] == ' ':
                cost = abs(_width(rest[:i - 1]) - target)
            elif ord(rest[i]) > 0x2000 and ord(rest[i - 1]) > 0x2000:
                cost = abs(_width(rest[:i]) - target) + 0.5
            else:
                continue
            if best_cost is None or cost < best_cost:
                best, best_cost = i, cost
        if best is None:
            best = len(rest)
        head, rest = rest[:best], rest[best:]
        lines.append(head if head.endswith(' ') or not trailing_space else head)
        rest = rest.lstrip(' ') if head.endswith(' ') else rest
    lines.append(rest)
    return lines


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

    for path in sorted(glob.glob(os.path.join(tdir, '*.txt')),
                       key=lambda p: int(os.path.basename(p)[:-4])):
        cid = os.path.basename(path)[:-4]
        try:
            parsed = ffdectext.read(path)
        except ValueError:
            continue  # DefineEditText -- handled separately
        fonts.update(ffdectext.fonts_used(parsed))

        nrec = len(parsed['records'])
        new_lines = translations.get(cid)
        if new_lines is not None:
            if isinstance(new_lines, str):
                new_lines = wrap_lines(new_lines, nrec)
            elif len(new_lines) != nrec:
                new_lines = wrap_lines(' '.join(new_lines), nrec)
            n_tr += 1
        else:
            new_lines = [r['text'] for r in parsed['records']]

        charset.update(''.join(new_lines))
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
        print('%-40s fonts=%-14s chars=%-5d translated=%-4d missing=%d'
              % (key, sorted(fonts), n_chars, n_tr, len(sev)))
        for l in sev[:5]:
            print('    ', l.strip())
    shutil.rmtree(tmp, ignore_errors=True)
    return out, sev


if __name__ == '__main__':
    key = sys.argv[1]
    tr = json.load(open(sys.argv[2], encoding='utf-8')) if len(sys.argv) > 2 else {}
    outdir = sys.argv[3] if len(sys.argv) > 3 else os.path.join(ROOT, 'work', 'patched')
    patch(key, tr, outdir)
