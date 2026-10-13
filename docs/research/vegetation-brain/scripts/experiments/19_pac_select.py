"""Select lake-years with sonar PAC/PVI (FWC layer 41) for lake-level S2 test. -> data/pac_lakeyears.json"""
import json, collections, datetime as dt, numpy as np
from pathlib import Path
from shapely.geometry import shape
ROOT = Path(__file__).resolve().parent.parent
rows = json.load(open(ROOT/"data/fwc_ltm_lakes_PAC_PVI.json"))
L = {f["properties"]["Lake_Id"]: (shape(f["geometry"]), f["properties"]) for f in json.load(open(ROOT/"data/fwc_ltm_lakes.geojson"))["features"]}
pts = json.load(open(ROOT/"data/fwc_ltm_point_intercepts.json"))
def pd(s):
    try: return dt.datetime.strptime(s.split()[0], "%m/%d/%Y").date()
    except Exception: return None
dates = collections.defaultdict(list)
for p in pts:
    d = pd(p["Date"] or "")
    if d: dates[(p["Lake_Id"], d.year)].append(d)
out = []
for r in rows:
    lid = r["LakeId"]
    if lid not in L or r["Year"] < 2018: continue
    ds = sorted(dates.get((lid, r["Year"]), []))
    if not ds: continue
    km2 = L[lid][1].get("AreaSqKm") or L[lid][0].area * 1e4 * 0.78
    out.append(dict(lake=r["LakeName"].strip(), lake_id=lid, year=r["Year"], PAC=r["PAC"], PVI=r["PVI"], km2=round(float(km2), 1), survey_med=ds[len(ds)//2].isoformat(), survey_min=ds[0].isoformat(), survey_max=ds[-1].isoformat()))
sel = [o for o in out if 1.5 <= o["km2"] <= 130 and 5 <= int(o["survey_med"][5:7]) <= 10]
json.dump(sel, open(ROOT/"data/pac_lakeyears.json", "w"), indent=1)
print(len(out), len(sel), "lakes", len({o["lake_id"] for o in sel}))
for o in sorted(sel, key=lambda o: (o["lake"], o["year"])): print(o["lake"], o["year"], o["PAC"], o["PVI"], o["km2"], o["survey_med"])
