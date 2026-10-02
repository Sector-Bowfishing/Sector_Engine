"""Stage 14 sections 2-6 and 9 on DEVELOPMENT rows only (PREREGISTRATION_STAGE14.md). Nested lake-held-out: outer
5 whole-lake folds; bands, cut-points, feet authorisation and tier-3 bands fitted on inner folds of the training lakes.
Writes dev14.json (comparison, tier-3 rule, clear diagnostic, historical capabilities) and dev14_rows.json."""
import json, math, collections, random
import numpy as np
from lib14 import *
ALL, T1, T2, REST = dev_rows()
TT = T1 + T2
print(len(ALL), "rows:", len(T1), "tier1,", len(T2), "tier2,", len(REST), "tier3/unknown", flush=True)
inner = lambda x: fold(x["lake"], 20) % 4
R = {}
for k in range(5):
    tr = [x for x in T1 if fold(x["lake"]) != k]
    te = [x for x in TT if fold(x["lake"]) == k]; te3 = [x for x in REST if fold(x["lake"]) == k]
    g, bl = fit_gbm(tr), fit_lin(tr)
    pg, pl = pred_gbm(g, te), pred_lin(bl, te)
    # inner folds of the training lakes: predictions for bands, O2 cut-points, feet authorisation, interval
    ipg, ipl, ic = [], [], []
    for j in range(4):
        itr = [x for x in tr if inner(x) != j]; ite = [x for x in TT if fold(x["lake"]) != k and inner(x) == j]
        gi, bi = fit_gbm(itr), fit_lin(itr)
        ipg += list(zip(pred_gbm(gi, ite), [x["y"] for x in ite], [x["secchi"] for x in ite], [x["tier"] for x in ite]))
        ipl += list(zip(pred_lin(bi, ite), [x["y"] for x in ite], [x["secchi"] for x in ite], [x["tier"] for x in ite]))
    cuts = L.learn_cuts([p for p, y, s, t in ipl if t == 1], [cls(s) for p, y, s, t in ipl if t == 1])        # Stage 13 O2 rule (tier-1 inner rows)
    bg, fg = bands_from([(p, y) for p, y, s, t in ipg]); blb, flb = bands_from([(p, y) for p, y, s, t in ipl])
    o2hard = lambda p, cuts=cuts: 0 if p >= cuts[0] else 1 if p >= cuts[1] else 2 if p >= cuts[2] else 3
    auth_g = authorise({c: [(p, y, s) for p, y, s, t in ipg if hard_std(p) == c] for c in range(4)})
    auth_l = authorise({c: [(p, y, s) for p, y, s, t in ipl if hard_std(p) == c] for c in range(4)})
    auth_o2 = authorise({c: [(p, y, s) for p, y, s, t in ipl if o2hard(p) == c] for c in range(4)})
    qg = np.quantile([y - p for p, y, s, t in ipg], [1 / 6, 5 / 6]); ql = np.quantile([y - p for p, y, s, t in ipl], [1 / 6, 5 / 6])
    # tier 3: C3 on Sen2Cor, fitted on all training rows (coverage13); inner tier-3 predictions for tier-3 bands
    b3 = fit_c3s([x for x in ALL if fold(x["lake"]) != k]); p3 = pred_c3s(b3, te3)
    i3 = []
    for j in range(4):
        bj = fit_c3s([x for x in ALL if fold(x["lake"]) != k and inner(x) != j]); ite = [x for x in REST if fold(x["lake"]) != k and inner(x) == j]
        i3 += list(zip(pred_c3s(bj, ite), [math.log10(x["secchi"]) for x in ite]))
    b3b, f3b = bands_from(i3)
    for x, a, b in zip(te, pg, pl):
        R[x["id"]] = {"id": x["id"], "lake": x["lake"], "tier": x["tier"], "c": x["c"], "y": x["y"], "secchi": x["secchi"], "state_abbr": x.get("state"),
                      "date": x["date"], "platform": x["platform"], "insitu_type": x["insitu_type"], "turb": x.get("turb"),
                      "p_gbm": a, "p_lin": b, "o2": o2hard(b),
                      "st_gbm": state_of(a, bg), "st_o2": state_of(b, blb, o2hard), "st_lin": state_of(b, blb),
                      "feet_gbm": CLASSES[hard_std(a)] in auth_g, "feet_o2": CLASSES[o2hard(b)] in auth_o2, "feet_lin": CLASSES[hard_std(b)] in auth_l,
                      "in_int_gbm": a + qg[0] <= x["y"] <= a + qg[1], "in_int_lin": b + ql[0] <= x["y"] <= b + ql[1], "fold": k}
    for x, v in zip(te3, p3):
        R[x["id"]] = {"id": x["id"], "lake": x["lake"], "tier": 3, "c": cls(x["secchi"]), "y": math.log10(x["secchi"]), "secchi": x["secchi"],
                      "state_abbr": x.get("state"), "date": x["date"], "platform": x["platform"], "insitu_type": x["insitu_type"], "turb": x.get("turb"),
                      "p3": v, "st3": state_of(v, b3b), "fold": k}
    print("fold", k, "cuts ft", [round(10 ** c, 2) for c in cuts], "bands gbm", {n: [round(10 ** e, 2) for e in v] for n, v in bg.items()},
          "auth gbm", auth_g, "o2", auth_o2, "tier3 bands", {n: [round(10 ** e, 2) for e in v] for n, v in b3b.items()}, flush=True)
