"""Stage 15 sections 2-6, 8 on DEVELOPMENT rows only. Replays the Stage 14 nested lake-held-out predictions (same folds,
same C-gbm settings; the frozen engine is not refitted), derives Clear-to-Normal, the very-clear floor and the algal
behaviour, decides adoption, and scores the final semantics. Writes dev15.json, semantics15.json."""
import json, math, collections
import numpy as np
from lib15 import *
import lib14
from lib14 import dev_rows, fit_gbm, pred_gbm, fold, cls, CLASSES
lib14.CONTAINS["Clear-to-Normal"] = {0, 1}
if "Clear-to-Normal" not in lib14.STATES: lib14.STATES.insert(1, "Clear-to-Normal")
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
E14 = json.load(open(f"{S}/stage14/engine/frozen_engine.json"))
ALL, T1, T2, REST = dev_rows(); TT = T1 + T2
X = {x["id"]: x for x in TT}
D14 = {r["id"]: r for r in json.load(open(f"{S}/stage14/analysis/dev14_rows.json"))}
inner = lambda x: fold(x["lake"], 20) % 4
# ---------------- nested replay: inner predictions per outer fold (identical procedure to dev14)
FOLD = {}
for k in range(5):
    tr = [x for x in T1 if fold(x["lake"]) != k]; ip = []
    for j in range(4):
        itr = [x for x in tr if inner(x) != j]; ite = [x for x in TT if fold(x["lake"]) != k and inner(x) == j]
        ip += list(zip(pred_gbm(fit_gbm(itr), ite), [x["y"] for x in ite]))
    b3, _ = bands_from(ip); b6, f6 = band6_from(ip)
    FOLD[k] = {"pairs": ip, "bands14": {"3ft": b3["3ft"], "2ft": b3["2ft"]}, "b6": b6}
    print("fold", k, "C-to-N band ft", [round(10 ** e, 2) for e in b6], "N-to-S", [round(10 ** e, 2) for e in b3["3ft"]], flush=True)
def floor_from(pairs):
    T = None
    for t in (10, 12, 15):
        sub = [(p, y) for p, y in pairs if p >= math.log10(t)]
        if len(sub) >= 20 and np.median([abs(p - y) for p, y in sub]) > 0.15: T = t; break
    if T is None: return None, {}
    sub = [(p, y) for p, y in pairs if p >= math.log10(T)]
    honesty = {d: float(np.mean([y >= math.log10(d) for p, y in sub])) for d in (8, 10, 12, 15) if d <= T}
    D = max([d for d, v in honesty.items() if v >= 2 / 3], default=None)
    errs = {t: float(np.median([abs(p - y) for p, y in pairs if p >= math.log10(t)])) for t in (10, 12, 15)}
    return ({"T": T, "D": D} if D else None), {"median_abs_log_above": errs, "honesty_at_T": honesty, "n_above_T": len(sub)}
# ---------------- dev rows with outer predictions
rows = []
for r in D14.values():
    x = X.get(r["id"])
    o = {"id": r["id"], "lake": r["lake"], "tier": r["tier"], "c": r["c"], "y": r["y"], "secchi": r["secchi"], "platform": r["platform"], "date": r["date"],
         "insitu_type": r["insitu_type"], "turb": r["turb"], "fold": r["fold"], "state_abbr": r.get("state_abbr")}
    if r["tier"] in (1, 2): o.update(p=r["p_gbm"], ndci=x["F"]["F_ndci"] if x else None)
    else: o.update(p=r["p3"], ndci=None, st3=r["st3"])
    rows.append(o)
pooled = [(r["p"], r["y"]) for r in rows if r["tier"] in (1, 2)]
FL, fl_diag = floor_from(pooled)
fl_nested = {k: floor_from(FOLD[k]["pairs"])[0] for k in range(5)}
print("floor", FL, fl_diag, "nested", fl_nested, flush=True)
def params(k, with6, floor, algal=None, s2c=True, algal_feet=False):
    b = dict(FOLD[k]["bands14"])
    if with6: b["6ft"] = FOLD[k]["b6"]
    return {"bands": b, "floor": floor, "algal": algal or {"moderate": "none", "strong": "none"}, "tier3_allowed": E14["tier3_allowed_states"], "algal_feet": algal_feet, "s2c": s2c}
def run(with6, floor, algal=None, s2c=True, algal_feet=False, rs=rows):
    out = []
    for r in rs:
        P = params(r["fold"], with6, floor if floor else None, algal, s2c, algal_feet)
        o = product(r["tier"], r["p"], r["platform"] if s2c else "x", r.get("ndci"), P, r.get("st3"))
        sc, oc, h, sv = op_score(o, r["c"], r["secchi"])
        out.append({**r, **{"o": o, "score": sc, "outcome": oc, "harmful": h, "severe": sv}})
    return out
# algal "none" must mean: no algal layer
_orig = product
def product(tier, p, platform, ndci, P, st3=None):
    P2 = dict(P); al = P2.get("algal") or {}
    if all(v in (None, "none") for v in al.values()): ndci = None
    return _orig(tier, p, platform, ndci, P2, st3)
