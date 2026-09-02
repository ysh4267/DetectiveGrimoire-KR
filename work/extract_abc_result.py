"""Pull the {en: ko} mapping out of the ABC workflow's task output file."""
import json, sys, os

path = sys.argv[1]
raw = open(path, encoding='utf-8', errors='replace').read()
try:
    data = json.loads(raw)
    mapping = data['result']['mapping']
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'abc_ui_ko_raw.json')
    json.dump(mapping, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('saved %d mappings -> %s' % (len(mapping), out))
    print('flagged minds:', len(data['result'].get('flagged', [])))
    for k in mapping:
        if 'font' in k:
            print('dialog key  :', repr(k[:80]))
            print('dialog value:', repr(mapping[k][:80]))
            break
    raise SystemExit(0)
except SystemExit:
    raise
except Exception:
    pass

i = raw.find('{"mapping"')
if i < 0:
    raise SystemExit('no mapping object in %s' % path)

BACKSLASH = chr(92)
depth = 0
j = i
in_str = False
esc = False
while j < len(raw):
    c = raw[j]
    if esc:
        esc = False
    elif c == BACKSLASH:
        esc = True
    elif c == '"':
        in_str = not in_str
    elif not in_str:
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                break
    j += 1

data = json.loads(raw[i:j + 1])
mapping = data['mapping']
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'abc_ui_ko_raw.json')
json.dump(mapping, open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)

print('saved %d mappings -> %s' % (len(mapping), out))
print('flagged minds:', len(data.get('flagged', [])))
for k in mapping:
    if 'font' in k:
        print('dialog key  :', repr(k[:80]))
        print('dialog value:', repr(mapping[k][:80]))
        break
