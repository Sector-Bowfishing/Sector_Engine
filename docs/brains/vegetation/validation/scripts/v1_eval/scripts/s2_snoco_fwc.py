"""STEP 2a/b: shipped observer on Snohomish polygons (cell P/R/F1/IoU) and FWC LTM points (recall only). usage: s2_snoco_fwc.py FLOOR_TAG(frozen|prov)"""
import sys; sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from v1lib import *
net_guard()
import glob, pickle, warnings; warnings.filterwarnings("ignore")
from multiprocessing import Pool
TAGFLOOR = sys.argv[1] if len(sys.argv) > 1 else "frozen"     # frozen | prov (0.03) ; suffix _nohaze = DIAGNOSTIC ablation (C.HAZE_SWIR=1e9)
FLOOR = frozen_floor() if TAGFLOOR.startswith("frozen") else 0.03
if TAGFLOOR.endswith("_nohaze"): C.HAZE_SWIR = 1e9
SNOCO = {"Lake Serene": "Serene", "Blackmans Lake": "Blackmans", "Storm Lake": "Storm", "Lake Roesiger": "Roesiger", "Lake Bosworth": "Bosworth"}
FWC_IDS = {"Orange": "288216", "Griffin": "305765", "Apopka": "293912", "Harris": "294031", "Panasoffkee": "294114", "Yale": "306620", "Cypress": "281219"}
def polys(tag):
    if tag == "snoco":
        return {SNOCO[f["properties"]["name"]]: shape(f["geometry"]) for f in json.load(open(ROOT / "data/snoco_layer15.geojson"))["features"]}
    L = {f["properties"]["Lake_Id"]: shape(f["geometry"]) for f in json.load(open(ROOT / "data/fwc_ltm_lakes.geojson"))["features"]}
    return {k: L[v] for k, v in FWC_IDS.items()}
_idx = {}
def index(tag):
    if tag in _idx: return _idx[tag]
    d = {}
    for f in glob.glob(str(ROOT / f"out/s2cache/{tag}_*.npz")):
        z = np.load(f, allow_pickle=True)
        d.setdefault((z["B04"].shape, str(z["date"])), []).append(f)
    _idx[tag] = d; return d
def stack_files(tag, nm):
    st = np.load(ROOT / f"out/stack_{tag}_{nm}.npz", allow_pickle=True)
    shp = st["lake"].shape; idx = index(tag); out = []
    for i, d in enumerate([str(x) for x in st["dates"]]):
        fs = idx.get((shp, d), [])
        if len(fs) != 1:
            ok = None; k = list(st["idx"]).index("NDVI_sector")
            for f in fs:
                z = np.load(f, allow_pickle=True); ndv = (z["B8A"] - z["B04"]) / np.maximum(1e-6, z["B8A"] + z["B04"])
                if np.allclose(np.nan_to_num(ndv), np.nan_to_num(st["X"][i, k]), atol=1e-4): ok = f; break
            fs = [ok] if ok else []
        out.append((d, fs[0] if fs else None))
    return st, out

def lake_job(a):
    tag, nm = a
    O.NIR_PLANT_MIN = FLOOR
    poly = polys(tag)[nm]
    st, files = stack_files(tag, nm)
    scenes = []; missing = 0; lake0 = None; iou = None
    for d, f in files:
        if f is None: missing += 1; continue
        z = np.load(f, allow_pickle=True)
        tr = rasterio.Affine(*z["transform"]); crs = rasterio.crs.CRS.from_string(str(z["crs"])); scl = z["SCL"]
        lake = rasterize_lake(poly, crs, tr, scl.shape)
        if lake0 is None:
            lake0 = lake; iou = float((lake & st["lake"]).sum() / max(1, (lake | st["lake"]).sum()))
        c = "sentinel-2-c1-l2a"                                # cached true reflectance -> c1-convention DN -> module's own reflectance()
        sc, fl, nir = make_scene(str(z["id"]), d2(d), c, refl_to_dn(z["B04"], c), refl_to_dn(z["B8A"], c), refl_to_dn(z["B11"], c), scl, lake)
        scenes.append(sc)
    ref = d2(str(st["survey"]))
    res = {}
    for m in ("S", "A", "P"):
        obs = O.observe(scenes, ref, mode=m); res[m] = obs
    sel = O.select_scenes(scenes, ref)
    base = scenes[0].cells
    lab = {k[4:]: block_mean(st[k]) for k in st.files if k.startswith("lab_")}
    dist = cell_center_dist(dist_to_edge_m(lake0))
    info = dict(tag=tag, nm=nm, ref=str(ref), n_scenes_total=len(scenes), n_missing=missing, lake_iou_vs_stack=iou,
                n_inwindow=len(sel["inWindow"]), n_accepted=len(sel["accepted"]), bursts=sel["bursts"],
                gaps=[abs((s.when - ref).days) for s in sel["inWindow"]], cov=[round(s.cells.coverage(), 3) for s in sel["inWindow"]],
                floor=FLOOR, n_interior=int(base.interior.sum()), n_eligible=int(base.eligible.sum()))
    # per-scene guard shares (all in-window scenes) over eligible cells
    gs = {}
    for s in sel["inWindow"]:
        c = s.cells; el = c.eligible
        for code, nmr in O.REASON_NAMES.items():
            k = int(((c.reason == code) & (c.state == O.UNKNOWN) & el).sum())
            if k: gs[nmr] = gs.get(nmr, 0) + k
    info["scene_unknown_cells"] = gs; info["scene_eligible_cells_total"] = int(sum(s.cells.eligible.sum() for s in sel["inWindow"]))
    obsd = {}
    for m, o in res.items():
        pres = O.presence(o)
        obsd[m] = dict(kind=o.evidence_kind, persistence=o.persistence, n_accepted=o.n_accepted, plant_cells=o.plant_cells, read_cells=o.read_cells,
                       interior=o.interior_cells, coverage=o.coverage, isolated_dropped=o.isolated_dropped, shares=o.refusal_shares, notes=o.notes,
                       presence=pres, state=None if o.state is None else o.state.copy(), scene_ids=o.scene_ids, observed_on=str(o.observed_on),
                       fallback=o.low_coverage_fallback)
    return dict(info=info, obs=obsd, lab=lab, dist=dist, eligible=base.eligible, interior=base.interior)

if __name__ == "__main__":
    jobs = [("snoco", n) for n in SNOCO.values()] + [("fwc", n) for n in FWC_IDS]
    with Pool(6) as p: R = p.map(lake_job, jobs, chunksize=1)
    pickle.dump({f"{j[0]}|{j[1]}": r for j, r in zip(jobs, R)}, open(OUT / f"snoco_fwc_{TAGFLOOR}.pkl", "wb"))
    for r in R: print(r["info"]["tag"], r["info"]["nm"], {k: r["info"][k] for k in ("n_inwindow", "n_accepted", "bursts", "lake_iou_vs_stack", "n_interior")}, {m: (r["obs"][m]["kind"], r["obs"][m]["plant_cells"], r["obs"][m]["presence"][0]) for m in "SAP"})
