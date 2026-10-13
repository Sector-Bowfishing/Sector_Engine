"""Per-scene observer-A cell metrics for one lake from the cache. Usage: s3_cells.py LAKEKEY
Outputs out/scenes_{lake}.jsonl (one row per STAC date), out/cells_{lake}.npz (veg/seen cell stacks for read scenes + belt/dist masks).
Observer A (prereg s1): 10 m plant pixel NDVI(B8A,B4)>=0.30 under the production gates (cell_lib.native_fields = verbatim port of derive_water_surface.py constants);
50 m cell = plant if mean plant-fraction of its SEEN pixels >= 0.5, >=50 % of its footprint seen, and no turbidity reading in the cell (grass_vote guard);
dark-water pixels (red and B8A < 0.01) excluded from 'seen'; SHORE_ADJACENT = cell centre < 35 m from the true polygon edge (excluded); belt = 35-90 m from shore.
Pass acceptance = reads >= 50 % of the non-plant clarity-mask water (cov); fallback 25-50 %, else refused."""
import sys, json, math, gzip, warnings, numpy as np, rasterio, pyproj, shapely
warnings.filterwarnings("ignore")
from multiprocessing import Pool
from shapely.geometry import shape, box
from shapely.ops import transform as shp_t
from common import *
import cell_lib as C
lk = sys.argv[1]; W = json.load(open(H/"out/windows.json"))[lk]
x0, y0, x1, y1 = W["window"]; lat = W["lat"]
kx = 111320*math.cos(math.radians(lat)); ky = 110570
b = (H/"geom"/f"{lk}.geojson.gz").read_bytes(); g = json.loads(gzip.decompress(b) if b[:2] == b"\x1f\x8b" else b)
FULL = shape(g["features"][0]["geometry"] if g.get("type") == "FeatureCollection" else g.get("geometry", g))
LOC = FULL.intersection(box(x0-1200/kx, y0-1200/ky, x1+1200/kx, y1+1200/ky))
cdir = H/"cache"/lk
files = sorted(cdir.glob("2*.npz"))
FR = C.Frame(LOC)
# analysis geometry (set up from first scene crs)
z0 = np.load(files[0], allow_pickle=True); m0 = json.loads(str(z0["meta"])); CRS = rasterio.crs.CRS.from_string(m0["crs"])
M = C.lake_masks(LOC, FR, CRS)
def cellxy():
    jj, ii = np.meshgrid(np.arange(FR.width), np.arange(FR.height))
    return FR.left + (jj+0.5)*FR.cell, FR.top - (ii+0.5)*FR.cell
X, Y = cellxy()
tr = pyproj.Transformer.from_crs(C.WEB_MERCATOR, CRS, always_xy=True).transform
UX, UY = tr(X, Y)
inner = pyproj.Transformer.from_crs("EPSG:4326", CRS, always_xy=True).transform
wbox = shp_t(inner, box(x0, y0, x1, y1)); sh = wbox.buffer(-100)
inbox = shapely.contains_xy(sh, UX, UY)
LOC_U = shp_t(inner, LOC)
lake = M["lake"] & inbox; clar = M["clarity"] & inbox
dist = np.full((FR.height, FR.width), np.nan, "float32")
dist[lake] = shapely.distance(shapely.points(UX[lake], UY[lake]), LOC_U.boundary).astype("float32")
ADJ = 35.0; BELT_MAX = 90.0
an = lake & (dist >= ADJ); belt = an & (dist <= BELT_MAX)
NAN16 = -32768
def load(f):
    z = np.load(f, allow_pickle=True); meta = json.loads(str(z["meta"]))
    s = {"transform": rasterio.Affine(*meta["tr"]), "crs": rasterio.crs.CRS.from_string(meta["crs"]), "SCL": z["SCL"]}
    for k in ("B04", "B8A", "B11"):
        a = z[k].astype("float32")*1e-4; a[z[k] == NAN16] = np.nan; s[k] = a
    return s, meta
