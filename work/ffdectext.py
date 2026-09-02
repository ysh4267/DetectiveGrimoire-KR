"""Parse / rebuild JPEXS FFDec 'text:formatted' export files.

Format:  [bounds-params]([style-params]text)+
Every line inside a [...] block is "key value". Records are separated by the
'[' that follows a text run. Line endings are CRLF and must stay CRLF.
"""
import re


def _split_blocks(raw):
    """Yield (params_text, following_text) pairs. First pair is the bounds block."""
    out = []
    i = 0
    n = len(raw)
    while i < n:
        if raw[i] != '[':
            raise ValueError('expected [ at %d' % i)
        j = raw.index(']', i)
        params = raw[i + 1:j]
        k = raw.find('[', j + 1)
        if k == -1:
            text = raw[j + 1:]
            i = n
        else:
            text = raw[j + 1:k]
            i = k
        out.append((params, text))
    return out


def parse(raw):
    """-> {'bounds': str, 'records': [{'params': str, 'text': str}, ...]}"""
    blocks = _split_blocks(raw)
    bounds = blocks[0][0]
    if blocks[0][1].strip():
        raise ValueError('bounds block had trailing text: %r' % blocks[0][1])
    records = [{'params': p, 'text': t} for p, t in blocks[1:]]
    return {'bounds': bounds, 'records': records}


def full_text(parsed):
    return ''.join(r['text'] for r in parsed['records'])


def strip_kerning(params):
    """Drop spacing/spacingpair lines -- they reference the old characters."""
    lines = params.split('\r\n')
    keep = [l for l in lines if not l.startswith('spacing')]
    return '\r\n'.join(keep)


def build(parsed, texts=None, drop_kerning=True):
    """Rebuild the file. `texts` is an optional list of replacement strings,
    one per record."""
    recs = parsed['records']
    if texts is not None:
        if len(texts) != len(recs):
            raise ValueError('need %d texts, got %d' % (len(recs), len(texts)))
    parts = ['[' + parsed['bounds'] + ']']
    for idx, r in enumerate(recs):
        p = strip_kerning(r['params']) if drop_kerning else r['params']
        t = r['text'] if texts is None else texts[idx]
        parts.append('[' + p + ']' + t)
    return ''.join(parts)


def get_param(params, key):
    m = re.search(r'^%s (.+)$' % re.escape(key), params, re.M)
    return m.group(1) if m else None


def fonts_used(parsed):
    fonts = []
    cur = None
    for r in parsed['records']:
        f = get_param(r['params'], 'font')
        if f is not None:
            cur = int(f)
        if cur is not None:
            fonts.append(cur)
    return fonts


def read(path):
    with open(path, encoding='utf-8', newline='') as f:
        return parse(f.read())


def write(path, parsed, texts=None):
    data = build(parsed, texts)
    with open(path, 'wb') as f:
        f.write(data.encode('utf-8'))
