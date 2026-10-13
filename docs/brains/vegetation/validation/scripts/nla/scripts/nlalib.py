"""NLA x S2 validation: cell-level observer (production rule port) restricted to the lake polygon.
Reuses constants/standoff logic of experiments/scripts/cell_lib.py (a port of jobs/lake-surface/derive_water_surface.py).
Deviations from production are listed in note 07 (polygon-masked pixels, no 40 m erosion, prereg guards)."""
import sys, json, gzip, math, hashlib, datetime as dt, numpy as np, rasterio
from pathlib import Path
from rasterio.windows import from_bounds
from rasterio.warp import transform_bounds
from rasterio.features import rasterize
from scipy import ndimage
from scipy.spatial import cKDTree
from shapely.geometry import shape
from shapely.ops import transform as shp_transform
import pyproj
H = Path(__file__).resolve().parents[1]; ROOT = H.parents[1]
sys.path.insert(0, str(ROOT/"scripts"))
import cell_lib as C
import s2lib as S2
CACHE = H/"out"/"s2cache_nla"; CACHE.mkdir(parents=True, exist_ok=True)
PAD_DEG = 0.007
ASSETS = {"red":"red", "nir08":"nir08", "swir16":"swir16"}

def load_poly(key):
    b = (H/f"data/geom/{key}.geojson.gz").read_bytes()
    g = json.loads(gzip.decompress(b) if b[:2] == b"\x1f\x8b" else b)
    return shape(g["features"][0]["geometry"] if g.get("type") == "FeatureCollection" else g.get("geometry", g))

def window_bbox(poly):
    x0, y0, x1, y1 = poly.bounds
    return [x0 - PAD_DEG, y0 - PAD_DEG, x1 + PAD_DEG, y1 + PAD_DEG]

def read_item(item, bbox_ll, key):
    """Minimal band read (red 10 m; B8A, B11, SCL 20 m nearest-upsampled to 10 m). Cached as raw DN + scale/offset."""
    f = CACHE/f"{key}_{item.id}.npz"
    if f.exists():
        z = np.load(f, allow_pickle=True)
        d = {k: z[k] for k in ("red", "nir08", "swir16", "scl")}
        meta = json.loads(str(z["meta"])); tr = rasterio.Affine(*meta["tr"]); crs = rasterio.crs.CRS.from_string(meta["crs"])
        sc = meta["sc"]
    else:
        with rasterio.Env(**S2.ENV):
            red = rasterio.open(S2.http(item.assets["red"].href)); crs = red.crs
            l, b, r, t = transform_bounds("EPSG:4326", crs, *bbox_ll)
            win = from_bounds(l, b, r, t, red.transform).round_offsets().round_lengths()
            tr = red.window_transform(win); Hh, W = int(win.height), int(win.width)
            d = {}; sc = {}
            for nm in ("red", "nir08", "swir16"):
                a = item.assets[nm]; src = rasterio.open(S2.http(a.href))
                w_ = from_bounds(*rasterio.windows.bounds(win, red.transform), src.transform)
                d[nm] = src.read(1, window=w_, out_shape=(Hh, W), resampling=rasterio.enums.Resampling.nearest, boundless=True, fill_value=0).astype("uint16")
                rb = a.extra_fields.get("raster:bands", [{}])[0]
                scale, off = rb.get("scale", 1e-4), rb.get("offset", 0.0)
                if item.collection_id == "sentinel-2-l2a": off = 0.0
                sc[nm] = [scale, off]
            ss = rasterio.open(S2.http(item.assets["scl"].href))
            d["scl"] = ss.read(1, window=from_bounds(*rasterio.windows.bounds(win, red.transform), ss.transform), out_shape=(Hh, W),
                               resampling=rasterio.enums.Resampling.nearest, boundless=True, fill_value=0).astype("uint8")
        meta = {"tr": list(tr)[:6], "crs": crs.to_string(), "sc": sc, "coll": item.collection_id}
        np.savez_compressed(f, **d, meta=json.dumps(meta))
    s = {}
    for nm, col in (("red", "B04"), ("nir08", "B8A"), ("swir16", "B11")):
        scale, off = sc[nm]; r_ = d[nm].astype("float32") * scale + off; r_[d[nm] == 0] = np.nan; s[col] = r_
    s["SCL"] = d["scl"]; s["transform"] = tr; s["crs"] = crs; s["date"] = item.datetime.date().isoformat(); s["id"] = item.id
    return s

