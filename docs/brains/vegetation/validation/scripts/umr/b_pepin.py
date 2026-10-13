import csv,json,gzip,urllib.request,collections
from pyproj import Transformer
from shapely.geometry import shape,Point
rows=list(csv.DictReader(open('sources/usgs_sav_upper_miss_rf/vegetation_data.csv')))
T=Transformer.from_crs("EPSG:32615","EPSG:4326",always_xy=True)
raw=urllib.request.urlopen('https://storage.googleapis.com/sector-lake-registry/lakes/Lake_Pepin_MN/geometry.v1.analysis.geojson.gz').read()
raw=gzip.decompress(raw) if raw[:2]==b'\x1f\x8b' else raw
g=json.loads(raw); geom=shape(g['features'][0]['geometry'] if 'features' in g else g)
print(geom.bounds)
sp=['CEDE4','CHAR','ELCA7','MYSI','MYSP2','NAFL','NAGU','NAMI','NLPW','POCR3','PONO2','POPE6','PORI2','POZO','RALO2','UTMA','VAAM3','ZAPA','ZODU']
yc=collections.Counter();pc=collections.defaultdict(collections.Counter);sc=collections.Counter();ins=[]
for r in rows:
    lon,lat=T.transform(float(r['EASTING.x']),float(r['NORTHING.x']))
    if geom.contains(Point(lon,lat)):
        ins.append((r,lon,lat))
        yc[int(r['YEAR'])]+=1;pc[r['POOL.x']][int(r['YEAR'])]+=1;sc[r['STRATUM.x']]+=1
print(sorted(yc.items()));print({k:sorted(v.items()) for k,v in pc.items()});print(sc)
print('lon/lat range',min(i[1] for i in ins),max(i[1] for i in ins),min(i[2] for i in ins),max(i[2] for i in ins))
late=[i for i in ins if int(i[0]['YEAR'])>=2015]
print('2015+ n',len(late),{y:sum(1 for i in late if int(i[0]['YEAR'])==y) for y in range(2015,2020)})
print('any-SAV prevalence all/2015+', sum(any(float(i[0][s])>0 for s in sp) for i in ins)/len(ins), sum(any(float(i[0][s])>0 for s in sp) for i in late)/max(1,len(late)))
print({s:round(sum(float(i[0][s])>0 for i in late)/max(1,len(late)),3) for s in sp})
print('depth 2015+',sorted(float(i[0]['AVGDEPTH']) for i in late if i[0]['AVGDEPTH'] not in ('','NA'))[::max(1,len(late)//10)])
