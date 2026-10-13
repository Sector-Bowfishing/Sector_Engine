"""Lake-level S2 summaries for FWC lake-years that have sonar-derived PAC/PVI (layer 41).
Per lake-year: up to 2 clear scenes within +-21 d of the survey median; lean uint16 DN cache; Sector cell-level grass fraction + pixel summaries.
Resume-safe: out/pac/{lakeid}_{year}.json. Usage: 20_pac_extract.py [workers]"""
import sys, json, datetime as dt, hashlib, numpy as np, rasterio, warnings, traceback
warnings.filterwarnings("ignore")
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from rasterio.windows import from_bounds
from rasterio.warp import transform_bounds
from shapely.geometry import shape
ROOT = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT/"scripts"))
import s2lib, cell_lib as C
CACHE = ROOT/"out/s2cache_pac"; OUT = ROOT/"out/pac"
B = {"B02":"blue","B03":"green","B04":"red","B08":"nir","B8A":"nir08","B11":"swir16"}
L = {f["properties"]["Lake_Id"]: shape(f["geometry"]) for f in json.load(open(ROOT/"data/fwc_ltm_lakes.geojson"))["features"]}
LY = [o for o in json.load(open(ROOT/"data/pac_lakeyears.json")) if o["lake"] != "Okeechobee"]

def read_lean(item, bbox, lid):
    f = CACHE/f"{lid}_{item.id}.npz"
    if f.exists():
        z = np.load(f, allow_pickle=True); return {k: z[k] for k in z.files if k not in ("transform","crs","off")} | {"transform": rasterio.Affine(*z["transform"]), "crs": rasterio.crs.CRS.from_string(str(z["crs"])), "off": float(z["off"])}
    off = -0.1 if item.collection_id == "sentinel-2-c1-l2a" else 0.0
    with rasterio.Env(**s2lib.ENV):
        red = rasterio.open(s2lib.http(item.assets["red"].href)); crs = red.crs
        l, b, r, t = transform_bounds("EPSG:4326", crs, *bbox)
        win = from_bounds(l, b, r, t, red.transform).round_offsets().round_lengths(); tr = red.window_transform(win); H, W = int(win.height), int(win.width)
        out = {}
        for bn, an in B.items():
            src = rasterio.open(s2lib.http(item.assets[an].href))
            w_ = from_bounds(*rasterio.windows.bounds(win, red.transform), src.transform)
            out[bn] = src.read(1, window=w_, out_shape=(H, W), resampling=rasterio.enums.Resampling.nearest, boundless=True, fill_value=0).astype("uint16")
        ss = rasterio.open(s2lib.http(item.assets["scl"].href))
        out["SCL"] = ss.read(1, window=from_bounds(*rasterio.windows.bounds(win, red.transform), ss.transform), out_shape=(H, W), resampling=rasterio.enums.Resampling.nearest, boundless=True, fill_value=0).astype("uint8")
    np.savez_compressed(f, **out, transform=np.array(tr)[:6], crs=str(crs), off=off, date=item.datetime.date().isoformat())
    out["transform"] = tr; out["crs"] = crs; out["off"] = off; return out

def to_refl(s):
    r = {}
    for bn in B:
        a = s[bn]; v = a.astype("float32") * 1e-4 + s["off"]; v[a == 0] = np.nan; r[bn] = v
    r["SCL"] = s["SCL"]; r["transform"] = s["transform"]; r["crs"] = s["crs"]; return r

