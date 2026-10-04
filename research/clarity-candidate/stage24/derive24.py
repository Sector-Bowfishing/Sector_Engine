"""Stage 24 sections 3 and 6 derivations (PREREGISTRATION_STAGE24.md): N2 offsets from T2N TOA (derivation set only) and the
geometry variance term gamma from FL23 (satellite-to-satellite only). Writes derived24.json and adds its hash to FREEZE_STAGE24.json."""
import json, os, sys, hashlib, numpy as np
S = os.environ["CLARITY_RESEARCH_ROOT"]; os.chdir(f"{S}/stage23")
F24 = json.load(open(f"{S}/stage24/FREEZE_STAGE24.json"))
assert hashlib.sha256(open(f"{S}/stage24/PREREGISTRATION_STAGE24.md", "rb").read()).hexdigest() == F24["prereg_sha256"]
sys.argv = ["anal23.py"]; exec(open("anal23.py").read().split("# ---------------- section 3: the floor")[0])
T2N = [p for p in pairs23("T2N", "res23_T2N", True) if (sun(p["c"].get("K0")) or 0) >= 25 and A22.ice_ok(p)]
rng = np.random.default_rng(24); N2 = {}; boot = {}
for b in ("B08", "B8A", "B11", "B12"):
    v = np.array([p["c"]["K0"]["diag"]["rhot"][b] - p["ref"]["diag"]["rhot"][b] for p in T2N if p["c"].get("K0") and p["ref"] and (p["c"]["K0"]["diag"].get("rhot") or {}).get(b) is not None and (p["ref"]["diag"].get("rhot") or {}).get(b) is not None])
    bs = [float(np.median(rng.choice(v, len(v)))) for _ in range(2000)]; lo, hi = np.percentile(bs, [2.5, 97.5]); med = float(np.median(v))
    boot[b] = {"n": len(v), "median": med, "ci95": [float(lo), float(hi)], "qualifies": bool(lo > 0 or hi < 0)}
    N2[b] = med if boot[b]["qualifies"] else 0.0
created = any(boot[b]["qualifies"] for b in boot)
FL = [p for p in pairs23("FL23", "res23_FL23", False) if A22.ice_ok(p)]; FP = build(FL, "FLOOR")
mad = lambda v: 1.4826 * float(np.median(np.abs(np.array(v) - np.median(v))))
dt_ = [x["c"]["p"] - x["r"]["p"] for x in FP if x["p"]["subtype"] == "tandem"]; da = [x["c"]["p"] - x["r"]["p"] for x in FP if x["p"]["subtype"] == "adjacent"]
st, sa = mad(dt_), mad(da); gamma = max(0.0, sa ** 2 - st ** 2)
out = {"N2": {"created": created, "offsets": {b: N2[b] for b in N2 if N2[b] != 0.0}, "bootstrap": boot, "plus_B05_adjustment": True},
       "gamma": {"value": gamma, "sigma_identical": st, "sigma_opposite": sa, "n_identical": len(dt_), "n_opposite": len(da),
                 "opposite_shift_median_reported_not_used": float(np.median(da))}}
json.dump(out, open(f"{S}/stage24/derived24.json", "w"), indent=1)
F24["derived24_sha256"] = hashlib.sha256(open(f"{S}/stage24/derived24.json", "rb").read()).hexdigest(); json.dump(F24, open(f"{S}/stage24/FREEZE_STAGE24.json", "w"), indent=1)
print(json.dumps(out, indent=1))
