"""NLA 2017 x fleet registry eligibility (prereg s4). Data-driven counts."""
import json, gzip, sys, requests, numpy as np, pandas as pd
from pathlib import Path
from shapely.geometry import shape, Point
from shapely.prepared import prep
R = Path(__file__).resolve().parents[4]            # vegetation-brain
H = Path(__file__).resolve().parents[1]
S = R/"sources/nla_2017_phab"
site = pd.read_csv(S/"nla_2017_site_information-data.csv", low_memory=False)
phab = pd.read_csv(S/"nla_2017_phab-data.csv", low_memory=False)
site = site[site.DATE_COL.notna() & site.SITE_ID.str.startswith("NLA17")].copy()
site["date"] = pd.to_datetime(site.DATE_COL, format="%m/%d/%Y")
v1 = site[site.VISIT_NO.fillna(1) == 1].drop_duplicates("SITE_ID")
print("NLA17 visit-1 sites with date:", len(v1), " visit-2 revisits:", int((site.VISIT_NO==2).sum()))
reg = json.load(open(R/"registry/lakes.v1.json"))["lakes"]
nullgeo = [l["lakeKey"] for l in reg if l.get("geometry") is None]
print("registry lakes", len(reg), "geometry:null", len(nullgeo))
# bbox prefilter
cand = {}
for l in reg:
    if l.get("geometry") is None: continue
    x0,y0,x1,y1 = l["bbox"]
    m = v1[(v1.LON_DD83>=x0)&(v1.LON_DD83<=x1)&(v1.LAT_DD83>=y0)&(v1.LAT_DD83<=y1)]
    if len(m): cand[l["lakeKey"]] = (l, m)
print("fleet lakes with an NLA17 point in bbox:", len(cand))
(H/"data/geom").mkdir(exist_ok=True)
rows = []
for k,(l,m) in cand.items():
    f = H/f"data/geom/{k}.geojson.gz"
    if not f.exists():
        r = requests.get(l["geometry"]["analysisUrl"], timeout=60)
        if r.status_code != 200: print("GEOM FAIL", k, r.status_code); continue
        f.write_bytes(r.content)
    b=f.read_bytes(); g = json.loads(gzip.decompress(b) if b[:2]==b"\x1f\x8b" else b)
    geom = shape(g["features"][0]["geometry"] if g.get("type")=="FeatureCollection" else g.get("geometry", g))
    pg = prep(geom)
    for _,r in m.iterrows():
        inside = pg.contains(Point(r.LON_DD83, r.LAT_DD83))
        rows.append(dict(lakeKey=k, name=l["name"], state=l["state"], areaKm2=l["areaKm2"], SITE_ID=r.SITE_ID, nla_lat=r.LAT_DD83, nla_lon=r.LON_DD83,
                         inside=bool(inside), dist_deg=float(geom.distance(Point(r.LON_DD83, r.LAT_DD83))), date=r.date.date().isoformat(), epa_reg=r.EPA_REG, eco9=r.AG_ECO9_NM, nla_name=r.GNIS_NAME))
j = pd.DataFrame(rows); j.to_csv(H/"out/nla_fleet_join_all_bbox.csv", index=False)
print(j.inside.value_counts())
ins = j[j.inside]
print("sites inside polygon:", len(ins), "lakes:", ins.lakeKey.nunique(), " sites mapping to >1 lake:", int((ins.groupby('SITE_ID').lakeKey.nunique()>1).sum()))
ins.to_csv(H/"out/nla_fleet_join.csv", index=False)
