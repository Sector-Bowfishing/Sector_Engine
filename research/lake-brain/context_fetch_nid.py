#!/usr/bin/env python3
"""Fetch the National Inventory of Dams (Esri Federal Data mirror of USACE NID) -- subset of fields, no geometry.
The official USACE API (nid.sec.usace.army.mil/api/nation/csv) returns 403 to scripted clients (ledger B-context-001)."""
import json, time, requests
from pathlib import Path
OUT = Path("/Users/mcather/Desktop/Development/Sector_Research_Data/lake-brain/context/nid/nid_v1_subset.json")
URL = "https://services2.arcgis.com/FiaPA4ga0iQKduv3/arcgis/rest/services/NID_v1/FeatureServer/0/query"
F = "NIDID,NAME,OTHER_NAMES,STATE,RIVER_OR_STREAM,LATITUDE,LONGITUDE,PRIMARY_PURPOSE,PURPOSES,PRIMARY_DAM_TYPE,NID_HEIGHT,DAM_HEIGHT,HYDRAULIC_HEIGHT,YEAR_COMPLETED,NID_STORAGE,MAX_STORAGE,NORMAL_STORAGE,SURFACE_AREA,DRAINAGE_AREA,MAX_DISCHARGE,NUMBER_OF_LOCKS,PRIMARY_OWNER_TYPE,FED_AGENCY_OWNERS,HAZARD_POTENTIAL,OPERATIONAL_STATUS,DATA_UPDATED"
rows = []; off = 0
while True:
    r = requests.get(URL, params=dict(where="1=1", outFields=F, returnGeometry="false", orderByFields="OBJECTID", resultOffset=off, resultRecordCount=2000, f="json"), timeout=120).json()
    fs = r.get("features", [])
    rows += [x["attributes"] for x in fs]
    print(off, len(fs), flush=True)
    if len(fs) < 2000 and not r.get("exceededTransferLimit"): break
    off += 2000; time.sleep(0.5)
OUT.parent.mkdir(parents=True, exist_ok=True); OUT.write_text(json.dumps(rows)); print(len(rows))
