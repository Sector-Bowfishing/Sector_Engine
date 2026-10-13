"""Two-stage windowed COG reads, 2017-2025, lake analysis window + 250 m pad.
Stage 1 (cheap, every STAC date with tile cloud < CLOUD_MAX): read SCL only -> per-date status inputs (cloud/shadow/snow/nodata shares over the lake pixels in the window).
Stage 2: read B04 (10 m), B8A, B11 (20 m -> 10 m nearest) only for dates whose SCL clear share >= CLEAR_MIN (lossless w.r.t. observer-A acceptance up to cell rounding);
         if more than MAX_MB would be needed, keep the max-clear date in each BIN-day bin (BIN chosen per lake, recorded).
Preference: sentinel-2-c1-l2a (DN*1e-4 - 0.1) else sentinel-2-l2a (offset-free: checked against a same-day c1 pair). Cache int16 reflectance*1e4 (-32768 nodata).
Usage: s2_fetch.py LAKEKEY [MAX_MB]"""
import sys, json, math, time, warnings, datetime as dt, numpy as np, rasterio, collections, pyproj
warnings.filterwarnings("ignore")
from concurrent.futures import ThreadPoolExecutor
from rasterio.windows import from_bounds
from rasterio.warp import transform_bounds
from rasterio.features import rasterize
from shapely.geometry import shape, box
from shapely.ops import transform as shp_t
from pystac_client import Client
import gzip
from common import *
import s2lib as S
CLOUD_MAX = 85; PAD_M = 250.0; CLEAR_MIN = 0.25; MB_PER_SCENE = 0.62
lk = sys.argv[1]; MAX_MB = float(sys.argv[2]) if len(sys.argv) > 2 else 210
W = json.load(open(H/"out/windows.json"))[lk]
x0, y0, x1, y1 = W["window"]; lat = W["lat"]
px = PAD_M/(111320*math.cos(math.radians(lat))); py = PAD_M/110570
BB = [x0-px, y0-py, x1+px, y1+py]
b = (H/"geom"/f"{lk}.geojson.gz").read_bytes(); g = json.loads(gzip.decompress(b) if b[:2] == b"\x1f\x8b" else b)
GEOM = shape(g["features"][0]["geometry"] if g.get("type") == "FeatureCollection" else g.get("geometry", g))
ANA = GEOM.intersection(box(x0, y0, x1, y1))
cdir = H/"cache"/lk; cdir.mkdir(parents=True, exist_ok=True)
cat = Client.open(S.STAC)
def find(coll):
    for k in range(6):
        try: return list(cat.search(collections=[coll], bbox=BB, datetime="2017-01-01/2025-12-31", query={"eo:cloud_cover": {"lt": CLOUD_MAX}}, max_items=6000).item_collection())
        except Exception as e: time.sleep(4)
    raise RuntimeError("stac fail")
c1 = find("sentinel-2-c1-l2a"); l2 = find("sentinel-2-l2a")
byk = {}
for src, items in (("c1", c1), ("l2a", l2)):
    for i in items:
        key = (i.properties.get("grid:code", i.id), i.datetime.date().isoformat())
        if key in byk:
            if byk[key][0] == "c1": continue
            if byk[key][1].properties.get("eo:cloud_cover", 100) <= i.properties.get("eo:cloud_cover", 100): continue
        byk[key] = (src, i)
bydate = collections.defaultdict(list)
for (t, d), v in byk.items(): bydate[d].append(v)
dates = sorted(bydate)
print(lk, "c1 items", len(c1), "l2a items", len(l2), "dates", len(dates), flush=True)

def window_for(item):
    red = rasterio.open(S.http(item.assets["red"].href)); crs = red.crs
    l, b_, r, t = transform_bounds("EPSG:4326", crs, *BB)
    win = from_bounds(l, b_, r, t, red.transform).round_offsets().round_lengths()
    return red, crs, win
def read_band(item, an, red, win, nearest=True):
    a = item.assets[an]; sr = rasterio.open(S.http(a.href)); Hh, Ww = int(win.height), int(win.width)
    w_ = from_bounds(*rasterio.windows.bounds(win, red.transform), sr.transform)
    return sr.read(1, window=w_, out_shape=(Hh, Ww), resampling=rasterio.enums.Resampling.nearest, boundless=True, fill_value=0)
def lake_mask(tr, crs, shape_hw):
    t = pyproj.Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform
    return rasterize([(shp_t(t, ANA), 1)], out_shape=shape_hw, transform=tr, fill=0, dtype="uint8").astype(bool)

