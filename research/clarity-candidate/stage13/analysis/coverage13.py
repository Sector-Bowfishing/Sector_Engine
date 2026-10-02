"""Stage 13 sections 8 and 11: coverage tiers and the capability scores for BEST (and for A, for comparison).
Tier 1 = ACOLITE default disk; tier 2 = relaxed-mask disk (variant chosen by the section 8 rule) where tier 1 has none;
tier 3 = C3 refitted on Sen2Cor reflectance (lower authority); Unknown = none. Every fit uses training lake-folds of
tier-1 rows only. Class: BEST's class; feet: BEST's continuous prediction (O-models use C-lin's), authorised per
predicted class from inner folds (Stage 12 rule). Writes coverage13.json."""
import json, math, glob, collections
import numpy as np
import models13_lib as L
from common13 import *
M = json.load(open(f"{D13}/analysis/models13.json")); BEST = M["BEST"]
FEET_OF = {"O1": "C-lin", "O2": "C-lin", "O1-noCDOM": "C-lin"}
rows12 = {x["id"]: x for x in load12()}
ALL = [x for x in rows12.values() if x["processed"] and not x["gunt"] and x["secchi"] and x["secchi"] > 0]
# tier-2 samples
T2 = {}
for f_ in glob.glob(f"{D13}/coverage/res/*.json"):
    r = json.load(open(f_))
    for c in r.get("crops", []):
        for pid, p in (c.get("points") or {}).items(): T2[pid] = p
VR = json.load(open(f"{S}/stage12/harm/score_tandem.json"))["production_vrhow_coef"]
def harm(p, platform):
    if platform != "sentinel-2c": return p
    q = dict(p)
    for b, c in VR.items():
        if isinstance(p.get(b), (int, float)):
            v = c["g"] * p[b] + c["o"]
            if b == "B05": v += c["k"] * (p.get("B06", 0) - p.get("B04", 0))
            q[b] = v
    return q
def valid(p): return p and p.get("n", 0) >= 5 and not p.get("rejected") and all(isinstance(p.get(b), (int, float)) and math.isfinite(p[b]) for b in ("B02", "B03", "B04", "B05"))
def prep(x, a):
    y = dict(x); y["aco"] = a; y["F"], y["q"] = features(a, x["sun_elev"]); y["y"] = math.log10(x["secchi"]); y["c"] = cls(x["secchi"])
    y["t_red"] = t_red(a["B04"]); y["t_sw"], y["w_sw"] = t_switch(a["B04"], a.get("B8A")); return y
res = {"BEST": BEST, "variants": {}}
tier1 = {x["id"]: prep(x, x["aco"]) for x in ALL if x["aco_valid"]}
# section 8 variant choice with engine A
def var_rows(v): return {x["id"]: prep(x, harm(T2[x["id"]][v], x["platform"])) for x in ALL if not x["aco_valid"] and valid((T2.get(x["id"]) or {}).get(v))}
def heldout(tr_rows, te_rows, models):
    out = {}
    for k in range(5):
        tr = [x for x in tr_rows if fold(x["lake"]) != k]; te = [x for x in te_rows if fold(x["lake"]) == k]
        if not te: continue
        P, C = L.fit_predict(tr, te)
        for i, x in enumerate(te): out[x["id"]] = ({m: P.get(m, [None] * len(te))[i] for m in models}, {m: C.get(m, [None] * len(te))[i] for m in models})
    return out
t1 = list(tier1.values()); H1 = heldout(t1, t1, ["A", "C-lin", "C-gbm", "O1", "O2", BEST, FEET_OF.get(BEST, BEST)])
e1 = float(np.median([abs(H1[x["id"]][0]["A"] - x["y"]) for x in t1]))
cand = {}
for v in ("M1", "M2", "M3"):
    rows = list(var_rows(v).values())
    if not rows: res["variants"][v] = {"n": 0}; continue
    H = heldout(t1, rows, ["A"]); ev = float(np.median([abs(H[x["id"]][0]["A"] - x["y"]) for x in rows]))
    res["variants"][v] = {"n": len(rows), "tier2_median_abs_log_A": round(ev, 4), "tier1_median_abs_log_A": round(e1, 4), "passes": ev <= e1 + 0.05}
    cand[v] = rows
choice = "M3" if res["variants"].get("M3", {}).get("passes") else next((v for v in sorted(("M1", "M2"), key=lambda v: -res["variants"].get(v, {}).get("n", 0)) if res["variants"].get(v, {}).get("passes")), None)
res["variant_chosen"] = choice
tier2 = {x["id"]: x for x in cand.get(choice, [])} if choice else {}
H2 = heldout(t1, list(tier2.values()), ["A", "C-lin", "C-gbm", "O1", "O2", BEST, FEET_OF.get(BEST, BEST)]) if tier2 else {}
# tier 3: C3 on Sen2Cor reflectance (fitted on tier-1 training rows' Sen2Cor values)
def c3s(x):
    s = x["sen2cor"]; red, re1 = max(s["red"], 0.001), max(s["re1"], 0.001); lr = math.log10(red); a = 1.0 if (re1 - red) / (re1 + red) > 0 else 0.0
    return [1 - a, (1 - a) * lr, a, a * lr]
