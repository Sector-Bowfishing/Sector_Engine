"""Stage 14 section 7: score the frozen engine ONCE on the certification set (US core = NLA + WQP; SYKE apart).
Inputs: frozen engine (engine/), ACOLITE samples (cert/res_ns, cert/res_wqp), Sen2Cor readouts and sun elevation from the
match outputs, truth14.json. Writes cert14.json and cert14_rows.json."""
import csv, json, glob, math, collections, sys
import numpy as np
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
sys.path.insert(0, f"{S}/stage14/engine"); sys.path.insert(0, f"{S}/stage14/analysis")
import engine14 as EN
from lib14 import *
C = f"{S}/stage14/cert"
TR = json.load(open(f"{S}/stage14/unseal/truth14.json"))
smp = [dict(r, part="NLA" if r["src"].startswith("NLA") else "SYKE") for r in csv.DictReader(open(f"{S}/stage13/cert/blind_sample13.csv"))]
smp += [dict(r, part="WQP") for r in csv.DictReader(open(f"{C}/wqp_sample.csv"))]
# Sen2Cor readouts + sun elevation: the matched pass (same id and item)
OUTS = sorted(glob.glob(f"{S}/stage12/cert/out_*.csv")) + [f"{S}/stage13/cert/out13_c1.csv", f"{S}/stage13/cert/out13_legacy.csv", f"{C}/out_wqp_c1.csv", f"{C}/out_wqp_legacy.csv"]
want = {(r["id"], r["item"]) for r in smp}; X = {}
for p in OUTS:
    if "discarded" in p: continue
    for r in csv.DictReader(open(p)):
        k = (r["id"], r.get("item"))
        if k in want and not r.get("error"):
            try: nv = int(float(r.get("n_valid") or 0))
            except ValueError: continue
            if k not in X or nv > X[k][0]: X[k] = (nv, r)
A = {}
for f in glob.glob(f"{C}/res_ns/*.json") + glob.glob(f"{C}/res_wqp/*.json"):
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
    sun = g(xr, "sun_elev") if xr else None
    plat = r.get("platform") or xr.get("platform") or ""
    a = EN.answer(pt.get("M0"), pt.get("M3"), sen, sun, plat)
    ft = t["secchi_ft"]; c = cls(ft)
    rows.append({"id": r["id"], "part": r["part"], "lake": r["lake"], "state_abbr": r["state"], "region": region(r["state"]) if r["part"] != "SYKE" else "FI",
                 "season": "cool" if int(r["date"][5:7]) in (10, 11, 12, 1, 2, 3, 4) else "warm", "platform": plat, "date": r["date"],
                 "strict": r.get("strict") == "True", "aco_done": bool(pt), "tier": a["tier"], "authority": a["authority"], "p": a["p"], "hard": a["hard"],
                 "state": a["state"], "feet": a["feet"], "interval": a["interval_ft"], "secchi": ft, "y": math.log10(ft), "c": c,
                 "chl": t.get("chl"), "turb": t.get("turb"), "insitu_type": t.get("insitu_type")})
def recs(rs):
    out = []
    for r in rs:
        auth = r["authority"] == "ACOLITE"; st = r["state"] if r["state"] in CONTAINS else None
        if auth: pred = CLASSES[r["hard"]]
        elif st and len(CONTAINS[st]) == 1: pred = CLASSES[list(CONTAINS[st])[0]]
        else: pred = "unknown"
        out.append({"true": CLASSES[r["c"]], "pred": pred, "ft": r["feet"], "secchi": r["secchi"], "feet": r["feet"] is not None, "insitu_type": r["insitu_type"],
                    "turb": r["turb"], "tier": r["tier"], "c": r["c"], "state": st if auth else None})
    return out
src = open(f"{S}/stage13/analysis/capscore13.py").read()
def capscore(rr):
    ns = {}
    code = src.split("rows = [r for r in")[0].replace('M = json.load(open(f"{D13}/analysis/models13.json")); ENG = M["BEST"]', 'ENG = "stage14"')
    code += "\nrows = RR\n" + "out = {" + src.split("out = {", 1)[1].split("json.dump(out")[0]
    ns["RR"] = rr; exec(code, ns); return ns["out"]
