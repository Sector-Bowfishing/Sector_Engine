"""Observers S / A / P exactly as in VEGETATION_VALIDATION_PREREGISTRATION.md section 1, evaluated on per-scene cell arrays
produced by the IMPORTED production s2_pass (10_run_cells.py / 12_run_pac.py). Constants = jobs/vegetation-brain contract.py = prereg."""
import numpy as np, datetime as dt
from scipy import ndimage

OFF, CLEAR, FLAG = 0, 1, 2
SHORE, NODATA, CLOUD, HAZE, DARK, NOSCENE, NOTACC = 10, 11, 12, 13, 14, 20, 21
NAMES = {SHORE: "SHORE_ADJACENT", NODATA: "NO_DATA_OFF_SWATH", CLOUD: "CLOUD_SHADOW_STANDOFF", HAZE: "HAZE_OR_CLOUD_EDGE_STANDOFF",
         DARK: "DARK_WATER", NOSCENE: "NO_SCENE", NOTACC: "PASS_NOT_ACCEPTED"}
PLANT_FRACTION_MIN = 0.5; MIN_SEEN_FRACTION = 0.5; DARK_CELL_MAX = 0.5; HIDDEN_MAX = 0.5
WINDOW_DAYS = 21; CLEAR_MIN = 0.75; PASS_MIN = 0.50; PASS_FALLBACK = 0.25; PERSIST_MIN = 3

def guard_masks(z, i):
    """non-exclusive guard flags per cell (all cells; combine with lake&clarity)"""
    g = z["gfrac"][i].astype("float32")
    seen_share = np.nan_to_num(z["seen_share"][i].astype("float32"))
    return dict(
        nodata=np.nan_to_num(z["nodata_share"][i].astype("float32")) >= 0.5,
        unseen=np.isnan(g) | (seen_share < MIN_SEEN_FRACTION),
        hidden=np.nan_to_num(z["hidden"][i].astype("float32")) >= HIDDEN_MAX,
        hidden_near_cloud=(np.nan_to_num(z["hidden"][i].astype("float32")) >= HIDDEN_MAX) & (np.nan_to_num(z["near"][i].astype("float32")) >= 0.5),
        dark=np.nan_to_num(z["dark_share"][i].astype("float32"), nan=0.0) >= DARK_CELL_MAX,
        glare=np.nan_to_num(z["glare_share"][i].astype("float32")) >= 0.5)

def scene_states(z, i, mode):
    """-> state int8 (HxW), pf float32 (plant fraction used for persistence; NaN where UNKNOWN), cov, clear_frac, extra masks"""
    lake, cl = z["lake"], z["clarity"]
    g = z["gfrac"][i].astype("float32"); read = z["read"][i]
    unseen = np.isnan(g)
    nodata = np.nan_to_num(z["nodata_share"][i].astype("float32")) >= 0.5
    st = np.zeros(lake.shape, "int8")
    st[lake] = CLEAR
    pf = np.full(lake.shape, np.nan, "float32")
    if mode == "prod":
        known = lake & cl & ~unseen
        pf[known] = np.where(read[known], 0.0, g[known])
        flag = z["grass_prod"][i] & lake & cl
        st[known] = CLEAR; st[known & flag] = FLAG
        st[lake & cl & unseen] = CLOUD; st[lake & cl & unseen & nodata] = NODATA
    else:
        gm = guard_masks(z, i)
        gv = z["gfrac_v1"][i].astype("float32")
        if mode == "v1fix":
            # SENSITIVITY (recommended fix, not the prereg text): a dark pixel can never be a plant (its NDVI is unstable),
            # but dark open water is a perfectly good CLEAR observation, so the cell is not refused for being dark.
            d_ = np.nan_to_num(z["dark_share"][i].astype("float32"))
            gv = np.where(np.isnan(gv), np.nan, np.nan_to_num(gv) * (1.0 - d_)).astype("float32")
            gv = np.where(gm["dark"] & np.isnan(z["gfrac_v1"][i].astype("float32")), 0.0, gv).astype("float32")
            gm = dict(gm, dark=np.zeros_like(gm["dark"]))
        rest = lake & cl
        # exclusive first-hit attribution: nodata > cloud/insufficient > haze/standoff > dark water
        for code, m in ((NODATA, gm["nodata"]), (CLOUD, gm["unseen"]), (HAZE, gm["hidden"]), (DARK, gm["dark"] | np.isnan(gv))):
            hit = rest & m
            st[hit] = code
            rest = rest & ~m
        known = rest
        pf[known] = np.where(read[known], 0.0, gv[known])
        st[known] = CLEAR; st[known & (pf >= PLANT_FRACTION_MIN)] = FLAG
    st[lake & ~cl] = SHORE
    flagm = st == FLAG
    water = cl & ~flagm
    cov = float((read & water).sum() / max(1, water.sum()))
    clear_frac = float((~unseen & lake).sum() / max(1, lake.sum()))
    return st, pf, cov, clear_frac

