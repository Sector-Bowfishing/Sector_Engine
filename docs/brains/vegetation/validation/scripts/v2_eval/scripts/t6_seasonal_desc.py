"""DESCRIPTIVE (not gate evidence): adaptive-floor / BLOOM_AMBIGUOUS behaviour on every cached scene of the seasonal-backtest caches (Hartwell, Leech, Guntersville + Pepin/others if cached). Frozen pair; no labels."""
from v2jobs import *
import pickle
from multiprocessing import Pool
install_guard()
fz = load_frozen(); PAIR = (fz["haze_swir"], fz["haze_standoff_px"])
LAKES = ["Lake_Hartwell_SC", "Leech_Lake_MN", "Guntersville_AL"]
def work(a):
    lk, f = a
    z = np.load(f, allow_pickle=True); meta = json.loads(str(z["meta"]))
    src = meta["src"][0] if meta["src"] else "l2a"; coll = "sentinel-2-c1-l2a" if src == "c1" else "sentinel-2-l2a"
    tr = rasterio.Affine(*meta["tr"]); crs = rasterio.crs.CRS.from_string(meta["crs"])
    def dn(k):
        a_ = z[k].astype("int32"); bad = a_ == -32768
        if coll == "sentinel-2-c1-l2a": a_ = a_ + 1000
        a_ = np.clip(a_, 1, 65534).astype("uint16"); a_[bad] = 0; return a_
    scl = z["SCL"]; lake = rasterize_lake(POLY[lk], crs, tr, scl.shape)
    if not lake.any(): return None
    sc, dg = make_scene2(f.stem, d2(f.stem), coll, dn("B04"), dn("B8A"), dn("B11"), scl, lake, *PAIR)
    dg["lake"] = lk; dg["coll"] = coll; dg["n_snow"] = int(((scl == C.SCL_SNOW) & lake).sum()); dg["lake_px"] = int(lake.sum()); dg["cloud_frac"] = float((np.isin(scl, (3, 8, 9, 10)) & lake).sum() / max(1, lake.sum()))
    return dg
POLY = {lk: load_poly(SEAS / "geom" / f"{lk}.geojson.gz") for lk in LAKES}
if __name__ == "__main__":
    jobs = [(lk, f) for lk in LAKES for f in sorted((SEAS / "cache" / lk).glob("2*.npz"))]
    with Pool(8) as p: res = [r for r in p.map(work, jobs, chunksize=4) if r]
    pickle.dump(res, open(OUT2 / "desc_seasonal.pkl", "wb")); print(len(res))
