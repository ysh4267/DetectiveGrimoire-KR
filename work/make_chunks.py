"""Split the English manifest into translation chunks.

Identical text sets are shared by several SWFs (the minigames all embed the
same UI library), so chunks are keyed by content and mapped back to every SWF
that uses them.
"""
import os, json, re, hashlib

MANIFEST = 'work/manifest_en.json'
OUT = 'work/chunks'
MAX_CHARS = 12000

os.makedirs(OUT, exist_ok=True)
entries = json.load(open(MANIFEST, encoding='utf-8'))


def is_content(e):
    """Skip decorative single glyphs and empties -- they stay as-is."""
    t = e['text'].strip()
    if not t:
        return False
    if len(t) <= 2 and not re.search(r'[A-Za-z]{2}', t):
        return False
    return True


by_swf = {}
for e in entries:
    by_swf.setdefault(e['swf'], []).append(e)

# fingerprint each SWF's translatable content so duplicates collapse
groups = {}
for swf in sorted(by_swf):
    items = [{'id': str(e['id']), 'lines': len(e['lines']), 'en': e['text']}
             for e in by_swf[swf] if is_content(e)]
    if not items:
        continue
    fp = hashlib.sha1(json.dumps(items, ensure_ascii=False,
                                 sort_keys=True).encode()).hexdigest()[:12]
    groups.setdefault(fp, {'items': items, 'swfs': []})['swfs'].append(swf)

chunks = []
for fp, g in sorted(groups.items(), key=lambda kv: -sum(len(i['en']) for i in kv[1]['items'])):
    name = g['swfs'][0]
    part, size = [], 0
    parts = []
    for it in g['items']:
        c = len(it['en'])
        if part and size + c > MAX_CHARS:
            parts.append(part)
            part, size = [], 0
        part.append(it)
        size += c
    if part:
        parts.append(part)
    for pi, p in enumerate(parts):
        chunks.append({'group': name, 'part': pi, 'nparts': len(parts),
                       'swfs': g['swfs'], 'items': p})

index = []
for ch in chunks:
    suffix = '' if ch['nparts'] == 1 else '_p%d' % (ch['part'] + 1)
    name = '%s%s.json' % (ch['group'], suffix)
    json.dump(ch, open(os.path.join(OUT, name), 'w', encoding='utf-8'),
              ensure_ascii=False, indent=1)
    index.append({'file': name, 'group': ch['group'], 'swfs': ch['swfs'],
                  'n': len(ch['items']),
                  'chars': sum(len(x['en']) for x in ch['items'])})

index.sort(key=lambda m: -m['chars'])
json.dump(index, open(os.path.join(OUT, '_index.json'), 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)

print('chunks: %d   items: %d   chars: %d'
      % (len(index), sum(m['n'] for m in index), sum(m['chars'] for m in index)))
print()
for m in index:
    extra = '  (shared by %d SWFs)' % len(m['swfs']) if len(m['swfs']) > 1 else ''
    print('  %-42s %4d items %6d chars%s' % (m['file'], m['n'], m['chars'], extra))
