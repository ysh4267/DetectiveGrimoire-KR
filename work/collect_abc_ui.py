"""Collect the ABC constant-pool strings that the game actually shows on screen.

Sources found by reading the decompiled ActionScript:
  * minds/*.as        -> joiner1Text / joiner2Text  (deduction sentence parts,
                         drawn into the MindsGraphic EditText)
  * DialogueBox       -> confirm-dialog messages passed as literals
  * anything else we whitelist by hand below
"""
import os, re, json, glob

DEC = 'work/decomp/scripts'
OUT = 'work/abc_ui_en.json'

found = {}   # exact ABC string -> list of "where" labels


ESCAPES = {'n': chr(10), 'r': chr(13), 't': chr(9)}


def unescape(s):
    return re.sub(r'\\(.)', lambda m: ESCAPES.get(m.group(1), m.group(1)), s)


def add(s, where):
    s = unescape(s)
    if not s:
        return
    found.setdefault(s, [])
    if where not in found[s]:
        found[s].append(where)


# --- 1. mind joiner arrays -------------------------------------------------
for path in sorted(glob.glob(os.path.join(DEC, 'minds', '*.as'))):
    src = open(path, encoding='utf-8', errors='replace').read()
    cls = os.path.basename(path)[:-3]
    for field in ('joiner1Text', 'joiner2Text'):
        m = re.search(field + r'\s*=\s*\[(.*?)\];', src, re.S)
        if not m:
            continue
        for lit in re.findall(r'"((?:[^"\\]|\\.)*)"', m.group(1)):
            add(lit, '%s.%s' % (cls, field))
    m = re.search(r'^\s*name\s*=\s*"((?:[^"\\]|\\.)*)";', src, re.M)
    if m:
        add(m.group(1), cls + '.name')

# --- 2. literal messages handed to DialogueBox ----------------------------
for path in glob.glob(os.path.join(DEC, '**', '*.as'), recursive=True):
    src = open(path, encoding='utf-8', errors='replace').read()
    if 'DialogueBox(' not in src:
        continue
    rel = os.path.relpath(path, DEC).replace(os.sep, '/')
    for lit in re.findall(r'new DialogueBox\(\s*"((?:[^"\\]|\\.)*)"', src):
        add(lit, rel + ':DialogueBox')

# --- 3. hand-picked UI strings seen in the constant pool -------------------
MANUAL = [
    "Are you sure you want to QUIT the game?<font size='4'><br/><br/></font>"
    "<font size='30' color='#555555'>This game autosaves, it is<br/>"
    "safe to quit anytime.</font>",
    "Are you sure you want to QUIT to the title menu?<font size='4'><br/><br/></font>"
    "<font size='30' color='#555555'>This game autosaves, it is<br/>"
    "safe to quit anytime.</font>",
    "Are you sure you want to DELETE save slot ",
    "You can click and HOLD the back button to exit immediately from menus",
]
for s in MANUAL:
    add(s, 'manual')

# --- verify every collected string really exists in the constant pool ------
pool = json.load(open('work/extract/strings.json', encoding='utf-8'))
index = {}
for i, t in enumerate(pool):
    index.setdefault(t, []).append(i)

rows, missing = [], []
for s, where in sorted(found.items()):
    if s in index:
        rows.append({'en': s, 'indices': index[s], 'where': where})
    else:
        missing.append((s, where))

json.dump(rows, open(OUT, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('collected  :', len(found))
print('in pool    :', len(rows))
print('NOT in pool:', len(missing))
for s, w in missing[:10]:
    print('   !!', w, repr(s[:60]))
print('chars      :', sum(len(r['en']) for r in rows))