def hidden_field(s):
    """Production 'hidden' indicator (derive_water_surface._s2_native_fields), re-derived here (cell_lib.native_fields omits it).
    Returns hidden (nan where scl==0 or bank), bank, water, seen0 (=scl>0 & clear), veg, ndvi, dark."""
    r_red, r_nir, r_sw, scl = s["B04"], s["B8A"], s["B11"], s["SCL"]
    water = scl == C.SCL_WATER
    with np.errstate(invalid="ignore", divide="ignore"):
        ndvi = (r_nir - r_red) / np.maximum(1e-6, r_nir + r_red)
        bright = np.nan_to_num(r_sw, nan=0) > C.BRIGHT_SWIR
        veg = ndvi >= C.GRASS_NDVI_MIN
        haze_px = water & (r_sw > C.HAZE_SWIR) & ~veg
    structure = bright & (np.nan_to_num(ndvi, nan=1.0) < C.S2_STRUCTURE_NDVI_MAX) & ~water
    haze = bright & water
    bank = np.isin(scl, C.S2_SCL_BANK); px = C.S2_NATIVE_PX
    to_bank, to_structure = C._edge_dist_px(bank), C._edge_dist_px(structure)
    cloudy = [c for c in C.SCL_CLOUDY if c != 0]
    cl = np.isin(scl, cloudy)
    to_cloud = C._edge_dist_px(cl); clear = to_cloud >= C.S2_CLOUD_STANDOFF_M / px
    lab, n = ndimage.label(cl)
    if n:
        sizes = ndimage.sum(cl, lab, index=np.arange(1, n + 1)); real = np.isin(lab, np.nonzero(sizes >= 4 * C.S2_REAL_CLOUD_MIN_PX20)[0] + 1)
    else: real = cl
    to_real = C._edge_dist_px(real); near_cloud = to_real < C.S2_CLOUD_EDGE_M / px; under_cloud = to_real < C.S2_REAL_CLOUD_STANDOFF_M / px
    offshore = (to_bank >= C.S2_CLOUD_EDGE_OFFSHORE_M / px) & (to_structure >= C.S2_CLOUD_EDGE_OFFSHORE_M / px)
    with np.errstate(invalid="ignore"):
        cloud_edge = near_cloud & offshore & (r_sw > C.S2_CLOUD_EDGE_SWIR)
        haze_edge = (C._edge_dist_px(haze_px) < C.HAZE_EDGE_M / px) & offshore & (r_sw > C.HAZE_EDGE_SWIR)
    beside_bright = C._edge_dist_px(haze) < C.S2_HAZE_STANDOFF_M / px
    unhazed = ~beside_bright & ~cloud_edge & ~haze_edge
    hidden = np.where((scl > 0) & ~bank, (under_cloud | cloud_edge | (beside_bright & near_cloud) | ((haze_px | haze_edge) & offshore)).astype("float32"), np.nan)
    ok = water & clear & ~under_cloud & unhazed
    ok &= to_bank >= C.S2_BANK_STANDOFF_M / px; ok &= to_structure >= C.S2_STRUCTURE_STANDOFF_M / px
    with np.errstate(invalid="ignore"):
        fai = r_nir - (r_red + (r_sw - r_red) * (865 - 665) / (1610 - 665))
        ok &= (r_sw <= C.SWIR_MAX) & (fai <= C.FAI_MAX) & (ndvi <= C.NDVI_MAX) & (r_red > 0)
        dark = (r_red < 0.01) & (r_nir < 0.01)          # prereg: red and B8A both < 0.01 -> pixel excluded
    seen0 = (scl > 0) & clear & ~np.isnan(r_red) & ~np.isnan(r_nir)
    return dict(hidden=hidden.astype("float32"), bank=bank, ok=ok, seen0=seen0, veg=veg, dark=dark, scl=scl)

