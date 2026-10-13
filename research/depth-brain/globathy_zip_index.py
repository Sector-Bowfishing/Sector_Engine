"""Parse the central directory of the 16.7 GB GLOBathy Bathymetry_Rasters.zip (fetched by HTTP range)
and write an index (name, comp_size, size, local header offset). Usage: globathy_zip_index.py cd.bin out.csv"""
import struct, sys, csv
cd = open(sys.argv[1], 'rb').read()
p = 0; rows = []
while p < len(cd) and cd[p:p+4] == b'PK\x01\x02':
    (_, _, _, flag, method, _, _, crc, csz, usz, nl, el, cl, _, _, _, off) = struct.unpack('<4s4H2HIIIHHHHHII', cd[p:p+46])
    name = cd[p+46:p+46+nl].decode('utf8', 'replace')
    ex = cd[p+46+nl:p+46+nl+el]
    q = 0
    while q + 4 <= len(ex):
        tid, sz = struct.unpack('<HH', ex[q:q+4])
        if tid == 1:
            d = ex[q+4:q+4+sz]; k = 0
            if usz == 0xFFFFFFFF and len(d) >= k+8: usz = struct.unpack('<Q', d[k:k+8])[0]; k += 8
            if csz == 0xFFFFFFFF and len(d) >= k+8: csz = struct.unpack('<Q', d[k:k+8])[0]; k += 8
            if off == 0xFFFFFFFF and len(d) >= k+8: off = struct.unpack('<Q', d[k:k+8])[0]; k += 8
        q += 4 + sz
    rows.append((name, method, csz, usz, off))
    p += 46 + nl + el + cl
w = csv.writer(open(sys.argv[2], 'w'))
w.writerow(['name', 'method', 'csize', 'usize', 'offset']); w.writerows(rows)
print(len(rows), rows[:3], rows[-2:])