def proc(f):
    d = f.stem; s, meta = load(f)
    if s["crs"] != CRS: return dict(date=d, error="crs mismatch " + meta["crs"])
    ok, gfrac, readable = C.native_fields(s)
    with np.errstate(invalid="ignore"):
        dark = (s["B04"] < 0.01) & (s["B8A"] < 0.01)
    gf = gfrac.copy(); gf[dark] = np.nan
    seenpx = (~np.isnan(gf)).astype("float32")
    gcell = C.to_grid(gf, s["transform"], s["crs"], FR); seenf = C.to_grid(seenpx, s["transform"], s["crs"], FR)
    rr = np.where(ok, 1.0, np.nan).astype("float32"); gg = C.to_grid(rr, s["transform"], s["crs"], FR); frac = C.to_grid(readable, s["transform"], s["crs"], FR)
    have = ~np.isnan(gg) & (np.nan_to_num(frac) >= C.S2_MIN_CELL_FRAC) & M["lake"]
    seen = (np.nan_to_num(seenf) >= 0.5) & ~np.isnan(gcell)
    veg = (np.nan_to_num(gcell) >= 0.5) & seen & ~have
    votes = (np.nan_to_num(gcell) >= 0.5) & clar & ~have
    den = int((clar & ~votes).sum()); cov = float((have & clar & ~votes).sum())/max(den, 1)
    r = dict(date=d, cov=round(cov, 4), n_an=int(an.sum()), n_belt=int(belt.sum()), seen_an=int((seen & an).sum()), seen_belt=int((seen & belt).sum()),
             veg_an=int((veg & an).sum()), veg_belt=int((veg & belt).sum()), read_an=int((have & an).sum()), src=meta["src"], items=meta["items"])
    return r, (veg & lake), (seen & lake)
if __name__ == "__main__":
    S1 = {p.stem[3:]: json.load(open(p)) for p in cdir.glob("s1_*.json")}
    plan = json.load(open(H/f"out/fetchplan_{lk}.json"))
    with Pool(6) as p: res = p.map(proc, files)
    rows = {}; V = []; SN = []; dv = []
    for r in res:
        if isinstance(r, dict): print("ERR", r); continue
        rec, v, sn = r; rows[rec["date"]] = rec; V.append(v); SN.append(sn); dv.append(rec["date"])
    out = []
    for d in sorted(S1):
        s1 = S1[d]
        if "error" in s1: out.append(dict(date=d, status="ERR")); continue
        rec = dict(date=d, n_px=s1["n"], nodata=round(s1["nodata"], 4), cloud=round(s1["cloud"], 4), shadow=round(s1["shadow"], 4), snow=round(s1["snow"], 4), clear=round(s1["clear"], 4),
                   cloud_tile=min([c for c in s1["cloud_tile"] if c is not None] or [None]) if any(c is not None for c in s1["cloud_tile"]) else None, src=s1["src"])
        if s1["nodata"] >= 0.5: rec["status"] = "NODATA"
        elif s1["snow"] >= 0.30: rec["status"] = "ICE"
        elif s1["clear"] < 0.25: rec["status"] = "CLOUD"
        elif d in rows:
            r = rows[d]; rec.update({k: r[k] for k in ("cov", "n_an", "n_belt", "seen_an", "seen_belt", "veg_an", "veg_belt", "read_an")})
            rec["status"] = "ACCEPTED" if r["cov"] >= 0.5 else ("FALLBACK" if r["cov"] >= 0.25 else "REFUSED")
            if rec["status"] == "ACCEPTED":
                rec["belt_share"] = r["veg_belt"]/r["seen_belt"] if r["seen_belt"] >= 20 else None
                rec["lake_share"] = r["veg_an"]/r["seen_an"] if r["seen_an"] >= 100 else None
        else: rec["status"] = "SKIPPED_SUBSAMPLE"
        out.append(rec)
    with open(H/f"out/scenes_{lk}.jsonl", "w") as f:
        for r in out: f.write(json.dumps(r)+"\n")
    np.savez_compressed(H/f"out/cells_{lk}.npz", V=np.array(V), SN=np.array(SN), dates=np.array(dv), dist=dist, belt=belt, an=an, lake=lake)
    from collections import Counter
    print(lk, "belt cells", int(belt.sum()), "analysis cells", int(an.sum()), Counter(r["status"] for r in out), "bin", plan["bin"])
