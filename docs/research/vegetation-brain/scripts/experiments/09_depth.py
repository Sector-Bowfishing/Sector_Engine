"""Stratify FWC results by depth band (FWC bathymetry band polygons, 4 lakes) -> out/metrics_depth.json"""
import sys, json, glob, numpy as np
from pathlib import Path
from rasterio.features import rasterize
from shapely.geometry import shape
from sklearn.metrics import roc_auc_score
ROOT = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT/"scripts"))
import importlib; M = importlib.import_module("04_metrics"); s2lib = M.s2lib
bat = json.load(open(ROOT/"data/fwc_lake_bathymetry_bands.geojson"))["features"]
lakes = {f["properties"]["Lake_Id"]: (f["properties"]["Name"], shape(f["geometry"])) for f in json.load(open(ROOT/"data/fwc_ltm_lakes.geojson"))["features"]}
map_ = {"Griffin": "Lake Griffin", "Harris": "Lake Harris", "Panasoffkee": "Lake Panasoffkee", "Cypress": "Cypress Lake"}
out = {}; rows = {"surface": [], "submerged": []}
for nm, bn in map_.items():
    p = ROOT/"out"/f"stack_fwc_{nm}.npz"
    if not p.exists(): continue
    d = M.load(str(p), "fwc", "single")
    if d is None: continue
    shp = d["lake"].shape
    cand = None
    for f in glob.glob(str(ROOT/"out/s2cache/fwc_*.npz")):
        z = np.load(f, allow_pickle=True)
        if z["B04"].shape != shp: continue
        from pyproj import Transformer
        from shapely.ops import transform as sht
        import rasterio
        tr = rasterio.Affine(*z["transform"]); crs = str(z["crs"])
        t = Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform
        feats = [f_ for f_ in bat if f_["properties"]["Waterbody"] == bn]
        D = np.full(shp, np.nan, "float32")
        for f_ in sorted(feats, key=lambda f_: abs(f_["properties"]["Depth_Feet"] or 0)):
            g = sht(t, shape(f_["geometry"]).buffer(0))
            m = rasterize([(g, 1)], out_shape=shp, transform=tr, fill=0, dtype="uint8").astype(bool)
            D[m] = abs(f_["properties"]["Depth_Feet"]) * 0.3048
        ok = np.isfinite(D)
        iou = (ok & d["lake"]).sum() / max(1, (ok | d["lake"]).sum())
        cand = (iou, D); break
    if not cand or cand[0] < 0.5: print("no depth grid", nm, cand and cand[0]); continue
    D = cand[1]; use, neg, cl = M.pixels(d, "fwc")
    print(nm, "depth/lake IoU", round(cand[0], 2))
    for g in ["surface", "submerged"]:
        sel = d["valid"] & (neg | cl[g]) & np.isfinite(D)
        rows[g].append((np.full(sel.sum(), nm), D[sel], cl[g][sel], {k: d["F"][k][sel] for k in ["NDVI", "NDAVI", "FAI", "NDRE1", "NDVI_sector"]}))
res = {}
for g, R in rows.items():
    if not R: continue
    dep = np.concatenate([r[1] for r in R]); y = np.concatenate([r[2] for r in R]); F = {k: np.concatenate([r[3][k] for r in R]) for k in R[0][3]}
    for a, b in [(0, 0.6), (0.6, 1.2), (1.2, 2.0), (2.0, 3.0), (3.0, 99)]:
        m = (dep >= a) & (dep < b)
        if y[m].sum() < 15 or (~y[m]).sum() < 15: continue
        res.setdefault(g, {})[f"{a}-{b} m"] = {"n_pos": int(y[m].sum()), "n_neg": int((~y[m]).sum()), **{f"AUC_{k}": round(float(roc_auc_score(y[m], np.nan_to_num(F[k][m]))), 3) for k in ["NDVI", "NDAVI", "FAI", "NDRE1"]},
                                            "recall_sector_ndvi>=0.30": round(float((F["NDVI_sector"][m][y[m]] >= 0.30).mean()), 3)}
json.dump(res, open(ROOT/"out/metrics_depth.json", "w"), indent=1); print(json.dumps(res, indent=1))
