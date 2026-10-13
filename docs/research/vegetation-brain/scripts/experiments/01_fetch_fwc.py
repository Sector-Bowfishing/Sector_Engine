import requests, json, sys
B="https://ocean.floridamarine.org/arcgis/rest/services/Projects_FWC/WhatsHappeningOnMyLake/MapServer"
out=[];off=0
while True:
    r=requests.get(B+"/33/query",params=dict(where="1=1",outFields="*",returnGeometry="false",resultOffset=off,resultRecordCount=20000,orderByFields="OBJECTID",f="json"),timeout=120).json()
    f=[x["attributes"] for x in r["features"]]
    out+=f; off+=len(f)
    print(off,flush=True)
    if not f or not r.get("exceededTransferLimit"): break
json.dump(out,open("data/fwc_ltm_point_intercepts.json","w"))
# lakes polygons layer 35
r=requests.get(B+"/35/query",params=dict(where="1=1",outFields="*",returnGeometry="true",outSR=4326,f="geojson"),timeout=120)
open("data/fwc_ltm_lakes.geojson","w").write(r.text)
print(len(r.text))