def stage1(d):
    f = cdir/f"s1_{d}.json"
    if f.exists(): return d, json.load(open(f))
    res = None
    for _ in range(3):
        try:
            rec = {}
            with rasterio.Env(**S.ENV):
                scl = None; crs0 = None
                for s_, it in bydate[d]:
                    red, crs, win = window_for(it)
                    if crs0 is None: crs0 = crs; tr0 = red.window_transform(win); sc = read_band(it, "scl", red, win)
                    elif crs == crs0 and sc.shape == (int(win.height), int(win.width)) and red.window_transform(win) == tr0:
                        s2 = read_band(it, "scl", red, win); m = sc == 0; sc[m] = s2[m]
                m = lake_mask(tr0, crs0, sc.shape); n = int(m.sum()); v = sc[m]
                fr = lambda cls: float(np.isin(v, cls).sum()/max(n, 1))
                rec = dict(date=d, n=n, nodata=fr([0]), cloud=fr([8, 9, 10]), shadow=fr([3]), defect=fr([1]), snow=fr([11]), water=fr([6]), land=fr([4, 5]), other=fr([2, 7]),
                           cloud_tile=[i.properties.get("eo:cloud_cover") for _, i in bydate[d]], src=sorted({s for s, _ in bydate[d]}), tiles=[i.id for _, i in bydate[d]])
                rec["clear"] = 1.0 - rec["nodata"] - rec["cloud"] - rec["shadow"] - rec["defect"] - rec["snow"]
            res = rec; break
        except Exception as e: err = str(e)[:80]; time.sleep(2)
    if res is None: res = dict(date=d, error=err)
    json.dump(res, open(f, "w")); return d, res

def read_item(src, item):
    with rasterio.Env(**S.ENV):
        red, crs, win = window_for(item); tr = red.window_transform(win); out = {}
        for bn, an in (("B04", "red"), ("B8A", "nir08"), ("B11", "swir16"), ("SCL", "scl")):
            arr = read_band(item, an, red, win)
            if bn == "SCL": out[bn] = arr.astype("uint8"); continue
            v = arr.astype("int32") + (-1000 if src == "c1" else 0); v[arr == 0] = -32768; out[bn] = v.astype("int16")
    return out, tr, str(crs)
def stage2(d):
    f = cdir/f"{d}.npz"
    if f.exists(): return d, f.stat().st_size, "cached"
    outs = None
    for _ in range(3):
        try: outs = [(s, i, *read_item(s, i)) for s, i in bydate[d]]; break
        except Exception as e: err = str(e)[:100]; time.sleep(2)
    if outs is None: return d, 0, "FAIL " + err
    crs0 = outs[0][4]; same = [o for o in outs if o[4] == crs0]
    if len(same) < len(outs): same = [max(outs, key=lambda o: int((o[2]["B04"] != -32768).sum()))]
    arrs = {k: v.copy() for k, v in same[0][2].items()}; tr = same[0][3]
    for o in same[1:]:
        if o[2]["B04"].shape != arrs["B04"].shape or o[3] != tr: continue
        m = arrs["B04"] == -32768
        for k in arrs: arrs[k][m] = o[2][k][m]
    meta = dict(date=d, items=[o[1].id for o in outs], src=sorted({o[0] for o in outs}), tr=list(tr)[:6], crs=crs0)
    np.savez_compressed(f, **arrs, meta=json.dumps(meta)); return d, f.stat().st_size, "ok"

t0 = time.time(); S1 = {}
with ThreadPoolExecutor(12) as ex:
    for n, (d, r) in enumerate(ex.map(stage1, dates)):
        S1[d] = r
        if n % 100 == 0: print("stage1", n+1, len(dates), f"{time.time()-t0:.0f}s", flush=True)
errs = [d for d, r in S1.items() if "error" in r]; print("stage1 errors", len(errs))
cand = [d for d in dates if "error" not in S1[d] and S1[d]["clear"] >= CLEAR_MIN and S1[d]["nodata"] < 0.5]
need = len(cand)*MB_PER_SCENE; BIN = 0
if need > MAX_MB:
    for BIN in (2, 3, 4, 5, 6, 8, 10):
        keep = {}
        for d in cand:
            bb_ = (dt.date.fromisoformat(d)-dt.date(2017, 1, 1)).days//BIN
            if bb_ not in keep or S1[d]["clear"] > S1[keep[bb_]]["clear"]: keep[bb_] = d
        sel = sorted(keep.values())
        if len(sel)*MB_PER_SCENE <= MAX_MB: break
    cand_all = cand; cand = sel
print(lk, f"stage-2 candidates {len(cand)} (clear>={CLEAR_MIN}); BIN={BIN}; est {len(cand)*MB_PER_SCENE:.0f} MB", flush=True)
json.dump(dict(lake=lk, dates=len(dates), bin=BIN, selected=cand, candidates_before_bin=len([d for d in dates if "error" not in S1[d] and S1[d]["clear"] >= CLEAR_MIN and S1[d]["nodata"] < 0.5])), open(H/f"out/fetchplan_{lk}.json", "w"))
tot = 0; fails = 0
with ThreadPoolExecutor(12) as ex:
    for n, (d, sz, st) in enumerate(ex.map(stage2, cand)):
        tot += sz; fails += st.startswith("FAIL")
        if st.startswith("FAIL"): print(d, st, flush=True)
        if n % 50 == 0: print(f"stage2 {n+1}/{len(cand)} {tot/1e6:.0f} MB {time.time()-t0:.0f}s", flush=True)
s1b = sum(p.stat().st_size for p in cdir.glob("s1_*.json"))
print(lk, "DONE stage2 dates", len(cand), "cache MB", round(tot/1e6, 1), "fails", fails, "sec", round(time.time()-t0), flush=True)
