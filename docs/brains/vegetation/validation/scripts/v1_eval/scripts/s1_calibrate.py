"""STEP 1 (A3): label-free NIR floor calibration. Hartwell SC/GA + Leech Lake MN from the seasonal caches.
NIR_PLANT_MIN = max(0.03, 99.5th pct of B8A over SCL-water pixels >=100 m from polygon edge, ACCEPTED scenes only), rounded UP to 0.005.
Acceptance uses the shipped observer at the provisional floor 0.03 (coverage >= 0.5). No truth label used. Writes out/calibration.json."""
import sys; sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from v1lib import *
net_guard()
import math, warnings; warnings.filterwarnings("ignore")
from multiprocessing import Pool
SEAS = ROOT / "adoption/seasonal"
LAKES = ["Lake_Hartwell_SC", "Leech_Lake_MN"]
NB = 12001   # DN histogram of true reflectance: bin i = reflectance (i-1000)*1e-4

def work(args):
    lk, f = args
    O.NIR_PLANT_MIN = 0.03
    z = np.load(f, allow_pickle=True); meta = json.loads(str(z["meta"]))
    src = meta["src"][0] if meta["src"] else "l2a"
    coll = "sentinel-2-c1-l2a" if src == "c1" else "sentinel-2-l2a"
    tr = rasterio.Affine(*meta["tr"]); crs = rasterio.crs.CRS.from_string(meta["crs"])
    def dn(k):
        a = z[k].astype("int32"); bad = a == -32768
        if coll == "sentinel-2-c1-l2a": a = a + 1000
        a = np.clip(a, 1, 65534).astype("uint16"); a[bad] = 0; return a
    scl = z["SCL"]
    lake = rasterize_lake(POLY[lk], crs, tr, scl.shape)
    if not lake.any(): return lk, f.stem, None
    sc, fl, nir = make_scene(f.stem, d2(f.stem), coll, dn("B04"), dn("B8A"), dn("B11"), scl, lake)
    cov = sc.cells.coverage(); acc = cov >= C.PASS_MIN_COVERAGE
    out = dict(lk=lk, date=f.stem, cov=cov, acc=bool(acc), coll=coll)
    if acc:
        d = dist_to_edge_m(lake)
        m = lake & (scl == C.SCL_WATER) & (d >= 100.0) & np.isfinite(nir)
        m2 = m & fl.seen          # variant: only pixels the observer itself "saw" (not cloud/haze blocked)
        m3 = m & ~fl.plant        # variant: also exclude plant-spectrum pixels
        def hist(mm):
            idx = np.clip(np.round(nir[mm] / 1e-4).astype(np.int64) + 1000, 0, NB - 1)
            return np.bincount(idx, minlength=NB).astype(np.int64)
        out.update(h=hist(m), h_seen=hist(m2), n=int(m.sum()))
    return lk, f.stem, out

POLY = {lk: load_poly(SEAS / "geom" / f"{lk}.geojson.gz") for lk in LAKES}
if __name__ == "__main__":
    jobs = [(lk, f) for lk in LAKES for f in sorted((SEAS / "cache" / lk).glob("2*.npz"))]
    with Pool(6) as p: res = p.map(work, jobs, chunksize=8)
    def pct(h, q):
        c = np.cumsum(h); k = int(np.searchsorted(c, q * c[-1])); return (k - 1000) * 1e-4
    summ = {}
    H = {k: np.zeros(NB, np.int64) for k in ("all", "all_seen") + tuple(LAKES)}
    ns = {lk: dict(scenes=0, accepted=0) for lk in LAKES}
    for lk, st, o in res:
        if o is None: continue
        ns[lk]["scenes"] += 1
        if o["acc"]:
            ns[lk]["accepted"] += 1; H[lk] += o["h"]; H["all"] += o["h"]; H["all_seen"] += o["h_seen"]
    q = 0.995
    p_all = pct(H["all"], q)
    floor = max(0.03, math.ceil(p_all / 0.005 - 1e-9) * 0.005)
    out = dict(rule="NIR_PLANT_MIN = max(0.03, ceil_to_0.005(P99.5 of B8A over SCL-water >=100 m from edge, accepted scenes)); accepted = shipped-observer coverage >= 0.5 at provisional floor 0.03",
               percentile_all=p_all, NIR_PLANT_MIN=round(floor, 3),
               per_lake={lk: dict(p995=pct(H[lk], q), p99=pct(H[lk], .99), p50=pct(H[lk], .5), n_pixels=int(H[lk].sum()), **ns[lk]) for lk in LAKES},
               sensitivity_seen_pixels_only_p995=pct(H["all_seen"], q), n_pixels_pooled=int(H["all"].sum()),
               n_scenes_total=sum(v["scenes"] for v in ns.values()), n_accepted=sum(v["accepted"] for v in ns.values()),
               frozen_at=dt.datetime.now().isoformat(timespec="seconds"), network_bytes=0)
    json.dump(out, open(OUT / "calibration.json", "w"), indent=1)
    print(json.dumps(out, indent=1))
