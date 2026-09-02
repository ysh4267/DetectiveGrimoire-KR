"""List every embedded font in a SWF, and which fonts DefineEditText uses."""
import struct, sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from swftags import parse_tags
from swfdec import decompress_swf

FONT_TAGS = {48: 'DefineFont2', 75: 'DefineFont3', 62: 'DefineFontInfo2',
             88: 'DefineFontName', 91: 'DefineFont4'}


def _rect_bits(d, p):
    nbits = d[p] >> 3
    total = 5 + nbits * 4
    return p + (total + 7) // 8


def scan(path):
    raw = decompress_swf(path)
    tmp = path + '.__scan'
    open(tmp, 'wb').write(raw)
    try:
        d, tags = parse_tags(tmp)
    finally:
        os.remove(tmp)

    fonts, edits = [], []
    for code, off, ln in tags:
        if code in (48, 75, 91):
            fonts.append(struct.unpack('<H', d[off:off + 2])[0])
        elif code == 37:                                   # DefineEditText
            cid = struct.unpack('<H', d[off:off + 2])[0]
            p = _rect_bits(d, off + 2)
            flags = struct.unpack('<H', d[p:p + 2])[0]; p += 2
            has_font = bool(flags & 0x0001)                # bit 0 of first byte
            font_id = None
            if has_font:
                font_id = struct.unpack('<H', d[p:p + 2])[0]
            edits.append({'id': cid, 'font': font_id, 'flags': flags})
    return sorted(set(fonts)), edits


if __name__ == '__main__':
    for p in sys.argv[1:]:
        f, e = scan(p)
        print('%-46s fonts=%s' % (os.path.basename(p), f))
        for x in e:
            print('      EditText id=%-4d font=%s flags=0x%04x' % (x['id'], x['font'], x['flags']))
