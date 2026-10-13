"""STAC scene inventory per eligible lake: +-21 d of NLA visit (2017), both collections; plus Jun-Sep 2018-2019 (secondary)."""
import json, pandas as pd, datetime as dt
from pathlib import Path
from pystac_client import Client
H = Path(__file__).resolve().parents[1]
reg = {l["lakeKey"]: l for l in json.load(open(H.parents[2]/"registry/lakes.v1.json"))["lakes"]}
d = pd.read_csv(H/"out/nla_lake_classes.csv"); d = d[d.n_stations>0]
cat = Client.open("https://earth-search.aws.element84.com/v1")
def q(coll, bbox, a, b):
    for t in range(4):
        try:
            return [(i.id, i.datetime.date().isoformat(), i.properties.get("eo:cloud_cover"), i.properties.get("s2:nodata_pixel_percentage"), i.properties.get("s2:processing_baseline")) for i in cat.search(collections=[coll], bbox=bbox, datetime=f"{a}/{b}").item_collection()]
        except Exception as e: err=e
    raise err
out = {}
for _,r in d.iterrows():
    bb = reg[r.lakeKey]["bbox"]; vd = dt.date.fromisoformat(r.visit_dates.split(";")[0])
    rec = {"ref_date": vd.isoformat()}
    for coll in ["sentinel-2-c1-l2a","sentinel-2-l2a"]:
        rec["y2017_"+coll] = q(coll, bb, (vd-dt.timedelta(21)).isoformat(), (vd+dt.timedelta(21)).isoformat())
        rec["jun_sep_2018_2019_"+coll] = q(coll, bb, "2018-06-01", "2018-09-30") + q(coll, bb, "2019-06-01", "2019-09-30")
    out[r.lakeKey] = rec
    print(r.lakeKey, vd, {k:len(v) for k,v in rec.items() if k!="ref_date"}, flush=True)
json.dump(out, open(H/"out/scene_inventory.json","w"))
