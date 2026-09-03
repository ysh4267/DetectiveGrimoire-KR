"""Minimal AMF3 reader for Flash SharedObject (.sol) files.

Enough of the format to dump Detective Grimoire's SaveData and see which
field makes a slot unloadable.
"""
import struct, sys, json


class AMF3:
    def __init__(self, d, p=0):
        self.d, self.p = d, p
        self.strings = []
        self.objects = []
        self.traits = []

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
        if v & 0x10000000:
            v -= 0x20000000
        return v

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
        if m == 0x00: return None            # undefined
        if m == 0x01: return None            # null
        if m == 0x02: return False
        if m == 0x03: return True
        if m == 0x04: return self.s29()      # integer
        if m == 0x05: return self.double()
        if m == 0x06: return self.string()
        if m == 0x08:                        # date
            n = self.u29()
            if not (n & 1):
                return self.objects[n >> 1]
            v = self.double()
            self.objects.append(v)
            return v
        if m == 0x09: return self.array()
        if m == 0x0a: return self.object()
        if m == 0x0c:                        # byte array
            n = self.u29()
            if not (n & 1):
                return self.objects[n >> 1]
            ln = n >> 1
            v = self.d[self.p:self.p + ln]; self.p += ln
            self.objects.append(v)
            return v
        raise ValueError('unsupported AMF3 marker 0x%02x at %d' % (m, self.p - 1))

    def array(self):
        n = self.u29()
        if not (n & 1):
            return self.objects[n >> 1]
        dense = n >> 1
        out = []
        self.objects.append(out)
        assoc = {}
        while True:
            k = self.string()
            if k == '':
                break
            assoc[k] = self.value()
        for _ in range(dense):
            out.append(self.value())
        if assoc:
            out.append({'__assoc__': assoc})
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
            externalizable = bool(n & 1)
            n >>= 1
            dynamic = bool(n & 1)
            count = n >> 1
            cls = self.string()
            members = [self.string() for _ in range(count)]
            tr = {'class': cls, 'members': members,
                  'dynamic': dynamic, 'ext': externalizable}
            self.traits.append(tr)
        obj = {'__class__': tr['class']} if tr['class'] else {}
        self.objects.append(obj)
        if tr['ext']:
            raise ValueError('externalizable class %r not supported' % tr['class'])
        for name in tr['members']:
            obj[name] = self.value()
        if tr['dynamic']:
            while True:
                k = self.string()
                if k == '':
                    break
                obj[k] = self.value()
        return obj


def read_sol(path):
    d = open(path, 'rb').read()
    if d[0:2] != b'\x00\xbf':
        raise ValueError('not a .sol')
    p = 6
    assert d[p:p + 4] == b'TCSO', d[p:p + 4]
    p += 4 + 6
    ln = struct.unpack('>H', d[p:p + 2])[0]; p += 2
    name = d[p:p + ln].decode(); p += ln
    version = struct.unpack('>I', d[p:p + 4])[0]; p += 4
    if version != 3:
        raise ValueError('AMF0 sol not supported (version %d)' % version)
    out = {}
    while p < len(d):
        a = AMF3(d, p)
        key = a.string()
        if not key:
            break
        val = a.value()
        out[key] = val
        p = a.p
        if p < len(d) and d[p] == 0:
            p += 1                       # trailing separator byte
    return name, out


if __name__ == '__main__':
    name, data = read_sol(sys.argv[1])
    print('SharedObject:', name)
    slots = data.get('saveSlots') or []
    for i, s in enumerate(slots):
        if not isinstance(s, dict):
            print('slot %d: %r' % (i, s))
            continue
        print('slot %d  class=%s' % (i, s.get('__class__')))
        for k in ('percentage', 'challenges', 'storyChapter', 'areaCurrent',
                  'areaFirstVisited', 'areaLastVisited', 'hintsOn'):
            print('    %-18s = %r' % (k, s.get(k)))
        for k in ('areaData', 'clueData', 'charData', 'mindData', 'shownTut'):
            v = s.get(k)
            print('    %-18s = %s' % (k, ('list[%d]' % len(v)) if isinstance(v, list)
                                      else repr(v)))
