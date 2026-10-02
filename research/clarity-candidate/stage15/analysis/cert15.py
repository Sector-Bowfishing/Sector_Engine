"""Stage 15 section 9: re-score the Stage 14 certification set (unchanged; NOT blind, see PREREGISTRATION_STAGE15.md)
under the frozen Stage 15 semantics. Writes cert15.json, cert15_rows.json."""
import csv, json, glob, math, collections, sys, hashlib
import numpy as np
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
sys.path.insert(0, f"{S}/stage15/engine"); sys.path.insert(0, f"{S}/stage15/analysis"); sys.path.insert(0, f"{S}/stage14/analysis")
F15 = json.load(open(f"{S}/stage15/FREEZE_STAGE15.json"))
for p, h in F15["files"].items():
    assert hashlib.sha256(open(f"{S}/{p}", "rb").read()).hexdigest() == h, f"hash mismatch {p}"
import engine15 as E
import lib14
from lib14 import class_metrics, region, cls, CLASSES, product_rubric, decision
from lib15 import CONTAINS, op_score, op_summary
lib14.CONTAINS["Clear-to-Normal"] = {0, 1}
if "Clear-to-Normal" not in lib14.STATES: lib14.STATES.insert(1, "Clear-to-Normal")
C = f"{S}/stage14/cert"
TR = json.load(open(f"{S}/stage14/unseal/truth14.json"))
smp = [dict(r, part="NLA" if r["src"].startswith("NLA") else "SYKE") for r in csv.DictReader(open(f"{S}/stage13/cert/blind_sample13.csv"))]
smp += [dict(r, part="WQP") for r in csv.DictReader(open(f"{C}/wqp_sample.csv"))]
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
    plat = r.get("platform") or xr.get("platform") or ""
    o = E.answer15(pt.get("M0"), pt.get("M3"), sen, g(xr, "sun_elev") if xr else None, plat)
    ft = t["secchi_ft"]; c = cls(ft); sc, oc, h, sv = op_score(o, c, ft)
    rows.append({"id": r["id"], "part": r["part"], "lake": r["lake"], "state_abbr": r["state"], "date": r["date"], "platform": plat,
                 "season": "cool" if int(r["date"][5:7]) in (10, 11, 12, 1, 2, 3, 4) else "warm", "tier": o["tier"], "o": o, "p": o["p"], "c": c, "secchi": ft,
                 "y": math.log10(ft), "insitu_type": t.get("insitu_type"), "turb": t.get("turb"), "score": sc, "outcome": oc, "harmful": h, "severe": sv})
src = open(f"{S}/stage13/analysis/capscore13.py").read()
def capscore(rr):
    ns = {}
    code = src.split("rows = [r for r in")[0].replace('M = json.load(open(f"{D13}/analysis/models13.json")); ENG = M["BEST"]', 'ENG = "stage15"')
    code += "\nrows = RR\n" + "out = {" + src.split("out = {", 1)[1].split("json.dump(out")[0]
    ns["RR"] = rr; exec(code, ns); return ns["out"]
def recs(rs):
    out = []
    for r in rs:
        o = r["o"]
        if o["tier"] in (1, 2): pred = CLASSES[o["hard"]]
        elif o["state"] in CONTAINS and len(CONTAINS[o["state"]]) == 1: pred = CLASSES[list(CONTAINS[o["state"]])[0]]
        else: pred = "unknown"
        out.append({"true": CLASSES[r["c"]], "pred": pred, "ft": o["feet_shown"], "secchi": r["secchi"], "feet": o["feet_shown"] is not None, "insitu_type": r["insitu_type"],
                    "turb": r["turb"], "tier": o["tier"], "c": r["c"], "state": o["state"] if o["authority"] == "full" and o["state"] in CONTAINS else None})
    return out
def evaluate(rs, full=True):
    if not rs: return {"n": 0}
    rr = recs(rs); op = op_summary(rs)
    d = decision([r["c"] for r in rr], [r["state"] for r in rr])
    o = {"n": len(rs), "lakes": len({r["lake"] for r in rs}), "op": op, "decision_balanced": d["balanced"], "specificity": d["specificity"],
         "decision": {n: (d[n]["decision_recall"], d[n]["decision_precision"], d[n]["authority_share"]) for n in CLASSES},
         "authority": dict(collections.Counter(r["o"]["authority"] for r in rs)), "display": dict(collections.Counter(r["o"]["display"] for r in rs)),
         "states": {st: {"n": sum(1 for r in rs if r["o"]["state"] == st), "precision": float(np.mean([r["c"] in CONTAINS[st] for r in rs if r["o"]["state"] == st])) if st in CONTAINS and any(r["o"]["state"] == st for r in rs) else None,
                         "full_authority_n": sum(1 for r in rs if r["o"]["state"] == st and r["o"]["authority"] == "full")} for st in list(CONTAINS) + ["Unknown / Low Authority"]}}
    if full:
        cap = capscore(rr); pc, ps = product_rubric(rr)
        o.update({"exact_feet": cap["exact_feet"], "hard_class_rubric": cap["clarity_class"], "EXACT_FEET": cap["EXACT_FEET_CAPABILITY"], "HARD_CLASS": cap["CLARITY_CLASS_CAPABILITY"],
                  "product": pc, "PRODUCT": ps, "shares": cap["shares"]})
    return o
