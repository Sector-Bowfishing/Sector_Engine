"""Stage 12 Part 1 scoring, exactly PREREGISTRATION_STAGE12.md section 1. AERONET-OC truth, band matching and F0 as
Stage 11 part_b.py (imported); K0 = Stage 11 ACOLITE own-mask values; K1-K4 from exp1/res. Guard: Dogliotti on each
candidate's B04 against same-day in-situ turbidity (guard.json stations). Writes exp1/score.json."""
import json, math, random, glob, os, sys, collections
import numpy as np
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
sys.path.insert(0, os.path.expanduser(__import__("os").environ["CLARITY_RESEARCH_ROOT"] + "/vendor/Sector_Engine-fusion/jobs/lake-surface"))
import derive_water_surface as dws
old = sys.argv; sys.argv = ["x"]
import importlib.util
spec = importlib.util.spec_from_file_location("pb", f"{S}/stage11/analysis/part_b.py")
# part_b.py runs on import; reuse its truth table by executing it into a namespace without writing output
ns = {"__name__": "part_b_import"}
code = open(f"{S}/stage11/analysis/part_b.py").read().split("PROCS = [")[0]
exec(compile(code, "part_b_truth", "exec"), ns)
sys.argv = old
truth_rows = {r["job"]: r for r in ns["rows"]}            # job -> {truth, proc{...}, site}
RES = {}
for f in glob.glob(f"{S}/stage12/exp1/res/*.json"):
    r = json.load(open(f)); RES[r["task"]] = r
KS = ["K0", "K1", "K2", "K3", "K4"]
def cand(job, k, key):
    if k == "K0":
        if job in truth_rows:  # Stage 11 value (own mask)
            v = truth_rows[job]["proc"].get("ACOLITE (own mask)") or {}
            return v if v else None
        r = RES.get(job, {}).get("configs", {}).get("K0", {})
    else:
        r = RES.get(job, {}).get("configs", {}).get(k, {})
    p = (r.get("points") or {}).get(key) or {}
    return p if p.get("n", 0) >= 5 and all(isinstance(p.get(b), (int, float)) and p[b] == p[b] for b in ("B02", "B03", "B04", "B05")) else None
BANDS = ("B02", "B03", "B04", "B05")
def err(v, t): return math.log10(v / t) if (v is not None and t and v > 0 and t > 0) else None
out = {"aeronet": {}, "guard": {}, "repro": {}, "feasible": {}}
jobs = sorted(truth_rows)
for k in KS:
    rec = {"valid_rate": float(np.mean([cand(j, k, "site") is not None for j in jobs])), "bands": {}}
    allv = []
    for b in BANDS:
        e = [err((cand(j, k, "site") or {}).get(b), truth_rows[j]["truth"].get(b)) for j in jobs]
        e = [x for x in e if x is not None]
        rec["bands"][b] = {"n": len(e), "median_abs_log": float(np.median(np.abs(e))) if e else None, "median_bias": float(np.median(e)) if e else None}
        allv += [abs(x) for x in e]
    vals = [(cand(j, k, "site") or {}).get(b) for j in jobs for b in BANDS if cand(j, k, "site")]
    rec["share_nonpositive"] = float(np.mean([v <= 0 for v in vals])) if vals else None
    rec["pooled_median_abs_log"] = float(np.median(allv)) if allv else None
    out["aeronet"][k] = rec
# paired vs K0 on B04 and pooled, matchup-block bootstrap
def paired(k, bands):
    pr = [(abs(err(cand(j, k, "site")[b], truth_rows[j]["truth"][b])), abs(err(cand(j, "K0", "site")[b], truth_rows[j]["truth"][b])), j)
          for j in jobs for b in bands if cand(j, k, "site") and cand(j, "K0", "site") and truth_rows[j]["truth"].get(b)
          and err(cand(j, k, "site")[b], truth_rows[j]["truth"][b]) is not None and err(cand(j, "K0", "site")[b], truth_rows[j]["truth"][b]) is not None]
    if len(pr) < 10: return None
    a = np.array([p[0] for p in pr]); z = np.array([p[1] for p in pr]); by = collections.defaultdict(list)
    for i, p in enumerate(pr): by[p[2]].append(i)
    J = sorted(by); g = random.Random(12); ds = []
    for _ in range(3000):
        idx = [i for _ in J for i in by[J[g.randrange(len(J))]]]
        ds.append(float(np.median(a[idx]) - np.median(z[idx])))
    ds.sort()
    return {"n": len(pr), "matchups": len(J), "cand": float(np.median(a)), "K0": float(np.median(z)), "diff": float(np.median(a) - np.median(z)), "ci95": [ds[75], ds[2924]]}
out["paired_B04_vs_K0"] = {k: paired(k, ("B04",)) for k in KS[1:]}
out["paired_pooled_vs_K0"] = {k: paired(k, BANDS) for k in KS[1:]}
# guard: inland turbidity
G = json.load(open(f"{S}/stage12/exp1/guard.json")); rows = {x["id"]: x for x in json.load(open(f"{S}/stage11/corpus/corpus.json"))}
def dog(r):
    r = max(r, 0.0); return float(dws.TURB_SATURATED_FNU if r >= dws.TURB_SATURATED else dws.TURB_A * r / max(1e-6, 1 - r / dws.TURB_C))
