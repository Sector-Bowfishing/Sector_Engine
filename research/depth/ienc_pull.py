"""Pull selected layers (all features, paged) of the 3 Guntersville IENC cells. Research only."""
import json,requests
B='https://ienccloud.us/arcgis/rest/services/IENC'
want=['DEPTH_AREA','DEPTH_CONTOUR_LINE','DATA_COVERAGE_AREA','DATA_QUALITY_AREA','LAKE_AREA','RIVERS_AREA','LAND_AREA','WATERWAY_GAUGE_POINT','DAM_AREA','LOCK_BASIN_AREA','SEA_AREA','CAUTION_AREA','RESTRICTED_AREA']
for c in ['U37TN306','U37TN361','U37TN391']:
    ms=json.load(open(f'ms_{c}.json'))
    for l in ms['layers']:
        if l['name'] not in want: continue
        u=f"{B}/{c}/MapServer/{l['id']}"
        meta=requests.get(u+'?f=json',timeout=60).json()
        json.dump(meta,open(f'meta_{c}_{l["name"]}.json','w'))
        feats=[];off=0
        while True:
            r=requests.get(u+'/query',params=dict(where='1=1',outFields='*',f='geojson',outSR=4326,resultOffset=off,resultRecordCount=1000),timeout=120).json()
            fs=r.get('features',[]);feats+=fs
            if len(fs)<1000 and not r.get('exceededTransferLimit'): break
            off+=len(fs)
            if not fs: break
        json.dump({'type':'FeatureCollection','features':feats},open(f'{c}_{l["name"]}.geojson','w'))
        print(c,l['name'],len(feats),[f['name'] for f in meta['fields']] if feats else '')