def work(o):
    key = f'{o["lake_id"]}_{o["year"]}_{o["PAC"]}_{o["PVI"]}'
    fo = OUT/f"{key}.json"
    if fo.exists(): return key, "cached"
    try:
        g = L[o["lake_id"]]; b = g.bounds; m = 0.002; bbox = (b[0]-m, b[1]-m, b[2]+m, b[3]+m)
        sv = dt.date.fromisoformat(o["survey_med"])
        items = s2lib.dedupe_by_date(s2lib.search(bbox, (sv - dt.timedelta(days=21)).isoformat(), (sv + dt.timedelta(days=21)).isoformat(), 50))
        items = sorted(items, key=lambda i: abs((i.datetime.date() - sv).days))
        fr = C.Frame(g); recs = []
        for it in items[:6]:
            if len(recs) >= 2: break
            try: s = to_refl(read_lean(it, bbox, o["lake_id"]))
            except Exception as e: continue
            if s["B04"].size == 0: continue
            msk = C.lake_masks(g, fr, s["crs"])
            gcell, have = C.scene_cells(s, fr, msk["lake"])
            seen = ~np.isnan(gcell); cl = msk["clarity"]
            clear_frac = float((seen & msk["lake"]).sum() / max(1, msk["lake"].sum()))
            if clear_frac < 0.75: continue
            vote = C.grass_vote(gcell, have, cl)
            cov = float((have & cl & ~vote).sum() / max(1, (cl & ~vote).sum()))
            # pixel summaries on lake pixels >= 40 m from shore (same erosion as Sector's clarity mask), SCL not cloud
            from rasterio.features import rasterize
            lake_px = rasterize([(C.to_crs(g, "EPSG:4326", s["crs"].to_string()).buffer(-40), 1)], out_shape=s["B04"].shape, transform=s["transform"], fill=0, dtype="uint8").astype(bool)
            ok = lake_px & ~np.isin(s["SCL"], list(s2lib.SCL_BAD)) & np.isfinite(s["B04"]) & np.isfinite(s["B8A"])
            with np.errstate(invalid="ignore", divide="ignore"):
                nd = lambda a, b_: (a - b_) / np.maximum(a + b_, 0.01)
                ndvi_s = (s["B8A"] - s["B04"]) / np.maximum(1e-6, s["B8A"] + s["B04"])
                fai = s["B8A"] - (s["B04"] + (s["B11"] - s["B04"]) * (865 - 665) / (1610 - 665))
                ndvi = nd(s["B08"], s["B04"]); ndavi = nd(s["B08"], s["B02"])
            q = lambda a, p: float(np.nanpercentile(a[ok], p)) if ok.sum() > 100 else None
            recs.append(dict(date=s["B04"].shape and str(np.load(CACHE/f"{o['lake_id']}_{it.id}.npz", allow_pickle=True)["date"]), dt=(it.datetime.date() - sv).days, clear=round(clear_frac, 3), cov=round(cov, 3),
                 cell_grass_frac_lake=float(vote.sum() / max(1, msk["lake"].sum())), cell_grass_frac_clarity=float(vote.sum() / max(1, cl.sum())),
                 px_ndvi_sector_ge30=float((ndvi_s[ok] >= 0.30).mean()) if ok.sum() > 100 else None, px_fai_gt005=float((fai[ok] > 0.005).mean()) if ok.sum() > 100 else None,
                 NDVI_q50=q(ndvi, 50), NDVI_q90=q(ndvi, 90), NDVI_q99=q(ndvi, 99), NDAVI_q90=q(ndavi, 90), FAI_q90=q(fai, 90), FAI_q99=q(fai, 99),
                 NIR_q90=q(s["B08"], 90), SWIR_q50=q(s["B11"], 50), n_lake_px=int(ok.sum()), n_cells=int(msk["lake"].sum()), collection=it.collection_id))
        json.dump(dict(meta=o, scenes=recs), open(fo, "w"))
        return key, f"{len(recs)} scenes"
    except Exception as e:
        return key, "ERR " + repr(e) + traceback.format_exc()[-300:]

if __name__ == "__main__":
    nw = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    LY = sorted(LY, key=lambda o: o["km2"])
    with ThreadPoolExecutor(nw) as ex:
        for k, st in ex.map(work, LY): print(k, st, flush=True)
