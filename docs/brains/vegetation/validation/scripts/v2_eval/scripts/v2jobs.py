"""Workers: shipped observer v0.2 on Snohomish / FWC (cached stacks) and NLA (cached tiles), looping over (haze_swir, haze_standoff_px) settings.
Raw scene arrays are read once per lake and reused for every setting."""
from v2lib import *
import glob, re, hashlib, warnings
warnings.filterwarnings("ignore")

SNOCO = {"Lake Serene": "Serene", "Blackmans Lake": "Blackmans", "Storm Lake": "Storm", "Lake Roesiger": "Roesiger", "Lake Bosworth": "Bosworth"}
FWC_IDS = {"Orange": "288216", "Griffin": "305765", "Apopka": "293912", "Harris": "294031", "Panasoffkee": "294114", "Yale": "306620", "Cypress": "281219"}
DEV_SNOCO = ["Roesiger", "Serene"]; TEST_SNOCO = ["Bosworth", "Blackmans", "Storm"]

# ------------------------------------------------------------------------- NLA split
def nla_split():
    reg = json.load(open(EXP.parent / "registry/lakes.v1.json"))["lakes"]
    m = {l["lakeKey"]: l["lakeId"] for l in reg}
    c = pd.read_csv(NLA / "out/nla_lake_classes.csv"); c = c[c.n_stations > 0].copy()
    c["lakeId"] = c.lakeKey.map(m)
    c["hash_byte0"] = c.lakeId.map(lambda s: hashlib.sha256(s.encode()).digest()[0])
    c["split"] = np.where(c.hash_byte0 % 2 == 0, "DEV", "TEST")
    return c[["lakeKey", "lakeId", "hash_byte0", "split", "cls", "epa_reg", "state", "name"]].reset_index(drop=True)

# ------------------------------------------------------------------------- Snohomish / FWC
def _polys(tag):
    if tag == "snoco":
        return {SNOCO[f["properties"]["name"]]: shape(f["geometry"]) for f in json.load(open(EXP / "data/snoco_layer15.geojson"))["features"]}
    L = {f["properties"]["Lake_Id"]: shape(f["geometry"]) for f in json.load(open(EXP / "data/fwc_ltm_lakes.geojson"))["features"]}
    return {k: L[v] for k, v in FWC_IDS.items()}

_idx = {}
def _index(tag):
    if tag in _idx: return _idx[tag]
    d = {}
    for f in glob.glob(str(EXP / f"out/s2cache/{tag}_*.npz")):
        z = np.load(f, allow_pickle=True)
        d.setdefault((z["B04"].shape, str(z["date"])), []).append(f)
    _idx[tag] = d; return d

def _stack_files(tag, nm):
    st = np.load(EXP / f"out/stack_{tag}_{nm}.npz", allow_pickle=True)
    shp = st["lake"].shape; idx = _index(tag); out = []
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

def snoco_fwc_job(a):
    """a = (tag, nm, settings[list of (hs,hp)], modes str, keep_state)"""
    tag, nm, settings, modes = a[:4]
    poly = _polys(tag)[nm]
    st, files = _stack_files(tag, nm)
    raws = []; missing = 0; lake0 = None; iou = None
    c = "sentinel-2-c1-l2a"
    for d, f in files:
        if f is None: missing += 1; continue
        z = np.load(f, allow_pickle=True)
        tr = rasterio.Affine(*z["transform"]); crs = rasterio.crs.CRS.from_string(str(z["crs"])); scl = z["SCL"]
        lake = rasterize_lake(poly, crs, tr, scl.shape)
        if lake0 is None:
            lake0 = lake; iou = float((lake & st["lake"]).sum() / max(1, (lake | st["lake"]).sum()))
        raws.append((str(z["id"]), d2(d), refl_to_dn(z["B04"], c), refl_to_dn(z["B8A"], c), refl_to_dn(z["B11"], c), scl, lake))
    ref = d2(str(st["survey"]))
    lab = {k[4:]: block_mean(st[k]) for k in st.files if k.startswith("lab_")}
    dist = cell_center_dist(dist_to_edge_m(lake0))
    runs = {}
    base = None
    for (hs, hp) in settings:
        scenes = []; diags = []
        for sid, when, r, n, s, scl, lake in raws:
            sc, dg = make_scene2(sid, when, c, r, n, s, scl, lake, hs, hp); scenes.append(sc); diags.append(dg)
        base = scenes[0].cells
        rec = dict(sel=sel_record(scenes, ref), scene_diag=diags, obs={m: obs_record(O.observe(scenes, ref, mode=m)) for m in modes})
        runs[pair_key(hs, hp)] = rec
    info = dict(tag=tag, nm=nm, ref=str(ref), n_scenes_total=len(raws), n_missing=missing, lake_iou_vs_stack=iou, n_interior=int(base.interior.sum()), n_eligible=int(base.eligible.sum()))
    return dict(info=info, runs=runs, lab=lab, dist=dist, eligible=base.eligible, interior=base.interior)

# ------------------------------------------------------------------------- NLA
BELT = (10.0, 90.0); MIN_BELT = 10

