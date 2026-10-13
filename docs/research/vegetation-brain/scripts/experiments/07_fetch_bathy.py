import requests, json
B="https://ocean.floridamarine.org/arcgis/rest/services/Projects_FWC/WhatsHappeningOnMyLake/MapServer/31/query"
names=["Lake Griffin","Lake Harris","Lake Panasoffkee","Cypress Lake"]
w="Waterbody IN (%s)"%",".join("'%s'"%n for n in names)
r=requests.get(B,params=dict(where=w,outFields="Waterbody,Depth_Feet,Depth_Meters",outSR=4326,f="geojson",returnGeometry="true"),timeout=180)
open("data/fwc_lake_bathymetry_bands.geojson","w").write(r.text)
g=r.json(); print(len(g.get("features",[])), {f["properties"]["Waterbody"] for f in g.get("features",[])})