rows = list(R.values()); r12 = [r for r in rows if r["tier"] in (1, 2)]; r3 = [r for r in rows if r["tier"] == 3]
out = {"n": {"tiers12": len(r12), "tier3": len(r3), "all": len(rows)}}
# ---------------- section 4 comparison
def summary(key_state, key_p, key_hard=None):
    d = decision([r["c"] for r in r12], [r[key_state] for r in r12])
    hard = [r[key_hard] if key_hard else hard_std(r[key_p]) for r in r12]
    cm = class_metrics([r["c"] for r in r12], hard)
    incons = float(np.mean([hard_std(r[key_p]) not in CONTAINS[r[key_state]] for r in r12]))
    err = float(np.median([abs(r[key_p] - r["y"]) for r in r12]))
    return {"decision": d, "hard": {n: (cm[n]["recall"], cm[n]["precision"]) for n in CLASSES} | {"balanced": cm["balanced_accuracy"], "qwk": cm.get("qwk")},
            "inconsistency": incons, "median_abs_log": err, "factor": 10 ** err}
out["compare"] = {"C-gbm": summary("st_gbm", "p_gbm"), "O2": summary("st_o2", "p_lin", "o2"), "C-lin (reference)": summary("st_lin", "p_lin")}
diff = lambda rs: bal_decision(rs, "st_o2") - bal_decision(rs, "st_gbm")
ci = lake_boot_diff(r12, diff, B=2000, seed=14)
out["compare"]["O2_minus_Cgbm_decision_balanced"] = {"value": diff(r12), "ci95": ci}
o2_wins = diff(r12) >= 0.03 and ci is not None and ci[0] > 0
SEL = "O2" if o2_wins else "C-gbm"; out["SELECTED"] = SEL
KS, KP, KF = ("st_o2", "p_lin", "feet_o2") if SEL == "O2" else ("st_gbm", "p_gbm", "feet_gbm")
out["interval_coverage_dev"] = {"C-gbm": float(np.mean([r["in_int_gbm"] for r in r12])), "C-lin": float(np.mean([r["in_int_lin"] for r in r12]))}
# ---------------- section 6 tier 3
d3 = decision([r["c"] for r in r3], [r["st3"] for r in r3])
allowed = [st for st, v in d3["by_state"].items() if v["n"] >= 15 and v["precision"] >= 0.75]
hard3 = [hard_std(r["p3"]) for r in r3]; cm3 = class_metrics([r["c"] for r in r3], hard3)
feet3 = {}
for c, name in enumerate(CLASSES):
    sub = [r for r in r3 if r["st3"] == HARD_STATE[c]]
    if len(sub) >= 10:
        feet3[name] = {"n": len(sub), "median_abs_log": float(np.median([abs(r["p3"] - r["y"]) for r in sub])), "median_signed_ft": float(np.median([10 ** r["p3"] - r["secchi"] for r in sub]))}