def evaluate(rs, full=True):
    if not rs: return {"n": 0}
    rr = recs(rs); a12 = [r for r in rs if r["authority"] == "ACOLITE"]
    d = decision([r["c"] for r in rs], [r["state"] if r["authority"] == "ACOLITE" else None for r in rs])
    cm = class_metrics([r["c"] for r in rs], [r["hard"] if r["authority"] == "ACOLITE" else None for r in rs])
    fe = [r for r in rs if r["feet"] is not None]
    o = {"n": len(rs), "lakes": len({r["lake"] for r in rs}), "classes": dict(collections.Counter(CLASSES[r["c"]] for r in rs)),
         "insitu": dict(collections.Counter(r["insitu_type"] for r in rs)), "tiers": dict(collections.Counter(r["tier"] for r in rs)),
         "decision_balanced": d["balanced"], "specificity": d["specificity"],
         "decision": {n: (d[n]["decision_recall"], d[n]["decision_precision"], d[n]["authority_share"], d[n]["n"]) for n in CLASSES},
         "by_state": d["by_state"], "hard": {n: (cm[n]["recall"], cm[n]["precision"]) for n in CLASSES} | {"balanced": cm["balanced_accuracy"], "qwk": cm.get("qwk")},
         "feet_median_abs_log": float(np.median([abs(math.log10(r["feet"] / r["secchi"])) for r in fe])) if fe else None,
         "feet_by_class": {CLASSES[c]: (float(np.median([abs(math.log10(r["feet"] / r["secchi"])) for r in fe if r["c"] == c])),
                                        float(np.median([r["feet"] - r["secchi"] for r in fe if r["c"] == c])), sum(1 for r in fe if r["c"] == c))
                           for c in range(4) if any(r["c"] == c for r in fe)},
         "interval_coverage": float(np.mean([r["interval"][0] <= r["secchi"] <= r["interval"][1] for r in a12])) if a12 else None}
    if full:
        cap = capscore(rr); pc, ps = product_rubric(rr)
        o.update({"exact_feet": cap["exact_feet"], "hard_class_rubric": cap["clarity_class"], "EXACT_FEET": cap["EXACT_FEET_CAPABILITY"],
                  "HARD_CLASS": cap["CLARITY_CLASS_CAPABILITY"], "product": pc, "PRODUCT": ps, "shares": cap["shares"]})
    return o
US = [r for r in rows if r["part"] in ("NLA", "WQP")]; SY = [r for r in rows if r["part"] == "SYKE"]
out = {"rows_total": len(rows), "missing_aco": sum(1 for r in rows if not r["aco_done"]), "US": evaluate(US), "SYKE": evaluate(SY)}
out["breakdown"] = {}
for name, key in (("source", "part"), ("tier", "tier"), ("platform", "platform"), ("season", "season"), ("region", "region")):
    groups = collections.defaultdict(list)
    for r in US: groups[str(r[key])].append(r)
    out["breakdown"][name] = {k: evaluate(v, full=False) for k, v in sorted(groups.items()) if len(v) >= 20}
out["breakdown"]["strict_subset"] = {"strict WQP + NLA": evaluate([r for r in US if r["part"] == "NLA" or r["strict"]], full=False),
                                     "non-strict WQP": evaluate([r for r in US if r["part"] == "WQP" and not r["strict"]], full=False)}
# minima and readiness lines (protocol section 5; prereg section 7)
MIN = {"clear": 40, "normal": 40, "stained": 60, "algae": 30, "sediment": 20, "limited": 25}
cnt = dict(collections.Counter(CLASSES[r["c"]] for r in US)); cnt["algae"] = sum(1 for r in US if r["insitu_type"] in ("algal", "mixed")); cnt["sediment"] = sum(1 for r in US if r["insitu_type"] == "sediment")
insuff = {k: cnt.get(k, 0) < v for k, v in MIN.items()}
U = out["US"]
def yn(v, k): return "NO (insufficient)" if insuff[k] else {"SUPPORTED": "YES", "PARTIAL": "PARTIAL"}.get(v, "NO")
lines = {"CLEAR FEET READY": yn(U["exact_feet"]["clear"]["verdict"], "clear"), "NORMAL READY": yn(U["product"]["normal"]["verdict"], "normal"),
         "STAINED READY": yn(U["product"]["stained"]["verdict"], "stained"), "LIMITED READY": yn(U["product"]["limited"]["verdict"], "limited"),
         "ALGAL READY": yn(U["product"]["algae"]["verdict"], "algae"), "SEDIMENT READY": yn(U["product"]["sediment"]["verdict"], "sediment")}
pts = sum(1.0 if v == "YES" else 0.5 if v == "PARTIAL" else 0 for v in lines.values())
out["readiness_lines"] = lines; out["counts_vs_minima"] = {k: (cnt.get(k, 0), MIN[k]) for k in MIN}
out["PASSED"] = "YES" if all(v == "YES" for v in lines.values()) else "PARTIAL" if pts >= 3 else "NO"; out["pass_points"] = pts
json.dump(out, open(f"{S}/stage14/analysis/cert14.json", "w"), indent=1, default=str)
json.dump(rows, open(f"{S}/stage14/analysis/cert14_rows.json", "w"), default=str)
print(json.dumps({k: out[k] for k in ("rows_total", "missing_aco", "readiness_lines", "PASSED", "counts_vs_minima")}, indent=1))
print("US", {k: U[k] for k in ("n", "lakes", "tiers", "decision_balanced", "specificity", "EXACT_FEET", "HARD_CLASS", "PRODUCT")})