rest = [x for x in ALL if x["id"] not in tier1 and x["id"] not in tier2]
H3 = {}
for k in range(5):
    tr = [x for x in ALL if fold(x["lake"]) != k]; te = [x for x in rest if fold(x["lake"]) == k]
    b = np.linalg.lstsq(np.array([c3s(x) for x in tr]), np.array([math.log10(x["secchi"]) for x in tr]), rcond=None)[0]
    for x in te: H3[x["id"]] = float(np.dot(b, c3s(x)))
# assemble per row
def row_out(x, model):
    fm = FEET_OF.get(model, model)
    if x["id"] in tier1: P, C = H1[x["id"]]; return 1, C[model], P[fm]
    if x["id"] in tier2: P, C = H2[x["id"]]; return 2, C[model], P[fm]
    if x["id"] in H3: v = H3[x["id"]]; return 3, cls(10 ** v), v
    return 0, None, None
def summarize(model):
    rr = [(x, *row_out(x, model)) for x in ALL]
    out = {"coverage": {"tier1": sum(t == 1 for _, t, _, _ in rr) / len(rr), "tier2": sum(t == 2 for _, t, _, _ in rr) / len(rr), "tier3": sum(t == 3 for _, t, _, _ in rr) / len(rr),
                        "unknown": sum(t == 0 for _, t, _, _ in rr) / len(rr)}}
    for name, keep in (("tier1_only", (1,)), ("tiers1-2", (1, 2)), ("tiers1-3", (1, 2, 3))):
        cm = class_metrics([cls(x["secchi"]) for x, *_ in rr], [c if t in keep else None for x, t, c, _ in rr])
        out[name] = {n: (round(cm[n]["recall"], 3), round(cm[n]["precision"] or 0, 3)) for n in CLASSES} | {"balanced": round(cm["balanced_accuracy"], 3)}
    for t in (2, 3):
        sub = [(x, c) for x, tt, c, _ in rr if tt == t]
        if sub:
            cm = class_metrics([cls(x["secchi"]) for x, _ in sub], [c for _, c in sub])
            out[f"tier{t}_own_rows"] = {"n": len(sub), "balanced": round(cm["balanced_accuracy"], 3), **{n: (round(cm[n]["recall"] or 0, 3), round(cm[n]["precision"] or 0, 3)) for n in CLASSES}}
    out["not_materially_worse"] = out["tiers1-3"]["balanced"] >= out["tier1_only"]["balanced"] - 0.03
    return out, rr
res["A"], _ = summarize("A")
res["best"], RR = summarize(BEST)
# section 11 capability rubrics (Stage 12 section 5), BEST with tiers 1-3 (tier 3 lower authority)
BAR = {"clear": 1.5, "normal": 1.0, "stained": 0.75, "limited": 0.75}
fm = FEET_OF.get(BEST, BEST)
auth = {}
for k in range(5):
    tr = [x for x in t1 if fold(x["lake"]) != k]; inner = []
    for j in range(4):
        itr = [x for x in tr if (fold(x["lake"], 20) % 4) != j]; ite = [x for x in tr if (fold(x["lake"], 20) % 4) == j]
        P, C = L.fit_predict(itr, ite)
        inner += [(x, C[BEST][i], P[fm][i]) for i, x in enumerate(ite)]
    ok = []
    for c, name in enumerate(CLASSES):
        sub = [(x, v) for x, cc, v in inner if cc == c and v is not None]
        if len(sub) < 10: continue
        if np.median([abs(v - x["y"]) for x, v in sub]) <= 0.15 and abs(np.median([10 ** v - x["secchi"] for x, v in sub])) <= BAR[name]: ok.append(name)
    auth[k] = ok
res["feet_authorisation"] = auth
recs = []
for x, t, c, v in RR:
    cp = CLASSES[c] if c is not None else "unknown"
    recs.append({"true": cname(x["secchi"]), "pred": cp, "ft": (10 ** v if v is not None else None), "secchi": x["secchi"], "feet": v is not None and cp in auth[fold(x["lake"])],
                 "insitu_type": x["insitu_type"], "turb": x.get("turb"), "tier": t})
json.dump(recs, open(f"{D13}/analysis/capability_rows13.json", "w"))
json.dump(res, open(f"{D13}/analysis/coverage13.json", "w"), indent=1, default=str)
print(json.dumps({k: res[k] for k in ("BEST", "variants", "variant_chosen", "feet_authorisation")}, indent=1, default=str)); print(json.dumps(res["best"], indent=1)); print("A", json.dumps(res["A"]["coverage"]), res["A"]["tiers1-3"])