class LakeGrid:
    """Frame + masks + boundary distance for one lake (UTM from the scene CRS)."""
    def __init__(self, poly, crs):
        self.poly = poly; self.crs = crs
        self.frame = C.Frame(poly)
        utm = C.to_crs(poly, "EPSG:4326", crs)
        self.poly_utm = utm
        merc = C.to_crs(utm, crs, C.WEB_MERCATOR)
        self.lake = self.frame.burn(merc)
        self.clarity = self.frame.burn(C.to_crs(utm.buffer(-40.0), crs, C.WEB_MERCATOR))
        # cell-centre ground distance to polygon edge (m), in the scene's UTM
        fr = self.frame
        xs = fr.left + (np.arange(fr.width) + 0.5) * fr.cell; ys = fr.top - (np.arange(fr.height) + 0.5) * fr.cell
        X, Y = np.meshgrid(xs, ys)
        tx = pyproj.Transformer.from_crs(C.WEB_MERCATOR, crs, always_xy=True)
        ux, uy = tx.transform(X[self.lake], Y[self.lake])
        b = utm.boundary; pts = []
        geoms = list(b.geoms) if hasattr(b, "geoms") else [b]
        for g in geoms:
            L = g.length; n = max(2, int(L / 4.0))
            pts.append(np.array([g.interpolate(i * L / n).coords[0] for i in range(n)]))
        pts = np.vstack(pts); tree = cKDTree(pts)
        dd, _ = tree.query(np.c_[ux, uy])
        self.dist = np.full(self.lake.shape, np.nan, "float32"); self.dist[self.lake] = dd
    def poly_px(self, tr, shape_):
        return rasterize([(self.poly_utm, 1)], out_shape=shape_, transform=tr, fill=0, dtype="uint8").astype(bool)

def scene_products(s, lg):
    """Per-scene cell fields on the 50 m frame, from in-polygon pixels only."""
    h = hidden_field(s); shp = s["B04"].shape
    inp = lg.poly_px(s["transform"], shp)
    nan = np.float32(np.nan)
    def grid(arr):   # arr float32 with nan outside what counts; averaged onto the frame
        return C.to_grid(arr.astype("float32"), s["transform"], s["crs"], lg.frame)
    seen_px = inp & h["seen0"] & ~h["dark"]
    # fraction of in-polygon pixels per cell that are seen
    f_seen = grid(np.where(inp, seen_px.astype("float32"), nan))
    f_plant = grid(np.where(seen_px, h["veg"].astype("float32"), nan))
    f_dark = grid(np.where(inp & h["seen0"], h["dark"].astype("float32"), nan))
    f_hid = grid(np.where(inp, h["hidden"], nan))
    f_nodata = grid(np.where(inp, (s["SCL"] == 0).astype("float32"), nan))
    ok = h["ok"] & inp
    g = grid(np.where(ok, 1.0, nan)); frac = grid(np.where(inp & (s["SCL"] > 0), ok.astype("float32"), nan))
    have = ~np.isnan(g) & (np.nan_to_num(frac) >= C.S2_MIN_CELL_FRAC)
    return dict(f_seen=f_seen, f_plant=f_plant, f_dark=f_dark, f_hid=f_hid, f_nodata=f_nodata, have=have)

# cell states
PLANT, OPEN, UNK_CLOUD, UNK_DARK, UNK_INSUFF = 1, 0, 2, 3, 4
def cell_state(p, lake):
    """-> int8 state per frame cell (-1 outside lake). Priority: haze/cloud, dark, insufficient, then vote."""
    st = np.full(lake.shape, -1, "int8")
    fs, fp, fd, fh, have = (np.nan_to_num(p["f_seen"]), p["f_plant"], np.nan_to_num(p["f_dark"]), np.nan_to_num(p["f_hid"]), p["have"])
    st[lake] = OPEN
    seen = (fs >= 0.5)
    vote = seen & (np.nan_to_num(fp) >= 0.5) & ~have
    st[lake & seen] = OPEN; st[lake & vote] = PLANT
    st[lake & ~seen] = UNK_INSUFF
    st[lake & ~seen & (fd > 0.5)] = UNK_DARK
    st[lake & (fh >= 0.5)] = UNK_CLOUD
    return st

def merge_same_grid(scs):
    """Merge scenes of the same date on an identical grid (tile overlap); first scene wins where it has data."""
    base = dict(scs[0])
    for o in scs[1:]:
        if o["B04"].shape != base["B04"].shape or tuple(o["transform"])[:6] != tuple(base["transform"])[:6] or o["crs"] != base["crs"]: continue
        m = base["SCL"] == 0
        for k in ("B04", "B8A", "B11"): base[k] = np.where(m, o[k], base[k])
        base["SCL"] = np.where(m, o["SCL"], base["SCL"])
    return base
