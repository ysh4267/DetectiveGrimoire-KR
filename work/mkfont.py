"""Create a static Korean base font from the system Noto Sans KR variable font."""
import os, sys
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

SRC = r'C:\Windows\Fonts\NotoSansKR-VF.ttf'
OUT = 'work/fonts/base_kr.ttf'
WEIGHT = 700  # Bold -- the game's Candela Bold is a heavy face

os.makedirs('work/fonts', exist_ok=True)
f = TTFont(SRC)
if 'fvar' in f:
    axes = {a.axisTag: (a.minValue, a.defaultValue, a.maxValue) for a in f['fvar'].axes}
    print('axes:', axes)
    f = instancer.instantiateVariableFont(f, {'wght': WEIGHT}, inplace=False, updateFontNames=False)
    print('instantiated at wght=%d' % WEIGHT)
f.save(OUT)
g = TTFont(OUT)
cmap = g.getBestCmap()
print('saved %s  glyphs=%d  cmap=%d' % (OUT, g['maxp'].numGlyphs, len(cmap)))
print('has hangul:', hex(0xAC00) if 0xAC00 in cmap else 'NO')
print('has latin A:', 0x41 in cmap)
