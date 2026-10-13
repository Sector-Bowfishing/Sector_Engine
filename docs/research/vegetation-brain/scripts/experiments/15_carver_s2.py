"""Reitz / Brickyard (MN): S2 scenes May-Oct 2019, sonar biovolume raster at 10 m, indices, per-scene AUC. Survey date unknown (layer published 2019-12-12 / 2020-02-10)."""
import sys, json, numpy as np, rasterio, datetime as dt
from pathlib import Path
from pyproj import Transformer
from rasterio.features import rasterize
from scipy.ndimage import distance_transform_edt
ROOT = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT/"scripts")); import s2lib
for nm in ["reitz", "brickyard"]:
    d = json.load(open(ROOT/f"data/carver_{nm}_biovolume.json"))["rows"]
    lon = np.array([r["Longitude"] for r in d]); lat = np.array([r["Latitude"] for r in d]); bv = np.array([r["BioVolume"] for r in d], float)
    m = 0.003; bbox = (lon.min()-m, lat.min()-m, lon.max()+m, lat.max()+m)
    items = s2lib.dedupe_by_date(s2lib.search(bbox, "2019-05-15", "2019-10-15", 60))
    print(nm, "bbox", [round(x,4) for x in bbox], "scenes", len(items), flush=True)
    scenes = []
    for it in items:
        try: scenes.append(s2lib.read_scene(it, bbox, "carver"))
        except Exception as e: print(" fail", it.id, e)
    tr, crs = scenes[0]["transform"], scenes[0]["crs"]; shp = scenes[0]["B04"].shape
    scenes = [s for s in scenes if s["transform"] == tr and s["B04"].shape == shp]
    t = Transformer.from_crs("EPSG:4326", crs, always_xy=True); x, y = t.transform(lon, lat)
    cc, rr = ~tr * (x, y); cc = np.floor(cc).astype(int); rr = np.floor(rr).astype(int)
    ok = (cc >= 0) & (cc < shp[1]) & (rr >= 0) & (rr < shp[0])
    S = np.zeros(shp); N = np.zeros(shp)
    np.add.at(S, (rr[ok], cc[ok]), bv[ok]); np.add.at(N, (rr[ok], cc[ok]), 1)
    BV = np.where(N > 0, S / np.maximum(N, 1), np.nan)
    X, V = s2lib.stack_scenes(scenes)
    # water mask: SCL water in >= 50 % of clear scenes
    wat = np.mean([(s["SCL"] == 6) for s in scenes], 0) >= 0.5
    dist = distance_transform_edt(wat) * 10.0
    out = ROOT/f"out/stack_carver_{nm}.npz"
    np.savez_compressed(out, X=X, V=V, dates=np.array([s["date"] for s in scenes]), BV=BV.astype("float32"), npts=N.astype("float32"), water=wat, dist=dist.astype("float32"), idx=np.array(s2lib.IDX_ORDER))
    print(nm, "scenes", len(scenes), "surveyed px", int((N > 0).sum()), "water px", int(wat.sum()), "BV pct>0.01:", float((bv > 0.01).mean()), "->", out.name, flush=True)
