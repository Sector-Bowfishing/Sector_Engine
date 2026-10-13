import csv,json,gzip,urllib.request,collections,re
from shapely.geometry import shape,Point
csv.field_size_limit(10**9)
F='sources/mn_umn/data_extracted/data/output/DRUM/plants_env_data.csv'
reg={L['lakeKey']:L for L in json.load(open('registry/lakes.v1.json'))['lakes']}
sg_by=collections.Counter(); taxa=collections.Counter()
FL=re.compile(r'^(Nymphaea|Nuphar|Brasenia|Nelumbo|Potamogeton natans|Potamogeton nodosus|Potamogeton gramineus.*floating|Sparganium fluctuans|Lemna|Spirodela|Wolffia|Persicaria amphibia|Polygonum amphibium|Utricularia.*)')
EM=re.compile(r'^(Typha|Schoenoplectus|Scirpus|Zizania|Sparganium (eurycarpum|emersum|angustifolium)|Sagittaria|Phragmites|Bolboschoenus|Pontederia|Carex|Eleocharis|Equisetum|Butomus|Iris|Calla|Decodon|Acorus|Phalaris)')
keys=['Lake_Minnetonka_MN','Mille_Lacs_Lake_MN','Lake_Winnibigoshish_MN','Gull_Lake_MN','Leech_Lake_MN']
geo={}
for k in keys:
    raw=urllib.request.urlopen(reg[k]['geometry']['analysisUrl']).read(); raw=gzip.decompress(raw) if raw[:2]==b'\x1f\x8b' else raw
    g=json.loads(raw); geo[k]=shape(g['features'][0]['geometry'] if 'features' in g else g)
pt={}
sglakes=collections.Counter()
for r in csv.DictReader(open(F)):
    if r['SURFACE_GROWTH'] in ('1',): sglakes[(r['LAKE_NAME'],r['SURVEY_DATE'][:4])]+=1
    t=r['TAXON']
    if t and t!='NA':
        pass
    try: lon=float(r['Longitude']);lat=float(r['Latitude'])
    except: continue
    for k in keys:
        b=reg[k]['bbox']
        if b[0]<=lon<=b[2] and b[1]<=lat<=b[3] and r['SURVEY_DATE'][:4]>='2014' or (k in('Mille_Lacs_Lake_MN',) and b[0]<=lon<=b[2] and b[1]<=lat<=b[3]):
            key=(k,r['SURVEY_ID'],r['POINT_ID'])
            d=pt.setdefault(key,dict(lon=lon,lat=lat,yr=r['SURVEY_DATE'][:4],fl=False,em=False,depth=r['DEPTH_FT']))
            if FL.match(t) and not t.startswith('Utric'): d['fl']=True
            if EM.match(t): d['em']=True
            if t: taxa[(k,t)]+=1
res=collections.defaultdict(lambda:[0,0,0])
for (k,s,p),d in pt.items():
    if geo[k].contains(Point(d['lon'],d['lat'])):
        a=res[(k,d['yr'])]; a[0]+=1; a[1]+=d['fl']; a[2]+=d['em']
for k,v in sorted(res.items()): print(k,'points',v[0],'floating-leaf-taxon pts',v[1],'emergent-taxon pts',v[2])
print('SURFACE_GROWTH==1 rows by lake-year (top):',sglakes.most_common(15))