US = [r for r in rows if r["part"] in ("NLA", "WQP")]; SY = [r for r in rows if r["part"] == "SYKE"]
out = {"rows_total": len(rows), "US": evaluate(US), "SYKE": evaluate(SY), "breakdown": {}}
for name, key in (("platform", "platform"), ("season", "season"), ("tier", "tier"), ("source", "part")):
    gr = collections.defaultdict(list)
    for r in US: gr[str(r[key])].append(r)
    out["breakdown"][name] = {k: evaluate(v, full=False) for k, v in sorted(gr.items()) if len(v) >= 20}
# Clear-to-Normal, algal and S2C specifics
c2n = [r for r in US if r["o"]["state"] == "Clear-to-Normal"]
was = collections.Counter(r["o"]["state14"] for r in c2n)
out["clear_to_normal"] = {"n": len(c2n), "precision": float(np.mean([r["c"] in (0, 1) for r in c2n])) if c2n else None, "truth": dict(collections.Counter(CLASSES[r["c"]] for r in c2n)), "stage14_state": dict(was),
                          "normal_state_precision": out["US"]["states"]["Normal"]["precision"], "normal_state_n": out["US"]["states"]["Normal"]["n"]}
lv = lambda n: None if n is None or n <= 0.03 else ("strong" if n > 0.10 else "moderate")
alg = {}
for level in ("moderate", "strong"):
    sub = [r for r in US if r["o"]["tier"] in (1, 2) and lv(r["o"]["ndci"]) == level and r["o"]["state"] in CONTAINS]
    ins = [r for r in sub if r["insitu_type"] is not None]
    alg[level] = {"n": len(sub), "state_precision": float(np.mean([r["c"] in CONTAINS[r["o"]["state"]] for r in sub])) if sub else None,
                  "insitu_algal_share": (sum(r["insitu_type"] in ("algal", "mixed") for r in ins) / len(ins)) if ins else None, "n_insitu": len(ins)}
insa = [r for r in US if r["insitu_type"] in ("algal", "mixed") and r["o"]["tier"] in (1, 2)]
alg["insitu_algal_rows_flagged"] = (sum(1 for r in insa if lv(r["o"]["ndci"])) / len(insa)) if insa else None
out["algal"] = alg
s2c = [r for r in US if r["platform"] == "sentinel-2c"]; y25 = [r for r in US if r["date"] >= "2025-01-01"]
out["s2c"] = {"n": len(s2c), "share_us": len(s2c) / len(US), "share_2025_rows": (sum(r["platform"] == "sentinel-2c" for r in y25) / len(y25)) if y25 else None, "n_2025": len(y25),
              "lowered_from_full": sum(1 for r in s2c if r["o"]["tier"] in (1, 2)), "feet_withheld": sum(1 for r in s2c if r["o"]["display"] == "state-only"),
              "op_mean": float(np.mean([r["score"] for r in s2c])) if s2c else None, "harmful": sum(r["harmful"] for r in s2c)}
# floor sensitivity (NOT adopted): a 12+ display for predictions >= 12 ft
hi = [r for r in US if r["o"]["tier"] in (1, 2) and r["p"] >= math.log10(12)]
out["floor_sensitivity_12"] = {"n": len(hi), "P(truth>=12)": float(np.mean([r["secchi"] >= 12 for r in hi])) if hi else None, "P(truth>=6)": float(np.mean([r["secchi"] >= 6 for r in hi])) if hi else None}
U = out["US"]; op = U["op"]
out["READY_cert"] = op["score_of_10"] >= 7 and all(v["mean"] >= 0.60 for v in op["per_class"].values()) and op["harmful_rate"] <= 0.15 and op["severe_rate"] <= 0.02
json.dump(out, open(f"{S}/stage15/analysis/cert15.json", "w"), indent=1, default=str)
json.dump(rows, open(f"{S}/stage15/analysis/cert15_rows.json", "w"), default=str)
print("US op", op["score_of_10"], round(op["balanced"], 3), "harmful", round(op["harmful_rate"], 3), "severe", round(op["severe_rate"], 3), {n: round(v["mean"], 3) for n, v in op["per_class"].items()})
print("rubrics: exact feet", U["EXACT_FEET"], "hard", U["HARD_CLASS"], "product", U["PRODUCT"], "decision bal", round(U["decision_balanced"], 3))
print("product caps", {k: v["verdict"] for k, v in U["product"].items()}, "feet caps", {k: v["verdict"] for k, v in U["exact_feet"].items()})
print("C-to-N", out["clear_to_normal"]); print("algal", alg); print("S2C", out["s2c"]); print("floor sens", out["floor_sensitivity_12"]); print("READY_cert", out["READY_cert"])
print("outcomes", op["outcomes"])