# ---------------- section 2 adoption (floor applied; algal and S2C layers neutral)
A0 = run(False, FL, s2c=False); A1 = run(True, FL, s2c=False)
s0, s1 = op_summary(A0), op_summary(A1)
adopt6 = s1["balanced"] > s0["balanced"] and s1["harmful_rate"] < s0["harmful_rate"]
print("C-to-N: without", round(s0["balanced"], 4), round(s0["harmful_rate"], 4), "with", round(s1["balanced"], 4), round(s1["harmful_rate"], 4), "ADOPT", adopt6, flush=True)
# ---------------- section 4 algal behaviour (states with the adopted bands)
base = A1 if adopt6 else A0
lv = lambda n: None if n is None or n <= 0.03 else ("strong" if n > 0.10 else "moderate")
alg = {}
for level in ("moderate", "strong"):
    sub = [r for r in base if r["tier"] in (1, 2) and lv(r.get("ndci")) == level and r["o"]["state"] in CONTAINS]
    prec = float(np.mean([r["c"] in CONTAINS[r["o"]["state"]] for r in sub])) if sub else None
    beh = "modifier" if prec is not None and prec >= 0.75 else "soften" if prec is not None and prec >= 0.60 else "withhold"
    chl = [r for r in sub if r["insitu_type"] is not None]
    alg[level] = {"n": len(sub), "decision_precision": prec, "behaviour": beh, "share_insitu_algal": (sum(r["insitu_type"] in ("algal", "mixed") for r in chl) / len(chl)) if chl else None, "n_with_insitu": len(chl)}
flagged = [r for r in base if r["tier"] in (1, 2) and lv(r.get("ndci"))]
af = {"median_abs_log": float(np.median([abs(r["p"] - r["y"]) for r in flagged])), "median_signed_ft": float(np.median([10 ** r["p"] - r["secchi"] for r in flagged]))}
algal_feet = af["median_abs_log"] <= 0.20 and abs(af["median_signed_ft"]) <= 1.5
ins = [r for r in base if r["tier"] in (1, 2) and r["insitu_type"] is not None]
flag_ppv = (sum(r["insitu_type"] in ("algal", "mixed") for r in ins if lv(r.get("ndci"))) / max(1, sum(1 for r in ins if lv(r.get("ndci")))))
flag_sens = (sum(1 for r in ins if lv(r.get("ndci")) and r["insitu_type"] in ("algal", "mixed")) / max(1, sum(1 for r in ins if r["insitu_type"] in ("algal", "mixed"))))
print("algal", alg, "feet", af, algal_feet, "flag PPV", round(flag_ppv, 3), "sensitivity", round(flag_sens, 3), flush=True)
ALG = {k: v["behaviour"] for k, v in alg.items()}
# ---------------- final semantics on development rows (nested), and the layers one at a time
FINAL = run(adopt6, FL, ALG, True, algal_feet); fs = op_summary(FINAL)
steps = {"Stage 14 states": op_summary(run(False, None, s2c=False)), "+ floor": s0, "+ Clear-to-Normal": s1,
         "+ algal": op_summary(run(adopt6, FL, ALG, False, algal_feet)), "+ S2C lower authority (final)": fs}
s2c_dev = [r for r in rows if r["platform"] == "sentinel-2c" and r["tier"] in (1, 2)]
s2c_diag = {"n": len(s2c_dev), "median_signed_log": float(np.median([r["p"] - r["y"] for r in s2c_dev])) if s2c_dev else None,
            "median_abs_log": float(np.median([abs(r["p"] - r["y"]) for r in s2c_dev])) if s2c_dev else None,
            "others_median_signed_log": float(np.median([r["p"] - r["y"] for r in rows if r["platform"] != "sentinel-2c" and r["tier"] in (1, 2)])),
            "share_rows": len([r for r in rows if r["platform"] == "sentinel-2c"]) / len(rows)}
# ---------------- production parameters (pooled development)
prod_b6, prod_f6 = band6_from(pooled)
SEM = {"engine": "Stage 14 frozen C-gbm (unchanged)", "bands": {"6ft": list(prod_b6) if adopt6 else None, "3ft": E14["bands"]["3ft"], "2ft": E14["bands"]["2ft"]},
       "bands_ft": {"6ft": [10 ** e for e in prod_b6] if adopt6 else None, "3ft": E14["bands_ft"]["3ft"], "2ft": E14["bands_ft"]["2ft"]}, "band6_fit": prod_f6,
       "clear_to_normal_adopted": adopt6, "floor": FL, "algal": ALG, "algal_feet_shown": algal_feet, "s2c_lower_authority": True, "tier3_allowed": E14["tier3_allowed_states"]}
json.dump(SEM, open(f"{S}/stage15/engine/semantics15.json", "w"), indent=1)
ready_dev = fs["score_of_10"] >= 7 and all(v["mean"] >= 0.60 for v in fs["per_class"].values()) and fs["harmful_rate"] <= 0.15 and fs["severe_rate"] <= 0.02
out = {"floor": FL, "floor_diag": fl_diag, "floor_nested": fl_nested, "c2n_without": s0, "c2n_with": s1, "adopt_c2n": adopt6, "algal": alg, "algal_feet": af,
       "algal_feet_shown": algal_feet, "flag_ppv": flag_ppv, "flag_sensitivity": flag_sens, "final": fs, "steps": steps, "s2c_dev": s2c_diag, "ready_dev": ready_dev,
       "semantics": SEM, "nested_b6_ft": {k: [10 ** e for e in FOLD[k]["b6"]] for k in range(5)}}
json.dump(out, open(f"{S}/stage15/analysis/dev15.json", "w"), indent=1, default=str)
json.dump([{k: v for k, v in r.items()} for r in FINAL], open(f"{S}/stage15/analysis/dev15_rows.json", "w"), default=str)
print("C-to-N production band ft", [round(10 ** e, 2) for e in prod_b6], prod_f6)
for k, v in steps.items(): print(f"{k:32s} op {v['score_of_10']}/10 bal {v['balanced']:.3f} harmful {v['harmful_rate']:.3f} severe {v['severe_rate']:.3f}", {n: round(c['mean'], 3) for n, c in v['per_class'].items()})
print("S2C dev", s2c_diag, "READY(dev)", ready_dev)
