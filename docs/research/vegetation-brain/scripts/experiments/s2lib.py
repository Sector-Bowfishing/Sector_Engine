"""Shared Sentinel-2 helpers: STAC search, windowed COG reads, index computation. Research only."""
import os, json, hashlib, datetime as dt, numpy as np, rasterio
from rasterio.windows import from_bounds
from rasterio.warp import transform_bounds
from pystac_client import Client
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
CACHE = ROOT / "out" / "s2cache"; CACHE.mkdir(parents=True, exist_ok=True)
STAC = "https://earth-search.aws.element84.com/v1"
COLL = "sentinel-2-c1-l2a"   # same collection Sector uses (reflectance = DN*1e-4 - 0.1); the older sentinel-2-l2a COGs already have the offset removed
# NOTE: first pass of this experiment accidentally used sentinel-2-l2a with the -0.1 offset applied twice; discarded.
BANDS = {"B02":"blue","B03":"green","B04":"red","B05":"rededge1","B06":"rededge2","B07":"rededge3",
         "B08":"nir","B8A":"nir08","B11":"swir16","B12":"swir22"}
SCL_BAD = {0,1,3,8,9,10,11}
ENV = dict(AWS_NO_SIGN_REQUEST="YES", GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR",
           CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif", GDAL_HTTP_MAX_RETRY="4", GDAL_HTTP_RETRY_DELAY="2")

def http(href):
    if href.startswith("s3://"):
        b, k = href[5:].split("/", 1)
        return f"/vsicurl/https://{b}.s3.us-west-2.amazonaws.com/{k}"
    return "/vsicurl/" + href

def search(bbox, d0, d1, max_cloud=80):
    cat = Client.open(STAC)
    items = list(cat.search(collections=[COLL], bbox=bbox, datetime=f"{d0}/{d1}",
                       query={"eo:cloud_cover": {"lt": max_cloud}}).item_collection())
    if not items:  # c1 has gaps (all of 2022 on 2026-10): fall back to the older collection, whose COGs have the offset already removed
        items = list(cat.search(collections=["sentinel-2-l2a"], bbox=bbox, datetime=f"{d0}/{d1}",
                       query={"eo:cloud_cover": {"lt": max_cloud}}).item_collection())
    return sorted(items, key=lambda i: i.datetime)

def read_scene(item, bbox_ll, tag):
    """Read all bands in a lon/lat bbox window at 10 m grid (20 m bands upsampled nearest).
    Returns dict(arrays..., transform, crs, date, item id). Cached as npz."""
    f = CACHE / f"{tag}_{hashlib.md5(repr([round(x,5) for x in bbox_ll]).encode()).hexdigest()[:8]}_{item.id}.npz"
    if f.exists():
        z = np.load(f, allow_pickle=True); return {k: (z[k].item() if k in ("date","id") else z[k]) for k in z.files} | {"transform": rasterio.Affine(*z["transform"]), "crs": rasterio.crs.CRS.from_string(str(z["crs"]))}
    with rasterio.Env(**ENV):
        red = rasterio.open(http(item.assets["red"].href))
        crs = red.crs
        l, b, r, t = transform_bounds("EPSG:4326", crs, *bbox_ll)
        win = from_bounds(l, b, r, t, red.transform).round_offsets().round_lengths()
        tr = red.window_transform(win); H, W = int(win.height), int(win.width)
        out = {}
        for bn, an in BANDS.items():
            a = item.assets[an]
            src = rasterio.open(http(a.href))
            w_ = from_bounds(*rasterio.windows.bounds(win, red.transform), src.transform)
            arr = src.read(1, window=w_, out_shape=(H, W), resampling=rasterio.enums.Resampling.nearest, boundless=True, fill_value=0)
            sc = a.extra_fields.get("raster:bands", [{}])[0]
            scale, off = sc.get("scale", 1e-4), sc.get("offset", 0.0)
            if item.collection_id == "sentinel-2-l2a": off = 0.0   # offset already removed in these COGs
            r_ = arr.astype("float32") * scale + off
            r_[arr == 0] = np.nan
            out[bn] = r_
        ssrc = rasterio.open(http(item.assets["scl"].href))
        scl = ssrc.read(1, window=from_bounds(*rasterio.windows.bounds(win, red.transform), ssrc.transform), out_shape=(H, W), resampling=rasterio.enums.Resampling.nearest, boundless=True, fill_value=0)
        out["SCL"] = scl.astype("uint8")
    out["transform"] = tr; out["crs"] = crs
    out["date"] = item.datetime.date().isoformat(); out["id"] = item.id
    np.savez_compressed(f, **{k: v for k, v in out.items() if k not in ("transform", "crs")}, transform=np.array(tr)[:6], crs=str(crs))
    return out

def indices(s):
    e = np.errstate(invalid="ignore", divide="ignore"); e.__enter__()
    B2,B3,B4,B5,B6,B7,B8,B8A,B11,B12 = (s[k] for k in ["B02","B03","B04","B05","B06","B07","B08","B8A","B11","B12"])
    nd = lambda a, b: (a - b) / np.maximum(a + b, 0.01)   # floor 0.01: stabilise dark-water pixels with ~0/negative reflectance
    nds = lambda a, b: (a - b) / np.maximum(1e-6, a + b)   # exact Sector formula
    ix = {
     "NDVI": nd(B8, B4), "NDAVI": nd(B8, B2) if False else nd(B8, B2),
     "FAI": B8 - (B4 + (B11 - B4) * (842 - 665) / (1610 - 665)),
     "FAI_sector": B8A - (B4 + (B11 - B4) * (865 - 665) / (1610 - 665)),  # exact Sector formula (B8A)
     "NDVI_sector": nds(B8A, B4),
     "NDRE1": nd(B8A, B5), "NDRE2": nd(B8A, B6), "NDRE3": nd(B7, B5), "RE_slope": nd(B6, B5),
     "NDWI": nd(B3, B8), "GNDVI": nd(B8, B3), "SWIR": B11, "NIR": B8, "RED": B4, "GREEN": B3, "BLUE": B2,
     "NDAVI_sw": nd(B8, B2),
    }
    # WAVI-like and SWIR-NIR sub-surface: NDII
    ix["NDII"] = nd(B8, B11)
    e.__exit__(None, None, None)
    return ix

def valid_mask(s, grow=1):
    bad = np.isin(s["SCL"], list(SCL_BAD))
    from scipy.ndimage import binary_dilation
    return ~(binary_dilation(bad, iterations=grow) if grow else bad)

IDX_ORDER = ["NDVI","NDAVI","FAI","NDVI_sector","FAI_sector","NDRE1","NDRE2","NDRE3","RE_slope","NDWI","GNDVI","NDII","SWIR","NIR","RED","GREEN","BLUE"]

def dedupe_by_date(items):
    seen = {}
    for i in items:
        d = i.datetime.date()
        if d not in seen or i.properties.get("eo:cloud_cover", 100) < seen[d].properties.get("eo:cloud_cover", 100):
            seen[d] = i
    return list(seen.values())

def grid_helpers(tr, crs, shape):
    from pyproj import Transformer
    from shapely.ops import transform as sh_transform
    t = Transformer.from_crs("EPSG:4326", crs, always_xy=True).transform
    return lambda g: sh_transform(t, g)

def stack_scenes(scenes):
    """list of scene dicts -> (S,K,H,W) float32 of IDX_ORDER, (S,H,W) valid bool"""
    X = []; V = []
    for s in scenes:
        ix = indices(s)
        X.append(np.stack([ix[k] for k in IDX_ORDER]).astype("float32"))
        V.append(valid_mask(s, 1))
    return np.stack(X), np.stack(V)
