"""Keep the game's own typeface on text that was never translated.

A SWF's embedded fonts are subsetted, so getting Korean in means replacing
the whole font -- and one font id usually serves both the labels we translate
and the names we leave alone. Replacing it in bulk therefore drags untouched
English into Noto Sans as well, which is glaring on the title screen where
the credits sit under artwork still drawn in Candela.

Fix: clone each original DefineFont3 under a fresh character id, then point
every DefineText we did NOT translate back at the clone -- restoring its
original tag bytes verbatim, so its advances and kerning come back too.
"""
import os, struct, sys, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from swftags import parse_tags
from swfdec import decompress_swf
import fixadvances as fa

# tags that define a character and therefore own an id in the dictionary
ID_TAGS = {2, 4, 6, 7, 8, 10, 11, 13, 14, 17, 20, 21, 22, 32, 33, 35, 36, 37,
           39, 46, 48, 60, 63, 75, 83, 84, 90, 91}


def _tags_of(path):
    raw = decompress_swf(path)
    tmp = path + '.__kf'
    open(tmp, 'wb').write(raw)
    try:
        d, tags = parse_tags(tmp)
    finally:
        os.remove(tmp)
    return raw, tags


def _tag_header(code, length):
    if length < 0x3f:
        return struct.pack('<H', (code << 6) | length)
    return struct.pack('<H', (code << 6) | 0x3f) + struct.pack('<I', length)


def _header_start(d, code, off, ln):
    """Locate the tag header immediately before a body at `off`."""
    for hlen in (6, 2):
        q = off - hlen
        if q < 0:
            continue
        cl = struct.unpack('<H', d[q:q + 2])[0]
        if (cl >> 6) != code:
            continue
        if hlen == 6:
            if (cl & 0x3f) == 0x3f and struct.unpack('<I', d[q + 2:q + 6])[0] == ln:
                return q
        elif (cl & 0x3f) == ln:
            return q
    return None


def restore(orig_swf, patched_swf, out_swf, translated_ids, verbose=False):
    """translated_ids: set of DefineText character ids that DID get Korean."""
    oraw, otags = _tags_of(orig_swf)
    praw, ptags = _tags_of(patched_swf)

    used = set()
    for code, off, ln in ptags:
        if code in ID_TAGS:
            used.add(struct.unpack('<H', praw[off:off + 2])[0])
    for code, off, ln in otags:
        if code in ID_TAGS:
            used.add(struct.unpack('<H', oraw[off:off + 2])[0])
    next_id = max(used) + 1 if used else 1

    # original DefineFont3 bodies, keyed by their id
    orig_fonts = {}
    for code, off, ln in otags:
        if code == 75:
            fid = struct.unpack('<H', oraw[off:off + 2])[0]
            orig_fonts[fid] = oraw[off:off + ln]

    # original DefineText tags we may want back, keyed by character id
    orig_texts = {}
    for code, off, ln in otags:
        if code in (11, 33):
            cid = struct.unpack('<H', oraw[off:off + 2])[0]
            start = _header_start(oraw, code, off, ln)
            if start is not None:
                orig_texts[cid] = (code, oraw[off:off + ln])

    # which patched DefineTexts were left in English and reference which fonts
    keep = []
    needed_fonts = set()
    for code, off, ln in ptags:
        if code not in (11, 33):
            continue
        cid = struct.unpack('<H', praw[off:off + 2])[0]
        if str(cid) in translated_ids or cid in translated_ids:
            continue
        if cid not in orig_texts:
            continue
        ocode, obody = orig_texts[cid]
        try:
            t = fa.parse_text(obody, 0, ocode == 33)
        except Exception:
            continue
        fonts = {r['font'] for r in t['records'] if r['font'] is not None}
        if not fonts or not fonts.issubset(orig_fonts):
            continue
        keep.append((cid, code, off, ln, t, ocode))
        needed_fonts |= fonts

    if not keep:
        if verbose:
            print('  (nothing to restore)')
        import shutil
        shutil.copy2(patched_swf, out_swf)
        return 0, 0

    clone_id = {}
    for fid in sorted(needed_fonts):
        clone_id[fid] = next_id
        next_id += 1

    edits = []
    # 1) append cloned fonts right after the last original font tag
    font_blob = b''
    for fid, nid in sorted(clone_id.items()):
        body = bytearray(orig_fonts[fid])
        body[0:2] = struct.pack('<H', nid)
        font_blob += _tag_header(75, len(body)) + bytes(body)
    last_font_end = None
    for code, off, ln in ptags:
        if code == 75:
            last_font_end = off + ln
    if last_font_end is None:
        last_font_end = ptags[0][1]
    edits.append((last_font_end, last_font_end, font_blob))

    # 2) put each untranslated text back, pointed at its cloned font
    for cid, code, off, ln, t, ocode in keep:
        for r in t['records']:
            if r['font'] is not None:
                r['font'] = clone_id[r['font']]
        body = fa.build_text(t, ocode == 33)
        start = _header_start(praw, code, off, ln)
        if start is None:
            continue
        edits.append((start, off + ln, _tag_header(code, len(body)) + body))

    edits.sort()
    out = bytearray()
    prev = 0
    for start, end, blob in edits:
        out += praw[prev:start]
        out += blob
        prev = end
    out += praw[prev:]

    body = bytes(out)[8:]
    head = b'CWS' + bytes([praw[3]]) + struct.pack('<I', 8 + len(body))
    open(out_swf, 'wb').write(head + zlib.compress(body, 9))
    if verbose:
        print('  original typeface kept on %d texts (%d font clones)'
              % (len(keep), len(clone_id)))
    return len(keep), len(clone_id)
