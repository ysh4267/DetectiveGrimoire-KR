"""Rewrite DefineText glyph advances from the real font metrics.

The game's DefineFont3 tags carry no FontAdvanceTable (FontFlagsHasLayout is
0) -- Flash Pro baked the advances straight into each DefineText at authoring
time. So when FFDec imports text it has no metrics to work from and falls back
to a constant for every glyph it does not already know: measured on
ClueGraphic, every Hangul syllable came out 0.778 em where Noto Sans KR says
0.920 em. That is the cramped spacing.

This pass walks every DefineText, maps each glyph index back to a character
through the font's CodeTable, and writes the advance the font actually
specifies (plus optional tracking). TextBounds is recomputed to match.
"""
import os, re, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from swftags import parse_tags
from swfdec import decompress_swf


# --------------------------------------------------------------------- bits
class BitReader:
    def __init__(self, d, p=0):
        self.d, self.p, self.bit = d, p, 0

    def align(self):
        if self.bit:
            self.bit = 0
            self.p += 1

    def ub(self, n):
        v = 0
        for _ in range(n):
            v = (v << 1) | ((self.d[self.p] >> (7 - self.bit)) & 1)
            self.bit += 1
            if self.bit == 8:
                self.bit = 0
                self.p += 1
        return v

    def sb(self, n):
        v = self.ub(n)
        if n and (v >> (n - 1)) & 1:
            v -= 1 << n
        return v

    def u8(self):
        self.align()
        v = self.d[self.p]
        self.p += 1
        return v

    def u16(self):
        self.align()
        v = struct.unpack('<H', self.d[self.p:self.p + 2])[0]
        self.p += 2
        return v

    def s16(self):
        self.align()
        v = struct.unpack('<h', self.d[self.p:self.p + 2])[0]
        self.p += 2
        return v

    def bytes(self, n):
        self.align()
        v = self.d[self.p:self.p + n]
        self.p += n
        return v


class BitWriter:
    def __init__(self):
        self.out = bytearray()
        self.acc = 0
        self.nbits = 0

    def ub(self, v, n):
        for i in range(n - 1, -1, -1):
            self.acc = (self.acc << 1) | ((v >> i) & 1)
            self.nbits += 1
            if self.nbits == 8:
                self.out.append(self.acc)
                self.acc = 0
                self.nbits = 0

    def sb(self, v, n):
        self.ub(v & ((1 << n) - 1), n)

    def align(self):
        if self.nbits:
            self.acc <<= (8 - self.nbits)
            self.out.append(self.acc)
            self.acc = 0
            self.nbits = 0

    def u8(self, v):
        self.align()
        self.out.append(v & 0xff)

    def u16(self, v):
        self.align()
        self.out += struct.pack('<H', v & 0xffff)

    def s16(self, v):
        self.align()
        self.out += struct.pack('<h', v)

    def raw(self, b):
        self.align()
        self.out += b

    def data(self):
        self.align()
        return bytes(self.out)


def bits_needed_u(values):
    n = 1
    for v in values:
        while v >= (1 << n):
            n += 1
    return n


def bits_needed_s(values):
    n = 2
    for v in values:
        while not (-(1 << (n - 1)) <= v < (1 << (n - 1))):
            n += 1
    return n


def write_rect(w, xmin, xmax, ymin, ymax):
    vals = [xmin, xmax, ymin, ymax]
    n = bits_needed_s(vals)
    w.align()
    w.ub(n, 5)
    for v in vals:
        w.sb(v, n)
    w.align()


# ---------------------------------------------------------------- font tags
def parse_font3_codes(d, off):
    """-> (font_id, [unicode per glyph index]) for a DefineFont3 tag body."""
    p = off
    font_id = struct.unpack('<H', d[p:p + 2])[0]; p += 2
    flags = d[p]; p += 1
    wide_offsets = bool(flags & 0x08)
    wide_codes = bool(flags & 0x04)
    p += 1                                   # LanguageCode
    name_len = d[p]; p += 1
    p += name_len
    num = struct.unpack('<H', d[p:p + 2])[0]; p += 2
    tbl = p
    osz = 4 if wide_offsets else 2
    fmt = '<I' if wide_offsets else '<H'
    code_off = struct.unpack(fmt, d[tbl + osz * num: tbl + osz * num + osz])[0]
    p = tbl + code_off
    csz = 2 if wide_codes else 1
    cfmt = '<H' if wide_codes else '<B'
    codes = [struct.unpack(cfmt, d[p + i * csz: p + i * csz + csz])[0] for i in range(num)]
    return font_id, codes


