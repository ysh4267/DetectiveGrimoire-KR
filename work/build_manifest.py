import os, json, sys, glob
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import ffdectext

RAW = 'work/text_raw'
entries = []
bad = []
for swfkey in sorted(os.listdir(RAW)):
    tdir = os.path.join(RAW, swfkey, 'texts')
    if not os.path.isdir(tdir):
        continue
    for path in sorted(glob.glob(os.path.join(tdir, '*.txt')),
                       key=lambda p: int(os.path.basename(p)[:-4])):
        cid = int(os.path.basename(path)[:-4])
        try:
            p = ffdectext.read(path)
        except Exception as e:
            bad.append((path, str(e)))
            continue
        entries.append({
            'swf': swfkey,
            'id': cid,
            'lines': [r['text'] for r in p['records']],
            'fonts': ffdectext.fonts_used(p),
            'text': ffdectext.full_text(p),
        })

json.dump(entries, open('work/manifest_en.json', 'w', encoding='utf-8'),
          ensure_ascii=False, indent=1)

nchars = sum(len(e['text']) for e in entries)
nwords = sum(len(e['text'].split()) for e in entries)
print('entries:', len(entries))
print('parse failures:', len(bad))
for p, e in bad[:10]:
    print('   ', p, e)
print('total chars:', nchars)
print('total words:', nwords)
print()
from collections import Counter
c = Counter(e['swf'] for e in entries)
w = Counter()
for e in entries:
    w[e['swf']] += len(e['text'].split())
print('%-40s %6s %8s' % ('SWF', 'TAGS', 'WORDS'))
for k, n in sorted(w.items(), key=lambda x: -x[1]):
    print('%-40s %6d %8d' % (k, c[k], n))
