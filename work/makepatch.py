"""Build the distributable patch file.

Ships DIFFERENCES, never the game's own data. Each entry is a zstd stream
compressed with the player's original (decompressed) SWF as the dictionary,
so a delta is useless without the file it patches -- and it comes out at
about 3% of the asset's size, because a SWF's bulk is artwork that the
translation never touches.

Raw file bytes would be pointless here: both sides are zlib streams, so a
byte delta between them runs at ~100%. Everything is done on the
decompressed body.
"""
import os, sys, json, glob, struct, hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from swfdec import decompress_swf

import zstandard as zstd

ROOT = os.path.dirname(HERE)
ORIG_ASSETS = os.path.join(ROOT, 'backup', 'swf-dsk-original')
ORIG_MAIN = os.path.join(ROOT, 'backup', 'DetectiveGrimoireDesktopSteam.swf')
DIST = os.path.join(ROOT, 'dist')
OUT = os.path.join(ROOT, 'release', 'DetectiveGrimoire-KR.dgpatch')

MAGIC = b'DGKRPATCH'
VERSION = 1
LEVEL = 19


def sha(b):
    return hashlib.sha256(b).hexdigest()


def collect():
    """-> [(game-relative path, original file, patched file)]"""
    out = []
    if os.path.exists(ORIG_MAIN) and os.path.exists(os.path.join(DIST, 'DetectiveGrimoireDesktopSteam.swf')):
        out.append(('DetectiveGrimoireDesktopSteam.swf', ORIG_MAIN,
                    os.path.join(DIST, 'DetectiveGrimoireDesktopSteam.swf')))
    for p in sorted(glob.glob(os.path.join(DIST, 'assets', 'swf-dsk', '**', '*.swf'),
                              recursive=True)):
        rel = os.path.relpath(p, os.path.join(DIST, 'assets', 'swf-dsk')).replace(os.sep, '/')
        o = os.path.join(ORIG_ASSETS, rel)
        if os.path.exists(o):
            out.append(('assets/swf-dsk/' + rel, o, p))
    return out


def main():
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    entries, blobs = [], []
    off = 0
    total_new = 0
    for rel, o, n in collect():
        orig_raw = open(o, 'rb').read()
        orig_body = decompress_swf(o)
        new_body = decompress_swf(n)
        c = zstd.ZstdCompressor(level=LEVEL,
                                dict_data=zstd.ZstdCompressionDict(orig_body))
        delta = c.compress(new_body)
        entries.append({
            'path': rel,
            'orig_sha': sha(orig_raw),
            'orig_body_sha': sha(orig_body),
            'new_body_sha': sha(new_body),
            'new_body_size': len(new_body),
            'off': off,
            'len': len(delta),
        })
        blobs.append(delta)
        off += len(delta)
        total_new += os.path.getsize(n)
        print('  %-42s %8d -> delta %7d (%.1f%%)'
              % (rel, os.path.getsize(n), len(delta),
                 100 * len(delta) / max(os.path.getsize(n), 1)))

    manifest = json.dumps({'version': VERSION, 'entries': entries},
                          ensure_ascii=False).encode('utf-8')
    with open(OUT, 'wb') as f:
        f.write(MAGIC)
        f.write(struct.pack('<II', VERSION, len(manifest)))
        f.write(manifest)
        for b in blobs:
            f.write(b)

    size = os.path.getsize(OUT)
    print()
    print('files      : %d' % len(entries))
    print('patched set: %.1f MB' % (total_new / 1048576))
    print('patch file : %.2f MB  (%.1f%%)  -> %s'
          % (size / 1048576, 100 * size / total_new, OUT))


if __name__ == '__main__':
    main()
