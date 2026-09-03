"""Create the static Korean base font from the system Noto Sans KR variable font.

Two things matter for SWF embedding:

1. The variable instance carries overlapping contours (a Hangul syllable is
   built from 4-8 stroke outlines that cross each other). Most renderers use
   non-zero winding and never show that, but SWF fills each edge with an
   explicit left/right style, so every crossing turns into a visible hairline
   seam through the glyph. Booleans have to be resolved up front.

2. unitsPerEm stays 1000 so downstream advance maths is exact.
"""
import os, sys
from fontTools.ttLib import TTFont
from fontTools.varLib import instancer
from fontTools.ttLib.removeOverlaps import removeOverlaps

SRC = r'C:\Windows\Fonts\NotoSansKR-VF.ttf'
OUT = 'work/fonts/base_kr.ttf'
WEIGHT = 700          # the game's Candela Bold is a heavy face

os.makedirs('work/fonts', exist_ok=True)

f = TTFont(SRC)
if 'fvar' in f:
    axes = {a.axisTag: (a.minValue, a.defaultValue, a.maxValue) for a in f['fvar'].axes}
    print('axes:', axes)
    f = instancer.instantiateVariableFont(f, {'wght': WEIGHT}, inplace=False,
                                          updateFontNames=False)
    print('instantiated at wght=%d' % WEIGHT)

print('removing contour overlaps (this is the seam fix; takes a minute)...')
removeOverlaps(f)

f.save(OUT)

g = TTFont(OUT)
cmap = g.getBestCmap()
print('saved %s  glyphs=%d  cmap=%d  upem=%d'
      % (OUT, g['maxp'].numGlyphs, len(cmap), g['head'].unitsPerEm))
print('hangul U+AC00:', 'yes' if 0xAC00 in cmap else 'NO')
print('latin A      :', 'yes' if 0x41 in cmap else 'NO')

# report how much overlap removal actually changed
gs = g.getGlyphSet()
from fontTools.pens.recordingPen import RecordingPen


def contours(gset, name):
    pen = RecordingPen()
    gset[name].draw(pen)
    return sum(1 for op, _ in pen.value if op == 'moveTo')


for ch in '관명소':
    n = cmap.get(ord(ch))
    if n:
        print('  %s contours after merge: %d' % (ch, contours(gs, n)))
