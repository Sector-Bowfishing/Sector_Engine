import numpy as np,collections,json
from pyogrio.raw import read
meta,fid,geom,fields=read('sources/umrs_landcover/pool5_dd_2015/x/lc_2015_p5dd/lc_2015_p5dd.shp',read_geometry=False)
f=dict(zip(meta['fields'],fields))
ha=f['HECTARES'].astype(float)
tot=ha.sum();print('polygons',len(ha),'total ha',round(tot,1))
for col in ['CLASS_31_C','CLASS_15_C','LAND_WATER']:
    c=collections.defaultdict(float);n=collections.Counter()
    for k,h in zip(f[col],ha): c[k]+=h;n[k]+=1
    print(col,[(k,n[k],round(v,1),round(100*v/tot,1)) for k,v in sorted(c.items(),key=lambda x:-x[1])])
# aquatic-veg related LCU_C1/LC_N1A
c=collections.defaultdict(float);n=collections.Counter()
for code,cls,nm,h in zip(f['LCU_C1'],f['CLASS_31_C'],f['LC_N1A'],ha):
    if cls in('Rf','Sv','Dma','Dmp','Sma','Smp'): c[(cls,code,nm)]+=h;n[(cls,code,nm)]+=1
for k,v in sorted(c.items(),key=lambda x:-x[1])[:60]: print(k,n[k],round(v,2))
