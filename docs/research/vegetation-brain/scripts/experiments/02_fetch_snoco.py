import requests, json
B="https://gis.snoco.org/host/rest/services/Hosted/Lake_Aquatic_Plant_Surveys_Service/FeatureServer"
for i in [0,6,7,8,9,10,11,12,13,14,15]:
    feats=[];off=0
    while True:
        r=requests.get(f"{B}/{i}/query",params=dict(where="1=1",outFields="*",outSR=4326,resultOffset=off,resultRecordCount=1000,f="geojson"),timeout=120).json()
        f=r.get("features",[]);feats+=f;off+=len(f)
        if not f or not r.get("exceededTransferLimit") and not r.get("properties",{}).get("exceededTransferLimit"): break
    json.dump({"type":"FeatureCollection","features":feats},open(f"data/snoco_layer{i}.geojson","w"))
    print(i,len(feats))
