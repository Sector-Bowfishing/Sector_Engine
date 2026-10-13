"""Join UMN points to fleet-lake canonical analysis polygons, assign per-point life-form flags. cwd = umn_sfwmd/"""
import csv,json,gzip,urllib.request,collections,os
from shapely.geometry import shape,Point
from shapely.prepared import prep
csv.field_size_limit(10**9)
ROOT='../../../'
reg=json.load(open(ROOT+'registry/lakes.v1.json'))['lakes']
cand=[l for l in reg if l.get('bbox') and l['bbox'][2]>-97.5 and l['bbox'][0]<-89 and l['bbox'][3]>43.4 and l['bbox'][1]<49.5]
os.makedirs('out/geom',exist_ok=True)
geo={}
for l in cand:
    k=l['lakeKey']; fp=f'out/geom/{k}.geojson'
    if not os.path.exists(fp):
        raw=urllib.request.urlopen(f"https://storage.googleapis.com/sector-lake-registry/lakes/{k}/geometry.v1.analysis.geojson.gz").read()
        raw=gzip.decompress(raw) if raw[:2]==b'\x1f\x8b' else raw
        open(fp,'wb').write(raw)
    g=json.load(open(fp)); geo[k]=shape(g['features'][0]['geometry'] if 'features' in g else (g['geometry'] if 'geometry' in g else g))
pg={k:prep(v) for k,v in geo.items()}; bb={l['lakeKey']:l['bbox'] for l in cand}
LK={}
for r in csv.DictReader(open('out/umn_taxon_lifeform_lookup.csv')): LK[r['taxon'].strip().lower()]=r
F=ROOT+'sources/mn_umn/data_extracted/data/output/DRUM/plants_env_data.csv'
pts={}
for r in csv.DictReader(open(F)):
    try: lon=float(r['Longitude']);lat=float(r['Latitude'])
    except: continue
    hit=None
    for k,b in bb.items():
        if b[0]<=lon<=b[2] and b[1]<=lat<=b[3]: 
            if pg[k].contains(Point(lon,lat)): hit=k;break
    if not hit: continue
    key=(hit,r['SURVEY_ID'],r['POINT_ID'])
    d=pts.setdefault(key,dict(lake=hit,survey=r['SURVEY_ID'],point=r['POINT_ID'],date=r['SURVEY_DATE'][:10],lon=lon,lat=lat,depth_ft=r['DEPTH_FT'],name=r['LAKE_NAME'],noveg=r['NO_VEG_FOUND'],sg=r['SURFACE_GROWTH'],multipart=r['MULTIPARTSURVEY'],
        strict=0,incl=0,canopy=0,sub=0,subnc=0,other=0,ntax=0,taxa=[]))
    t=r['TAXON'].strip().lower()
    if not t: continue
    d['ntax']+=1; d['taxa'].append(r['TAXON'])
    m=LK[t]
    if m['surface_tier']=='STRICT': d['strict']=1
    if m['surface_tier'] in('STRICT','INCLUSIVE'): d['incl']=1
    if m['life_form']=='SUBMERSED': d['sub']=1; d['canopy']|=(m['canopy_capable_submersed']=='Y'); d['subnc']|=(m['canopy_capable_submersed']!='Y')
    else: d['other']|= (m['surface_tier']=='NO')
w=csv.writer(open('out/umn_fleet_points.csv','w',newline=''))
cols=['lake','survey','point','date','lon','lat','depth_ft','name','noveg','sg','multipart','strict','incl','canopy','sub','subnc','other','ntax']
w.writerow(cols+['taxa'])
for d in pts.values(): w.writerow([d[c] for c in cols]+['; '.join(d['taxa'])[:300]])
sm=collections.defaultdict(lambda:collections.Counter())
for d in pts.values(): sm[(d['lake'],d['date'][:4])]['n']+=1; sm[(d['lake'],d['date'][:4])]['strict']+=d['strict']; sm[(d['lake'],d['date'][:4])]['incl']+=d['incl']; sm[(d['lake'],d['date'][:4])]['sub_only']+=(d['sub'] and not d['incl'])
for k,v in sorted(sm.items()): print(k,dict(v))
