"""Stage 16 section 5-6: score the frozen product ONCE on the fresh holdout. Also scores the Stage 15 semantics on the
same rows for comparison (not a selection). Writes score16.json, score16_rows.json."""
import csv, json, glob, math, collections, sys, hashlib
import numpy as np
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
D = f"{S}/stage16/fresh"
F = json.load(open(f"{S}/stage16/FREEZE_STAGE16.json"))
for p, h in F["files"].items():
    assert hashlib.sha256(open(f"{S}/{p}", "rb").read()).hexdigest() == h, f"hash mismatch {p}"
sys.path.insert(0, f"{S}/stage16/engine"); sys.path.insert(0, f"{S}/stage15/engine"); sys.path.insert(0, f"{S}/stage16/analysis")
import engine16 as E16, engine15 as E15
from lib16 import CONTAINS, op_score, op_summary, evidence, CLASSES
from lib14 import cls
TR = json.load(open(f"{D}/truth16.json")); smp = list(csv.DictReader(open(f"{D}/fresh_sample.csv")))
X = {}
for r in csv.DictReader(open(f"{D}/out_fresh_c1.csv")):
    k = (r["id"], r.get("item"))
    if not r.get("error"):
        try: nv = int(float(r.get("n_valid") or 0))
        except ValueError: continue
        if k not in X or nv > X[k][0]: X[k] = (nv, r)
A = {}
for f in glob.glob(f"{D}/res_fresh/*.json"):
    r = json.load(open(f))
    for c in r.get("crops", []):
        for pid, pt in (c.get("points") or {}).items(): A[(pid, r["item"])] = pt
g = lambda r, k: float(r[k]) if r.get(k) not in (None, "") else None
rows = []
for r in smp:
    t = TR.get(r["id"]) or {}
    if not t.get("secchi_ft"): continue
    xr = X.get((r["id"], r["item"]), (0, {}))[1]; pt = A.get((r["id"], r["item"])) or {}
    sen = {"blue": g(xr, "rho_blue_v"), "green": g(xr, "rho_green_v"), "red": g(xr, "rho_red_v"), "re1": g(xr, "rho_rededge1_v"), "swir16": g(xr, "rho_swir16_v")} if xr else None
    sun, plat = (g(xr, "sun_elev") if xr else None), r["platform"]
    o = E16.answer16(pt.get("M0"), pt.get("M3"), sen, sun, plat); o15 = E15.answer15(pt.get("M0"), pt.get("M3"), sen, sun, plat)
    ft = t["secchi_ft"]; c = cls(ft); sc, oc, h, sv = op_score(o, c, ft); sc15, oc15, h15, sv15 = op_score(o15, c, ft)
    rows.append({"id": r["id"], "lake": r["lake"], "state_abbr": r["state"], "date": r["date"], "platform": plat, "strict": r["strict"] == "True",
                 "season": "cool" if int(r["date"][5:7]) in (10, 11, 12, 1, 2, 3, 4) else "warm", "tier": o["tier"], "o": o, "p": o["p"], "c": c, "secchi": ft,
                 "y": math.log10(ft), "insitu_type": t.get("insitu_type"), "turb": t.get("turb"), "score": sc, "outcome": oc, "harmful": h, "severe": sv,
                 "s15": {"score": sc15, "outcome": oc15, "harmful": h15, "severe": sv15, "state": o15["state"]}, "aco_done": bool(pt)})
src = open(f"{S}/stage13/analysis/capscore13.py").read()
def capscore(rr):
    ns = {}
    code = src.split("rows = [r for r in")[0].replace('M = json.load(open(f"{D13}/analysis/models13.json")); ENG = M["BEST"]', 'ENG = "stage16"')
    code += "\nrows = RR\n" + "out = {" + src.split("out = {", 1)[1].split("json.dump(out")[0]
    ns["RR"] = rr; exec(code, ns); return ns["out"]
def recs(rs):
    out = []
    for r in rs:
        o = r["o"]
        if o["tier"] in (1, 2): pred = CLASSES[o["hard"]]
        elif o["state"] in CONTAINS and len(CONTAINS[o["state"]]) == 1: pred = CLASSES[list(CONTAINS[o["state"]])[0]]
        else: pred = "unknown"
        out.append({"true": CLASSES[r["c"]], "pred": pred, "ft": o["feet_shown"], "secchi": r["secchi"], "feet": o["feet_shown"] is not None, "insitu_type": r["insitu_type"], "turb": r["turb"]})
    return out
