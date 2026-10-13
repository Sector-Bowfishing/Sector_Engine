"""DESCRIPTIVE: lake cloud fraction (SCL 3/8/9/10) per NLA 2017 in-window scene vs the adaptive-floor / BLOOM_AMBIGUOUS flag (frozen pair). No labels, no scoring."""
from v2jobs import *
import pickle
from multiprocessing import Pool
install_guard()
fz = load_frozen(); PAIR = (fz["haze_swir"], fz["haze_standoff_px"])
CLS = pd.read_csv(NLA / "out/nla_lake_classes.csv").set_index("lakeKey")
def job(k):
    ref = dt.date.fromisoformat(CLS.loc[k, "visit_dates"].split(";")[0]); fb = files_by_date(k)
    dates = sorted(d for d in fb if abs((dt.date.fromisoformat(d) - ref).days) <= 21)
    if not dates: return []
    poly = load_poly(NLA / f"data/geom/{k}.geojson.gz"); cv = canvas_for({d: fb[d] for d in dates}); out = []; lake = None
    for d in dates:
        dn, scl, tr, crs, coll, ids = read_mosaic(fb[d], cv)
        if (scl > 0).sum() == 0: continue
        if lake is None: lake = rasterize_lake(poly, crs, tr, scl.shape)
        sc, dg = make_scene2(k + d, dt.date.fromisoformat(d), coll, dn["red"], dn["nir"], dn["swir"], scl, lake, *PAIR)
        dg["lake"] = k; dg["cloud_frac"] = float((np.isin(scl, (3, 8, 9, 10)) & lake).sum() / max(1, lake.sum())); dg["cirrus_frac"] = float(((scl == 10) & lake).sum() / max(1, lake.sum())); out.append(dg)
    return out
if __name__ == "__main__":
    keys = [k for k in CLS.index[CLS.n_stations > 0] if k != "Lake_Mead_NV"]
    with Pool(8) as p: r = p.map(job, keys, chunksize=1)
    pickle.dump([d for x in r for d in x], open(OUT2 / "desc_nla_cloud.pkl", "wb")); print(sum(len(x) for x in r))
