"""Parse DefineText / DefineFont3 out of a SWF to inspect real glyph advances.

Used to tell apart two possible causes of cramped Korean:
  * FFDec wrote advances that do not match the font's own metrics, or
  * the font itself is simply tight and needs tracking added.
"""
import struct, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from swftags import parse_tags
from swfdec import decompress_swf


class Bits:
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

    def rect(self):
        self.align()
        n = self.ub(5)
        for _ in range(4):
            self.sb(n)
        self.align()

    def matrix(self):
        self.align()
        if self.ub(1):
            n = self.ub(5)
            self.sb(n); self.sb(n)
        if self.ub(1):
            n = self.ub(5)
            self.sb(n); self.sb(n)
        n = self.ub(5)
        tx = self.sb(n); ty = self.sb(n)
        self.align()
        return tx, ty


def parse_define_text(d, off, ln):
    b = Bits(d, off)
    cid = b.u16()
    b.rect()
    tx, ty = b.matrix()
    glyph_bits = b.u8()
    adv_bits = b.u8()
    records = []
    while True:
        flags = b.u8()
        if flags == 0:
            break
        if flags & 0x80:                        # record type: style change
            font_id = color = xo = yo = height = None
            if flags & 0x08:
                font_id = b.u16()
            if flags & 0x04:
                n = 4 if (flags & 0x04) and False else 3
                b.u8(); b.u8(); b.u8()          # RGB (DefineText is RGB)
            if flags & 0x01:
                xo = b.s16()
            if flags & 0x02:
                yo = b.s16()
            if flags & 0x08:
                height = b.u16()
            records.append({'style': True, 'font': font_id, 'x': xo, 'y': yo,
                            'height': height, 'glyphs': []})
        else:
            count = flags & 0x7f
            g = []
            for _ in range(count):
                idx = b.ub(glyph_bits)
                adv = b.sb(adv_bits)
                g.append((idx, adv))
            b.align()
            if not records:
                records.append({'style': False, 'glyphs': []})
            records[-1]['glyphs'].extend(g)
    return {'id': cid, 'glyph_bits': glyph_bits, 'adv_bits': adv_bits,
            'records': records}


def texts(path):
    raw = decompress_swf(path)
    tmp = path + '.__rt'
    open(tmp, 'wb').write(raw)
    try:
        d, tags = parse_tags(tmp)
    finally:
        os.remove(tmp)
    out = []
    for code, off, ln in tags:
        if code == 11:                          # DefineText
            try:
                out.append(parse_define_text(d, off, ln))
            except Exception:
                pass
    return out


if __name__ == '__main__':
    swf, want = sys.argv[1], int(sys.argv[2])
    for t in texts(swf):
        if t['id'] != want:
            continue
        print('DefineText %d  glyphBits=%d advBits=%d' % (t['id'], t['glyph_bits'], t['adv_bits']))
        for r in t['records']:
            print('  style font=%s height=%s x=%s y=%s  glyphs=%d'
                  % (r.get('font'), r.get('height'), r.get('x'), r.get('y'), len(r['glyphs'])))
            print('   advances:', [a for _, a in r['glyphs']][:24])
