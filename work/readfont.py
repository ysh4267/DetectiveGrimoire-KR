"""Read a DefineFont3's code table and FontAdvanceTable straight out of a SWF.

FFDec's font export rewrites metrics (and warns about hmtx), so it cannot be
trusted to say what the player actually sees. The advance table in the tag is
authoritative: rendered advance = entry * textHeight / 1024.
"""
import struct, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from swftags import parse_tags
from swfdec import decompress_swf


def parse_font3(d, off, ln):
    p = off
    font_id = struct.unpack('<H', d[p:p + 2])[0]; p += 2
    flags = d[p]; p += 1
    has_layout = bool(flags & 0x80)
    wide_offsets = bool(flags & 0x08)
    wide_codes = bool(flags & 0x04)
    p += 1                                        # LanguageCode
    name_len = d[p]; p += 1
    name = d[p:p + name_len].decode('utf-8', 'replace'); p += name_len
    num = struct.unpack('<H', d[p:p + 2])[0]; p += 2

    tbl_start = p
    osz = 4 if wide_offsets else 2
    p += osz * num + osz                          # offset table + CodeTableOffset
    if wide_offsets:
        code_off = struct.unpack('<I', d[tbl_start + osz * num:tbl_start + osz * num + 4])[0]
    else:
        code_off = struct.unpack('<H', d[tbl_start + osz * num:tbl_start + osz * num + 2])[0]

    p = tbl_start + code_off                      # start of CodeTable
    csz = 2 if wide_codes else 1
    codes = []
    for i in range(num):
        codes.append(struct.unpack('<H' if wide_codes else '<B', d[p:p + csz])[0])
        p += csz

    out = {'id': font_id, 'name': name, 'num': num, 'codes': codes,
           'has_layout': has_layout, 'advances': None,
           'ascent': None, 'descent': None, 'leading': None}
    if has_layout:
        out['ascent'] = struct.unpack('<h', d[p:p + 2])[0]; p += 2
        out['descent'] = struct.unpack('<h', d[p:p + 2])[0]; p += 2
        out['leading'] = struct.unpack('<h', d[p:p + 2])[0]; p += 2
        adv = []
        for i in range(num):
            adv.append(struct.unpack('<h', d[p:p + 2])[0]); p += 2
        out['advances'] = adv
    return out


def fonts(path):
    raw = decompress_swf(path)
    tmp = path + '.__rf'
    open(tmp, 'wb').write(raw)
    try:
        d, tags = parse_tags(tmp)
    finally:
        os.remove(tmp)
    out = []
    for code, off, ln in tags:
        if code == 75:                            # DefineFont3
            try:
                out.append(parse_font3(d, off, ln))
            except Exception as e:
                out.append({'id': None, 'error': str(e)})
    return out


if __name__ == '__main__':
    swf = sys.argv[1]
    want = int(sys.argv[2]) if len(sys.argv) > 2 else None
    chars = sys.argv[3] if len(sys.argv) > 3 else '관광 명소A1'
    for f in fonts(swf):
        if 'error' in f:
            print('parse error:', f['error']); continue
        if want is not None and f['id'] != want:
            continue
        print('DefineFont3 id=%d name=%r glyphs=%d layout=%s ascent=%s descent=%s'
              % (f['id'], f['name'], f['num'], f['has_layout'], f['ascent'], f['descent']))
        if not f['advances']:
            continue
        idx = {c: i for i, c in enumerate(f['codes'])}
        for ch in chars:
            i = idx.get(ord(ch))
            if i is None:
                print('   %-3r not in font' % ch); continue
            a = f['advances'][i]
            print('   %-3r code=U+%04X adv=%-6d = %.3f em   (at height 600 -> %.0f twips)'
                  % (ch, ord(ch), a, a / 1024.0, a * 600 / 1024.0))
