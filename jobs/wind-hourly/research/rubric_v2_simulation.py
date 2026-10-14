"""Exact before/after simulation of the PROPOSED Wind rubric v2 changes, from EXISTING evidence only (nothing generated, H2 never opened).
Reads: the scorer's own skill evidence (stage3a/evidence via wind_skill_source.json) and the research branch's bowfishing_validation.json
(forecast-keyed direction slices). Does not touch the canonical scorer, score log or Engine artifacts.
  python research/rubric_v2_simulation.py BOWFISHING_VALIDATION.json OUT.json"""
import json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from sector_wind import scoreboard as SB

EVID = os.path.expanduser("~/Desktop/Development/iOS/sector-wind/docs/intelligence/wind/stage3a/evidence")
bv_path, out = sys.argv[1], sys.argv[2]
w = json.load(open(EVID + "/wind_skill_source.json")); ev = json.load(open(EVID + "/" + w["file"]))
nbm = ev["nbm"]; night, allh = nbm["night"], nbm["allHours"]
pn, pa = SB.pooled(night), SB.pooled(allh)
lin = SB.lin

# ---- v1 components (identical to scoreboard.dims_1_to_4) ----
obs15 = sum(night[k].get("n_obs_15mph", 0) for k in SB.LEADS if k in night)
pod15 = [night[k].get("pod_15mph") for k in SB.LEADS if k in night]; far15 = [night[k].get("far_15mph") for k in SB.LEADS if k in night]
speed_A = min(lin(pn["mae"], 1.6, 1.0), 1.0 if abs(pn["bias"]) <= 0.3 else 0.0)
speed_B = 0.0 if obs15 == 0 else (1.0 if all(p is not None and p >= 0.5 for p in pod15) and all(f is None or f <= 0.5 for f in far15) else 0.0)
pods = [allh[k].get("gust20_pod") for k in SB.LEADS if k in allh]; fars = [allh[k].get("gust20_far") for k in SB.LEADS if k in allh]
gust_A = lin(abs(pa["gust_bias"]), 3.0, 1.0)
gust_B = 0.0 if all(p is None for p in pods) else (1.0 if all(p is not None and p >= 0.6 for p in pods) and all(f is None or f <= 0.6 for f in fars) else 0.0)

def dir_credit(within, circ):
    return min(lin(within, 0.65, 0.85), 1.0 if circ <= 20 else 0.0)

# ---- direction slices ----
V1 = json.load(open(bv_path))["V1_direction"]
def pool(keys):
    n = sum(V1[k]["n"] for k in keys)
    return {"n": n, "within22_5": sum(V1[k]["within22_5"] * V1[k]["n"] for k in keys) / n, "circMAE": sum(V1[k]["circMAE"] * V1[k]["n"] for k in keys) / n}
fc_keys = [f"night|{l}|byForecast|{b}" for l in ("lead<=6", "lead12-18") for b in ("5-10mph", "10-99mph")]
slices = {
    "A all hours, both winds >= 2.6 m/s (v1 rule)": {"n": pa["dir_n"], "within22_5": pa["dir_within22_5"], "circMAE": pa["dir_mean"]},
    "B night, both winds >= 2.6 m/s (observed-conditioned)": {"n": pn["dir_n"], "within22_5": pn["dir_within22_5"], "circMAE": pn["dir_mean"]},
    "C night, FORECAST >= 5 mph (forecast-keyed: what the customer sees)": pool(fc_keys),
}
for s in slices.values():
    s["credit"] = round(dir_credit(s["within22_5"], s["circMAE"]), 4); s["points_of_8"] = round(8 * s["credit"], 2)

CUR = {"speed": 0.0, "direction": 8 * dir_credit(pa["dir_within22_5"], pa["dir_mean"]), "gust": 0.0}
CURRAW_PTS = 32.92   # canonical rawPoints at the time of the simulation (scorer rerun 2026-10-14)
def variant(name, speed_split, gust_split, dslice):
    sp = speed_split[0] * speed_A + speed_split[1] * speed_B
    gu = gust_split[0] * gust_A + gust_split[1] * gust_B
    dr = slices[dslice]["points_of_8"]
    pts = CURRAW_PTS - CUR["direction"] + dr + sp + gu
    return {"name": name, "speedPts": round(sp, 2), "gustPts": round(gu, 2), "directionPts": dr, "rawPoints": round(pts, 2), "raw10": round(pts / 10, 2),
            "displayed": round(min(pts / 10, 6.0), 1)}
sims = [variant("V2-primary: speed 8/4, gust 2.5/2.5, direction slice C (forecast-keyed night)", (8, 4), (2.5, 2.5), list(slices)[2]),
        variant("V2-alt weights: speed 6/6, gust 2.5/2.5, direction slice C", (6, 6), (2.5, 2.5), list(slices)[2]),
        variant("V2 with direction slice B (observed-conditioned; NOT recommended)", (8, 4), (2.5, 2.5), list(slices)[1]),
        variant("V2 with direction slice A (v1 all-hours; speed+gust split only)", (8, 4), (2.5, 2.5), list(slices)[0])]
res = {"inputs": {"skillEvidence": w["file"], "forecastKeyed": os.path.basename(bv_path)}, "components": {"speedA_credit": round(speed_A, 4), "speedB_credit": speed_B, "gustA_credit": round(gust_A, 4), "gustB_credit": gust_B},
       "directionSlices": slices, "currentV1": {"rawPoints": CURRAW_PTS, "raw10": 3.29, "displayed": 3.3}, "simulations": sims}
json.dump(res, open(out, "w"), indent=1); print(json.dumps(res, indent=1))
