"""STEP 2c/d: shipped observer on NLA 2017 eligible lakes (primary, +-21 d of visit, collection l2a) and the labelled 2018/2019 secondary.
usage: s4_nla.py TAG [primary|secondary|both] [lakeKey ...]   TAG: frozen | prov | frozen_nohaze | prov_nohaze (suffix = DIAGNOSTIC ablation)"""
import sys; sys.path.insert(0, str(__import__("pathlib").Path(__file__).parent))
from v1lib import *
net_guard()
import glob, re, pickle, warnings, pandas as pd; warnings.filterwarnings("ignore")
from multiprocessing import Pool
TAG = sys.argv[1]; MODE = sys.argv[2] if len(sys.argv) > 2 else "primary"; ONLY = sys.argv[3:]
FLOOR = frozen_floor() if TAG.startswith("frozen") else 0.03
if TAG.endswith("_nohaze"): C.HAZE_SWIR = 1e9
NLA = ROOT / "adoption/nla"
CLS = pd.read_csv(NLA / "out/nla_lake_classes.csv").set_index("lakeKey")
MIN_BELT = 10; BELT = (10.0, 90.0)

def files_by_date(key):
    d = {}
    for f in sorted(glob.glob(str(NLA / f"out/s2cache_nla/{key}_S2*.npz"))):
        m = re.search(r"_(\d{8})_\d+_L2A\.npz$", f) or re.search(r"_(\d{8})T", f)
        if not m: continue
        s = m.group(1); d.setdefault(f"{s[:4]}-{s[4:6]}-{s[6:]}", []).append(f)
    return d

def canvas_for(fbd):
    """common 10 m canvas for ALL dates of a lake: union of tile windows in the dominant CRS."""
    info = []
    for d, fs in fbd.items():
        for f in fs:
            z = np.load(f, allow_pickle=True); meta = json.loads(str(z["meta"])); tr = rasterio.Affine(*meta["tr"]); h, w = z["scl"].shape
            info.append((meta["crs"], tr, h, w))
    cnt = {}
    for c, *_ in info: cnt[c] = cnt.get(c, 0) + 1
    crs = max(cnt, key=cnt.get); g = [i for i in info if i[0] == crs]
    x0 = min(t.c for _, t, _, _ in g); y0 = max(t.f for _, t, _, _ in g)
    x1 = max(t.c + 10 * w for _, t, h, w in g); y1 = min(t.f - 10 * h for _, t, h, w in g)
    return dict(x0=x0, y0=y0, W=int(round((x1 - x0) / 10)), H=int(round((y0 - y1) / 10)), crs=crs)

def read_mosaic(fs, cv):
    """tiles of one date in the canvas CRS pasted onto the lake canvas (first tile wins where it has data)."""
    out = {k: np.zeros((cv["H"], cv["W"]), np.uint16) for k in ("red", "nir", "swir")}; scl = np.zeros((cv["H"], cv["W"]), np.uint8); colls = set(); ids = []
    for f in fs:
        z = np.load(f, allow_pickle=True); meta = json.loads(str(z["meta"]))
        if meta["crs"] != cv["crs"]: continue
        tr = rasterio.Affine(*meta["tr"]); c0 = int(round((tr.c - cv["x0"]) / 10)); r0 = int(round((cv["y0"] - tr.f) / 10)); h, w = z["scl"].shape
        sub = scl[r0:r0 + h, c0:c0 + w]; fill = (sub == 0)
        for k, kk in (("red", "red"), ("nir", "nir08"), ("swir", "swir16")):
            s_ = out[k][r0:r0 + h, c0:c0 + w]; s_[fill] = z[kk][fill]
        sub[fill] = z["scl"][fill]; colls.add(meta["coll"]); ids.append(os.path.basename(f))
    return out, scl, rasterio.Affine(10.0, 0, cv["x0"], 0, -10.0, cv["y0"]), rasterio.crs.CRS.from_string(cv["crs"]), (sorted(colls)[0] if colls else None), ids

def band_stats(obs, lake_cd):
    """belt = interior cells with centre distance in (10, 90] m ; share = flagged / read."""
    c = obs.cells; st = obs.state
    if c is None or st is None: return None
    def stat(lo, hi):
        m = c.interior & (lake_cd > lo) & (lake_cd <= hi)
        read = m & (st != O.UNKNOWN); pl = m & (st == O.PLANT)
        return int(pl.sum()), int(read.sum()), int(m.sum())
    out = {}
    for nm, (lo, hi) in dict(belt=BELT, b1=(10, 30), b2=(30, 60), b3=(60, 90), b40=(40, 90), lake=(10, 1e9)).items():
        p, r, n = stat(lo, hi); out[nm + "_plant"], out[nm + "_read"], out[nm + "_cells"] = p, r, n
    return out