# ---------------------------------------------------------------- text tags
def parse_text(d, off, is_text2):
    b = BitReader(d, off)
    cid = b.u16()
    b.align()
    nb = b.ub(5)
    bounds = [b.sb(nb) for _ in range(4)]        # xmin xmax ymin ymax
    b.align()
    # MATRIX
    mstart = b.p
    if b.ub(1):
        n = b.ub(5); b.sb(n); b.sb(n)
    if b.ub(1):
        n = b.ub(5); b.sb(n); b.sb(n)
    n = b.ub(5)
    tx = b.sb(n); ty = b.sb(n)
    b.align()
    matrix = d[mstart:b.p]
    glyph_bits = b.u8()
    adv_bits = b.u8()

    records = []
    while True:
        save = b.p
        flags = b.u8()
        if flags == 0:
            break
        if flags & 0x80:
            rec = {'type': 'style', 'font': None, 'color': None,
                   'x': None, 'y': None, 'height': None, 'glyphs': []}
            if flags & 0x08:
                rec['font'] = b.u16()
            if flags & 0x04:
                rec['color'] = b.bytes(4 if is_text2 else 3)
            if flags & 0x01:
                rec['x'] = b.s16()
            if flags & 0x02:
                rec['y'] = b.s16()
            if flags & 0x08:
                rec['height'] = b.u16()
            records.append(rec)
        else:
            count = flags & 0x7f
            g = [(b.ub(glyph_bits), b.sb(adv_bits)) for _ in range(count)]
            b.align()
            if not records:
                records.append({'type': 'style', 'font': None, 'color': None,
                                'x': None, 'y': None, 'height': None, 'glyphs': []})
            records[-1]['glyphs'].extend(g)
    return {'id': cid, 'bounds': bounds, 'matrix': matrix, 'records': records,
            'end': b.p}


def build_text(t, is_text2):
    all_g = [g for r in t['records'] for g in r['glyphs']]
    gb = bits_needed_u([i for i, _ in all_g]) if all_g else 1
    ab = bits_needed_s([a for _, a in all_g]) if all_g else 2

    w = BitWriter()
    w.u16(t['id'])
    write_rect(w, t['bounds'][0], t['bounds'][1], t['bounds'][2], t['bounds'][3])
    w.raw(t['matrix'])
    w.u8(gb)
    w.u8(ab)
    for r in t['records']:
        flags = 0x80
        if r['font'] is not None:
            flags |= 0x08
        if r['color'] is not None:
            flags |= 0x04
        if r['x'] is not None:
            flags |= 0x01
        if r['y'] is not None:
            flags |= 0x02
        w.u8(flags)
        if r['font'] is not None:
            w.u16(r['font'])
        if r['color'] is not None:
            w.raw(r['color'])
        if r['x'] is not None:
            w.s16(r['x'])
        if r['y'] is not None:
            w.s16(r['y'])
        if r['font'] is not None:
            w.u16(r['height'] if r['height'] is not None else 0)
        g = r['glyphs']
        for i in range(0, len(g), 127):
            chunk = g[i:i + 127]
            w.u8(len(chunk))
            for idx, adv in chunk:
                w.ub(idx, gb)
                w.sb(adv, ab)
            w.align()
    w.u8(0)
    return w.data()


# ------------------------------------------------------------------- driver
def u30(v):
    out = bytearray()
    while True:
        b = v & 0x7f
        v >>= 7
        if v:
            out.append(b | 0x80)
        else:
            out.append(b)
            break
    return bytes(out)


def tag_header(code, length):
    if length < 0x3f:
        return struct.pack('<H', (code << 6) | length)
    return struct.pack('<H', (code << 6) | 0x3f) + struct.pack('<I', length)