def files_by_date(key):
    d = {}
    for f in sorted(glob.glob(str(NLA / f"out/s2cache_nla/{key}_S2*.npz"))):
        m = re.search(r"_(\d{8})_\d+_L2A\.npz$", f) or re.search(r"_(\d{8})T", f)
        if not m: continue
        s = m.group(1); d.setdefault(f"{s[:4]}-{s[4:6]}-{s[6:]}", []).append(f)
    return d

def canvas_for(fbd):
    info = []
    for d, fs in fbd.items():
        for f in fs:
            z = np.load(f, allow_pickle=True); meta = json.loads(str(z["meta"])); tr = rasterio.Affine(*meta["tr"]); h, w = z["scl"].shape
            info.append((meta["crs"], tr, h, w))
    cnt = {}
    for c_, *_ in info: cnt[c_] = cnt.get(c_, 0) + 1
    crs = max(cnt, key=cnt.get); g = [i for i in info if i[0] == crs]
    x0 = min(t.c for _, t, _, _ in g); y0 = max(t.f for _, t, _, _ in g)
    x1 = max(t.c + 10 * w for _, t, h, w in g); y1 = min(t.f - 10 * h for _, t, h, w in g)
    return dict(x0=x0, y0=y0, W=int(round((x1 - x0) / 10)), H=int(round((y0 - y1) / 10)), crs=crs)

def read_mosaic(fs, cv):
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
    c = obs.cells; st = obs.state
    if c is None or st is None: return None
    out = {}
    for nm, (lo, hi) in dict(belt=BELT, b1=(10, 30), b2=(30, 60), b3=(60, 90), b40=(40, 90), lake=(10, 1e9)).items():
        m = c.interior & (lake_cd > lo) & (lake_cd <= hi)
        read = m & (st != O.UNKNOWN); pl = m & (st == O.PLANT)
        out[nm + "_plant"], out[nm + "_read"], out[nm + "_cells"] = int(pl.sum()), int(read.sum()), int(m.sum())
    return out

def nla_job(a):
    """a = (key, tag, ref_iso, settings, modes)"""
    key, tag, ref, settings, modes = a
    ref = dt.date.fromisoformat(ref)
    fb = files_by_date(key)
    lo, hi = ref - dt.timedelta(21), ref + dt.timedelta(21)
    dates = sorted(d for d in fb if lo <= dt.date.fromisoformat(d) <= hi)
    poly = load_poly(NLA / f"data/geom/{key}.geojson.gz")
    raws = []; lake = None; cd = None; errs = []
    cv = canvas_for({d: fb[d] for d in dates}) if dates else None
    for d in dates:
        try:
            dn, scl, tr, crs, coll, ids = read_mosaic(fb[d], cv)
            if (scl > 0).sum() == 0: continue
            if lake is None:
                lake = rasterize_lake(poly, crs, tr, scl.shape)
                if not lake.any(): errs.append("EMPTY_LAKE_MASK"); break
                cd = cell_center_dist(dist_to_edge_m(lake))
            raws.append((f"{key}|{d}|{ids[0]}", dt.date.fromisoformat(d), coll, dn["red"], dn["nir"], dn["swir"], scl))
        except Exception as e:
            errs.append(f"{d}: {e!r}"[:200])
    row = dict(lakeKey=key, tag=tag, ref=str(ref), n_scene_dates_cached=len(dates), n_scenes_ok=len(raws), errs=errs, collections=sorted({r[2] for r in raws}), runs={})
    if not raws: row["why"] = "NO_SCENE"; return row
    for (hs, hp) in settings:
        scenes = []; diags = []
        for sid, when, coll, r, n, s, scl in raws:
            sc, dg = make_scene2(sid, when, coll, r, n, s, scl, lake, hs, hp); scenes.append(sc); diags.append(dg)
        rec = dict(sel=sel_record(scenes, ref), scene_diag=diags, n_interior=int(scenes[0].cells.interior.sum()), n_eligible=int(scenes[0].cells.eligible.sum()), obs={})
        for m in modes:
            o = O.observe(scenes, ref, mode=m); pres = O.presence(o); b = band_stats(o, cd)
            r = dict(kind=o.evidence_kind, persistence=o.persistence, n_acc=o.n_accepted, coverage=o.coverage, plant_cells=o.plant_cells, read_cells=o.read_cells, interior_cells=o.interior_cells,
                     presence=pres[0], presence_reason=pres[1], shares=o.refusal_shares, notes=o.notes, fallback=o.low_coverage_fallback, observed_on=str(o.observed_on),
                     gap=abs((o.observed_on - ref).days) if o.observed_on else None, scene_ids=o.scene_ids)
            if b:
                r.update(b); r["belt_share"] = b["belt_plant"] / b["belt_read"] if b["belt_read"] >= MIN_BELT else float("nan"); r["why"] = None if b["belt_read"] >= MIN_BELT else "BELT_TOO_SMALL"
            else: r["why"] = next(iter(o.refusal_shares), "NONE")
            rec["obs"][m] = r
        row["runs"][pair_key(hs, hp)] = rec
    return row
