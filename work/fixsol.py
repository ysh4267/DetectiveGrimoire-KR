"""Repair a Detective Grimoire save whose slot will not load.

TitleScreen.onLoadSlot does:

    screenManager.replaceScreen(new HeadphonesScreen(
        Area(GameData.areaList.byID(saveData.areaCurrent)).screen))

AreaList.currentAreaID starts at -1 and only becomes a real id once the player
walks into an area. If the game saves while that is still -1 -- which is what
happens if it exits during the intro -- then byID(-1) returns undefined,
Area(undefined) is null, reading .screen throws, and the exception is
swallowed. The slot renders fine but clicking it does nothing at all.

Rewriting areaCurrent to a real area id makes the slot loadable again.
DGAreas.ID_AREA_A_Dock is 0 (the Swamp Dock), which is where a save this
early belongs.
"""
import os, shutil, struct, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from readsol import AMF3


def amf3_int(v):
    """AMF3 integer marker + U29S."""
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


class Spans(AMF3):
    """AMF3 reader that also records where each SaveData member's value sits."""

    def __init__(self, d, p=0):
        super().__init__(d, p)
        self.spans = []          # (slot_index, member, start, end)
        self._slot = -1

    def array(self):
        n = self.d[self.p]
        top = not self.spans and self._slot == -1
        if not top:
            return super().array()
        # the saveSlots array: tag each element with its index
        m = self.u29()
        if not (m & 1):
            return self.objects[m >> 1]
        dense = m >> 1
        out = []
        self.objects.append(out)
        while True:
            k = self.string()
            if k == '':
                break
            self.value()
        for i in range(dense):
            self._slot = i
            out.append(self.value())
        self._slot = -1
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
            ext = bool(n & 1)
            n >>= 1
            dynamic = bool(n & 1)
            count = n >> 1
            cls = self.string()
            members = [self.string() for _ in range(count)]
            tr = {'class': cls, 'members': members, 'dynamic': dynamic, 'ext': ext}
            self.traits.append(tr)
        obj = {'__class__': tr['class']} if tr['class'] else {}
        self.objects.append(obj)
        is_save = tr['class'].endswith('SaveData')
        slot = self._slot
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


def parse_spans(path):
    d = open(path, 'rb').read()
    p = 6
    assert d[p:p + 4] == b'TCSO'
    p += 4 + 6
    ln = struct.unpack('>H', d[p:p + 2])[0]; p += 2 + ln
    p += 4                                     # AMF version
    a = Spans(d, p)
    key = a.string()
    val = a.value()
    return d, {key: val}, a.spans


def repair(path, area_id=0, dry_run=False):
    d, data, spans = parse_spans(path)
    slots = data.get('saveSlots') or []

    edits = []
    for slot, name, start, end in spans:
        if name not in ('areaCurrent', 'areaFirstVisited', 'areaLastVisited'):
            continue
        s = slots[slot] if slot < len(slots) else None
        if not isinstance(s, dict) or s.get('areaCurrent') != -1:
            continue
        edits.append((start, end, amf3_int(area_id), slot, name, s.get(name)))

    if not edits:
        print('nothing to repair: no slot has areaCurrent == -1')
        return False

    edits.sort()
    out = bytearray()
    prev = 0
    for start, end, blob, slot, name, old in edits:
        print('  slot %d  %-18s %r -> %d' % (slot, name, old, area_id))
        out += d[prev:start]
        out += blob
        prev = end
    out += d[prev:]

    # the SOL header's length field counts everything after itself
    body_len = len(out) - 6
    out[2:6] = struct.pack('>I', body_len)

    if dry_run:
        print('dry run: %d -> %d bytes' % (len(d), len(out)))
        return True

    bak = path + '.bak'
    if not os.path.exists(bak):
        shutil.copy2(path, bak)
        print('  backup ->', bak)
    open(path, 'wb').write(bytes(out))
    print('  written: %d -> %d bytes' % (len(d), len(out)))
    return True


if __name__ == '__main__':
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument('sol')
    ap.add_argument('--area', type=int, default=0, help='area id (0 = Swamp Dock)')
    ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args()
    repair(a.sol, a.area, a.dry_run)
