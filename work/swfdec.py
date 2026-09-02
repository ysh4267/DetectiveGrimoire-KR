import sys, zlib, lzma, struct, os

def decompress_swf(path):
    data = open(path,'rb').read()
    sig = data[:3]
    version = data[3]
    filelen = struct.unpack('<I', data[4:8])[0]
    if sig == b'FWS':
        return b'FWS' + data[3:]
    if sig == b'CWS':
        body = zlib.decompress(data[8:])
        return b'FWS' + bytes([version]) + struct.pack('<I', filelen) + body
    if sig == b'ZWS':
        # ZWS: 4 bytes compressed-len, then 5 byte lzma props, then stream
        props = data[12:17]
        comp = data[17:]
        lc, lp, pb = props[0] % 9, (props[0] // 9) % 5, (props[0] // 45)
        dict_size = struct.unpack('<I', props[1:5])[0]
        filt = [{'id': lzma.FILTER_LZMA1, 'lc': lc, 'lp': lp, 'pb': pb, 'dict_size': dict_size}]
        d = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=filt)
        body = d.decompress(comp)
        return b'FWS' + bytes([version]) + struct.pack('<I', filelen) + body
    raise ValueError('unknown sig %r' % sig)

if __name__ == '__main__':
    src, dst = sys.argv[1], sys.argv[2]
    out = decompress_swf(src)
    open(dst,'wb').write(out)
    print('%s -> %s  (%d bytes)' % (src, dst, len(out)))
