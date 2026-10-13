"""Download the National Inventory of Dams point layer (public ArcGIS FeatureServer hosting NID_v1) in pages -> raw/nid/nid.jsonl."""
import json, os, urllib.parse
from common import *
os.makedirs(f"{RAW}/nid", exist_ok=True)
BASE = "https://services2.arcgis.com/FiaPA4ga0iQKduv3/arcgis/rest/services/NID_v1/FeatureServer/0/query"
F = "OBJECTID,NIDID,FEDERAL_ID,NAME,OTHER_NAMES,FORMER_NAMES,LATITUDE,LONGITUDE,STATE,RIVER_OR_STREAM,OWNER_TYPES,PRIMARY_OWNER_TYPE,FED_AGENCY_OWNERS,FED_AGENCY_OPERATIONS,STATE_FED_AGENCY,PRIMARY_PURPOSE,PURPOSES,PRIMARY_DAM_TYPE,DAM_HEIGHT,NID_STORAGE,NORMAL_STORAGE,MAX_STORAGE,SURFACE_AREA,DRAINAGE_AREA,YEAR_COMPLETED,HAZARD_POTENTIAL,IS_ASSOCIATED_STRUCTURE,OPERATIONAL_STATUS,COUNTYSTATE,CITY,DISTANCE".split(",")
off, n = 0, 0
with open(f"{RAW}/nid/nid.jsonl", "w") as f:
    while True:
        q = dict(where="1=1", outFields=",".join(F), returnGeometry="false", orderByFields="OBJECTID", resultOffset=off, resultRecordCount=2000, f="json")
        s, d = get_json(BASE + "?" + urllib.parse.urlencode(q), timeout=120, sleep=0.3)
        if not d or "features" not in d:
            print("fail at", off, s); break
        feats = d["features"]
        for ft in feats:
            f.write(json.dumps(ft["attributes"]) + "\n")
        n += len(feats); off += len(feats)
        print(n, flush=True)
        if len(feats) == 0 or not d.get("exceededTransferLimit"):
            break
print("done", n)
