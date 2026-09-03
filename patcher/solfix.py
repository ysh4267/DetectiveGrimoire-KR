"""세이브 슬롯이 눌러도 열리지 않을 때 고치는 모듈 (게임 자체 버그).

TitleScreen.onLoadSlot 은 이렇게 동작합니다.

    Area(GameData.areaList.byID(saveData.areaCurrent)).screen

AreaList.currentAreaID 의 초깃값은 -1 이고, 플레이어가 실제로 장소에 들어가야
진짜 id가 됩니다. 인트로 도중에 게임이 종료되면 자동저장이 -1 을 기록하고,
다시 켜서 그 슬롯을 누르면 byID(-1) 이 undefined 를 돌려줍니다. Area(undefined)
는 null 이라 .screen 접근에서 예외가 나고, 그 예외가 삼켜져서 화면이 그대로
멈춥니다.

areaCurrent 를 실제 장소 id로 바꿔 주면 다시 열립니다. (0 = 늪 선착장)
"""
import os
import shutil
import struct


class AMF3:
    def __init__(self, d, p=0):
        self.d, self.p = d, p
        self.strings, self.objects, self.traits = [], [], []

    def u8(self):
        v = self.d[self.p]; self.p += 1; return v

    def u29(self):
        v = 0
        for i in range(4):
            b = self.d[self.p]; self.p += 1
            if i == 3:
                return (v << 8) | b
            v = (v << 7) | (b & 0x7f)
            if not (b & 0x80):
                return v
        return v

    def s29(self):
        v = self.u29()
        return v - 0x20000000 if v & 0x10000000 else v

    def double(self):
        v = struct.unpack('>d', self.d[self.p:self.p + 8])[0]; self.p += 8; return v

    def string(self):
        n = self.u29()
        if not (n & 1):
            return self.strings[n >> 1]
        ln = n >> 1
        s = self.d[self.p:self.p + ln].decode('utf-8', 'replace'); self.p += ln
        if s:
            self.strings.append(s)
        return s

    def value(self):
        m = self.u8()
        if m in (0x00, 0x01): return None
        if m == 0x02: return False
        if m == 0x03: return True
        if m == 0x04: return self.s29()
        if m == 0x05: return self.double()
        if m == 0x06: return self.string()
        if m == 0x09: return self.array()
        if m == 0x0a: return self.object()
        if m in (0x08, 0x0c):
            n = self.u29()
            if not (n & 1):
                return self.objects[n >> 1]
            if m == 0x08:
                v = self.double()
            else:
                ln = n >> 1
                v = self.d[self.p:self.p + ln]; self.p += ln
            self.objects.append(v)
            return v
        raise ValueError('AMF3 marker 0x%02x' % m)

    def array(self):
        n = self.u29()
        if not (n & 1):
            return self.objects[n >> 1]
        dense = n >> 1
        out = []
        self.objects.append(out)
        while True:
            if self.string() == '':
                break
            self.value()
        for i in range(dense):
            self._index = i
            out.append(self.value())
        self._index = -1
        return out

    def object(self):
        n = self.u29()
        if not (n & 1):
            return self.objects[n >> 1]
        n >>= 1
        if not (n & 1):
            tr = self.traits[n >> 1]
        else:
            n >>= 1
            ext = bool(n & 1); n >>= 1
            dynamic = bool(n & 1); count = n >> 1
            cls = self.string()
            tr = {'class': cls, 'members': [self.string() for _ in range(count)],
                  'dynamic': dynamic, 'ext': ext}
            self.traits.append(tr)
        if tr['ext']:
            raise ValueError('externalizable class not supported')
        obj = {'__class__': tr['class']} if tr['class'] else {}
        self.objects.append(obj)
        slot = getattr(self, '_index', -1)
        is_save = tr['class'].endswith('SaveData')
        for name in tr['members']:
            start = self.p
            obj[name] = self.value()
            if is_save:
                self.spans.append((slot, name, start, self.p))
        if tr['dynamic']:
            while True:
                k = self.string()
                if k == '':
                    break
                obj[k] = self.value()
        return obj


def amf3_int(v):
    u = v & 0x1FFFFFFF
    if u < 0x80:
        body = bytes([u])
    elif u < 0x4000:
        body = bytes([(u >> 7) | 0x80, u & 0x7f])
    elif u < 0x200000:
        body = bytes([(u >> 14) | 0x80, ((u >> 7) & 0x7f) | 0x80, u & 0x7f])
    else:
        body = bytes([(u >> 22) | 0x80, ((u >> 15) & 0x7f) | 0x80,
                      ((u >> 8) & 0x7f) | 0x80, u & 0xff])
    return b'\x04' + body


def parse(path):
    d = open(path, 'rb').read()
    p = 6
    if d[p:p + 4] != b'TCSO':
        raise ValueError('.sol 파일이 아닙니다')
    p += 10
    ln = struct.unpack('>H', d[p:p + 2])[0]
    p += 2 + ln + 4
    a = AMF3(d, p)
    a.spans = []
    a._index = -1
    key = a.string()
    val = a.value()
    return d, {key: val}, a.spans


def repair(path, area_id=0):
    d, data, spans = parse(path)
    slots = data.get('saveSlots') or []

    edits = []
    for slot, name, start, end in spans:
        if name not in ('areaCurrent', 'areaFirstVisited', 'areaLastVisited'):
            continue
        s = slots[slot] if 0 <= slot < len(slots) else None
        if not isinstance(s, dict) or s.get('areaCurrent') != -1:
            continue
        edits.append((start, end, amf3_int(area_id), slot, name))

    if not edits:
        return False

    edits.sort()
    out = bytearray()
    prev = 0
    for start, end, blob, slot, name in edits:
        print('  슬롯 %d  %-18s -1 -> %d' % (slot + 1, name, area_id))
        out += d[prev:start] + blob
        prev = end
    out += d[prev:]
    out[2:6] = struct.pack('>I', len(out) - 6)      # SOL length header

    bak = path + '.bak'
    if not os.path.exists(bak):
        shutil.copy2(path, bak)
        print('  백업: %s' % bak)
    open(path, 'wb').write(bytes(out))
    return True
