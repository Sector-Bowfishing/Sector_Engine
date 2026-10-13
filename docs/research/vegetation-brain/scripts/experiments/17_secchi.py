"""Secchi depth per FL lake from the Water Quality Portal (FL LAKEWATCH + FDEP + water-management districts): fetch, filter to lake polygon, summarise. Output data/secchi/*.csv, out/secchi_summary.json"""
import json, requests, io, csv, datetime as dt, numpy as np
from pathlib import Path
from shapely.geometry import shape, Point
ROOT = Path(__file__).resolve().parent.parent
ids = {"Orange":("288216",2022),"Griffin":("305765",2019),"Apopka":("293912",2021),"Harris":("294031",2018),"Panasoffkee":("294114",2022),"Yale":("306620",2023),"Cypress":("281219",2022)}
L = {f["properties"]["Lake_Id"]: shape(f["geometry"]) for f in json.load(open(ROOT/"data/fwc_ltm_lakes.geojson"))["features"]}
out = {}
for nm, (i, yr) in ids.items():
    g = L[i]; b = g.bounds; m = 0.004
    p = dict(bBox=f"{b[0]-m},{b[1]-m},{b[2]+m},{b[3]+m}", characteristicName="Depth, Secchi disk depth", mimeType="csv", zip="no")
    st = list(csv.DictReader(io.StringIO(requests.get("https://www.waterqualitydata.us/data/Station/search", params=p, timeout=120).text)))
    open(ROOT/f"data/secchi/wqp_stations_{nm}.csv", "w").write("\n".join([",".join(["MonitoringLocationIdentifier","LatitudeMeasure","LongitudeMeasure"])] + [f'{s["MonitoringLocationIdentifier"]},{s["LatitudeMeasure"]},{s["LongitudeMeasure"]}' for s in st]))
    inside = {s["MonitoringLocationIdentifier"] for s in st if g.buffer(0.0008).contains(Point(float(s["LongitudeMeasure"]), float(s["LatitudeMeasure"])))}
    rows = [r for r in csv.DictReader(open(ROOT/f"data/secchi/wqp_secchi_{nm}.csv")) if r["MonitoringLocationIdentifier"] in inside]
    def val(r):
        try: v = float(r["ResultMeasureValue"])
        except Exception: return None
        u = r["ResultMeasure/MeasureUnitCode"].lower()
        return v * 0.3048 if u in ("ft", "feet") else v if u in ("m", "meters") else v / 100 if u == "cm" else None
    data = [(dt.date.fromisoformat(r["ActivityStartDate"]), val(r), r["OrganizationFormalName"], ("bottom" in (r["ResultDetectionConditionText"] + r.get("ResultCommentText", "")).lower())) for r in rows]
    data = [d for d in data if d[1] is not None]
    gs = lambda y0, y1: [d[1] for d in data if y0 <= d[0].year <= y1 and 5 <= d[0].month <= 9]
    out[nm] = dict(stations=len(inside), n_all=len(data), n_year=len(gs(yr, yr)), median_year_MaySep=(round(float(np.median(gs(yr, yr))), 2) if gs(yr, yr) else None),
                   n_pm2=len(gs(yr-2, yr+1)), median_pm2yr_MaySep=(round(float(np.median(gs(yr-2, yr+1))), 2) if gs(yr-2, yr+1) else None),
                   orgs=sorted({d[2] for d in data}), on_bottom_frac=round(float(np.mean([d[3] for d in data])), 3) if data else None)
    print(nm, out[nm])
json.dump(out, open(ROOT/"out/secchi_summary.json", "w"), indent=1)
