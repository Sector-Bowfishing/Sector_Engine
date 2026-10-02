"""Stage 12 Part 3, reflectance first (section 3 R1-R4). Must run before any visibility script; writes reflectance.json.
Primary rows: not Guntersville. e_T = log10(FNU / in-situ turbidity), FNU = production Dogliotti on the B04 of each path,
0.1 floor. Same-day satellite pass (dt = 0) is primary; |dt| <= 1 secondary. Lake-bootstrap CIs (seed 11, Stage 11)."""
import json, math, collections
from common12 import *
R = load12()
out = {}
def eT(fnu, t): return math.log10(max(fnu, 0.1) / max(t, 0.1))
# R1 retrieval rate
P = [x for x in R if x["processed"] and not x["gunt"]]
out["R1"] = {"rows_processed": len(P), "aco_valid_rate": round(sum(x["aco_valid"] for x in P) / len(P), 3), "sen2cor_valid_rate": 1.0,
             "by_class": {c: round(float(np.mean([x["aco_valid"] for x in P if cname(x["secchi"]) == c])), 3) for c in CLASSES},
             "by_set": {s: round(float(np.mean([x["aco_valid"] for x in P if x["set"] == s])), 3) for s in sorted({x["set"] for x in P})},
             "not_processed": sum(1 for x in R if not x["processed"])}
# R2 turbidity
def r2(rows):
    A = [eT(dog(x["aco"]["B04"]), x["turb"]) for x in rows]; B = [eT(x["fnu"], x["turb"]) for x in rows]
    res = {"n": len(rows), "lakes": len({x["lake"] for x in rows}),
           "aco_median_abs_eT": round(float(np.median(np.abs(A))), 3), "aco_median_eT": round(float(np.median(A)), 3),
           "s2c_median_abs_eT": round(float(np.median(np.abs(B))), 3), "s2c_median_eT": round(float(np.median(B)), 3)}
    fn = lambda rr: float(np.median([abs(eT(dog(x["aco"]["B04"]), x["turb"])) for x in rr]) - np.median([abs(eT(x["fnu"], x["turb"])) for x in rr]))
    res["diff"] = round(fn(rows), 3); res["diff_ci"] = lake_boot(rows, fn) if len(rows) >= 20 else None
    return res
T0 = [x for x in R if not x["gunt"] and x["aco_valid"] and x.get("turb") is not None and x.get("dt") == 0]
T1 = [x for x in R if not x["gunt"] and x["aco_valid"] and x.get("turb") is not None and abs(x.get("dt") or 0) <= 1]
out["R2"] = {"same_day": r2(T0), "within_1_day": r2(T1),
             "by_class_same_day": {c: r2([x for x in T0 if cname(x["secchi"]) == c]) for c in CLASSES if sum(1 for x in T0 if cname(x["secchi"]) == c) >= 10},
             "by_insitu_type_same_day": {t: r2([x for x in T0 if x["insitu_type"] == t]) for t in ("clear", "algal", "sediment", "mixed") if sum(1 for x in T0 if x["insitu_type"] == t) >= 10}}
d = out["R2"]["same_day"]
out["R2"]["reflectance_improved"] = bool(d["diff"] < 0 and d["diff_ci"] and d["diff_ci"][1] < 0)
# R3 the Part A split with each path's FNU (champion frozen)
def split(rows, key):
    eS = np.array([math.log10(champ(key(x)) / x["secchi"]) for x in rows]); e_T = np.array([eT(key(x), x["turb"]) for x in rows])
    rad = -0.637 * e_T; conv = eS - rad; v = float(np.var(eS))
    return {"n": len(rows), "var_eS": round(v, 4), "share_radiometric": round(float(np.cov(rad, eS, bias=True)[0, 1] / v), 3),
            "share_conversion": round(float(np.cov(conv, eS, bias=True)[0, 1] / v), 3), "median_abs_eS": round(float(np.median(np.abs(eS))), 3)}
TS = [x for x in T0 if x["secchi"] and x["secchi"] > 0]
out["R3"] = {"acolite": split(TS, lambda x: dog(x["aco"]["B04"])), "sen2cor": split(TS, lambda x: x["fnu"])}
# R4 platform
plat = collections.defaultdict(list)
for x in T1: plat[x["platform"]].append(x)
out["R4"] = {p: {"n": len(v), "aco_median_eT": round(float(np.median([eT(dog(x["aco"]["B04"]), x["turb"]) for x in v])), 3),
                 "s2c_median_eT": round(float(np.median([eT(x["fnu"], x["turb"]) for x in v])), 3)} for p, v in plat.items() if len(v) >= 5}
S2C = [x for x in R if x["platform"] == "sentinel-2c" and x["aco_valid"] and x["aco_raw_valid"]]
out["R4"]["s2c_rows_harmonised_vs_raw"] = {"n": len(S2C), **{b: round(float(np.median([x["aco"][b] / x["aco_raw"][b] for x in S2C if x["aco_raw"].get(b) and abs(x["aco_raw"][b]) > 1e-4])), 3) for b in ("B02", "B04", "B05", "B11")} } if S2C else None
# band-level context: ACOLITE / Sen2Cor on the same stations
V = [x for x in R if x["aco_valid"] and not x["gunt"]]
out["band_ratio_aco_over_s2c"] = {b: round(float(np.median([x["aco"][bb] / x["sen2cor"][b] for x in V if x["sen2cor"].get(b) and x["sen2cor"][b] > 0.001])), 3)
                                  for b, bb in (("blue", "B02"), ("green", "B03"), ("red", "B04"), ("re1", "B05"))}
json.dump(out, open(f"{D12}/analysis/reflectance.json", "w"), indent=1)
print(json.dumps(out, indent=1)[:4000])
