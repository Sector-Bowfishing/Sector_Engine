"""Fallback submerged ground truth: Carver County MN BioBase biovolume points (Reitz Lake, Brickyard Lake). ArcGIS Online feature services."""
import requests, json
from pathlib import Path
D = Path(__file__).resolve().parent.parent/"data"
S = {"reitz": "https://services.arcgis.com/wMZT8kNwa6tOxhKg/arcgis/rest/services/ReitzLakeBiovolume/FeatureServer/0",
     "brickyard": "https://services.arcgis.com/wMZT8kNwa6tOxhKg/arcgis/rest/services/BrickyardVegetationBiovolume/FeatureServer/0"}
for k, u in S.items():
    info = requests.get(u, params=dict(f="json"), timeout=60).json()
    rows = []; off = 0
    while True:
        r = requests.get(u+"/query", params=dict(where="1=1", outFields="BioVolume,Longitude,Latitude", returnGeometry="false", f="json", resultOffset=off, resultRecordCount=2000), timeout=120).json()
        f = r.get("features", []); rows += [x["attributes"] for x in f]; off += len(f)
        if len(f) < 2000 and not r.get("exceededTransferLimit"): break
    json.dump(dict(info={k_: info.get(k_) for k_ in ["name","editingInfo","description","maxRecordCount"]}, rows=rows), open(D/f"carver_{k}_biovolume.json","w"))
    print(k, len(rows), info.get("editingInfo"))
