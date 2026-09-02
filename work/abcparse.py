import struct, sys

class R:
    def __init__(self,d,p=0): self.d=d; self.p=p
    def u8(self):
        v=self.d[self.p]; self.p+=1; return v
    def u16(self):
        v=struct.unpack('<H',self.d[self.p:self.p+2])[0]; self.p+=2; return v
    def u30(self):
        r=0; s=0
        for _ in range(5):
            b=self.d[self.p]; self.p+=1
            r |= (b & 0x7f) << s
            if not (b & 0x80): break
            s += 7
        return r
    def s32(self): return self.u30()
    def d64(self):
        v=struct.unpack('<d',self.d[self.p:self.p+8])[0]; self.p+=8; return v

def parse_cpool(abc):
    r=R(abc)
    minor=r.u16(); major=r.u16()
    info={'minor':minor,'major':major}
    n=r.u30(); info['int_start']=r.p
    for _ in range(max(0,n-1)): r.s32()
    n=r.u30()
    for _ in range(max(0,n-1)): r.u30()
    n=r.u30()
    for _ in range(max(0,n-1)): r.d64()
    # strings
    scount=r.u30()
    info['str_count']=scount
    info['str_table_start']=r.p
    strings=[b'']
    spans=[None]
    for _ in range(max(0,scount-1)):
        st=r.p
        ln=r.u30()
        b=abc[r.p:r.p+ln]; r.p+=ln
        strings.append(b)
        spans.append((st, r.p))
    info['str_table_end']=r.p
    return info, strings, spans

def get_doabc(swfpath):
    sys.path.insert(0,'work')
    from swftags import parse_tags
    d,tags=parse_tags(swfpath)
    for code,off,ln in tags:
        if code==82:
            body=d[off:off+ln]
            flags=struct.unpack('<I',body[:4])[0]
            z=body.index(b'\x00',4)
            name=body[4:z].decode('utf-8')
            return d, off, ln, flags, name, body[z+1:]
    raise SystemExit('no DoABC')

if __name__=='__main__':
    d,off,ln,flags,name,abc = get_doabc(sys.argv[1])
    print('DoABC name=%r flags=%d abclen=%d' % (name, flags, len(abc)))
    info,strings,spans=parse_cpool(abc)
    print('abc version %d.%d  strings=%d  table=[%d..%d]' % (info['major'],info['minor'],info['str_count'],info['str_table_start'],info['str_table_end']))
    tot=sum(len(s) for s in strings)
    print('total string bytes:', tot)
