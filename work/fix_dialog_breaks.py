"""Insert explicit <br/> in the confirm-dialog headlines.

The dialog body is a wordWrap DefineEditText, so Flash decides the break and
leaves an orphan ("...종료하시겠습니 / 까?"). Breaking at a phrase boundary
ourselves keeps the headline balanced.
"""
import json, os

P = 'work/abc_ui_ko.json'
m = json.load(open(P, encoding='utf-8'))

FIX = {
    '정말 게임을 종료하시겠습니까?': '정말 게임을<br/>종료하시겠습니까?',
    '정말 타이틀 메뉴로 나가시겠습니까?': '정말 타이틀 메뉴로<br/>나가시겠습니까?',
}

n = 0
for en, ko in list(m.items()):
    for old, new in FIX.items():
        if ko.startswith(old):
            m[en] = new + ko[len(old):]
            n += 1
            break

json.dump(m, open(P, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print('patched %d headlines' % n)
for en, ko in m.items():
    if '<br/>' in ko and '종료' in ko or '나가' in ko:
        print('  ', ko[:100])
