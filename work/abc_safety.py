"""Decide which ABC constant-pool strings are safe to translate.

ABC strings are shared by index, so replacing one rewrites EVERY use of it.
Several game strings double as machine identifiers:

  * DataItem.name  -> DataList._nameLookup key, and byName("cogs") literals
  * char.name      -> built into audio paths: "surprised/" + name + "/x.mp3"
  * area.name      -> MovieClip frame label: gotoAndStop(area.name)
                      and child lookup: _menuGraphic.locations[name]

Translating any of those breaks the game silently, so a string is only
translatable when its sole appearance in the decompiled source is inside a
joiner1Text / joiner2Text array or a DialogueBox message literal.
"""
import os, re, json, glob

DEC = 'work/decomp/scripts'


ESCAPES = {'n': chr(10), 'r': chr(13), 't': chr(9)}


def unescape(s):
    return re.sub(r'\\(.)', lambda m: ESCAPES.get(m.group(1), m.group(1)), s)


def source_files():
    return glob.glob(os.path.join(DEC, '**', '*.as'), recursive=True)


def joiner_literals():
    """-> set of strings that appear inside a joiner array"""
    out = set()
    for path in glob.glob(os.path.join(DEC, 'minds', '*.as')):
        src = open(path, encoding='utf-8', errors='replace').read()
        for field in ('joiner1Text', 'joiner2Text'):
            m = re.search(field + r'\s*=\s*\[(.*?)\];', src, re.S)
            if m:
                for lit in re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(1)):
                    out.add(unescape(lit))
    return out


def unsafe_literals():
    """Strings used anywhere as an identifier, path fragment or lookup key."""
    bad = set()
    pat_name = re.compile(r'^\s*name\s*=\s*"((?:[^"\\]|\\.)*)";', re.M)
    pat_byname = re.compile(r'byName\(\s*"((?:[^"\\]|\\.)*)"')
    pat_frame = re.compile(r'gotoAndStop\(\s*"((?:[^"\\]|\\.)*)"')
    pat_audio = re.compile(r'(?:Audio|playShortAudio|playAudio|audioPath)[^;\n]*"((?:[^"\\]|\\.)*)"')
    for path in source_files():
        src = open(path, encoding='utf-8', errors='replace').read()
        for pat in (pat_name, pat_byname, pat_frame, pat_audio):
            bad.update(unescape(x) for x in pat.findall(src))
        # every *Audio array entry is a filename
        for field in ('itemAudio', 'joiner1Audio', 'joiner2Audio', 'hintAudio',
                      'examineAudio', '_centralAudio'):
            for m in re.finditer(field + r'\s*=\s*\[(.*?)\];', src, re.S):
                bad.update(unescape(x) for x in
                           re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(1)))
    return bad


def _reescape(s):
    """Turn a decoded literal back into its ActionScript source form."""
    return s.replace('\\', '\\\\').replace('"', '\\"')


def other_context_hits(literal):
    """Count appearances of the literal outside joiner arrays."""
    n = 0
    needle = '"' + _reescape(literal) + '"'
    for path in source_files():
        src = open(path, encoding='utf-8', errors='replace').read()
        if needle not in src:
            continue
        stripped = src
        for field in ('joiner1Text', 'joiner2Text'):
            stripped = re.sub(field + r'\s*=\s*\[.*?\];', '', stripped, flags=re.S)
        stripped = re.sub(r'new DialogueBox\(.*?\)', '', stripped, flags=re.S)
        n += stripped.count(needle)
    return n


def build(mapping):
    """Filter a {en: ko} mapping down to the entries that are safe."""
    joiners = joiner_literals()
    bad = unsafe_literals()
    pool = json.load(open('work/extract/strings.json', encoding='utf-8'))
    counts = {}
    for t in pool:
        counts[t] = counts.get(t, 0) + 1

    safe, rejected = {}, []
    for en, ko in mapping.items():
        if en in bad:
            rejected.append((en, 'used as identifier / audio path / frame label'))
            continue
        if en not in counts:
            rejected.append((en, 'not present in constant pool'))
            continue
        is_dialog = '<font' in en or en.startswith('Are you sure') or en.startswith('You can click')
        if not is_dialog:
            if en not in joiners:
                rejected.append((en, 'not a joiner literal'))
                continue
            if other_context_hits(en):
                rejected.append((en, 'also referenced outside a joiner array'))
                continue
        safe[en] = ko
    return safe, rejected


if __name__ == '__main__':
    import sys
    src = sys.argv[1] if len(sys.argv) > 1 else 'work/abc_ui_ko_raw.json'
    mapping = json.load(open(src, encoding='utf-8'))
    safe, rejected = build(mapping)
    json.dump(safe, open('work/abc_ui_ko.json', 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    print('input   : %d' % len(mapping))
    print('safe    : %d  -> work/abc_ui_ko.json' % len(safe))
    print('rejected: %d' % len(rejected))
    for en, why in rejected:
        print('   - %-46s %s' % (repr(en[:44]), why))
