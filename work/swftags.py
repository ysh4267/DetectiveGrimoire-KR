import struct, sys

TAGNAMES={0:'End',1:'ShowFrame',2:'DefineShape',9:'SetBackgroundColor',12:'DoAction',
20:'DefineBitsLossless',21:'DefineBitsJPEG2',22:'DefineShape2',26:'PlaceObject2',
32:'DefineShape3',36:'DefineBitsLossless2',37:'DefineEditText',39:'DefineSprite',
43:'FrameLabel',48:'DefineFont2',56:'ExportAssets',59:'DoInitAction',
62:'DefineFontInfo2',69:'FileAttributes',73:'DefineFontAlignZones',74:'CSMTextSettings',
75:'DefineFont3',76:'SymbolClass',77:'Metadata',82:'DoABC',83:'DefineShape4',
86:'DefineSceneAndFrameLabelData',88:'DefineFontName',91:'DefineFont4'}

def parse_tags(path):
    d=open(path,'rb').read()
    # header: sig(3) ver(1) len(4) then rect, framerate, framecount
    p=8
    b=d[p]; nbits=b>>3
    total_bits=5+nbits*4
    p += (total_bits+7)//8
    p += 4  # framerate(2) + framecount(2)
    tags=[]
    while p < len(d):
        if p+2>len(d): break
        code_len=struct.unpack('<H', d[p:p+2])[0]; p+=2
        code=code_len>>6; length=code_len & 0x3f
        if length==0x3f:
            length=struct.unpack('<I', d[p:p+4])[0]; p+=4
        tags.append((code, p, length))
        p+=length
        if code==0: break
    return d, tags

if __name__=='__main__':
    d,tags=parse_tags(sys.argv[1])
    print('file bytes:', len(d), 'tags:', len(tags))
    from collections import Counter
    c=Counter(t[0] for t in tags)
    for code,n in c.most_common():
        print('  tag %3d %-28s x%d' % (code, TAGNAMES.get(code,'?'), n))
    print()
    print('=== big tags ===')
    for code,off,ln in sorted(tags,key=lambda t:-t[2])[:15]:
        print('  %-28s off=%-9d len=%d' % (TAGNAMES.get(code,'tag%d'%code), off, ln))