def prep(z, mode, use_rejected=False):
    """per-scene derived arrays for one lake; scenes rejected by production (SWIR-DN gate) are dropped unless use_rejected."""
    S = z["gfrac"].shape[0]; out = []
    dates = [dt.date.fromisoformat(str(d)) for d in z["dates"]]
    keys = z.files if hasattr(z, "files") else list(z)
    ok = z["ok"] if "ok" in keys else np.array([str(e) == "" for e in z["error"]])
    rej = z["rejected"]
    for i in range(S):
        if not ok[i]: continue
        if str(rej[i]) != "" and not use_rejected: continue
        st, pf, cov, cf = scene_states(z, i, mode)
        out.append(dict(i=i, date=dates[i], st=st, pf=pf, cov=cov, clear=cf, rejected=str(rej[i]) != ""))
    return out

def _blank(z, code):
    st = np.zeros(z["lake"].shape, "int8"); st[z["lake"]] = code
    st[z["lake"] & ~z["clarity"]] = SHORE
    return st

def observer_S(z, sc, ref):
    c = [s for s in sc if abs((s["date"] - ref).days) <= WINDOW_DAYS and s["clear"] >= CLEAR_MIN]
    if not c: return _blank(z, NOSCENE), dict(kind="NONE", gap=None, n=0)
    s = min(c, key=lambda s: (abs((s["date"] - ref).days), s["date"]))
    return s["st"], dict(kind="SINGLE", gap=abs((s["date"] - ref).days), date=str(s["date"]), cov=s["cov"], n=1)

def _pick_A(z, sc, ref):
    c = sorted([s for s in sc if abs((s["date"] - ref).days) <= WINDOW_DAYS], key=lambda s: (abs((s["date"] - ref).days), s["date"]))
    acc = [s for s in c if s["cov"] >= PASS_MIN]
    if acc: return acc[0], "ACCEPTED"
    fb = [s for s in c if s["cov"] >= PASS_FALLBACK]
    if fb: return max(fb, key=lambda s: (s["cov"], -abs((s["date"] - ref).days))), "FALLBACK"
    return None, "NONE"

def observer_A(z, sc, ref):
    s, how = _pick_A(z, sc, ref)
    if s is None: return _blank(z, NOTACC), dict(kind="NONE", gap=None, n=0)
    return s["st"], dict(kind=how, gap=abs((s["date"] - ref).days), date=str(s["date"]), cov=s["cov"], n=1)

def observer_P(z, sc, ref):
    stA, infoA = observer_A(z, sc, ref)
    acc = [s for s in sc if abs((s["date"] - ref).days) <= WINDOW_DAYS and s["cov"] >= PASS_MIN]
    info = dict(kind="PERSISTENCE", n_accepted=len(acc), gap=min([abs((s["date"] - ref).days) for s in acc]) if acc else None)
    if len(acc) < PERSIST_MIN:
        info.update(persistence="INSUFFICIENT", cells_persistent=0, A=infoA); return stA.copy(), info
    PF = np.stack([s["pf"] for s in acc])
    n = np.sum(~np.isnan(PF), axis=0)
    with np.errstate(all="ignore"):
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter("ignore"); med = np.nanmedian(PF, axis=0)
    st = stA.copy()
    use = (n >= PERSIST_MIN) & z["lake"] & z["clarity"]
    st[use] = np.where(med[use] >= PLANT_FRACTION_MIN, FLAG, CLEAR).astype("int8")
    info.update(persistence="MEDIAN_OF_ACCEPTED", cells_persistent=int(use.sum()), cells_fallback_A=int((z["lake"] & z["clarity"] & ~use).sum()), A=infoA)
    return st, info

OBS = {"S": observer_S, "A": observer_A, "P": observer_P}

# ---- metrics -----------------------------------------------------------------
BINS = [0, 15, 30, 45, 60, 90, 150, 300, 1e9]
def dist_bin(z):
    d = ndimage.distance_transform_edt(z["lake"]) * float(z["ground_m"])
    return np.digitize(d, BINS[1:-1]), d

def prf(tp, fp, fn, tn):
    P = tp / max(1e-9, tp + fp) if tp + fp > 0 else float("nan")
    R = tp / max(1e-9, tp + fn) if tp + fn > 0 else float("nan")
    F = 2 * P * R / (P + R) if (P == P and R == R and P + R > 0) else float("nan")
    I = tp / max(1e-9, tp + fp + fn) if tp + fp + fn > 0 else float("nan")
    return P, R, F, I

def bootstrap_lakes(per_lake, fn, n=2000, seed=7):
    """per_lake: list of dicts of additive counts; fn(sum_dict)->float. resample lakes with replacement."""
    rng = np.random.default_rng(seed); L = len(per_lake); vals = []
    keys = per_lake[0].keys()
    for _ in range(n):
        ix = rng.integers(0, L, L)
        tot = {k: sum(per_lake[j][k] for j in ix) for k in keys}
        v = fn(tot)
        if v == v: vals.append(v)
    if len(vals) < 20: return None, None, len(vals)
    return float(np.percentile(vals, 2.5)), float(np.percentile(vals, 97.5)), len(vals)
