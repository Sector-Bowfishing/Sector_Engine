import csv,collections,sys,json,numpy as np
from pyproj import Transformer
rows=list(csv.DictReader(open(sys.argv[1])))
print(len(rows), rows[0].keys())
by=collections.defaultdict(list)
for r in rows: by[(r['POOL.x'],r['OLDPOOLNAME'])].append(r)
out=[]
for (p,o),rs in sorted(by.items(), key=lambda x:x[0][0]):
    E=np.array([float(r['EASTING.x']) for r in rs]);N=np.array([float(r['NORTHING.x']) for r in rs]);Y=[int(r['YEAR']) for r in rs]
    # zone guess: UMR upstream of ~-90 -> 15N else 15/16 ; test both
    for z in (15,16):
        t=Transformer.from_crs(f"EPSG:326{z}","EPSG:4326",always_xy=True); lon,lat=t.transform(E.mean(),N.mean())
        print(p,o,len(rs),min(Y),max(Y),'zone',z,round(lon,3),round(lat,3))
