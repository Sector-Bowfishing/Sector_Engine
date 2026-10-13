"""Per-lake: read scenes (window: primary +-21 d of NLA visit 2017; secondary: same window anchored to 2018/2019 anniversary, clipped Jun1-Sep30),
compute per-scene cell products and save states. usage: n4_cells.py LAKEKEY [primary|secondary|both]"""
import sys, json, datetime as dt, numpy as np, traceback
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import nlalib as L
from pystac_client import Client
key = sys.argv[1]; mode = sys.argv[2] if len(sys.argv) > 2 else "both"
H = L.H; (H/"out/cells").mkdir(exist_ok=True)
import pandas as pd
_d = pd.read_csv(H/"out/nla_lake_classes.csv").set_index("lakeKey")
ref = dt.date.fromisoformat(_d.loc[key,"visit_dates"].split(";")[0]); poly = L.load_poly(key); bb = L.window_bbox(poly)
cat = Client.open(L.S2.STAC)
def items_for(a, b):
    got = {}; global LAST_COUNTS; LAST_COUNTS = {}
    for coll in ["sentinel-2-l2a", "sentinel-2-c1-l2a"]:     # c1 written last -> c1 wins per (date, tile)
        for t in range(4):
            try: its = list(cat.search(collections=[coll], bbox=bb, datetime=f"{a}/{b}").item_collection()); break
            except Exception as e: its = []
        LAST_COUNTS[coll] = sorted({(i.datetime.date().isoformat(), round(i.properties.get("eo:cloud_cover") or -1)) for i in its})
        for i in its: got[(i.datetime.date().isoformat(), i.properties.get("grid:code") or i.id.split("_")[1])] = i
    return got
def run(tagname, a, b, anchor=None, cap=None, maxcloud=90):
    got = items_for(a.isoformat(), b.isoformat()); counts = dict(LAST_COUNTS)
    # skip very cloudy tiles (tile-level cloud >= 90 %)
    got = {k: i for k, i in got.items() if (i.properties.get("eo:cloud_cover") or 0) < maxcloud}
    bydate = {}
    for (d, tile), i in got.items(): bydate.setdefault(d, []).append(i)
    if cap:   # data-volume cap (secondary only): the `cap` dates nearest the anniversary, chosen without looking at any result
        keep = sorted(bydate, key=lambda d: abs((dt.date.fromisoformat(d) - anchor).days))[:cap]
        bydate = {d: bydate[d] for d in keep}
    lg = None; res = {}
    for d in sorted(bydate):
        outf = H/f"out/cells/{key}_{tagname}_{d}.npz"
        if outf.exists(): res[d] = True; continue
        try:
            scs = [L.read_item(i, bb, key) for i in bydate[d]]
            # group by CRS, take the group with most valid pixels; merge same-grid tiles
            groups = {}
            for s in scs: groups.setdefault(s["crs"].to_string(), []).append(s)
            gbest = max(groups.values(), key=lambda g: sum(int((x["SCL"] > 0).sum()) for x in g))
            s = L.merge_same_grid(gbest)
            if lg is None or lg.crs != s["crs"]: lg = L.LakeGrid(poly, s["crs"])
            if (s["SCL"] > 0).sum() == 0: res[d] = "EMPTY"; continue
            p = L.scene_products(s, lg); st = L.cell_state(p, lg.lake)
            fp = np.where(p["have"], 0.0, np.nan_to_num(p["f_plant"], nan=np.nan)).astype("float32")
            np.savez_compressed(outf, state=st, fplant=np.where(st >= 0, fp, np.nan).astype("float16"), have=p["have"], dist=lg.dist.astype("float16"), lake=lg.lake, clarity=lg.clarity,
                                swir_med=float(np.nanmedian(s["B11"][s["SCL"]==6])) if (s["SCL"]==6).any() else np.nan, red_med=float(np.nanmedian(s["B04"][s["SCL"]==6])) if (s["SCL"]==6).any() else np.nan, ids=",".join(x["id"] for x in gbest), ground_m=lg.frame.ground_m())
            res[d] = True
            print(key, tagname, d, "ok", flush=True)
        except Exception as e:
            res[d] = "ERR " + repr(e)[:200]; print(key, tagname, d, "ERR", repr(e)[:200], flush=True)
    res["_search"] = counts; res["_window"] = [a.isoformat(), b.isoformat()]
    return res
out = {}
if mode in ("primary", "both"):
    out["primary"] = run("p2017", ref - dt.timedelta(21), ref + dt.timedelta(21))
if mode in ("secondary", "both"):
    for y in (2018, 2019):
        try: an = ref.replace(year=y)
        except ValueError: an = ref.replace(year=y, day=28)
        a = max(an - dt.timedelta(21), dt.date(y, 6, 1)); b = min(an + dt.timedelta(21), dt.date(y, 9, 30))
        out[f"s{y}"] = run(f"s{y}", a, b, anchor=an, cap=6, maxcloud=50)
json.dump(out, open(H/f"out/cells/{key}_status_{mode}.json", "w"))