PBAR = {"clear": 2.5, "normal": 1.5, "stained": 1.0, "limited": 1.0}
feet3_ok = [n for n, v in feet3.items() if HARD_STATE[CLASSES.index(n)] in allowed and v["median_abs_log"] <= 0.20 and abs(v["median_signed_ft"]) <= PBAR[n]]
beh = ("Unknown" if not allowed else
       ("lower-confidence feet" if feet3_ok else "class only") if all(len(CONTAINS[s]) == 1 for s in allowed) else
       "broad boundary state" + (" + class" if any(len(CONTAINS[s]) == 1 for s in allowed) else ""))
out["tier3"] = {"n": len(r3), "decision_states": d3, "hard_class": {n: (cm3[n]["recall"], cm3[n]["precision"]) for n in CLASSES} | {"balanced": cm3["balanced_accuracy"]},
                "feet_by_state": feet3, "allowed_states": allowed, "feet_shown_for": feet3_ok, "behaviour": beh,
                "covered_by_allowed": sum(1 for r in r3 if r["st3"] in allowed) / len(r3)}
# ---------------- section 5 clear diagnostic (selected engine, tiers 1-2)
cl = [r for r in r12 if r["secchi"] >= 6]
BINS = [(6, 8), (8, 10), (10, 13), (13, 20), (20, 99)]
tot = sum(10 ** r[KP] - r["secchi"] for r in cl); totneg = sum(min(0, 10 ** r[KP] - r["secchi"]) for r in cl)
bins = {}
for a, b in BINS:
    sub = [r for r in cl if a <= r["secchi"] < b]
    if sub:
        bins[f"{a}-{b if b < 99 else ''}"] = {"n": len(sub), "median_signed_ft": float(np.median([10 ** r[KP] - r["secchi"] for r in sub])),
                                              "median_signed_log": float(np.median([r[KP] - r["y"] for r in sub])),
                                              "share_of_negative_ft": sum(min(0, 10 ** r[KP] - r["secchi"]) for r in sub) / totneg if totneg else None}
predhi = [r for r in r12 if r[KP] >= L6]
slope_t = np.polyfit([r["y"] for r in cl], [r[KP] - r["y"] for r in cl], 1)[0]      # signed log error vs log truth
slope_p = np.polyfit([r[KP] for r in r12], [r["y"] - r[KP] for r in r12], 1)[0]     # residual vs prediction (calibration)
deep = [v for k, v in bins.items() if k.startswith(("13", "20"))]; typ = [v for k, v in bins.items() if k.startswith(("6-", "8-"))]
fm = [v["median_signed_ft"] for v in bins.values()]; lm = [v["median_signed_log"] for v in bins.values()]
overall = float(np.median([10 ** r[KP] - r["secchi"] for r in cl]))
tests = {"tail_problem": all(abs(v["median_signed_ft"]) <= 1.5 for v in typ) and all(v["median_signed_ft"] <= -3 for v in deep),
         "concentrated_deep": sum(v["share_of_negative_ft"] for v in deep) > 0.5,
         "constant_bias": (max(fm) - min(fm)) <= 1.0 and abs(overall) > 1.0,
         "proportional": (max(lm) - min(lm)) <= 0.05 and (max(fm) - min(fm)) > 1.0}
out["clear"] = {"n": len(cl), "median_signed_ft": overall, "median_signed_log": float(np.median([r[KP] - r["y"] for r in cl])), "bins": bins,
                "pred_ge6": {"n": len(predhi), "median_true_minus_pred_ft": float(np.median([r["secchi"] - 10 ** r[KP] for r in predhi])),
                             "median_true_minus_pred_log": float(np.median([r["y"] - r[KP] for r in predhi]))},
                "slope_signed_log_on_log_truth_clear": float(slope_t), "slope_residual_on_prediction_all": float(slope_p), "tests": tests}
