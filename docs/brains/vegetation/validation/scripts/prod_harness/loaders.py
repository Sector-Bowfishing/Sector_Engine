import sys, json, glob, numpy as np, rasterio
from pathlib import Path
from shapely.geometry import shape
ROOT = Path("{HOME}/Desktop/Development/Sector_Research_Data/vegetation-brain/experiments")
import prod_import as P

SNOCO_SHORT = {"Lake Serene":"Serene","Blackmans Lake":"Blackmans","Storm Lake":"Storm","Lake Roesiger":"Roesiger","Lake Bosworth":"Bosworth"}
FWC_IDS = {"Orange":"288216","Griffin":"305765","Apopka":"293912","Harris":"294031","Panasoffkee":"294114","Yale":"306620","Cypress":"281219"}

def lakes(tag):
    if tag == "snoco":
        return {SNOCO_SHORT[f["properties"]["name"]]: shape(f["geometry"]) for f in json.load(open(ROOT/"data/snoco_layer15.geojson"))["features"]}
    L = {f["properties"]["Lake_Id"]: shape(f["geometry"]) for f in json.load(open(ROOT/"data/fwc_ltm_lakes.geojson"))["features"]}
    return {k: L[v] for k, v in FWC_IDS.items()}

def fwc_all_lakes():
    return {f["properties"]["Lake_Id"]: shape(f["geometry"]) for f in json.load(open(ROOT/"data/fwc_ltm_lakes.geojson"))["features"]}

_caches = {}
def _index(tag):
    if tag in _caches: return _caches[tag]
    d = {}
    for f in glob.glob(str(ROOT/f"out/s2cache/{tag}_*.npz")):
        z = np.load(f, allow_pickle=True)
        d.setdefault((z["B04"].shape, str(z["date"].item() if z["date"].shape == () else z["date"])), []).append(f)
    _caches[tag] = d; return d

def stack_scenes(tag, nm):
    """-> list of dict(date, id, dn arrays, transform, crs) for every scene in the lake's note-04 stack (+-45 d of survey)."""
    st = np.load(ROOT/f"out/stack_{tag}_{nm}.npz", allow_pickle=True)
    shp = st["lake"].shape; dates = [str(d) for d in st["dates"]]; idx = _index(tag); out = []
    for i, d in enumerate(dates):
        fs = idx.get((shp, d), [])
        if len(fs) != 1:
            ok = None
            for f in fs:
                z = np.load(f, allow_pickle=True); ndv = (z["B8A"]-z["B04"])/np.maximum(1e-6, z["B8A"]+z["B04"])
                k = list(st["idx"]).index("NDVI_sector")
                if np.allclose(np.nan_to_num(ndv), np.nan_to_num(st["X"][i, k]), atol=1e-4): ok = f; break
            fs = [ok] if ok else []
        if not fs: out.append(None); continue
        z = np.load(fs[0], allow_pickle=True)
        tr = rasterio.Affine(*z["transform"]); crs = rasterio.crs.CRS.from_string(str(z["crs"]))
        # collection: note 04 used c1 (offset -0.1) except 2022 -> l2a; both already stored as true reflectance, so refl->DN(c1 convention)
        tile = P.build_tile(P.refl_to_dn(z["B04"]), P.refl_to_dn(z["B8A"]), P.refl_to_dn(z["B11"]), z["SCL"], tr, crs)
        out.append(dict(date=d, id=str(z["id"].item()), tile=tile, crs=crs, transform=tr, file=fs[0],
                        blockcons=P.block_consistency(z["B8A"], tr)))
    return st, out

def pac_scenes(lake_id, survey, win=21):
    """cached lean scenes for a FWC lake (all attempted scenes), within +-win d of survey"""
    import datetime as dt
    out = []
    sv = dt.date.fromisoformat(survey)
    for f in sorted(glob.glob(str(ROOT/f"out/s2cache_pac/{lake_id}_*.npz"))):
        z = np.load(f, allow_pickle=True)
        d = str(z["date"].item() if z["date"].shape == () else z["date"])
        if abs((dt.date.fromisoformat(d) - sv).days) > win: continue
        off = float(z["off"]); tr = rasterio.Affine(*z["transform"]); crs = rasterio.crs.CRS.from_string(str(z["crs"]))
        tile = P.build_tile(P.raw_to_dn(z["B04"], off), P.raw_to_dn(z["B8A"], off), P.raw_to_dn(z["B11"], off), z["SCL"], tr, crs)
        out.append(dict(date=d, id=Path(f).stem, tile=tile, crs=crs, transform=tr, file=f, off=off))
    return out
