"""Stage 16 sections 2-3 on DEVELOPMENT rows only: nested posteriors (inner folds of the training lakes, tier-tagged),
the threshold x tier-2 grid, the pre-registered selection, the frozen production rule. Writes dev16.json, rule16.json."""
import json, math, collections, itertools
import numpy as np
from lib16 import *
from lib14 import dev_rows, fit_gbm, pred_gbm, fold
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
E14 = json.load(open(f"{S}/stage14/engine/frozen_engine.json"))
ALL, T1, T2, REST = dev_rows(); TT = T1 + T2
inner = lambda x: fold(x["lake"], 20) % 4
POST = {}
for k in range(5):
    tr = [x for x in T1 if fold(x["lake"]) != k]; ip = []
    for j in range(4):
        itr = [x for x in tr if inner(x) != j]; ite = [x for x in TT if fold(x["lake"]) != k and inner(x) == j]
        ip += list(zip(pred_gbm(fit_gbm(itr), ite), [x["y"] for x in ite], [x["tier"] for x in ite]))
    POST[k] = {"post1": fit_post([(p, y) for p, y, t in ip if t == 1]), "post2": fit_post([(p, y) for p, y, t in ip if t == 2]), "n2": sum(t == 2 for _, _, t in ip)}
    print("fold", k, "tier-2 inner rows", POST[k]["n2"], {b: tuple(round(v, 2) for v in POST[k]["post1"][b]) for b in (6, 3, 2)}, flush=True)
rows = [r for r in json.load(open(f"{S}/stage15/analysis/dev15_rows.json"))]
def run(t1, t2, opt, rs=rows, post=None):
    out = []
    for r in rs:
        R = {**(post or POST[r["fold"]]), "t1": t1, "t2": t2, "t2opt": opt, "tier3_allowed": E14["tier3_allowed_states"]}
        o = product16(r["tier"], r["p"], r["platform"], r.get("ndci"), r.get("st3"), R)
        sc, oc, h, sv = op_score(o, r["c"], r["secchi"])
        out.append({**r, "o": o, "score": sc, "outcome": oc, "harmful": h, "severe": sv})
    return out
grid = []
T1G = [round(x, 2) for x in np.arange(0.60, 0.901, 0.05)]; T2G = [round(x, 2) for x in np.arange(0.70, 0.951, 0.05)]
for t1, t2, opt in itertools.product(T1G, T2G, ("T2-A", "T2-B", "T2-C", "T2-D")):
    if t2 < t1: continue
    s = op_summary(run(t1, t2, opt))
    t2rows = [r for r in run(t1, t2, opt, [r for r in rows if r["tier"] == 2])]
    grid.append({"t1": t1, "t2": t2, "opt": opt, "bal": s["balanced"], "harm": s["harmful_rate"], "sev": s["severe_rate"],
                 "min_class": min(v["mean"] for v in s["per_class"].values()), "per_class": {n: v["mean"] for n, v in s["per_class"].items()},
                 "unknown_share": (s["outcomes"].get("unknown_appropriate", 0) + s["outcomes"].get("unknown_missed_right", 0)) / s["n"],
                 "tier2_harm": float(np.mean([r["harmful"] for r in t2rows]))})
def pick(cands):
    if not cands: return None
    best = max(c["bal"] for c in cands)
    tie = [c for c in cands if c["bal"] >= best - 0.005]
    return min(tie, key=lambda c: (c["harm"], -c["bal"]))
c1 = [g for g in grid if g["harm"] <= 0.12 and g["sev"] <= 0.015 and g["min_class"] >= 0.60]
c2 = [g for g in grid if g["harm"] <= 0.15 and g["sev"] <= 0.02]
SEL = pick(c1) or pick(c2) or min(grid, key=lambda g: g["harm"]); tierused = "primary" if pick(c1) else "fallback-1" if pick(c2) else "fallback-2"
print("candidates primary", len(c1), "fallback", len(c2), "SELECTED", SEL, tierused, flush=True)
# the selected rule on development (nested), full detail
FIN = run(SEL["t1"], SEL["t2"], SEL["opt"]); fs = op_summary(FIN)
ev = collections.defaultdict(list)
for r in FIN:
    e = evidence(r["o"]); ev[e].append(r)