def fix(swf_in, swf_out, ttf, tracking_em=0.0, verbose=False):
    """Rewrite every DefineText advance using `ttf`'s metrics.

    tracking_em adds uniform letter spacing, expressed in em.
    """
    from fontTools.ttLib import TTFont
    fnt = TTFont(ttf)
    upem = fnt['head'].unitsPerEm
    cmap = fnt.getBestCmap()
    hmtx = fnt['hmtx']

    def adv_units(ch):
        g = cmap.get(ch)
        if g is None:
            return None
        return hmtx[g][0]

    raw = decompress_swf(swf_in)
    tmp = swf_out + '.__fa'
    open(tmp, 'wb').write(raw)
    try:
        d, tags = parse_tags(tmp)
    finally:
        os.remove(tmp)

    codes = {}
    for code, off, ln in tags:
        if code == 75:
            try:
                fid, cs = parse_font3_codes(d, off)
                codes[fid] = cs
            except Exception:
                pass

    edits = []      # (tag_start, tag_end, new_body, code)
    n_glyphs = n_changed = 0
    for code, off, ln in tags:
        if code not in (11, 33):
            continue
        try:
            t = parse_text(d, off, code == 33)
        except Exception:
            continue

        font = height = None
        changed = False
        minx = 10 ** 9
        maxx = -10 ** 9
        pen = 0
        for r in t['records']:
            if r['font'] is not None:
                font = r['font']
                height = r['height']
            if r['x'] is not None:
                pen = r['x']
            cs = codes.get(font)
            newg = []
            for idx, adv in r['glyphs']:
                n_glyphs += 1
                want = adv
                if cs and idx < len(cs) and height:
                    a = adv_units(cs[idx])
                    if a is not None:
                        want = int(round((a / upem + tracking_em) * height))
                if want != adv:
                    changed = True
                    n_changed += 1
                newg.append((idx, want))
                minx = min(minx, pen)
                pen += want
                maxx = max(maxx, pen)
            r['glyphs'] = newg

        if not changed:
            continue
        # widen the recorded bounds if the new run is longer
        if maxx > -10 ** 9:
            t['bounds'][1] = max(t['bounds'][1], maxx + 40)
            t['bounds'][0] = min(t['bounds'][0], minx - 40)
        body = build_text(t, code == 33)

        # locate the tag header that precedes this body
        start = None
        for hlen in (6, 2):
            q = off - hlen
            if q < 0:
                continue
            cl = struct.unpack('<H', d[q:q + 2])[0]
            if (cl >> 6) != code:
                continue
            if hlen == 6:
                if (cl & 0x3f) == 0x3f and struct.unpack('<I', d[q + 2:q + 6])[0] == ln:
                    start = q
                    break
            else:
                if (cl & 0x3f) == ln:
                    start = q
                    break
        if start is None:
            continue
        edits.append((start, off + ln, tag_header(code, len(body)) + body))

    if not edits:
        if verbose:
            print('%s: nothing to fix' % os.path.basename(swf_in))
        import shutil
        shutil.copy2(swf_in, swf_out)
        return 0, 0

    edits.sort()
    out = bytearray()
    prev = 0
    for start, end, blob in edits:
        out += raw[prev:start]
        out += blob
        prev = end
    out += raw[prev:]

    # rewrite FileLength then recompress
    import zlib
    body = bytes(out)[8:]
    total = 8 + len(body)
    head = b'CWS' + bytes([raw[3]]) + struct.pack('<I', total)
    open(swf_out, 'wb').write(head + zlib.compress(body, 9))
    if verbose:
        print('%-34s texts=%-4d glyphs=%-6d rewritten=%d'
              % (os.path.basename(swf_in), len(edits), n_glyphs, n_changed))
    return len(edits), n_changed


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('swf_in')
    ap.add_argument('swf_out')
    ap.add_argument('--font', default='work/fonts/base_kr.ttf')
    ap.add_argument('--tracking', type=float, default=0.0)
    a = ap.parse_args()
    fix(a.swf_in, a.swf_out, a.font, a.tracking, verbose=True)
