"""Stage 11 Part B, metrics 2-4 on the representative corpus scenes: for every processor, Dogliotti FNU (production
coefficients) from its B04 against same-day in-situ turbidity, and the frozen P1 on its B02-B05 against Secchi, on the
same stations. Sen2Cor = the production readout of the corpus row. Writes part_b_repr.json."""
import json, math, sys, os, collections
import numpy as np
from common import *
sys.path.insert(0, os.path.expanduser(__import__("os").environ["CLARITY_RESEARCH_ROOT"] + "/vendor/Sector_Engine-fusion/jobs/lake-surface"))
import derive_water_surface as dws
rows = {x["id"]: x for x in load()}
jobs = json.load(open(f"{D11}/ac/jobs_repr.json"))
R = json.load(open(f"{D11}/ac/results_repr.json"))
R2 = json.load(open(f"{D11}/ac/results_repr_relaxed.json")) if os.path.exists(f"{D11}/ac/results_repr_relaxed.json") else {}
def dog(r):
    r = max(r, 0.0)
    return float(dws.TURB_SATURATED_FNU if r >= dws.TURB_SATURATED else dws.TURB_A * r / max(1e-6, 1 - r / dws.TURB_C))
PROCS = ["Sen2Cor (production)", "ACOLITE (own mask)", "ACOLITE (water/cloud mask)", "C2RCC-Nets", "C2X-Nets"]
recs = []
for j in jobs:
    r = R.get(j["job"], {}); r2 = R2.get(j["job"], {})
    for plat, plon, pid in j["points"]:
        x = rows.get(pid)
        if not x: continue
        sp = {"Sen2Cor (production)": {"B02": x["raw"]["blue"], "B03": x["raw"]["green"], "B04": x["raw"]["red"], "B05": x["raw"]["re1"]}}
        a = (r.get("acolite") or {}).get(pid) or {}
        sp["ACOLITE (own mask)"] = a if a.get("n", 0) >= 5 else {}
        b = (r2.get(pid) or {}).get("relaxed") or {}
        sp["ACOLITE (water/cloud mask)"] = b if b.get("n", 0) >= 5 else {}
        for net in ("C2RCC-Nets", "C2X-Nets"):
            c = ((r.get("c2rcc") or {}).get(net) or {}).get(pid) or {}
            sp[net] = c if c.get("n", 0) >= 5 else {}
        rec = {"id": pid, "job": j["job"], "classes": j["classes"], "secchi": x["secchi"], "turb": x.get("turb"), "chl": x.get("chl"), "proc": {}}
        for p in PROCS:
            v = sp.get(p) or {}
            if not all(isinstance(v.get(k), (int, float)) and v.get(k) == v.get(k) for k in ("B02", "B03", "B04", "B05")):
                rec["proc"][p] = None; continue
            fnu = dog(v["B04"])
            z, why, _ = P1({"blue": v["B02"], "green": v["B03"], "red": v["B04"], "re1": v["B05"]}, x["sun_elev"])
            rec["proc"][p] = {"fnu": fnu, "eT": math.log10(max(fnu, 0.1) / max(x["turb"], 0.1)) if x.get("turb") is not None else None,
                              "champ_e": math.log10(champ(fnu) / x["secchi"]), "p1": z, "p1_e": math.log10(z / x["secchi"]) if z else None, "p1_why": why,
                              "B04": v["B04"], "B05": v["B05"]}
        recs.append(rec)
out = {"points": len(recs), "scenes": len(jobs), "by_class": dict(collections.Counter(c for r in recs for c in r["classes"])), "processors": {}}
for p in PROCS:
    ok = [r for r in recs if r["proc"].get(p)]
    eT = [abs(r["proc"][p]["eT"]) for r in ok if r["proc"][p]["eT"] is not None]
    ce = [abs(r["proc"][p]["champ_e"]) for r in ok]
    pe = [abs(r["proc"][p]["p1_e"]) for r in ok if r["proc"][p]["p1_e"] is not None]
    out["processors"][p] = {"valid": len(ok), "median_abs_eT": round(float(np.median(eT)), 3) if eT else None, "median_eT": round(float(np.median([r["proc"][p]["eT"] for r in ok if r["proc"][p]["eT"] is not None])), 3) if eT else None,
                            "champion_formula median_abs_log": round(float(np.median(ce)), 3) if ce else None,
                            "P1 answers": len(pe), "P1 median_abs_log": round(float(np.median(pe)), 3) if pe else None}
# paired on the points every processor answers
common = [r for r in recs if all(r["proc"].get(p) for p in ("Sen2Cor (production)", "ACOLITE (water/cloud mask)", "C2RCC-Nets", "C2X-Nets"))]
out["paired_common_points"] = {"n": len(common), **{p: {"median_abs_eT": round(float(np.median([abs(r["proc"][p]["eT"]) for r in common if r["proc"][p]["eT"] is not None])), 3) if common else None}
                                                   for p in ("Sen2Cor (production)", "ACOLITE (water/cloud mask)", "C2RCC-Nets", "C2X-Nets")}}
# criterion (b) of the best-path rule, pairwise: each processor against Sen2Cor on the stations both answer
def pair(p):
    pr = [(abs(r["proc"][p]["eT"]), abs(r["proc"]["Sen2Cor (production)"]["eT"])) for r in recs
          if r["proc"].get(p) and r["proc"].get("Sen2Cor (production)") and r["proc"][p]["eT"] is not None and r["proc"]["Sen2Cor (production)"]["eT"] is not None]
    return {"n": len(pr), "processor_median_abs_eT": round(float(np.median([a for a, _ in pr])), 3) if pr else None,
            "sen2cor_median_abs_eT": round(float(np.median([b for _, b in pr])), 3) if pr else None,
            "processor_better_count": sum(1 for a, b in pr if a < b)}
out["pairwise_vs_sen2cor"] = {p: pair(p) for p in PROCS[1:]}
json.dump({"summary": out, "points": recs}, open(f"{D11}/analysis/part_b_repr.json", "w"), indent=1, default=float)
print(json.dumps(out, indent=1))
