"""Assemble the Korean patch.

  work/ko/*.json   (chunk translations)  ->  dist/assets/swf-dsk/**/*.swf
  work/abc_ui_ko.json                    ->  dist/DetectiveGrimoireDesktopSteam.swf

Run with --install to copy the result over the live game (a backup must
already exist under backup/).
"""
import os, sys, json, glob, shutil, argparse

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import patch_swf
import abcpatch

ROOT = os.path.dirname(HERE)
GAME = r'e:/Program Files/SteamLibrary/steamapps/common/Detective Grimoire'
DIST = os.path.join(ROOT, 'dist')
KO = os.path.join(ROOT, 'work', 'ko')
CHUNKS = os.path.join(ROOT, 'work', 'chunks')

# SWFs whose DefineEditText is filled at runtime from ABC strings -- their
# replacement font must carry those glyphs too.
DYNAMIC = {
    'minds__MindsGraphic': 'minds',
    'menus__DialogueBoxGraphic': 'dialogs',
    'menus__MapGraphic': 'minds',
}


def load_abc_ko():
    p = os.path.join(ROOT, 'work', 'abc_ui_ko.json')
    return json.load(open(p, encoding='utf-8')) if os.path.exists(p) else {}


def collect():
    """-> {swfkey: {charId: korean}}"""
    index = json.load(open(os.path.join(CHUNKS, '_index.json'), encoding='utf-8'))
    per_swf = {}
    missing_files = []
    for row in index:
        kp = os.path.join(KO, row['file'])
        if not os.path.exists(kp):
            missing_files.append(row['file'])
            continue
        try:
            tr = json.load(open(kp, encoding='utf-8'))
        except Exception as e:
            print('!! unreadable %s: %s' % (row['file'], e))
            continue
        for swf in row['swfs']:
            per_swf.setdefault(swf, {}).update(tr)
    return per_swf, missing_files


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--install', action='store_true')
    ap.add_argument('--only', help='patch just this swf key')
    ap.add_argument('--skip-main', action='store_true')
    args = ap.parse_args()

    per_swf, missing = collect()
    if missing:
        print('!! missing translation files: %s' % ', '.join(missing))

    abc_ko = load_abc_ko()
    dyn_chars = ''.join(abc_ko.values())

    outdir_assets = os.path.join(DIST, 'assets', 'swf-dsk')
    os.makedirs(DIST, exist_ok=True)

    total_missing_glyphs = 0
    done = 0
    for key in sorted(per_swf):
        if args.only and key != args.only:
            continue
        sub = os.path.join(outdir_assets, os.path.dirname(key.replace('__', '/')))
        os.makedirs(sub, exist_ok=True)
        extra = dyn_chars if key in DYNAMIC else ''
        _, sev = patch_swf.patch(key, per_swf[key], sub, extra_chars=extra)
        total_missing_glyphs += len(sev)
        done += 1

    if not args.skip_main and abc_ko:
        src = os.path.join(GAME, 'DetectiveGrimoireDesktopSteam.swf')
        dst = os.path.join(DIST, 'DetectiveGrimoireDesktopSteam.swf')
        hit, before, after = abcpatch.patch_swf_strings(src, dst, abc_ko)
        print('main SWF: replaced %d/%d ABC strings  (%d -> %d bytes)'
              % (hit, len(abc_ko), before, after))

    print('\npatched %d SWFs, %d missing-glyph warnings' % (done, total_missing_glyphs))

    if args.install:
        n = 0
        for p in glob.glob(os.path.join(DIST, '**', '*.swf'), recursive=True):
            rel = os.path.relpath(p, DIST)
            dst = os.path.join(GAME, rel)
            shutil.copy2(p, dst)
            n += 1
        print('installed %d files into the game' % n)


if __name__ == '__main__':
    main()
