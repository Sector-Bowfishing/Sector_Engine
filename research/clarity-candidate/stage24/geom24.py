"""Stage 24 section 6 (PREREGISTRATION_STAGE24.md): geometry vs satellite-to-satellite disagreement on the Stage 23 FL23 floor
(no truth). Writes geom24.json."""
import json, os, sys, math, hashlib, numpy as np
from scipy.stats import spearmanr
S = os.environ["CLARITY_RESEARCH_ROOT"]; os.chdir(f"{S}/stage23")
F24 = json.load(open(f"{S}/stage24/FREEZE_STAGE24.json"))
assert hashlib.sha256(open(f"{S}/stage24/PREREGISTRATION_STAGE24.md", "rb").read()).hexdigest() == F24["prereg_sha256"]
sys.argv = ["anal23.py"]; exec(open("anal23.py").read().split("# ---------------- section 3: the floor")[0])
G = json.load(open(f"{S}/stage24/geom24_items.json")); CONTAINS = L20.CONTAINS
def psi(g):
    ts, tv, d = math.radians(90 - g["sun_elev"]), math.radians(g["view_inc"]), math.radians(g["sun_az"] - g["view_az"])
    return math.degrees(math.acos(max(-1, min(1, math.cos(ts) * math.cos(tv) - math.sin(ts) * math.sin(tv) * math.cos(d)))))
daz = lambda a, b: abs((a - b + 180) % 360 - 180)
FL = [p for p in pairs23("FL23", "res23_FL23", False) if A22.ice_ok(p)]; FP = build(FL, "FLOOR")
rows = []
for x in FP:
    q = x["p"]["meta"]; a, b = G[q["o"]], G[q["c"]]
    ra, rb = x["p"]["ref"]["diag"], x["p"]["c"]["K0"]["diag"]
    rows.append({"dp": abs(x["c"]["p"] - x["r"]["p"]), "dps": x["c"]["p"] - x["r"]["p"], "opp": daz(a["view_az"], b["view_az"]) > 90, "dvz": abs(a["view_inc"] - b["view_inc"]),
                 "dpsi": abs(psi(a) - psi(b)), "minpsi": min(psi(a), psi(b)), "drg": abs((ra.get("rhog_ref") or 0) - (rb.get("rhog_ref") or 0)) if ra.get("rhog_ref") is not None and rb.get("rhog_ref") is not None else None,
                 "drgB04": abs(((ra.get("rhog") or {}).get("B04") or 0) - ((rb.get("rhog") or {}).get("B04") or 0)) if (ra.get("rhog") or {}).get("B04") is not None and (rb.get("rhog") or {}).get("B04") is not None else None,
                 "state_dis": bool(x["c"]["state"] and x["r"]["state"] and not (CONTAINS[x["c"]["state"]] & CONTAINS[x["r"]["state"]])) if True else None,
                 "jump": abs(x["c"]["hard"] - x["r"]["hard"]) >= 2, "conf": (x["c"]["conf"] - x["r"]["conf"]) if x["c"]["conf"] is not None and x["r"]["conf"] is not None else None,
                 "bands": {b_: math.log10(x["c"]["a"][b_] / x["r"]["a"][b_]) for b_ in VIS if x["c"]["a"].get(b_, 0) > 0.001 and x["r"]["a"].get(b_, 0) > 0.001},
                 "vza_aco": (ra.get("vza"), rb.get("vza")), "stac_vz": (a["view_inc"], b["view_inc"]), "raa_aco": (ra.get("raa"), rb.get("raa"))})
def rho(k, R):
    v = [(r[k], r["dp"]) for r in R if r[k] is not None]; return {"rho": float(spearmanr([a for a, b in v], [b for a, b in v]).correlation), "n": len(v)} if len(v) > 5 else None
out = {"n": len(rows), "pooled": {k: rho(k, rows) for k in ("opp", "dvz", "dpsi", "minpsi", "drg", "drgB04")},
       "within_opposite": {k: rho(k, [r for r in rows if r["opp"]]) for k in ("dvz", "dpsi", "minpsi", "drg", "drgB04")}}
def grp(R):
    if not R: return {"n": 0}
    return {"n": len(R), "abs_dp_median": float(np.median([r["dp"] for r in R])), "dp_signed_median": float(np.median([r["dps"] for r in R])),
            "band_abs_median": {b_: float(np.median([abs(r["bands"][b_]) for r in R if b_ in r["bands"]])) for b_ in VIS},
            "state_disagreement": float(np.mean([r["state_dis"] for r in R])), "jumps": float(np.mean([r["jump"] for r in R])),
            "posterior_abs_median": float(np.median([abs(r["conf"]) for r in R if r["conf"] is not None]))}
out["groups"] = {"identical": grp([r for r in rows if not r["opp"]]), "opposite": grp([r for r in rows if r["opp"]])}
op = sorted([r for r in rows if r["opp"]], key=lambda r: r["dpsi"]); h = len(op) // 2
out["groups"]["opposite_small_dpsi"] = grp(op[:h]); out["groups"]["opposite_large_dpsi"] = grp(op[h:])
bi = abs(out["pooled"]["opp"]["rho"]); best = max(((k, abs(v["rho"])) for k, v in out["pooled"].items() if k in ("dvz", "dpsi", "minpsi") and v), key=lambda z: z[1])
out["signal"] = {"binary_rho": bi, "best_continuous": best[0], "best_continuous_rho": best[1], "continuous_reported_better": best[1] >= bi + 0.05, "rule_used": "binary side (frozen)"}
va = [(r["vza_aco"][0], r["stac_vz"][0]) for r in rows if r["vza_aco"][0] is not None] + [(r["vza_aco"][1], r["stac_vz"][1]) for r in rows if r["vza_aco"][1] is not None]
out["aco_vs_stac_view_zenith"] = {"n": len(va), "median_abs_diff_deg": float(np.median([abs(a - b) for a, b in va])) if va else None}
json.dump(out, open(f"{S}/stage24/geom24.json", "w"), indent=1)
print(json.dumps({k: out[k] for k in ("n", "pooled", "within_opposite", "signal", "aco_vs_stac_view_zenith")}, indent=0))
for k, v in out["groups"].items(): print(k, {a: (round(b, 4) if isinstance(b, float) else b) for a, b in v.items() if a != "band_abs_median"}, {b_: round(x, 3) for b_, x in v.get("band_abs_median", {}).items()})
