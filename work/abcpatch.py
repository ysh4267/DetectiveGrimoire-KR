"""Rewrite strings in an ABC constant pool inside a SWF's DoABC tag.

ABC references strings purely by index, so swapping the bytes of the string
table (keeping count and order) is safe even when lengths change. Everything
downstream -- DoABC tag length, SWF FileLength -- is recomputed.
"""
import struct, zlib, sys, os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from swftags import parse_tags


# ---------------------------------------------------------------- primitives
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


class R:
    def __init__(self, d, p=0):
        self.d, self.p = d, p

    def u8(self):
        v = self.d[self.p]; self.p += 1; return v

    def u16(self):
        v = struct.unpack('<H', self.d[self.p:self.p + 2])[0]; self.p += 2; return v

    def u30(self):
        r = s = 0
        while True:
            b = self.d[self.p]; self.p += 1
            r |= (b & 0x7f) << s
            if not (b & 0x80):
                return r
            s += 7

    def d64(self):
        v = struct.unpack('<d', self.d[self.p:self.p + 8])[0]; self.p += 8; return v


# ------------------------------------------------------------------ ABC pool
def string_table_span(abc):
    """-> (start, end, [bytes...]) covering the whole cpool string section
    including its leading count."""
    r = R(abc)
    r.u16(); r.u16()                       # minor / major
    n = r.u30()
    for _ in range(max(0, n - 1)):
        r.u30()                            # ints (s32 shares the varint shape)
    n = r.u30()
    for _ in range(max(0, n - 1)):
        r.u30()                            # uints
    n = r.u30()
    for _ in range(max(0, n - 1)):
        r.d64()                            # doubles

    start = r.p
    count = r.u30()
    strings = [b'']
    for _ in range(max(0, count - 1)):
        ln = r.u30()
        strings.append(abc[r.p:r.p + ln])
        r.p += ln
    return start, r.p, strings


def rebuild_pool(abc, new_strings):
    start, end, old = string_table_span(abc)
    if len(new_strings) != len(old):
        raise ValueError('string count must stay %d (got %d)' % (len(old), len(new_strings)))
    out = bytearray(u30(len(new_strings)))
    for s in new_strings[1:]:
        out += u30(len(s)) + s
    return abc[:start] + bytes(out) + abc[end:]


# ------------------------------------------------------------------ SWF glue
def read_swf(path):
    """Return the fully decompressed SWF bytes (FWS)."""
    from swfdec import decompress_swf
    return decompress_swf(path)


def write_swf(raw, path, compress='zlib'):
    """raw must be an uncompressed FWS image. Rewrites FileLength and emits
    FWS / CWS."""
    body = raw[8:]
    total = 8 + len(body)
    version = raw[3]
    head = b'FWS' + bytes([version]) + struct.pack('<I', total)
    if compress == 'zlib':
        head = b'CWS' + head[3:]
        payload = zlib.compress(body, 9)
    else:
        payload = body
    with open(path, 'wb') as f:
        f.write(head + payload)
    return total


def patch_swf_strings(src, dst, replacements, compress='zlib'):
    """replacements: {old_string_text: new_string_text} matched on exact UTF-8."""
    raw = read_swf(src)
    tmp = dst + '.__tmp'
    open(tmp, 'wb').write(raw)
    d, tags = parse_tags(tmp)
    os.remove(tmp)

    doabc = [t for t in tags if t[0] == 82]
    if len(doabc) != 1:
        raise ValueError('expected exactly one DoABC, found %d' % len(doabc))
    code, off, ln = doabc[0]

    body = raw[off:off + ln]
    zpos = body.index(b'\x00', 4)
    prefix = body[:zpos + 1]                # flags + null-terminated name
    abc = body[zpos + 1:]

    start, end, strings = string_table_span(abc)
    n_hit = 0
    new_strings = []
    for s in strings:
        try:
            t = s.decode('utf-8')
        except UnicodeDecodeError:
            new_strings.append(s)
            continue
        if t in replacements:
            new_strings.append(replacements[t].encode('utf-8'))
            n_hit += 1
        else:
            new_strings.append(s)

    new_abc = rebuild_pool(abc, new_strings)
    new_body = prefix + new_abc

    # splice the tag back in, rewriting its header (force the long form)
    tag_hdr_start = off
    # walk back over the existing header to find where it began
    p = off - 1
    # long header is 6 bytes, short is 2; detect by re-reading
    for hdr_len in (6, 2):
        q = off - hdr_len
        if q < 0:
            continue
        cl = struct.unpack('<H', raw[q:q + 2])[0]
        if (cl >> 6) == 82:
            if hdr_len == 6:
                if (cl & 0x3f) == 0x3f and struct.unpack('<I', raw[q + 2:q + 6])[0] == ln:
                    tag_hdr_start = q
                    break
            else:
                if (cl & 0x3f) == ln:
                    tag_hdr_start = q
                    break
    else:
        raise ValueError('could not locate DoABC tag header')

    new_hdr = struct.pack('<H', (82 << 6) | 0x3f) + struct.pack('<I', len(new_body))
    new_raw = raw[:tag_hdr_start] + new_hdr + new_body + raw[off + ln:]
    total = write_swf(new_raw, dst, compress)
    return n_hit, len(raw), total


if __name__ == '__main__':
    import json
    src, dst, mapfile = sys.argv[1], sys.argv[2], sys.argv[3]
    reps = json.load(open(mapfile, encoding='utf-8'))
    hit, before, after = patch_swf_strings(src, dst, reps)
    print('replaced %d strings   %d -> %d bytes (uncompressed)' % (hit, before, after))
