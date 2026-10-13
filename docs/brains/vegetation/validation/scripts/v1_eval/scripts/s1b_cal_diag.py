"""Post-hoc diagnostic of WHY the A3 percentile is high (does not change the frozen floor)."""
import sys; sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from v1lib import *
net_guard()
import warnings; warnings.filterwarnings("ignore")
from multiprocessing import Pool
import s1_calibrate as S
def w(a):
    lk, f = a; O.NIR_PLANT_MIN = 0.03
    z = np.load(f, allow_pickle=True); meta = json.loads(str(z["meta"])); src = meta["src"][0] if meta["src"] else "l2a"
    coll = "sentinel-2-c1-l2a" if src == "c1" else "sentinel-2-l2a"
    tr = rasterio.Affine(*meta["tr"]); crs = rasterio.crs.CRS.from_string(meta["crs"]); scl = z["SCL"]
    def dn(k):
        a_ = z[k].astype("int32"); bad = a_ == -32768
        if coll.endswith("c1-l2a"): a_ = a_ + 1000
        a_ = np.clip(a_, 1, 65534).astype("uint16"); a_[bad] = 0; return a_
    lake = rasterize_lake(S.POLY[lk], crs, tr, scl.shape)
    sc, fl, nir = make_scene(f.stem, d2(f.stem), coll, dn("B04"), dn("B8A"), dn("B11"), scl, lake)
    if sc.cells.coverage() < 0.5: return None
    m = lake & (scl == 6) & (dist_to_edge_m(lake) >= 100) & np.isfinite(nir)
    if m.sum() < 1000: return None
    v = nir[m]
    sw = O.reflectance(dn("B11"), coll)[m]
    return lk, f.stem, float(np.percentile(v, 99.5)), float(np.median(v)), float(np.percentile(sw, 50)), int(m.sum())
if __name__ == "__main__":
    jobs = [(lk, f) for lk in S.LAKES for f in sorted((S.SEAS / "cache" / lk).glob("2*.npz"))]
    with Pool(6) as p: r = [x for x in p.map(w, jobs, chunksize=8) if x]
    import collections
    for lk in S.LAKES:
        rr = [x for x in r if x[0] == lk]; p = np.array([x[2] for x in rr])
        print(lk, "accepted scenes", len(rr), "per-scene P99.5 quantiles(10/50/90/max):", np.round(np.percentile(p, [10, 50, 90, 100]), 3), "share scenes P99.5>0.10:", round(float((p > 0.10).mean()), 2))
        bym = collections.defaultdict(list)
        for x in rr: bym[int(x[1][5:7])].append(x[2])
        print("  by month median(per-scene P99.5):", {m: (round(float(np.median(v)), 3), len(v)) for m, v in sorted(bym.items())})
        hi = sorted(rr, key=lambda x: -x[2])[:6]; print("  top scenes:", [(x[1], round(x[2], 3), round(x[4], 3)) for x in hi])
