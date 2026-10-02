"""Stage 18 freeze: Stage 16 = baseline (engine16 + rule16, unchanged); Stage 17 M-iuw +-10 d, no rain rule, S2C off =
challenger. Challenger production parameters are pooled from the Stage 17 DEVELOPMENT lake-held-out predictions only
(sigma by tier from anchor residuals, kappa from anchor-neighbour pairs, n=2 / n>=3 posteriors from the outer-fold
consensus predictions), exactly the quantities Stage 17 fitted per fold. Writes engine/challenger17.json, FREEZE_STAGE18.json."""
import json, hashlib, datetime, sys, numpy as np
S = __import__("os").environ["CLARITY_RESEARCH_ROOT"] + ""
src = open(f"{S}/stage17/analysis/dev17.py").read().split("RES = {}")[0]          # data, fold predictions, per-fold params; no variants
sys.argv = ["dev17.py"]; ns = {"__name__": "freeze18"}; exec(compile(src, "dev17_prefix", "exec"), ns)
PRED, NB, EVENTS, corp, fit_post, combine, build = ns["PRED"], ns["NB"], ns["EVENTS"], ns["corp"], ns["fit_post"], ns["combine"], ns["build"]
an = [(PRED[(e["id"], "outer", e["fold"])]["anchor"], e["y"], e["tier"]) for e in EVENTS if PRED[(e["id"], "outer", e["fold"])]["anchor"] is not None and e["tier"] in (1, 2)]
mad = lambda r: 1.4826 * float(np.median(np.abs(np.array(r) - np.median(r))))
sig = {t: mad([y - p for p, y, tt in an if tt == t]) for t in (1, 2)}
dd, sep = [], []
for e in EVENTS:
    pr = PRED[(e["id"], "outer", e["fold"])]
    if pr["anchor"] is None or e["tier"] not in (1, 2): continue
    for n, p in zip(NB.get(e["id"], []), pr["nb"]): dd.append((p - pr["anchor"]) ** 2); sep.append(abs(n["dt"]) + abs(int(corp[e["id"]].get("dt") or 0)))
kappa = max(0.0, float(np.linalg.lstsq(np.vstack([np.ones(len(sep)), sep]).T, np.array(dd), rcond=None)[0][1]))
ys = [e["y"] for e in EVENTS]
par = {"sig": sig, "kappa": kappa, "mu0": float(np.mean(ys)), "s0": float(np.std(ys))}
R16 = json.load(open(f"{S}/stage16/engine/rule16.json"))
post = {"post1": {int(b): tuple(v) for b, v in R16["post1"].items()}, "post2": {int(b): tuple(v) for b, v in R16["post2"].items()}}
grp = {"n2": [], "n3": []}
for e in EVENTS:
    o = build(e, (e["id"], "outer", e["fold"]), "M-iuw", 10, "H0", "S-off", par, post, {})
    if o.get("consensus") and o.get("n_use", 1) >= 2: grp["n2" if o["n_use"] == 2 else "n3"].append((o["p"], e["y"]))
cal = {g: {str(b): list(v) for b, v in fit_post(rows).items()} for g, rows in grp.items()}
CH = {"engine": "Stage 17 challenger: inverse-uncertainty weighting of frozen C-gbm scene predictions, +-10 days, no rain rule, S2C off",
      "scene_predictor": "stage14/engine/frozen_gbm.pkl (unchanged)", "scene_path": "stage14/cert/run_cert_aco_a1.py (unchanged)",
      "neighbours": "<= 3 nearest valid passes (production gates, >= 5 px) within +-10 days, excluding the anchor; tiers 1-2 only; S2C excluded",
      "sigma_tier": sig, "kappa_per_day": kappa, "posteriors_n2": cal.get("n2"), "posteriors_n3": cal.get("n3"), "n_calibration": {g: len(v) for g, v in grp.items()},
      "gate": {"t1": R16["t1"], "t2": R16["t2"], "tier2_only": "boundary-only (Stage 16)"}, "fallback": "Stage 16 product when no full-authority scene contributes",
      "strong_rule": ">= 2 compatible full-authority scenes whose states contain the answer, none disjoint, posterior >= 0.90"}
json.dump(CH, open(f"{S}/stage18/engine/challenger17.json", "w"), indent=1)
h = lambda p: hashlib.sha256(open(f"{S}/{p}", "rb").read()).hexdigest()
files = ["stage14/engine/engine14.py", "stage14/engine/frozen_engine.json", "stage14/engine/frozen_gbm.pkl", "stage16/engine/engine16.py", "stage16/engine/rule16.json",
         "stage16/analysis/lib16.py", "stage17/analysis/dev17.py", "stage17/PREREGISTRATION_STAGE17.md", "stage18/engine/challenger17.json", "stage18/freeze18.py"]
F = {"stage": 18, "frozen_utc": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "baseline": "Stage 16 (engine16 + rule16)",
     "challenger": "Stage 17 M-iuw +-10 d, H0, S-off (challenger17.json)", "files": {p: h(p) for p in files}}
json.dump(F, open(f"{S}/stage18/FREEZE_STAGE18.json", "w"), indent=1)
print(json.dumps({k: CH[k] for k in ("sigma_tier", "kappa_per_day", "n_calibration")}), F["frozen_utc"])
