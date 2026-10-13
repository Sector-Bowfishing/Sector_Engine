import csv,json,gzip,urllib.request,collections,sys
from shapely.geometry import shape,Point
from shapely.prepared import prep
csv.field_size_limit(10**9)
reg=json.load(open('registry/lakes.v1.json'))['lakes']
mn=[L for L in reg if 'MN' in (L.get('states') or [L['state']]) and L.get('geometry') and L.get('bbox')]
print('MN fleet lakes',[(L['lakeKey'],L['areaKm2']) for L in mn])
geoms={}
for L in mn:
    raw=urllib.request.urlopen(L['geometry']['analysisUrl']).read()
    raw=gzip.decompress(raw) if raw[:2]==b'\x1f\x8b' else raw
    g=json.loads(raw); geoms[L['lakeKey']]=prep(shape(g['features'][0]['geometry'] if 'features' in g else g))
bb={L['lakeKey']:L['bbox'] for L in mn}
F='sources/mn_umn/data_extracted/data/output/DRUM/plants_env_data.csv'
pts={}  # (survey,point)->info
for r in csv.DictReader(open(F)):
    k=(r['SURVEY_ID'],r['POINT_ID'])
    d=pts.get(k)
    sg=r['SURFACE_GROWTH'] not in ('','NA','0','FALSE','F')
    if d is None:
        pts[k]=dict(lon=r['Longitude'],lat=r['Latitude'],date=r['SURVEY_DATE'],name=r['LAKE_NAME'],dow=r['DOW'],sg=sg,sv=r['SURVEY_ID'],noveg=r['NO_VEG_FOUND'],secchi=r['Secchi_m'])
    else: d['sg']=d['sg'] or sg
print('points',len(pts)); print(collections.Counter(r['SURFACE_GROWTH'] for r in csv.DictReader(open(F))).most_common(6))
res=collections.defaultdict(lambda:collections.defaultdict(lambda:[0,0]))
for k,d in pts.items():
    try: lon=float(d['lon']);lat=float(d['lat'])
    except: continue
    p=Point(lon,lat)
    for lk,b in bb.items():
        if b[0]<=lon<=b[2] and b[1]<=lat<=b[3] and geoms[lk].contains(p):
            y=d['date'][:4]; res[lk][(d['sv'],d['date'][:10])][0]+=1; res[lk][(d['sv'],d['date'][:10])][1]+=d['sg']
out={}
for lk,v in res.items():
    out[lk]=[dict(survey=s,date=dt,n_points=n,n_surface=sg) for (s,dt),(n,sg) in sorted(v.items(),key=lambda x:x[0][1])]
    print(lk,[(o['date'],o['n_points'],o['n_surface']) for o in out[lk]])
json.dump(out,open('experiments/adoption/umr/c_mn_overlap.json','w'),indent=1)