# ---------------- section 9 historical capabilities (selected engine; tiers 1-3, tier 3 per the section 6 rule)
def recs_for(key_state, key_p, key_feet, key_hard=None):
    rr = []
    for r in rows:
        if r["tier"] in (1, 2):
            hc = r[key_hard] if key_hard else hard_std(r[key_p])
            rr.append({"true": CLASSES[r["c"]], "pred": CLASSES[hc], "ft": 10 ** r[key_p], "secchi": r["secchi"], "feet": r[key_feet], "insitu_type": r["insitu_type"],
                       "turb": r["turb"], "tier": r["tier"], "c": r["c"], "state": r[key_state], "state_any": r[key_state]})
        else:
            ok = r["st3"] in allowed; single = ok and len(CONTAINS[r["st3"]]) == 1
            pred = CLASSES[list(CONTAINS[r["st3"]])[0]] if single else "unknown"
            rr.append({"true": CLASSES[r["c"]], "pred": pred, "ft": 10 ** r["p3"] if (single and pred in feet3_ok) else None, "secchi": r["secchi"],
                       "feet": bool(single and pred in feet3_ok), "insitu_type": r["insitu_type"], "turb": r["turb"], "tier": 3, "c": r["c"],
                       "state": None, "state_any": r["st3"] if ok else None})
    return rr
src = open(f"{S}/stage13/analysis/capscore13.py").read()
def capscore(rr):
    ns = {}
    code = src.split("rows = [r for r in")[0].replace('M = json.load(open(f"{D13}/analysis/models13.json")); ENG = M["BEST"]', 'ENG = "stage14"')
    code += "\nrows = RR\n" + "out = {" + src.split("out = {", 1)[1].split("json.dump(out")[0]
    ns["RR"] = rr; exec(code, ns); return ns["out"]
REC = recs_for(KS, KP, KF, "o2" if SEL == "O2" else None)
cap = capscore(REC)
prod_caps, prod_score = product_rubric([{"c": r["c"], "state": r["state"], "ft": r["ft"] if r["feet"] else None, "secchi": r["secchi"], "insitu_type": r["insitu_type"], "turb": r["turb"]} for r in REC])
out["historical"] = {"engine": SEL, "exact_feet": cap["exact_feet"], "hard_class": cap["clarity_class"], "EXACT_FEET": cap["EXACT_FEET_CAPABILITY"],
                     "HARD_CLASS": cap["CLARITY_CLASS_CAPABILITY"], "shares": cap["shares"], "product": prod_caps, "PRODUCT": prod_score}
# the other engine's historical scores, for the record
OTH = recs_for(*(("st_gbm", "p_gbm", "feet_gbm", None) if SEL == "O2" else ("st_o2", "p_lin", "feet_o2", "o2")))
co = capscore(OTH); po = product_rubric([{"c": r["c"], "state": r["state"], "ft": r["ft"] if r["feet"] else None, "secchi": r["secchi"], "insitu_type": r["insitu_type"], "turb": r["turb"]} for r in OTH])
out["historical_other"] = {"engine": "O2" if SEL == "C-gbm" else "C-gbm", "EXACT_FEET": co["EXACT_FEET_CAPABILITY"], "HARD_CLASS": co["CLARITY_CLASS_CAPABILITY"], "PRODUCT": po[1],
                           "product": po[0], "exact_feet": co["exact_feet"], "hard_class": co["clarity_class"]}
json.dump(out, open(f"{S}/stage14/analysis/dev14.json", "w"), indent=1, default=str)
json.dump(rows, open(f"{S}/stage14/analysis/dev14_rows.json", "w"), default=str)
c = out["compare"]
for m in ("C-gbm", "O2", "C-lin (reference)"):
    d = c[m]["decision"]
    print(m, "decision bal", round(d["balanced"], 3), "spec", round(d["specificity"], 3), {n: (round(d[n]["decision_recall"], 2), round(d[n]["decision_precision"], 2)) for n in CLASSES},
          "hard bal", round(c[m]["hard"]["balanced"], 3), "incons", round(c[m]["inconsistency"], 3), "err", round(c[m]["factor"], 3))
print("O2-Cgbm", c["O2_minus_Cgbm_decision_balanced"], "SELECTED", SEL)
print("tier3", out["tier3"]["behaviour"], out["tier3"]["allowed_states"], {k: (v["n"], round(v["precision"], 2)) for k, v in d3["by_state"].items()}, feet3)
print("clear", json.dumps(out["clear"], indent=0)[:1500])
print("historical", out["historical"]["EXACT_FEET"], out["historical"]["HARD_CLASS"], out["historical"]["PRODUCT"], "other", out["historical_other"]["EXACT_FEET"], out["historical_other"]["HARD_CLASS"], out["historical_other"]["PRODUCT"])
