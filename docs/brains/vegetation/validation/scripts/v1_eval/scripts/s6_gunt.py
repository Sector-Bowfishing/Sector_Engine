"""STEP 4: UNVALIDATED sanity run on Guntersville 2025 scenes from the seasonal cache (5x5 km upper-reach window; the exact central-reach pilot rasters are NOT cached, only derived arrays)."""
import sys; sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from v1lib import *
net_guard()
import warnings; warnings.filterwarnings("ignore")
SEAS = ROOT / "adoption/seasonal"; LK = "Guntersville_AL"
poly = load_poly(SEAS / "geom" / f"{LK}.geojson.gz")
def run(floor, nohaze=False):
    O.NIR_PLANT_MIN = floor; C.HAZE_SWIR = 1e9 if nohaze else 0.02
    scenes = []; lake = None
    for f in sorted((SEAS / "cache" / LK).glob("2025-*.npz")):
        z = np.load(f, allow_pickle=True); meta = json.loads(str(z["meta"])); src = meta["src"][0] if meta["src"] else "l2a"
        coll = "sentinel-2-c1-l2a" if src == "c1" else "sentinel-2-l2a"
        tr = rasterio.Affine(*meta["tr"]); crs = rasterio.crs.CRS.from_string(meta["crs"]); scl = z["SCL"]
        def dn(k):
            a = z[k].astype("int32"); bad = a == -32768
            if coll.endswith("c1-l2a"): a = a + 1000
            a = np.clip(a, 1, 65534).astype("uint16"); a[bad] = 0; return a
        if lake is None: lake = rasterize_lake(poly, crs, tr, scl.shape)
        sc, fl, nir = make_scene(f.stem, d2(f.stem), coll, dn("B04"), dn("B8A"), dn("B11"), scl, lake); scenes.append(sc)
    out = dict(floor=floor, nohaze=nohaze, n_scenes_2025=len(scenes), lake_px=int(lake.sum()), interior_cells=int(scenes[0].cells.interior.sum()), refs={})
    for ref in ("2025-06-15", "2025-07-15", "2025-08-15", "2025-09-15"):
        r = d2(ref); sel = O.select_scenes(scenes, r); rr = dict(n_inwindow=len(sel["inWindow"]), n_accepted=len(sel["accepted"]), bursts=sel["bursts"], cov=[round(s.cells.coverage(), 2) for s in sel["inWindow"]])
        for m in "AP":
            o = O.observe(scenes, r, mode=m); pr = O.presence(o)
            rr[m] = dict(kind=o.evidence_kind, pers=o.persistence, n_acc=o.n_accepted, plant_cells=o.plant_cells, read=o.read_cells, interior=o.interior_cells, presence=pr[0], coverage=round(o.coverage, 3), shares={k: round(v, 3) for k, v in o.refusal_shares.items()}, fallback=o.low_coverage_fallback)
        out["refs"][ref] = rr
    C.HAZE_SWIR = 0.02
    return out
res = [run(frozen_floor()), run(0.03), run(frozen_floor(), True), run(0.03, True)]
json.dump(res, open(OUT / "guntersville_2025.json", "w"), indent=1, default=float)
for r in res:
    print("floor", r["floor"], "nohaze", r["nohaze"], "scenes", r["n_scenes_2025"], "interior cells", r["interior_cells"])
    for ref, rr in r["refs"].items(): print("  ", ref, "inwin", rr["n_inwindow"], "acc", rr["n_accepted"], "| P:", rr["P"]["kind"], rr["P"]["pers"], "plant", rr["P"]["plant_cells"], "read", rr["P"]["read"], "/", rr["P"]["interior"], rr["P"]["presence"], rr["P"]["shares"])