def job(a):
    key, tag, ref = a
    O.NIR_PLANT_MIN = FLOOR
    ref = dt.date.fromisoformat(ref)
    fb = files_by_date(key)
    lo, hi = ref - dt.timedelta(21), ref + dt.timedelta(21)
    dates = sorted(d for d in fb if lo <= dt.date.fromisoformat(d) <= hi)
    poly = load_poly(NLA / f"data/geom/{key}.geojson.gz")
    scenes = []; lake = None; cd = None; errs = []
    cv = canvas_for({d: fb[d] for d in dates}) if dates else None
    for d in dates:
        try:
            dn, scl, tr, crs, coll, ids = read_mosaic(fb[d], cv)
            if (scl > 0).sum() == 0: continue
            if lake is None:
                lake = rasterize_lake(poly, crs, tr, scl.shape)
                if not lake.any(): errs.append("EMPTY_LAKE_MASK"); break
                cd = cell_center_dist(dist_to_edge_m(lake))
            sc, fl, nir = make_scene(f"{key}|{d}|{ids[0]}", dt.date.fromisoformat(d), coll, dn["red"], dn["nir"], dn["swir"], scl, lake)
            scenes.append(sc)
        except Exception as e:
            errs.append(f"{d}: {e!r}"[:200])
    row = dict(lakeKey=key, tag=tag, ref=str(ref), floor=FLOOR, n_scene_dates_cached=len(dates), n_scenes_ok=len(scenes), errs=errs, collections=sorted({s.collection for s in scenes}))
    if not scenes: row["why"] = "NO_SCENE"; return row
    sel = O.select_scenes(scenes, ref)
    row.update(n_inwindow=len(sel["inWindow"]), n_accepted=len(sel["accepted"]), bursts=sel["bursts"], cov=[round(s.cells.coverage(), 3) for s in sel["inWindow"]],
               gaps=[abs((s.when - ref).days) for s in sel["inWindow"]], n_interior=int(scenes[0].cells.interior.sum()), n_eligible=int(scenes[0].cells.eligible.sum()))
    gs = {}
    for s in sel["inWindow"]:
        c = s.cells
        for code, nmr in O.REASON_NAMES.items():
            k = int(((c.reason == code) & (c.state == O.UNKNOWN) & c.eligible).sum())
            if k: gs[nmr] = gs.get(nmr, 0) + k
    row["scene_unknown_cells"] = gs; row["scene_eligible_cells_total"] = int(sum(s.cells.eligible.sum() for s in sel["inWindow"]))
    for m in ("S", "A", "P"):
        o = O.observe(scenes, ref, mode=m); pres = O.presence(o); b = band_stats(o, cd)
        r = dict(kind=o.evidence_kind, persistence=o.persistence, n_acc=o.n_accepted, coverage=o.coverage, plant_cells=o.plant_cells, read_cells=o.read_cells, interior_cells=o.interior_cells,
                 presence=pres[0], presence_reason=pres[1], shares=o.refusal_shares, notes=o.notes, fallback=o.low_coverage_fallback, observed_on=str(o.observed_on),
                 gap=abs((o.observed_on - ref).days) if o.observed_on else None, scene_ids=o.scene_ids)
        if b: r.update(b); r["belt_share"] = b["belt_plant"] / b["belt_read"] if b["belt_read"] >= MIN_BELT else float("nan"); r["why"] = None if b["belt_read"] >= MIN_BELT else "BELT_TOO_SMALL"
        else: r["why"] = next(iter(o.refusal_shares), "NONE")
        row[m] = r
    return row

if __name__ == "__main__":
    keys = [k for k in CLS.index[CLS.n_stations > 0] if (not ONLY or k in ONLY)]
    jobs = []
    for k in keys:
        ref0 = dt.date.fromisoformat(CLS.loc[k, "visit_dates"].split(";")[0])
        if k == "Lake_Mead_NV": continue
        if MODE in ("primary", "both"): jobs.append((k, "p2017", str(ref0)))
        if MODE in ("secondary", "both"):
            for y in (2018, 2019):
                try: an = ref0.replace(year=y)
                except ValueError: an = ref0.replace(year=y, day=28)
                jobs.append((k, f"s{y}", str(an)))
    with Pool(int(os.environ.get("NPROC", 5))) as p: rows = p.map(job, jobs, chunksize=1)
    json.dump(rows, open(OUT / f"nla_{TAG}_{MODE}{'_' + '_'.join(ONLY) if ONLY else ''}.json", "w"), default=float)
    for r in rows: print(r["lakeKey"], r["tag"], r.get("n_inwindow"), r.get("n_accepted"), {m: (r[m]["kind"], r[m].get("belt_share"), r[m]["presence"]) for m in "AP" if m in r} if "A" in r else r.get("why"), flush=True)
