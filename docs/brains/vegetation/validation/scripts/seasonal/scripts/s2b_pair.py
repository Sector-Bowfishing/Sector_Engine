"""Paired collection check: same MGRS tile + date in sentinel-2-c1-l2a (DN-1000) and sentinel-2-l2a (offset-free); reads B04/B8A/B11/SCL for ~N pairs
and writes cache/_pair/{lake}/{src}_{date}.npz. Usage: s2b_pair.py LAKE N"""
import sys, json, math, warnings, numpy as np, rasterio, collections, random
warnings.filterwarnings("ignore")
from rasterio.windows import from_bounds
from rasterio.warp import transform_bounds
from pystac_client import Client
from common import *
import s2lib as S
lk = sys.argv[1]; N = int(sys.argv[2]); W = json.load(open(H/"out/windows.json"))[lk]
x0, y0, x1, y1 = W["window"]; lat = W["lat"]; px = 250/(111320*math.cos(math.radians(lat))); py = 250/110570
BB = [x0-px, y0-py, x1+px, y1+py]; cat = Client.open(S.STAC)
def find(c): return list(cat.search(collections=[c], bbox=BB, datetime="2017-01-01/2025-12-31", query={"eo:cloud_cover": {"lt": 30}}, max_items=3000).item_collection())
c1 = {(i.properties.get("grid:code"), i.datetime.date().isoformat()): i for i in find("sentinel-2-c1-l2a")}
l2 = {}
for i in find("sentinel-2-l2a"): l2.setdefault((i.properties.get("grid:code"), i.datetime.date().isoformat()), i)
common = sorted(set(c1) & set(l2)); random.Random(1).shuffle(common)
# stratify: half in 2018-2021 (older l2a baselines), half 2023-2025
old = [k for k in common if k[1] < "2022"]; new = [k for k in common if k[1] >= "2022"]
sel = old[:N//2] + new[:N - N//2]
(H/"cache/_pair"/lk).mkdir(parents=True, exist_ok=True)
def rd(src, item, d):
    f = H/"cache/_pair"/lk/f"{src}_{d}.npz"
    if f.exists(): return
    with rasterio.Env(**S.ENV):
        red = rasterio.open(S.http(item.assets["red"].href)); crs = red.crs
        l, b, r, t = transform_bounds("EPSG:4326", crs, *BB); win = from_bounds(l, b, r, t, red.transform).round_offsets().round_lengths(); tr = red.window_transform(win)
        out = {}
        for bn, an in (("B04", "red"), ("B8A", "nir08"), ("B11", "swir16"), ("SCL", "scl")):
            sr = rasterio.open(S.http(item.assets[an].href)); w_ = from_bounds(*rasterio.windows.bounds(win, red.transform), sr.transform)
            arr = sr.read(1, window=w_, out_shape=(int(win.height), int(win.width)), resampling=rasterio.enums.Resampling.nearest, boundless=True, fill_value=0)
            if bn == "SCL": out[bn] = arr.astype("uint8"); continue
            v = arr.astype("int32") + (-1000 if src == "c1" else 0); v[arr == 0] = -32768; out[bn] = v.astype("int16")
    np.savez_compressed(f, **out, meta=json.dumps(dict(date=d, items=[item.id], src=[src], tr=list(tr)[:6], crs=str(crs), baseline=item.properties.get("s2:processing_baseline"))))
for k in sel:
    rd("c1", c1[k], k[1]); rd("l2a", l2[k], k[1]); print(k, c1[k].properties.get("s2:processing_baseline"), l2[k].properties.get("s2:processing_baseline"))