evs = {e: {"n": len(v), "share": len(v) / len(FIN), "containment": (float(np.mean([r["c"] in CONTAINS[r["o"]["state"]] for r in v])) if e != "unavailable" else None)} for e, v in ev.items()}
st = collections.Counter(r["o"]["state"] for r in FIN)
stp = {s: float(np.mean([r["c"] in CONTAINS[s] for r in FIN if r["o"]["state"] == s])) for s in st if s in CONTAINS}
by_tier = {t: op_summary([r for r in FIN if r["tier"] == t]) for t in (1, 2, 3)}
# tier-2 options at the selected thresholds
t2cmp = {o: next(g for g in grid if g["t1"] == SEL["t1"] and g["t2"] == SEL["t2"] and g["opt"] == o) for o in ("T2-A", "T2-B", "T2-C", "T2-D")}
# Stage 15 reference (the same rows, Stage 15 semantics)
s15 = json.load(open(f"{S}/stage15/analysis/dev15.json"))["final"]
# production rule: posteriors on all development lake-held-out predictions (outer folds)
pr1 = [(r["p"], r["y"]) for r in rows if r["tier"] == 1]; pr2 = [(r["p"], r["y"]) for r in rows if r["tier"] == 2]
RULE = {"post1": {str(b): v for b, v in fit_post(pr1).items()}, "post2": {str(b): v for b, v in fit_post(pr2).items()}, "t1": SEL["t1"], "t2": SEL["t2"], "t2opt": SEL["opt"],
        "tier3_allowed": E14["tier3_allowed_states"], "selection": tierused, "unchanged": "Stage 14 engine; Stage 15 tier 3, algal modifier, S2C lower authority"}
json.dump(RULE, open(f"{S}/stage16/engine/rule16.json", "w"), indent=1)
# what the production rule issues across the prediction range (tier 1)
P1 = {int(b): tuple(v) for b, v in RULE["post1"].items()}
zones = []; prev = None
for ft in np.arange(0.5, 30.01, 0.01):
    s_, c_, w_ = gate(math.log10(ft), P1, SEL["t1"], SEL["t2"])
    lab = s_ or f"Unknown ({w_})"
    if lab != prev: zones.append([round(float(ft), 2), lab]); prev = lab
ready_dev = fs["score_of_10"] >= 7 and all(v["mean"] >= 0.60 for v in fs["per_class"].values()) and fs["harmful_rate"] <= 0.15 and fs["severe_rate"] <= 0.02
out = {"selected": SEL, "selection_tier": tierused, "n_grid": len(grid), "n_primary": len(c1), "n_fallback": len(c2), "final": fs, "evidence": evs, "state_counts": dict(st),
       "state_precision": stp, "by_tier": {t: {"bal": v["balanced"], "harm": v["harmful_rate"], "n": v["n"]} for t, v in by_tier.items()}, "tier2_options": t2cmp,
       "stage15": {"bal": s15["balanced"], "harm": s15["harmful_rate"], "sev": s15["severe_rate"], "per_class": {n: v["mean"] for n, v in s15["per_class"].items()}},
       "zones_tier1_ft": zones, "ready_dev": ready_dev, "top_grid": sorted(grid, key=lambda g: -g["bal"])[:10]}
json.dump(out, open(f"{S}/stage16/analysis/dev16.json", "w"), indent=1, default=str)
json.dump(FIN, open(f"{S}/stage16/analysis/dev16_rows.json", "w"), default=str)
print("FINAL dev", fs["score_of_10"], round(fs["balanced"], 3), "harm", round(fs["harmful_rate"], 3), "sev", round(fs["severe_rate"], 3), {n: round(v["mean"], 3) for n, v in fs["per_class"].items()})
print("evidence", evs); print("states", dict(st), {k: round(v, 2) for k, v in stp.items()}); print("tiers", out["by_tier"])
print("tier2 options", {o: (round(g["bal"], 3), round(g["harm"], 3), round(g["tier2_harm"], 3)) for o, g in t2cmp.items()})
print("zones", zones); print("READY(dev)", ready_dev)
