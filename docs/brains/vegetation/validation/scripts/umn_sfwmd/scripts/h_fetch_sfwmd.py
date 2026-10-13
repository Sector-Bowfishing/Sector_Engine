"""Download SFWMD littoral vegetation FeatureServer layers (anonymous, public) as GeoJSON (EPSG:4326), paging by resultOffset. cwd=umn_sfwmd/
usage: h_fetch_sfwmd.py SERVICE [SERVICE...]"""
import json,sys,urllib.request,urllib.parse,time
BASE="https://services1.arcgis.com/sDAPyc2rGRn7vf9B/arcgis/rest/services/{}/FeatureServer/0"
def get(u,n=5):
    for i in range(n):
        try: return json.load(urllib.request.urlopen(u,timeout=60))
        except Exception as e: err=e; time.sleep(2*(i+1))
    raise err
for svc in sys.argv[1:]:
    meta=get(BASE.format(svc)+"?f=json"); cnt=get(BASE.format(svc)+"/query?where=1%3D1&returnCountOnly=true&f=json")['count']
    feats=[]; off=0
    while off<cnt:
        q=urllib.parse.urlencode(dict(where='1=1',outFields='*',outSR=4326,f='geojson',resultOffset=off,resultRecordCount=250,orderByFields='OBJECTID'))
        d=get(BASE.format(svc)+"/query?"+q); fs=d.get('features',[])
        if not fs: print('empty page at',off); break
        feats+=fs; off+=len(fs); print(svc,off,flush=True)
    json.dump(dict(type='FeatureCollection',features=feats,meta=dict(service=svc,count_server=cnt,description=meta.get('description','')[:1500],fields=[f['name'] for f in meta['fields']])),open(f'out/sfwmd/{svc}.geojson','w'))
    print(svc,cnt,len(feats))
