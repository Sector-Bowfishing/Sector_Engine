"""Stage 22 S2C path for the shadow candidate (research/clarity-candidate/stage22, Decision B): Stage 12 is RETIRED for
nominal S2C (processing baselines 05.11, 05.12, 05.13 and newer nominal equivalents) and replaced by C3:
  1. before ACOLITE, the frozen Stage 21 additive top-of-atmosphere offsets for B11 and B12 only are removed from the L1R
     (B11 = 0.00173 + 0.00445 x this tile's own clear-pixel B11 median; B12 = 0.0011), so ACOLITE's residual-glint
     reference no longer reads the sensor's dark-water offset as glint (corr21.json, frozen 2026-10-03);
  2. after ACOLITE, the B05 band adjustment B05' = 1.0332*B05 - 0.0397*(B06 - B04) (srf20.json);
  3. the frozen C-gbm and Stage 16 gate, WITHOUT the Stage 12 V-rho_w correction; S2C keeps LOWER authority (Stage 16
     product rule unchanged).
Preliminary research baselines (N9905/N9906) never reach this path. Provenance is returned with every result."""
import hashlib, json, os, shutil, subprocess, time
import numpy as np
ROOT = os.environ["CLARITY_RESEARCH_ROOT"]
CORR = json.load(open(f"{ROOT}/stage21/corr21.json"))
B11, B12 = CORR["bands"]["B11"], CORR["bands"]["B12"]
SBAF = CORR["b05_l2w"]
PATH = "stage22-c3"
HASHES = {k: hashlib.sha256(open(f"{ROOT}/{p}", "rb").read()).hexdigest() for k, p in
          (("corr21", "stage21/corr21.json"), ("cand22", "stage22/cand22.json"), ("prereg22", "stage22/PREREGISTRATION_STAGE22.md"))}
ACO = f"{ROOT}/stage11/tools/acolite/venv/bin/python"
OV = {"dsf_interface_reflectance": True, "dsf_interface_option": "ffss_boa", "l2w_mask": False}


def nominal(platform, baseline):
    try: return platform == "sentinel-2c" and baseline is not None and float(baseline) >= 5.11
    except (TypeError, ValueError): return False


def offsets(safe):
    """C3 offsets from the S2C tile itself (no pairing, no future data): B11 from its clear-pixel B11 median."""
    import sys
    sys.path.insert(0, f"{ROOT}/stage21"); import toa21 as T21
    q, off = T21.meta(safe)
    b11 = T21.read(safe, "B11", q, off, "native20"); b10 = T21.read(safe, "B10", q, off, "rep60"); b02 = T21.read(safe, "B02", q, off, "level20")
    m_c = float(np.nanmedian(b11[(b10 < 0.002) & (b02 < 0.3)]))
    return {"B11": B11["alpha"] + B11["beta"] * m_c, "B12": B12["delta"]}, m_c


def run_c3(task, l1c, safe_fetch, safe_delete, workdir):
    """The frozen ACOLITE K4 crop path with the C3 TOA offsets -> {crops: [...], toa_sub, m_C} (same point format as RCA.one)."""
    r = {"item": task["item"], "l1c": l1c, "crops": [], "s2c_path": PATH}; t0 = time.time()
    path = safe_fetch(l1c)
    try:
        sub, m_c = offsets(path); r.update({"toa_sub": sub, "m_C": m_c})
        for i, c in enumerate(task["crops"]):
            ov = dict(OV, _toa_sub=sub)
            if c.get("elev") is not None: ov["elevation"] = c["elev"]
            wd = os.path.join(workdir, f"c3_{task['item']}_{i}")
            p = subprocess.run([ACO, f"{ROOT}/stage21/aco21_one.py", path, str(c["lat"]), str(c["lon"]), wd, json.dumps(c["points"]), json.dumps(ov)],
                               capture_output=True, text=True, timeout=3600, env=dict(os.environ))
            line = [l for l in p.stdout.split("\n") if l.startswith("@@JSON@@")]
            rec = json.loads(line[0][8:]) if line else {"error": (p.stderr or p.stdout)[-300:]}
            rec.update({"lat": c["lat"], "lon": c["lon"], "elevation_m": c.get("elev")}); r["crops"].append(rec)
            shutil.rmtree(wd, ignore_errors=True)
    finally:
        safe_delete(l1c)
    r["seconds"] = round(time.time() - t0, 1)
    return r


def sbaf(a):
    if not a or not all(isinstance(a.get(b), (int, float)) for b in ("B04", "B05", "B06")): return a
    v = dict(a); v["B05"] = SBAF["g"] * a["B05"] + SBAF["k"] * (a["B06"] - a["B04"]); return v


def answer16_c3(m0, m3, sen, sun, E14, E16):
    """engine16.answer16 for nominal S2C on the C3 path: B05 band adjustment, no Stage 12, Stage 16 product with S2C lower
    authority (product16 is given the real platform)."""
    from lib14 import features, state_of, valid
    from lib16 import product16, evidence
    m0c = sbaf(m0) if valid(m0) else m0; m3c = sbaf(m3) if valid(m3) else m3
    a = E14.answer(m0c, m3c, sen, sun, "sentinel-2a")            # "sentinel-2a" = the harmonisation switch off (no Stage 12)
    ndci = features(dict(m0c if a["tier"] == 1 else m3c), sun)[0]["F_ndci"] if a["tier"] in (1, 2) else None
    st3 = state_of(a["p"], E16.TB3) if a["tier"] == 3 and a["p"] is not None else None
    o = product16(a["tier"], a["p"], "sentinel-2c", ndci, st3, E16.R)
    o.update({"p": a["p"], "hard": a["hard"], "ndci": ndci, "interval_ft": a["interval_ft"], "evidence": evidence(o), "s2c_path": PATH})
    o["feet_shown"] = (10 ** a["p"]) if (o["display"] in ("exact", "approx") and a["p"] is not None) else None
    return o