def evaluate(rs, full=False):
    if not rs: return {"n": 0}
    op = op_summary(rs); ev = collections.defaultdict(list)
    for r in rs: ev[r["o"]["evidence"]].append(r)
    o = {"n": len(rs), "lakes": len({r["lake"] for r in rs}), "op": op, "classes": dict(collections.Counter(CLASSES[r["c"]] for r in rs)),
         "evidence": {e: {"n": len(v), "share": len(v) / len(rs), "containment": float(np.mean([r["c"] in CONTAINS[r["o"]["state"]] for r in v])) if e != "unavailable" else None} for e, v in ev.items()},
         "states": {s: {"n": n, "right": float(np.mean([r["c"] in CONTAINS[s] for r in rs if r["o"]["state"] == s])) if s in CONTAINS else None} for s, n in collections.Counter(r["o"]["state"] for r in rs).items()},
         "stage15_semantics": op_summary([{**r["s15"], "c": r["c"]} for r in rs])}
    if full:
        cap = capscore(recs(rs)); o.update({"exact_feet": cap["exact_feet"], "EXACT_FEET": cap["EXACT_FEET_CAPABILITY"], "hard_class": cap["clarity_class"], "HARD_CLASS": cap["CLARITY_CLASS_CAPABILITY"], "shares": cap["shares"]})
    return o
out = {"n_sample": len(smp), "n_scored": len(rows), "missing_aco": sum(1 for r in rows if not r["aco_done"]), "ALL": evaluate(rows, True), "breakdown": {}}
for name, fn in (("platform", lambda r: r["platform"]), ("tier", lambda r: str(r["tier"])), ("strict", lambda r: "strict" if r["strict"] else "same-lake"),
                 ("wisconsin", lambda r: "WI" if r["state_abbr"] == "WI" else "outside WI"), ("season", lambda r: r["season"])):
    gr = collections.defaultdict(list)
    for r in rows: gr[fn(r)].append(r)
    out["breakdown"][name] = {k: evaluate(v) for k, v in sorted(gr.items()) if len(v) >= 10}
MIN = {"clear": 40, "normal": 40, "stained": 60, "limited": 25}
cnt = out["ALL"]["classes"]; insuff = [k for k, v in MIN.items() if cnt.get(k, 0) < v] + (["total"] if len(rows) < 200 else [])
op = out["ALL"]["op"]; ev = out["ALL"]["evidence"]
lvl = lambda e, bar: (ev.get(e, {}).get("n", 0) >= 30 and (ev[e]["containment"] or 0) >= bar)
safe = "YES" if lvl("strong", 0.90) and lvl("moderate", 0.80) and lvl("weak", 0.65) else "PARTIAL" if lvl("strong", 0.90) and lvl("moderate", 0.80) else "NO"
s2 = [r for r in rows if r["platform"] == "sentinel-2c" and r["tier"] in (1, 2)]; s2ab = [r for r in rows if r["platform"] != "sentinel-2c" and r["tier"] in (1, 2)]
out["s2c_evidence"] = {"n_tiers12": len(s2), "median_signed_log": float(np.median([r["p"] - r["y"] for r in s2])) if s2 else None,
                       "s2ab_median_signed_log": float(np.median([r["p"] - r["y"] for r in s2ab])) if s2ab else None,
                       "lift_criterion_met_if_scored": bool(len(s2) >= 60 and s2 and abs(float(np.median([r["p"] - r["y"] for r in s2]))) <= 0.05)}
dev_ready = json.load(open(f"{S}/stage16/analysis/dev16.json"))["ready_dev"]
fresh_ready = (not insuff) and op["score_of_10"] >= 7 and all((v["mean"] or 0) >= 0.60 for v in op["per_class"].values()) and op["harmful_rate"] <= 0.15 and op["severe_rate"] <= 0.02
stretch = {"op>=9": op["score_of_10"] >= 9, "classes>=0.80": all((v["mean"] or 0) >= 0.80 for v in op["per_class"].values()), "harmful<=5%": op["harmful_rate"] <= 0.05,
           "severe<=0.5%": op["severe_rate"] <= 0.005, "strong>=50%": ev.get("strong", {}).get("share", 0) >= 0.50}
out.update({"minima": MIN, "insufficient": insuff, "SAFE_SI": safe, "fresh_ready": fresh_ready, "dev_ready": dev_ready, "READY": fresh_ready and dev_ready, "stretch": stretch})
json.dump(out, open(f"{S}/stage16/analysis/score16.json", "w"), indent=1, default=str)
json.dump(rows, open(f"{S}/stage16/analysis/score16_rows.json", "w"), default=str)
print(json.dumps({k: out[k] for k in ("n_sample", "n_scored", "missing_aco", "insufficient", "SAFE_SI", "fresh_ready", "dev_ready", "READY", "stretch")}, indent=1))
print("classes", cnt, "op", op["score_of_10"], round(op["balanced"], 3), "harm", round(op["harmful_rate"], 3), "sev", round(op["severe_rate"], 3), {n: (v["n"], v["mean"] and round(v["mean"], 3)) for n, v in op["per_class"].items()})
print("evidence", ev); print("exact feet", out["ALL"]["EXACT_FEET"], {k: v["verdict"] for k, v in out["ALL"]["exact_feet"].items()})
print("stage15 semantics on fresh", round(out["ALL"]["stage15_semantics"]["balanced"], 3), round(out["ALL"]["stage15_semantics"]["harmful_rate"], 3))
print("S2C", out["s2c_evidence"])
