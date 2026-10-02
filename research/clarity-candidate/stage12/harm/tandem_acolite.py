"""Stage 12 Part 2, ACOLITE path (section 2 + addendum A): for each tandem pair, BEST on S2A L1C, on raw S2C L1C, and
on the TOA-harmonised S2C L1R (V-full and V-op, leave-one-pair-out coefficients). Water: valid in every L2W output,
TOA NDWI(B03, B08) > 0 on both passes, >= 180 m (9 px) from anything that is not. Up to 4,000 pixels per pair (seed 12).
Saves the matched spectra (B01-B12 rhow, 20 m) per pair to harm/tandem_acolite/<pair>.npz.
  python tandem_acolite.py OVERRIDES_JSON"""
import json, os, sys, glob, subprocess, shutil, numpy as np, h5py
from scipy import ndimage
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
sys.path.insert(0, f"{S}/stage11/tools")
import safe as SAFE
ACO = f"{S}/stage11/tools/acolite/venv/bin/python"
OUT = f"{S}/stage12/harm/tandem_acolite"; os.makedirs(OUT, exist_ok=True)
OV = json.loads(sys.argv[1]) if len(sys.argv) > 1 else {}
IDS = ["1", "2", "3", "4", "5", "6", "7", "8", "8A", "9", "11", "12"]
BID = {i: ("B8A" if i == "8A" else f"B{int(i):02d}") for i in IDS}


def run(inp, lat, lon, wd):
    p = subprocess.run([ACO, f"{S}/stage12/tools/aco12_one.py", inp, str(lat), str(lon), wd, "[]", json.dumps(OV), "--keep"], capture_output=True, text=True, timeout=3600)
    line = [l for l in p.stdout.split("\n") if l.startswith("@@JSON@@")]
    return json.loads(line[0][8:]) if line else {"error": (p.stderr or p.stdout)[-300:]}


def read(wd, kind):
    f = glob.glob(f"{wd}/*_{kind}.nc")
    if not f: return None
    d = h5py.File(f[0], "r"); pre = "rhow_" if kind == "L2W" else "rhot_"
    out = {}
    for i in IDS:
        nm = d.attrs.get(f"{i}_name")
        nm = nm.decode() if isinstance(nm, bytes) else (str(nm) if nm is not None else None)
        if nm and f"{pre}{nm}" in d: out[BID[i]] = d[f"{pre}{nm}"][:].astype("float64")
    return out


pairs = [p for p in json.load(open(f"{S}/stage11/tandem/tandem_clear.json")) if p["gcp_s2a"] and p["gcp_s2c"]]
for p in pairs:
    day = p["s2a_product"].split("_")[2]; key = f"{p['tile'].lstrip('T')}_{day[:4]}-{day[4:6]}-{day[6:8]}"
    dst = f"{OUT}/{key}.npz"
    if os.path.exists(dst): print(key, "done"); continue
    base = f"{S}/stage12/work/tan_{key}"
    try:
        sa, sc = SAFE.fetch(p["gcp_s2a"][-1]), SAFE.fetch(p["gcp_s2c"][-1])
        ra = run(sa, p["lat"], p["lon"], f"{base}_A"); rc = run(sc, p["lat"], p["lon"], f"{base}_C")
        l1r = glob.glob(f"{base}_C/*_L1R.nc")[0]
        coef = f"{S}/stage12/harm/lopo_toa_{key}.json"
        for mode in ("vfull", "vop"):
            h = f"{base}_{mode}_L1R.nc"
            subprocess.run([ACO, f"{S}/stage12/tools/harm_l1r.py", l1r, h, coef, mode], check=True, capture_output=True)
            run(h, p["lat"], p["lon"], f"{base}_{mode}")
        A, C = read(f"{base}_A", "L2W"), read(f"{base}_C", "L2W")
        F, O = read(f"{base}_vfull", "L2W"), read(f"{base}_vop", "L2W")
        tA, tC = read(f"{base}_A", "L1R"), read(f"{base}_C", "L1R")
        shapes = {k: v["B04"].shape for k, v in (("A", A), ("C", C), ("F", F), ("O", O))}
        if len(set(shapes.values())) != 1: raise RuntimeError(f"grid mismatch {shapes}")
        with np.errstate(invalid="ignore", divide="ignore"):
            ndA = (tA["B03"] - tA["B08"]) / (tA["B03"] + tA["B08"]); ndC = (tC["B03"] - tC["B08"]) / (tC["B03"] + tC["B08"])
            w = (ndA > 0) & (ndC > 0)
            for X in (A, C, F, O): w &= np.isfinite(X["B04"]) & np.isfinite(X["B05"]) & np.isfinite(X["B02"])
        w &= ndimage.distance_transform_edt(w) > 9
        idx = np.flatnonzero(w.ravel())
        idx = np.random.default_rng(12).choice(idx, min(4000, idx.size), replace=False) if idx.size else idx
        pack = {f"{tag}_{b}": X[b].ravel()[idx] for tag, X in (("A", A), ("C", C), ("F", F), ("O", O)) for b in X}
        pack["sun"] = np.array([p["sun"]]); pack["water_px"] = np.array([int(w.sum())])
        np.savez_compressed(dst, **pack)
        print(key, "water px", int(w.sum()), "sampled", idx.size, flush=True)
    except Exception as e:
        print(key, "ERROR", str(e)[:200], flush=True)
    finally:
        for d in glob.glob(f"{base}_*"): shutil.rmtree(d, ignore_errors=True) if os.path.isdir(d) else os.remove(d)
        SAFE.delete(p["gcp_s2a"][-1]); SAFE.delete(p["gcp_s2c"][-1])
print("TANDEM_ACOLITE_DONE")
