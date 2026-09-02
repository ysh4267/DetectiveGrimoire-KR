import os, subprocess, sys

GAME = r'e:/Program Files/SteamLibrary/steamapps/common/Detective Grimoire'
SWFDIR = os.path.join(GAME, 'assets', 'swf-dsk')
OUT = 'work/text_raw'
FFDEC = ['java', '-Xmx2g', '-jar', 'tools/ffdec/ffdec.jar']

os.makedirs(OUT, exist_ok=True)

swfs = []
for root, dirs, files in os.walk(SWFDIR):
    for f in files:
        if f.endswith('.swf'):
            swfs.append(os.path.join(root, f))
swfs.sort()

total = 0
for p in swfs:
    rel = os.path.relpath(p, SWFDIR).replace(os.sep, '/')
    key = rel[:-4].replace('/', '__')
    dst = os.path.join(OUT, key, 'texts')
    os.makedirs(dst, exist_ok=True)
    subprocess.run(FFDEC + ['-format', 'text:formatted', '-export', 'text', dst, p],
                   capture_output=True, text=True, timeout=900)
    n = len([x for x in os.listdir(dst) if x.endswith('.txt')])
    total += n
    print('%-50s %3d texts' % (rel, n), flush=True)

print('TOTAL TEXT TAGS:', total)
