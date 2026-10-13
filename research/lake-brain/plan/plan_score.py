#!/usr/bin/env python3
"""Score deltas from the UNMODIFIED rubric (jobs/brain_platform/.../scoring.py::score_lake via research/lake-brain/tools/research_score.py).
Scenarios (profiled = core VERIFIED/VERIFIED_CORROBORATED, optionally + flagged):
  S0  published research state  (fleet_score.classify: plan/flood from the binding thread's operatorPlan text, history from verified.csv, TVA pilots composite)
  S1  S0 + this thread's history extension (complete years >= 5 -> SUFFICIENT; 2-4 -> LIMITED)
  S2  S1 + authoritative plan/flood table, strict rules (guide OR zone; flood = top of conservation / bottom of flood)
  S3  S2 + inclusive tier (seasonal Top-of-Conservation curves, regulation-zone schedules)
  S4  S3 + tier-2 regulator evidence (TWDB conservation/dead pool; NWPS normal pool counts as flood only)
Every number is conditional on the evidence being adopted by a human-reviewed binding (rubric cannotCount) and ingested by the Engine."""
import csv, json, sys
from common import *
sys.path.insert(0, os.path.join(REPO, "research", "lake-brain")); sys.path.insert(0, os.path.join(REPO, "research", "lake-brain", "tools"))
import fleet_score as fs
from research_score import score

def run(with_flagged, min_years=5):
    rows = list(csv.DictReader(open(f"{DATA}/binding/verified.csv")))
    ok = {"VERIFIED", "VERIFIED_CORROBORATED"} | ({"VERIFIED_FLAG"} if with_flagged else set())
    prof = [r for r in rows if r["bindingStatus"] in ok]
    ty = fs.tva_years()
    ext = {r["lake"]: r for r in json.load(open(f"{PLAN}/history_ext_results.json"))}
    ev = {r["lakeId"]: r for r in csv.DictReader(open(f"{DOCS_DATA}/plan_flood_evidence.csv"))}
    T = lambda x: str(x) == "True"
    sc = {k: [] for k in ("S0", "S1", "S2", "S3", "S4")}
    for r in prof:
        c0 = fs.classify(r, ty, min_years)
        yrs = c0["years"]; hist0 = c0["hist"]; base0 = c0["base"]
        e = ext.get(r["lakeId"]); hist1, base1 = hist0, base0
        if e and e.get("status") == "EXTENDED" and r["lakeId"] not in fs.TVA_PILOTS:
            y = int(e["completeYears"]); hist1 = y >= min_years; base1 = y >= 2
        v = ev[r["lakeId"]]
        pl2 = T(v["planStrict"]); fl2 = T(v["floodStrict"]); pl3 = T(v["planInclusive"])
        fl4 = fl2 or v["tier2Flood"] == "True"; pl4 = pl3 or (v["tier2Zone"] == "True" and v["tier2Flood"] == "True")
        sc["S0"].append((c0["plan"], c0["flood"], hist0, base0))
        sc["S1"].append((c0["plan"], c0["flood"], hist1, base1))
        sc["S2"].append((pl2, fl2, hist1, base1))
        sc["S3"].append((pl3, fl2, hist1, base1))
        sc["S4"].append((pl4, fl4, hist1, base1))
    n = len(prof); out = {"profiled": n, "withFlagged": with_flagged, "minYears": min_years, "scenarios": {}}
    prev = None
    for k, L in sc.items():
        sh = {"src": 1.0, "obs": 1.0, "plan": sum(x[0] for x in L) / n, "flood": sum(x[1] for x in L) / n, "hist": sum(x[2] for x in L) / n, "base": sum(x[3] for x in L) / n}
        d = {"shares": {a: round(b, 3) for a, b in sh.items()}, "scores": {}}
        for vs in ("NOT_VALIDATED", "PARTIAL", "VALIDATED"):
            s = score(621, n, sh, vs)
            d["scores"][vs] = {"value": s["value"], "uncapped": s["uncapped"], "dims": {a: b.get("value") for a, b in s["scoreBreakdown"].items()}}
        out["scenarios"][k] = d
    return out

if __name__ == "__main__":
    res = {}
    for wf in (False, True):
        for my in (5, 10):
            res[f"flagged={wf},minYears={my}"] = run(wf, my)
    json.dump(res, open(f"{DOCS_DATA}/plan_score_deltas.json", "w"), indent=1)
    for k, r in res.items():
        print("==", k, "profiled", r["profiled"])
        for s, d in r["scenarios"].items():
            u = d["scores"]["NOT_VALIDATED"]["uncapped"]; uv = d["scores"]["VALIDATED"]["uncapped"]
            print(f"  {s} plan={d['shares']['plan']:.3f} flood={d['shares']['flood']:.3f} hist={d['shares']['hist']:.3f} base={d['shares']['base']:.3f}  uncapped(NOT_VALIDATED)={u}  uncapped(VALIDATED)={uv}  displayed(NV)={d['scores']['NOT_VALIDATED']['value']}")
