import csv,json,gzip,urllib.request,collections,numpy as np,sys
from pyproj import Transformer
from shapely.geometry import shape,Point
from shapely.ops import transform as stx
V='sources/usgs_sav_upper_miss_rf/vegetation_data.csv'
rows=list(csv.DictReader(open(V)))
T=Transformer.from_crs("EPSG:32615","EPSG:4326",always_xy=True)
for r in rows:
    r['lon'],r['lat']=T.transform(float(r['EASTING.x']),float(r['NORTHING.x']))
reg=json.load(open('registry/lakes.v1.json'))['lakes']
lons=np.array([r['lon'] for r in rows]);lats=np.array([r['lat'] for r in rows])
# per-pool bbox
pools=collections.defaultdict(list)
for r in rows: pools[r['POOL.x']].append(r)
M=np.array([[r['lon'],r['lat']] for r in rows])
# candidates: fleet lake whose bbox (padded 0.1deg) contains >=1 site, or lat 36.5-45.5, lon -93.5..-87 name hit
cand=[]
for L in reg:
    b=L['bbox'];p=0.05
    if not b: continue
    m=((M[:,0]>=b[0]-p)&(M[:,0]<=b[2]+p)&(M[:,1]>=b[1]-p)&(M[:,1]<=b[3]+p)).sum()
    nm=any(k in (L['name']+' '.join(L.get('aliases',[]))).lower() for k in ['pepin','keokuk','pool','illinois','mississippi','peoria','la grange','lagrange','alton','saint croix','st. croix','onalaska','upper miss'])
    if m or (nm and 36<L['centroid'][1]<46 and -94<L['centroid'][0]<-87.5): cand.append((L,m))
res=[]
for L,m in cand:
    raw=urllib.request.urlopen(L['geometry']['analysisUrl']).read()
    raw=gzip.decompress(raw) if raw[:2]==b'\x1f\x8b' else raw
    g=json.loads(raw)
    geom=shape(g['features'][0]['geometry'] if g.get('type')=='FeatureCollection' else g.get('geometry',g))
    inside=[r for r in rows if geom.contains(Point(r['lon'],r['lat']))]
    # proximity (deg-based approx to metres at lat)
    kx=111320*np.cos(np.radians(L['centroid'][1]));ky=110540
    d=[geom.distance(Point(r['lon'],r['lat']))*np.sqrt(((kx+ky)/2)**2) for r in rows if abs(r['lon']-L['centroid'][0])<1 and abs(r['lat']-L['centroid'][1])<1]
    near=sum(1 for x in d if x<500)
    yrs=sorted({int(r['YEAR']) for r in inside}); pl=collections.Counter(r['POOL.x'] for r in inside)
    res.append(dict(lakeKey=L['lakeKey'],name=L['name'],state=L['state'],area=L['areaKm2'],bbox_sites=int(m),inside=len(inside),near500m=near,years=[yrs[0],yrs[-1]] if yrs else None,pools=dict(pl),
      yrs2015=sum(1 for r in inside if int(r['YEAR'])>=2015)))
json.dump(res,open('experiments/adoption/umr/b_overlap.json','w'),indent=1)
for r in sorted(res,key=lambda x:-x['inside']): print(r)