gjobs = [(j["job"], p[2]) for j in G["guard"] for p in j["points"]] + [(j["job"], p[2]) for j in G["repr"] for p in j["points"]]
S11R = json.load(open(f"{S}/stage11/ac/results_repr.json"))
def gcand(job, k, pid):
    if k == "K0" and job.startswith("rep_"):
        a = ((S11R.get(job) or {}).get("acolite") or {}).get(pid) or {}
        return a if a.get("n", 0) >= 5 else None
    return cand(job, k, pid)
for k in KS:
    e = []
    for job, pid in gjobs:
        v = gcand(job, k, pid); x = rows.get(pid)
        if v and x and x.get("turb") is not None and v.get("B04") is not None:
            e.append(math.log10(max(dog(v["B04"]), 0.1) / max(x["turb"], 0.1)))
    out["guard"][k] = {"n": len(e), "median_abs_eT": float(np.median(np.abs(e))) if e else None, "median_eT": float(np.median(e)) if e else None}
# feasibility ("fails to run"): ACOLITE error / no L2W, or an L2W with no finite water reflectance at any station of any
# scene (all-NaN output). Station-level loss of valid pixels is criterion 3, not feasibility.
for k in KS[1:]:
    tot = fail = 0; any_finite = False
    for r in RES.values():
        c = r.get("configs", {}).get(k)
        if c is None: continue
        tot += 1
        if c.get("error") or not c.get("attempts") or all(a.get("error") for a in c["attempts"]): fail += 1
        any_finite |= any((p or {}).get("n", 0) > 0 for p in (c.get("points") or {}).values())
    fs = 1.0 if not any_finite else fail / tot
    out["feasible"][k] = {"scenes": tot, "technical_failures": fail, "all_output_nan": not any_finite, "failure_share": round(fs, 3) if tot else None}
# reproducibility: K0 rerun vs Stage 11 K0
for j, r in RES.items():
    if "K0" in r.get("configs", {}) and j in truth_rows:
        a = (r["configs"]["K0"].get("points") or {}).get("site") or {}; b = truth_rows[j]["proc"].get("ACOLITE (own mask)") or {}
        out["repro"][j] = {bd: (a.get(bd), b.get(bd)) for bd in BANDS}
# eligibility and verdicts
K0 = out["aeronet"]["K0"]; elig = {}
for k in KS[1:]:
    A = out["aeronet"][k]; pb = out["paired_B04_vs_K0"][k]; fz = out["feasible"][k]
    c = {"feasible": fz["failure_share"] is not None and fz["failure_share"] <= 0.20,
         "1_B04_better_CI": bool(pb and pb["diff"] < 0 and pb["ci95"][1] < 0),
         "2_no_degradation": all(A["bands"][b]["median_abs_log"] is not None and A["bands"][b]["median_abs_log"] <= K0["bands"][b]["median_abs_log"] + 0.02 for b in ("B02", "B03", "B05")),
         "3_valid_rate": A["valid_rate"] >= K0["valid_rate"] - 0.05,
         "4_nonpositive": A["share_nonpositive"] is not None and A["share_nonpositive"] <= 0.02,
         "5_guard": out["guard"][k]["median_abs_eT"] is not None and out["guard"][k]["median_abs_eT"] <= out["guard"]["K0"]["median_abs_eT"] + 0.03}
    c["eligible"] = all(c.values()); elig[k] = c
out["eligibility"] = elig
E = [k for k in KS[1:] if elig[k]["eligible"]]
if E:
    E.sort(key=lambda k: (out["aeronet"][k]["pooled_median_abs_log"], KS.index(k)))
    best = E[0]
    for k in E[1:]:
        if out["aeronet"][k]["pooled_median_abs_log"] - out["aeronet"][best]["pooled_median_abs_log"] <= 0.005 and KS.index(k) < KS.index(best): best = k
else:
    best = "K0"
out["BEST"] = best
b0, bb = K0["bands"]["B04"]["median_bias"], out["aeronet"][best]["bands"]["B04"]["median_bias"]
out["RED_BAND_RESIDUAL_FIXED"] = "YES" if abs(bb) <= 0.05 else ("PARTIAL" if bb <= 0.7 * b0 else "NO")
json.dump(out, open(f"{S}/stage12/exp1/score.json", "w"), indent=1)
print(json.dumps({k: out[k] for k in ("BEST", "RED_BAND_RESIDUAL_FIXED", "eligibility", "feasible", "guard")}, indent=1))
for k in KS: print(k, round(out["aeronet"][k]["valid_rate"], 3), {b: (round(v["median_abs_log"], 3) if v["median_abs_log"] is not None else None, round(v["median_bias"], 3) if v["median_bias"] is not None else None, v["n"]) for b, v in out["aeronet"][k]["bands"].items()}, round(out["aeronet"][k]["pooled_median_abs_log"] or 9, 3))
