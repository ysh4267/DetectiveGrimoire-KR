"""Render the same dialogue line at several tracking values.

Spacing in the SWF is pure advance arithmetic, so a PIL render with the same
per-glyph advances shows exactly what the game will do -- without paying for a
20-minute rebuild per candidate.
"""
import os
from PIL import Image, ImageDraw, ImageFont
from fontTools.ttLib import TTFont

FONT = 'work/fonts/base_kr.ttf'
OUT = 'work/shots/tracking_preview.png'
LINE = '내가 읽은 건 백 년'
LINE2 = '관광 명소 "보기의 늪"의'
PX = 64
CANDIDATES = [0.0, 0.015, 0.03, 0.045, 0.06]

tt = TTFont(FONT)
upem = tt['head'].unitsPerEm
cmap = tt.getBestCmap()
hmtx = tt['hmtx']
pil = ImageFont.truetype(FONT, PX)


def adv_px(ch, track):
    g = cmap.get(ord(ch))
    a = hmtx[g][0] if g else upem // 2
    return (a / upem + track) * PX


def draw_line(dr, text, x, y, track, fill):
    pen = x
    for ch in text:
        dr.text((pen, y), ch, font=pil, fill=fill)
        pen += adv_px(ch, track)
    return pen - x


W, H = 1180, 130 * len(CANDIDATES) + 30
img = Image.new('RGB', (W, H), (34, 34, 30))
dr = ImageDraw.Draw(img)
small = ImageFont.truetype(FONT, 22)

y = 16
for t in CANDIDATES:
    label = 'tracking %.3f em%s' % (t, '   <- 현재값' if abs(t - 0.015) < 1e-9 else '')
    dr.text((16, y), label, font=small, fill=(150, 200, 120))
    draw_line(dr, LINE, 16, y + 30, t, (255, 255, 255))
    draw_line(dr, LINE2, 600, y + 30, t, (235, 235, 220))
    y += 130

os.makedirs('work/shots', exist_ok=True)
img.save(OUT)
print('saved', OUT)
for t in CANDIDATES:
    w = sum(adv_px(c, t) for c in LINE)
    print('  tracking %.3f -> line width %.0f px (%.1f%% vs 0.0)'
          % (t, w, 100 * w / sum(adv_px(c, 0.0) for c in LINE) - 100))
