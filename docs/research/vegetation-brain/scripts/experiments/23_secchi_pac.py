"""Secchi (WQP: LAKEWATCH, FDEP, WMDs) per lake-year for the PAC/PVI lake set. -> data/secchi/pac/*.csv, out/secchi_pac.json"""
import json, requests, io, csv, datetime as dt, numpy as np, time
from pathlib import Path
from shapely.geometry import shape, Point
ROOT = Path(__file__).resolve().parent.parent
L = {f["properties"]["Lake_Id"]: shape(f["geometry"]) for f in json.load(open(ROOT/"data/fwc_ltm_lakes.geojson"))["features"]}
LY = [o for o in json.load(open(ROOT/"data/pac_lakeyears.json")) if o["lake"] != "Okeechobee"]
def get(url, p, tries=4):
    for t in range(tries):
        try:
            r = requests.get(url, params=p, timeout=180)
            if r.status_code == 200: return r.text
        except Exception: pass
        time.sleep(8)
    return ""
import os
out = json.load(open(ROOT/"out/secchi_pac.json")) if os.path.exists(ROOT/"out/secchi_pac.json") else {}
for lid in sorted({o["lake_id"] for o in LY}):
    if out.get(lid): continue
    g = L[lid]; b = g.bounds; m = 0.003; bb = f"{b[0]-m},{b[1]-m},{b[2]+m},{b[3]+m}"
    p = dict(bBox=bb, characteristicName="Depth, Secchi disk depth", mimeType="csv", zip="no")
    for att in range(4):
        st = list(csv.DictReader(io.StringIO(get("https://www.waterqualitydata.us/data/Station/search", p))))
        if st: break
        time.sleep(15)
    inside = {s["MonitoringLocationIdentifier"] for s in st if s.get("LatitudeMeasure") and g.buffer(0.0008).contains(Point(float(s["LongitudeMeasure"]), float(s["LatitudeMeasure"])))}
    time.sleep(6)
    txt = get("https://www.waterqualitydata.us/data/Result/search", dict(p, startDateLo="01-01-2017", startDateHi="12-31-2023", dataProfile="narrowResult"))
    open(ROOT/f"data/secchi/pac/wqp_secchi_{lid}.csv", "w").write(txt)
    rows = [r for r in csv.DictReader(io.StringIO(txt)) if r["MonitoringLocationIdentifier"] in inside]
    vals = []
    for r in rows:
        try: v = float(r["ResultMeasureValue"])
        except Exception: continue
        u = r["ResultMeasure/MeasureUnitCode"].lower(); v = v*0.3048 if u in ("ft", "feet") else v if u in ("m", "meters") else v/100 if u == "cm" else None
        if v is not None: vals.append((dt.date.fromisoformat(r["ActivityStartDate"]), v))
    out[lid] = [(d.isoformat(), round(v, 3)) for d, v in vals]
    print(lid, len(inside), "stations", len(vals), "secchi", flush=True)
json.dump(out, open(ROOT/"out/secchi_pac.json", "w"))
